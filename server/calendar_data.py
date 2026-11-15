"""Normalisation + fusion des calendriers (TradingView, Forex Factory, Trading Economics)."""
import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import storage
from .config import TIMEZONE
from .countries import (COUNTRY_TO_CCY, CURRENCIES, ALL_COUNTRIES, INVERSE_KEYWORDS)
from . import sources

log = logging.getLogger("calendar")
TZ = ZoneInfo(TIMEZONE)
IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}


# ------------------------------------------------------------------ helpers
def parse_time(s: str) -> datetime:
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def week_bounds(now: datetime | None = None):
    """Semaine de trading : du dimanche 00:00 (heure de l'Est) au dimanche suivant.
    Le dimanche, on regarde donc déjà la semaine qui commence."""
    now = (now or datetime.now(timezone.utc)).astimezone(TZ)
    days_since_sunday = (now.weekday() + 1) % 7
    start = (now - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=7)).astimezone(timezone.utc)


def _num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^\s*([-+]?\d*\.?\d+)\s*([KMBT%]?)", str(v))
    if not m:
        return None
    return float(m.group(1))


def fmt(v, scale=None, unit=None):
    if v is None:
        return "—"
    if isinstance(v, str):
        return v or "—"
    s = f"{v:,.3f}".rstrip("0").rstrip(".") if abs(v) < 1e6 else f"{v:,.0f}"
    suffix = (scale or "") + (unit if unit in ("%",) else "")
    return s + suffix


def _tokens(s: str) -> set:
    s = s.lower().replace("y/y", "yoy").replace("m/m", "mom").replace("q/q", "qoq")
    syn = {"cpi": "inflation", "hicp": "inflation", "jobless": "unemployment", "nfp": "payrolls",
           "prelim": "prel", "flash": "prel"}
    return {syn.get(t, t) for t in re.findall(r"[a-z0-9]+", s)
            if t not in {"the", "of", "s", "a", "rate", "index", "growth"}}


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_inverse(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in INVERSE_KEYWORDS)


def surprise(ev: dict) -> dict | None:
    a, f = _num(ev.get("actual")), _num(ev.get("forecast"))
    if a is None or f is None:
        return None
    diff = a - f
    sign = 0 if abs(diff) < 1e-9 else (1 if diff > 0 else -1)
    ccy_sign = -sign if is_inverse(ev["title"]) else sign
    label = {1: "Au-dessus du consensus", -1: "Sous le consensus", 0: "En ligne avec le consensus"}[sign]
    bias = {1: "positif", -1: "négatif", 0: "neutre"}[ccy_sign]
    return {"diff": round(diff, 4), "label": label, "ccy_bias": bias,
            "diff_str": ("+" if diff > 0 else "") + fmt(diff, ev.get("scale"), ev.get("unit"))}


# ------------------------------------------------------------- normalisation
def norm_tv(row: dict) -> dict:
    imp = {1: "high", 0: "medium"}.get(row.get("importance"), "low")
    country = row.get("country", "")
    return {
        "id": f"tv-{row.get('id')}",
        "time": parse_time(row["date"]).isoformat(),
        "country": country,
        "currency": COUNTRY_TO_CCY.get(country, row.get("currency", "")),
        "title": row.get("title") or row.get("indicator", ""),
        "period": row.get("period") or "",
        "impact": imp,
        "actual": row.get("actual"), "forecast": row.get("forecast"), "previous": row.get("previous"),
        "unit": row.get("unit"), "scale": row.get("scale"),
        "te_forecast": None,
        "sources": ["TradingView"],
    }


def norm_ff(row: dict) -> dict | None:
    ccy = row.get("country", "")
    if ccy not in CURRENCIES or not row.get("date"):
        return None
    imp = {"High": "high", "Medium": "medium", "Low": "low"}.get(row.get("impact"))
    if not imp:
        return None  # jours fériés etc.
    return {
        "id": "ff-" + re.sub(r"[^a-z0-9]+", "-", f"{ccy}-{row['date']}-{row.get('title','')}".lower()),
        "time": parse_time(row["date"]).isoformat(),
        "country": CURRENCIES[ccy]["countries"][0],
        "currency": ccy, "title": row.get("title", ""), "period": "", "impact": imp,
        "actual": row.get("actual") or None, "forecast": row.get("forecast") or None,
        "previous": row.get("previous") or None, "unit": None, "scale": None, "te_forecast": None,
        "sources": ["Forex Factory"],
    }


def _match(target: dict, candidates: list[dict], max_minutes=5, min_sim=0.25):
    t = parse_time(target["time"])
    best, best_s = None, 0.0
    for c in candidates:
        if c["currency"] != target["currency"]:
            continue
        if abs((parse_time(c["time"]) - t).total_seconds()) > max_minutes * 60:
            continue
        s = similarity(c["title"], target["title"])
        if s > best_s:
            best, best_s = c, s
    return best if best_s >= min_sim else None


def merge(tv_rows: list[dict], ff_rows: list[dict], te_rows: list[dict]) -> list[dict]:
    events = [norm_tv(r) for r in tv_rows if r.get("date")]
    events = [e for e in events if e["currency"] in CURRENCIES]

    for raw in ff_rows:
        ff = norm_ff(raw)
        if not ff:
            continue
        m = _match(ff, events)
        if m:
            # Quand l'événement existe sur Forex Factory, sa couleur de dossier fait autorité
            m["impact"] = ff["impact"]
            m["ff_impact"] = ff["impact"]
            if m["forecast"] is None and ff["forecast"]:
                m["forecast"] = ff["forecast"]
            if "Forex Factory" not in m["sources"]:
                m["sources"].append("Forex Factory")
        elif ff["impact"] in ("high", "medium"):
            ff["ff_impact"] = ff["impact"]
            events.append(ff)

    # TradingView classe beaucoup d'indicateurs secondaires en "moyen" : quand Forex Factory
    # couvre la période, un orange TradingView absent de Forex Factory devient jaune (pas d'alerte).
    if ff_rows:
        for e in events:
            if e["impact"] == "medium" and "ff_impact" not in e:
                e["impact"] = "low"

    for row in te_rows:
        try:
            te = {"currency": COUNTRY_TO_CCY.get(row["_code"]), "time": parse_time(row["Date"]).isoformat(),
                  "title": row.get("Event", "")}
        except Exception:
            continue
        m = _match(te, events)
        if m:
            m["te_forecast"] = row.get("TEForecast") or None
            if m["actual"] is None and row.get("Actual"):
                m["actual"] = row.get("Actual")
            if m["forecast"] is None and row.get("Forecast"):
                m["forecast"] = row.get("Forecast")
            if "Trading Economics" not in m["sources"]:
                m["sources"].append("Trading Economics")

    for e in events:
        decorate(e)
    events.sort(key=lambda e: (e["time"], -IMPACT_RANK[e["impact"]]))
    return events


def decorate(e: dict) -> dict:
    e["actual_str"] = fmt(e.get("actual"), e.get("scale"), e.get("unit"))
    e["forecast_str"] = fmt(e.get("forecast"), e.get("scale"), e.get("unit"))
    e["previous_str"] = fmt(e.get("previous"), e.get("scale"), e.get("unit"))
    e["te_forecast_str"] = fmt(e.get("te_forecast"), e.get("scale"), e.get("unit")) if e.get("te_forecast") is not None else None
    e["surprise"] = surprise(e)
    e["released"] = e.get("actual") is not None
    return e


# ------------------------------------------------------------ opérations
def refresh_week(force_ff=False) -> list[dict]:
    """Recharge la semaine en cours (TV + FF + TE) et sauvegarde dans data/week.json."""
    start, end = week_bounds()
    errors = []
    try:
        tv = sources.fetch_tradingview(start, end, ALL_COUNTRIES)
        storage.save("raw_tv_week.json", tv)
    except Exception as e:
        errors.append(f"TradingView: {e}")
        tv = storage.load("raw_tv_week.json", [])

    ff_cache = storage.load("raw_ff.json", {"ts": 0, "rows": []})
    from .config import FF_REFRESH_MINUTES
    if force_ff or (datetime.now().timestamp() - ff_cache["ts"]) > FF_REFRESH_MINUTES * 60:
        rows = []
        for which in ("thisweek", "nextweek"):
            try:
                rows += sources.fetch_forexfactory(which)
            except Exception as e:
                if which == "thisweek":
                    errors.append(f"Forex Factory: {e}")
        if rows:
            ff_cache = {"ts": datetime.now().timestamp(), "rows": rows}
            storage.save("raw_ff.json", ff_cache)
    ff = [r for r in ff_cache["rows"]
          if r.get("date") and start <= parse_time(r["date"]) < end]

    try:
        te = sources.fetch_tradingeconomics(start, end)
    except Exception as e:
        errors.append(f"Trading Economics: {e}")
        te = []

    events = merge(tv, ff, te)
    storage.save("week.json", {"updated": datetime.now(timezone.utc).isoformat(), "start": start.isoformat(),
                               "end": end.isoformat(), "errors": errors, "events": events})
    if errors:
        log.warning("Erreurs sources: %s", errors)
    return events


def fast_actual(events_at_slot: list[dict]) -> list[dict]:
    """Interroge TradingView autour d'une heure de publication pour récupérer les 'actual'."""
    if not events_at_slot:
        return []
    t = parse_time(events_at_slot[0]["time"])
    countries = sorted({e["country"] for e in events_at_slot})
    rows = sources.fetch_tradingview(t - timedelta(minutes=2), t + timedelta(minutes=2), countries)
    fresh = [decorate(norm_tv(r)) for r in rows if r.get("date")]
    updated = []
    for ev in events_at_slot:
        m = next((f for f in fresh if f["id"] == ev["id"]), None) or _match(ev, fresh, 3, 0.3)
        if m and m.get("actual") is not None:
            ev["actual"] = m["actual"]
            if ev.get("forecast") is None:
                ev["forecast"] = m.get("forecast")
            decorate(ev)
            updated.append(ev)
    return updated


def load_week() -> dict:
    return storage.load("week.json", {"events": [], "errors": ["Pas encore chargé"], "updated": None})


def refresh_history(days=400) -> list[dict]:
    """Historique ~13 mois (moyen + élevé) pour taux directeurs, CPI, données clés."""
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=days)
    out, cur = [], start
    while cur < end:
        nxt = min(cur + timedelta(days=60), end)
        try:
            rows = sources.fetch_tradingview(cur, nxt, ALL_COUNTRIES)
            out += [norm_tv(r) for r in rows if r.get("date") and r.get("importance", -1) >= 0]
        except Exception as e:
            log.warning("Historique %s→%s: %s", cur.date(), nxt.date(), e)
        cur = nxt
    if out:
        uniq = {e["id"]: e for e in out}
        out = sorted(uniq.values(), key=lambda e: e["time"])
        for e in out:
            decorate(e)
        storage.save("history.json", {"updated": datetime.now(timezone.utc).isoformat(), "events": out})
    return out


def load_history() -> list[dict]:
    return storage.load("history.json", {"events": []})["events"]
