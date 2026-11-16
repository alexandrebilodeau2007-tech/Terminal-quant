"""Probabilités de taux des banques centrales, estimées à partir des futures de taux (prix TradingView).

- Fed : futures Fed funds 30 jours (ZQ), méthode classique mois par mois (comme CME FedWatch).
- BoC, BCE, BoE, BNS : futures 3 mois (CORRA, Euribor, SONIA, SARON) → courbe à terme interpolée.
- RBA, RBNZ, BoJ : pas de futures accessibles gratuitement → non disponible.
"""
import logging
import time
from datetime import date, datetime, timedelta, timezone

import httpx

from . import storage

log = logging.getLogger("rates")
SCAN = "https://scanner.tradingview.com/futures/scan"
MONTH_CODES = "FGHJKMNQUVXZ"

MEETINGS = {
    "USD": ["2026-12-09", "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08"],
    "CAD": ["2026-12-09", "2027-01-27", "2027-03-03", "2027-04-28", "2027-06-02", "2027-07-21", "2027-09-08", "2027-10-27", "2027-12-08"],
    "EUR": ["2026-12-17", "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-10", "2027-07-22", "2027-09-09", "2027-10-28", "2027-12-16"],
    "GBP": ["2026-12-17", "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-17", "2027-07-29", "2027-09-16", "2027-11-04", "2027-12-16"],
    "CHF": ["2026-12-10", "2027-03-25", "2027-06-17", "2027-09-23", "2027-12-16"],
    "AUD": ["2026-12-08", "2027-02-09", "2027-03-23", "2027-05-04", "2027-06-22", "2027-08-10", "2027-09-21", "2027-11-02", "2027-12-14"],
    "NZD": ["2026-11-25", "2027-02-17", "2027-04-07", "2027-05-26", "2027-07-14", "2027-08-25", "2027-10-06", "2027-11-24"],
    "JPY": ["2026-12-18", "2027-01-22", "2027-03-18", "2027-04-27", "2027-06-16", "2027-07-29", "2027-09-16", "2027-10-28", "2027-12-16"],
}
BANKS = {"USD": "Federal Reserve", "CAD": "Banque du Canada", "EUR": "Banque centrale européenne", "GBP": "Bank of England",
         "CHF": "Banque nationale suisse", "AUD": "Reserve Bank of Australia", "NZD": "Reserve Bank of New Zealand", "JPY": "Bank of Japan"}
# futures 3 mois : (préfixe, écart habituel fixing 3M − taux directeur, en %)
QUARTERLY = {"CAD": ("TMX:CRA", -0.07), "EUR": ("EUREX:FEU3", 0.12), "GBP": ("ICEEUR:SO3", -0.05), "CHF": ("EUREX:FSR3", -0.02)}
STEP = 0.25


def _contracts_monthly(prefix, months=14):
    d = date.today().replace(day=1)
    out = []
    for _ in range(months):
        out.append((f"{prefix}{MONTH_CODES[d.month - 1]}{d.year}", d))
        d = (d + timedelta(days=32)).replace(day=1)
    return out


def _contracts_quarterly(prefix, n=6):
    d = date.today()
    out = []
    q = 3 * ((d.month - 1) // 3) + 3  # mois du trimestre en cours : 3, 6, 9, 12
    y = d.year
    # le contrat du trimestre « en cours » couvre de la 3e semaine du mois q jusqu'à q+3
    # on prend le dernier contrat dont la période a déjà commencé
    m, yy = q, y
    start = _third_wednesday(yy, m)
    if start > d:
        m -= 3
        if m == 0:
            m, yy = 12, yy - 1
    for _ in range(n):
        out.append((f"{prefix}{MONTH_CODES[m - 1]}{yy}", _third_wednesday(yy, m)))
        m += 3
        if m > 12:
            m, yy = m - 12, yy + 1
    return out


def _third_wednesday(y, m):
    d = date(y, m, 15)
    while d.weekday() != 2:
        d += timedelta(days=1)
    return d


def _scan(tickers):
    r = httpx.post(SCAN, json={"symbols": {"tickers": tickers}, "columns": ["close"]}, timeout=25,
                   headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return {d["s"]: d["d"][0] for d in r.json().get("data", []) if d["d"] and d["d"][0] is not None}


def _probs(delta):
    """Répartition hausse / statu quo / baisse pour un changement attendu (en %)."""
    p = min(abs(delta) / STEP, 1.0)
    if delta > 0:
        return {"hike": round(100 * p), "hold": round(100 * (1 - p)), "cut": 0}
    return {"hike": 0, "hold": round(100 * (1 - p)), "cut": round(100 * p)}


def fed(prices, current_rate):
    """Chaîne Fed funds : r_après = résolu mois par mois."""
    contracts = _contracts_monthly("CBOT:ZQ")
    implied = {d: 100 - prices[t] for t, d in contracts if t in prices}
    if not implied:
        raise RuntimeError("Fed funds indisponibles")
    today = date.today()
    meetings = [date.fromisoformat(m) for m in MEETINGS["USD"] if date.fromisoformat(m) >= today]
    cur_month = today.replace(day=1)
    effective = current_rate - 0.12  # taux effectif ≈ borne supérieure − 12 pb
    r_prev = implied.get(cur_month, effective)
    # si une réunion a déjà eu lieu ce mois-ci, le contrat du mois est un mélange : on garde le taux effectif courant
    if any(m.replace(day=1) == cur_month and m < today for m in [date.fromisoformat(x) for x in MEETINGS["USD"]]):
        r_prev = effective
    offset = current_rate - r_prev  # pour afficher en borne supérieure de la fourchette cible
    rows = []
    for i, m in enumerate(meetings):
        month = m.replace(day=1)
        nxt = (month + timedelta(days=32)).replace(day=1)
        n_days = (nxt - month).days
        next_has_meeting = any(x.replace(day=1) == nxt for x in meetings)
        if nxt in implied and not next_has_meeting:
            r_after = implied[nxt]
        elif month in implied:
            before = m.day  # jours au taux précédent (changement effectif le lendemain)
            r_after = (implied[month] * n_days - r_prev * before) / (n_days - before)
        else:
            break
        rows.append({"date": m.isoformat(), "rate": round(r_after + offset, 3), "change_bps": round((r_after - r_prev) * 100, 1),
                     **_probs(r_after - r_prev)})
        r_prev = r_after
    curve = [{"date": d.isoformat(), "rate": round(v + offset, 3)} for d, v in sorted(implied.items())]
    return rows, curve


def quarterly(ccy, prices, current_rate):
    prefix, spread = QUARTERLY[ccy]
    contracts = _contracts_quarterly(prefix)
    pts = []
    for t, start in contracts:
        if t in prices:
            mid = start + timedelta(days=45)
            pts.append((mid, 100 - prices[t] - spread))
    if len(pts) < 2:
        raise RuntimeError(f"Futures {prefix} indisponibles")
    today = date.today()
    # ancre : aujourd'hui = taux directeur actuel
    pts = [(today, current_rate)] + [p for p in pts if p[0] > today]

    def interp(d):
        if d <= pts[0][0]:
            return pts[0][1]
        for (d0, r0), (d1, r1) in zip(pts, pts[1:]):
            if d0 <= d <= d1:
                return r0 + (r1 - r0) * (d - d0).days / max((d1 - d0).days, 1)
        return pts[-1][1]

    rows, r_prev = [], current_rate
    meetings = [date.fromisoformat(m) for m in MEETINGS[ccy] if date.fromisoformat(m) >= today]
    for m in meetings:
        if m > pts[-1][0]:
            break
        # le taux après la réunion vaut jusqu'à la suivante : on lit la courbe au milieu de cette période
        nxt = next((x for x in meetings if x > m), m + timedelta(days=42))
        r_after = interp(m + (nxt - m) / 2)
        rows.append({"date": m.isoformat(), "rate": round(r_after, 3), "change_bps": round((r_after - r_prev) * 100, 1),
                     **_probs(r_after - r_prev)})
        r_prev = r_after
    curve = [{"date": d.isoformat(), "rate": round(r, 3)} for d, r in pts]
    return rows, curve


def refresh(current_rates: dict):
    tickers = [t for t, _ in _contracts_monthly("CBOT:ZQ")]
    for ccy in QUARTERLY:
        tickers += [t for t, _ in _contracts_quarterly(QUARTERLY[ccy][0])]
    prices = _scan(tickers)
    out = {"updated": time.time(), "banks": {}}
    hist = storage.load("rates_hist.json", {"snapshots": []})
    week_ago = next((s for s in hist["snapshots"] if time.time() - s["t"] >= 6 * 86400), None)
    for ccy in ["USD", "CAD", "EUR", "GBP", "CHF", "AUD", "NZD", "JPY"]:
        cur = current_rates.get(ccy)
        entry = {"bank": BANKS[ccy], "current": cur, "meetings": [date.fromisoformat(m).isoformat() for m in MEETINGS[ccy]
                                                                  if date.fromisoformat(m) >= date.today()]}
        try:
            if cur is None:
                raise RuntimeError("taux directeur inconnu")
            if ccy == "USD":
                rows, curve = fed(prices, cur)
            elif ccy in QUARTERLY:
                rows, curve = quarterly(ccy, prices, cur)
            else:
                raise RuntimeError("pas de futures accessibles pour cette banque")
            nxt = rows[0] if rows else None
            entry.update({"ok": True, "rows": rows, "curve": curve, "next": nxt,
                          "last_week_curve": (week_ago or {}).get("banks", {}).get(ccy)})
            if nxt:
                entry["next_move"] = "Hausse" if nxt["hike"] > nxt["cut"] and nxt["hike"] > nxt["hold"] else \
                    "Baisse" if nxt["cut"] > nxt["hold"] else "Statu quo"
                entry["probability"] = max(nxt["hike"], nxt["cut"], nxt["hold"])
        except Exception as e:
            entry.update({"ok": False, "error": str(e)[:120]})
        out["banks"][ccy] = entry
    # historique quotidien des courbes (pour « semaine dernière »)
    today = date.today().isoformat()
    if not hist["snapshots"] or hist["snapshots"][-1].get("day") != today:
        hist["snapshots"].append({"t": time.time(), "day": today,
                                  "banks": {c: e.get("curve") for c, e in out["banks"].items() if e.get("ok")}})
        hist["snapshots"] = hist["snapshots"][-40:]
        storage.save("rates_hist.json", hist)
    storage.save("rates.json", out)
    return out


def latest():
    return storage.load("rates.json")
