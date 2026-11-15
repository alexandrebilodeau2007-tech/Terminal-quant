"""Analyse du dimanche : ce qui s'en vient la semaine prochaine (dossiers ORANGE + ROUGE seulement)."""
import json
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from . import storage
from .config import TIMEZONE, ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from .countries import CURRENCIES
from .calendar_data import parse_time, _num, week_bounds
from .central_banks import _is_rate

log = logging.getLogger("weekly")
TZ = ZoneInfo(TIMEZONE)
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

TOP_WORDS = ["rate decision", "interest rate", "cash rate", "bank rate", "non farm", "nonfarm", "payroll",
             "cpi", "inflation", "pce", "gdp", "unemployment", "employment change", "retail sales", "pmi",
             "fomc", "minutes", "press conference", "speech"]


def _expect(e):
    f, p = _num(e.get("forecast")), _num(e.get("previous"))
    if f is None or p is None:
        return "consensus non disponible" if f is None else ""
    if abs(f - p) < 1e-9:
        return "attendu stable"
    return "attendu en hausse" if f > p else "attendu en baisse"


def _when(e):
    t = parse_time(e["time"]).astimezone(TZ)
    return f"{JOURS[t.weekday()]} {t:%d/%m} {t:%H:%M}"


def _weight(e):
    t = e["title"].lower()
    w = 10 if e["impact"] == "high" else 3
    if _is_rate(e["title"]):
        w += 20
    w += sum(4 for k in TOP_WORDS if k in t)
    return w


def build(week_events: list[dict], overviews: dict) -> dict:
    start, end = week_bounds()
    evs = [e for e in week_events if e["impact"] in ("high", "medium")
           and start <= parse_time(e["time"]) < end]
    per_ccy = {}
    for ccy in CURRENCIES:
        lst = [e for e in evs if e["currency"] == ccy]
        ov = overviews.get(ccy, {})
        rate_week = [e for e in lst if _is_rate(e["title"])]
        reds = [e for e in lst if e["impact"] == "high"]
        load = "très chargée" if len(reds) >= 5 else "chargée" if len(reds) >= 2 else "calme" if not reds else "modérée"
        bullets = []
        for e in sorted(lst, key=_weight, reverse=True)[:5]:
            exp = _expect(e)
            bullets.append(f"{_when(e)} — {e['title']} ({'🔴' if e['impact']=='high' else '🟠'}) : "
                           f"consensus {e['forecast_str']} vs préc. {e['previous_str']}" + (f", {exp}" if exp else ""))
        st = (ov.get("stance") or {}).get("label", "—")
        pr = ov.get("policy_rate") or {}
        text = f"Semaine {load} pour le {ccy} ({len(reds)} 🔴, {len(lst)-len(reds)} 🟠). "
        text += f"Ton de la {CURRENCIES[ccy]['bank'].split('(')[-1].rstrip(')')} : {st}"
        if pr.get("rate") is not None:
            text += f" (taux {pr['rate']:g}%)"
        text += ". "
        if rate_week:
            text += f"⚠️ Décision de taux cette semaine : {_when(rate_week[0])} — volatilité maximale attendue sur le {ccy}. "
        per_ccy[ccy] = {"summary": text, "bullets": bullets, "events": lst, "red": len(reds), "orange": len(lst) - len(reds),
                        "stance": st}

    top = sorted(evs, key=_weight, reverse=True)[:8]
    headline = "Catalyseurs majeurs : " + "; ".join(f"{e['currency']} {e['title']} ({_when(e)})" for e in top[:4]) \
        if top else "Aucun événement orange/rouge cette semaine."
    by_day = {}
    for e in evs:
        d = parse_time(e["time"]).astimezone(TZ)
        by_day.setdefault(f"{JOURS[d.weekday()]} {d:%d/%m}", []).append(e)

    report = {"week_start": start.isoformat(), "week_end": end.isoformat(),
              "generated": datetime.now(timezone.utc).isoformat(), "headline": headline,
              "top": top, "per_currency": per_ccy, "by_day": by_day,
              "counts": {"red": sum(1 for e in evs if e["impact"] == "high"),
                         "orange": sum(1 for e in evs if e["impact"] == "medium")},
              "ai_analysis": None}
    report["ai_analysis"] = _ai(report, overviews)
    return report


def _ai(report, overviews):
    if not ANTHROPIC_API_KEY:
        return None
    compact = {
        "evenements": [{"devise": e["currency"], "quand_ET": _when(e), "titre": e["title"], "impact": e["impact"],
                        "consensus": e["forecast_str"], "precedent": e["previous_str"]}
                       for d in report["by_day"].values() for e in d],
        "banques_centrales": {c: {"ton": (o.get("stance") or {}).get("label"),
                                  "composantes": [x["label"] for x in (o.get("stance") or {}).get("components", [])],
                                  "taux": (o.get("policy_rate") or {}).get("rate"),
                                  "cpi": (o.get("cpi") or {}).get("value")}
                              for c, o in overviews.items()},
    }
    prompt = ("Tu es un stratège macro FX institutionnel. Rédige en français, de façon directe et concise, "
              "l'analyse de la semaine à venir à partir de ces données (événements orange/rouge seulement, heures de l'Est). "
              "Structure : 1) Vue d'ensemble (3-4 phrases) 2) Par devise : ce qui compte, scénarios au-dessus/sous le consensus "
              "et l'effet probable sur la devise 3) Les 3 moments les plus risqués de la semaine 4) Ce qui pourrait surprendre. "
              "N'invente aucun chiffre absent des données. Maximum 600 mots.\n\nDONNÉES:\n"
              + json.dumps(compact, ensure_ascii=False))
    try:
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=90,
                       headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                                "content-type": "application/json"},
                       json={"model": ANTHROPIC_MODEL, "max_tokens": 1600,
                             "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    except Exception as e:
        log.warning("Analyse IA impossible: %s", e)
        return None


def save(report):
    key = parse_time(report["week_start"]).astimezone(TZ).strftime("%Y-%m-%d")
    storage.save(f"weekly/{key}.json", report)
    storage.save("weekly/latest.json", report)


def latest():
    return storage.load("weekly/latest.json")
