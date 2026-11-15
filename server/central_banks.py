"""Fiche par devise : taux directeur, inflation vs cible, données clés, ton de la banque
centrale (hawkish / dovish) et nouvelles associées.

Le ton est un indicateur HEURISTIQUE transparent (chaque composante est affichée) :
  - dernier mouvement de taux et mouvements sur 12 mois
  - inflation vs cible de la banque centrale
  - ton des titres de nouvelles récents (mots-clés hawkish/dovish)
"""
import re
from datetime import datetime, timedelta, timezone

from .countries import CURRENCIES, RATE_KEYWORDS, KEY_INDICATOR_HINTS
from .calendar_data import parse_time, _num

HAWK = ["hawkish", "hike", "hikes", "hiking", "tighten", "tightening", "higher for longer", "raise rates",
        "rate rise", "inflation risks", "upside risk", "no rush to cut", "pause cuts", "sticky inflation",
        "restrictive", "fewer cuts", "pushes back on cuts"]
DOVE = ["dovish", "cut", "cuts", "cutting", "easing", "ease", "lower rates", "rate reduction", "downside risk",
        "slowdown", "weakening", "accommodative", "stimulus", "qe"]
_HAWK_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in HAWK) + r")\b")
_HAWK_P = re.compile(r"\b(no rush|not in a hurry|no hurry|in no hurry|push(?:es|ed)? back|patient|premature to cut)\b")
_DOVE_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in DOVE) + r")\b")


def _primary_country(ccy):
    return CURRENCIES[ccy]["countries"][0]


def _is_rate(title: str) -> bool:
    t = title.lower().strip()
    if "projection" in t or "reserve balances" in t or "mortgage" in t:
        return False
    return t == "interest rate" or any(k in t for k in RATE_KEYWORDS)


def _latest(events, country, pred):
    cands = [e for e in events if e["country"] == country and e.get("actual") is not None and pred(e["title"].lower())]
    return cands[-1] if cands else None


def policy_rate(events, ccy):
    country = _primary_country(ccy)
    rate_events = [e for e in events if e["country"] == country and _is_rate(e["title"]) and e.get("actual") is not None]
    if ccy == "EUR":  # la BCE pilote par le taux de dépôt
        dep = [e for e in rate_events if "deposit" in e["title"].lower()]
        rate_events = dep or rate_events
    if ccy == "CNY":
        lpr = [e for e in rate_events if "1y" in e["title"].lower() or "1-year" in e["title"].lower()]
        rate_events = lpr or rate_events
    if not rate_events:
        return None
    last = rate_events[-1]
    one_year = datetime.now(timezone.utc) - timedelta(days=365)
    moves = []
    for e in rate_events:
        a, p = _num(e.get("actual")), _num(e.get("previous"))
        if a is not None and p is not None and abs(a - p) > 1e-9 and parse_time(e["time"]) >= one_year:
            moves.append({"time": e["time"], "from": p, "to": a, "bp": round((a - p) * 100)})
    a, p = _num(last.get("actual")), _num(last.get("previous"))
    return {"title": last["title"], "time": last["time"], "rate": a, "previous": p,
            "last_change_bp": round((a - p) * 100) if a is not None and p is not None else None,
            "moves_12m": moves}


def inflation(events, ccy):
    country = _primary_country(ccy)
    head = _latest(events, country, lambda t: ("inflation rate yoy" in t or "cpi y/y" in t or "cpi yoy" in t)
                   and "core" not in t)
    core = _latest(events, country, lambda t: "core" in t and ("inflation" in t or "cpi" in t or "pce" in t)
                   and ("yoy" in t or "y/y" in t))
    return head, core


def news_tone(news_items, ccy, days=14):
    d = CURRENCIES[ccy]
    bank_words = [w for w in d["keywords"][:3]]
    since = datetime.now(timezone.utc) - timedelta(days=days)
    score, hits = 0, []
    for n in news_items:
        txt = f" {n.get('title','')} {n.get('summary','')} ".lower()
        if not any(w in txt for w in bank_words):
            continue
        if n.get("time"):
            try:
                if parse_time(n["time"]) < since:
                    continue
            except Exception:
                pass
        h = len(_HAWK_RE.findall(txt)) + 2 * len(_HAWK_P.findall(txt))
        dv = len(_DOVE_RE.findall(txt))
        if h == dv:
            continue
        s = 1 if h > dv else -1
        score += s
        hits.append({"title": n["title"], "link": n.get("link"), "tone": "hawkish" if s > 0 else "dovish",
                     "time": n.get("time"), "source": n.get("source")})
    return score, hits[:8]


def stance(ccy, events, news_items):
    pr = policy_rate(events, ccy)
    cpi, core = inflation(events, ccy)
    target = CURRENCIES[ccy]["target"]
    comps, score = [], 0.0

    if pr:
        if pr["last_change_bp"]:
            v = 1.5 if pr["last_change_bp"] > 0 else -1.5
            score += v
            comps.append({"label": f"Dernière décision : {'+' if pr['last_change_bp']>0 else ''}{pr['last_change_bp']} pb", "score": v})
        else:
            comps.append({"label": "Dernière décision : statu quo", "score": 0})
        net = sum(m["bp"] for m in pr["moves_12m"])
        if net:
            v = max(-1.0, min(1.0, net / 100))
            score += v
            comps.append({"label": f"Mouvements nets 12 mois : {'+' if net>0 else ''}{net} pb", "score": round(v, 2)})

    infl = _num(core["actual"]) if core else (_num(cpi["actual"]) if cpi else None)
    if infl is not None:
        gap = infl - target
        v = 1.0 if gap > 0.75 else (-1.0 if gap < -0.5 else 0.0)
        score += v
        comps.append({"label": f"Inflation {'core ' if core else ''}{infl:g}% vs cible {target:g}%", "score": v})

    ns, hits = news_tone(news_items, ccy)
    if ns:
        v = max(-1.5, min(1.5, ns * 0.5))
        score += v
        comps.append({"label": f"Ton des nouvelles (14 j) : {ns:+d}", "score": v})

    label = "Hawkish" if score >= 1.0 else ("Dovish" if score <= -1.0 else "Neutre")
    return {"label": label, "score": round(score, 2), "components": comps}, pr, cpi, core, hits


def key_data(events, ccy, limit=14):
    countries = CURRENCIES[ccy]["countries"]
    latest = {}
    for e in events:
        if e["country"] not in countries or e.get("actual") is None:
            continue
        t = e["title"].lower()
        if e["impact"] != "high" and not any(h in t for h in KEY_INDICATOR_HINTS):
            continue
        latest[(e["country"], e["title"])] = e

    def prio(e):
        t = e["title"].lower()
        for i, h in enumerate(KEY_INDICATOR_HINTS):
            if h in t:
                return (0 if e["country"] == countries[0] else 1, i)
        return (2, 99)

    rows = sorted(latest.values(), key=prio)[:limit]
    return [{"title": e["title"], "country": e["country"], "period": e.get("period"), "time": e["time"],
             "actual": e["actual_str"], "forecast": e["forecast_str"], "previous": e["previous_str"],
             "surprise": e.get("surprise"), "impact": e["impact"]} for e in rows]


def currency_overview(ccy, history, week_events, news_items):
    by_id = {e["id"]: e for e in history}
    by_id.update({e["id"]: e for e in week_events})
    all_events = sorted(by_id.values(), key=lambda e: e["time"])
    st, pr, cpi, core, hits = stance(ccy, all_events, news_items)
    d = CURRENCIES[ccy]
    now = datetime.now(timezone.utc)
    upcoming = [e for e in week_events if e["currency"] == ccy and e["impact"] in ("high", "medium")
                and parse_time(e["time"]) >= now - timedelta(hours=2)]
    kw = d["keywords"]
    news = [n for n in news_items if any(k in f" {n.get('title','')} ".lower() for k in kw)][:12]
    return {
        "code": ccy, "name": d["name"], "flag": d["flag"], "bank": d["bank"], "countries": d["countries"],
        "index_symbol": d["index"], "target": d["target"],
        "stance": st, "policy_rate": pr,
        "cpi": {"value": cpi["actual_str"], "period": cpi.get("period"), "title": cpi["title"]} if cpi else None,
        "core_cpi": {"value": core["actual_str"], "period": core.get("period"), "title": core["title"]} if core else None,
        "key_data": key_data(all_events, ccy),
        "upcoming": upcoming,
        "red_count": sum(1 for e in week_events if e["currency"] == ccy and e["impact"] == "high"),
        "orange_count": sum(1 for e in week_events if e["currency"] == ccy and e["impact"] == "medium"),
        "tone_news": hits, "news": news,
    }
