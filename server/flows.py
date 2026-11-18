"""Flux quotidiens : prix + intérêts ouverts (open interest) des contrats à terme (TradingView).

Lecture classique, au jour le jour (proxy du positionnement, pas le COT) :
  prix ↑ et OI ↑  → nouvelles positions acheteuses
  prix ↓ et OI ↑  → nouvelles positions vendeuses
  prix ↑ et OI ↓  → rachat de positions vendeuses (short covering)
  prix ↓ et OI ↓  → liquidation de positions acheteuses
Une forte baisse d'OI d'un coup signale plutôt le roulement vers le contrat suivant.
"""
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from . import storage

log = logging.getLogger("flows")
SCAN = "https://scanner.tradingview.com/futures/scan"
TZ = ZoneInfo("America/Toronto")

FUTURES = {
    # devises
    "CME:6E1!": ("EUR", "Euro", "fx"), "CME:6B1!": ("GBP", "Livre sterling", "fx"), "CME:6J1!": ("JPY", "Yen", "fx"),
    "CME:6C1!": ("CAD", "Dollar canadien", "fx"), "CME:6A1!": ("AUD", "Dollar australien", "fx"),
    "CME:6N1!": ("NZD", "Dollar néo-zélandais", "fx"), "CME:6S1!": ("CHF", "Franc suisse", "fx"),
    "ICEUS:DX1!": ("USD", "Dollar US (DXY)", "fx"),
    # indices
    "CME_MINI:ES1!": ("SPX", "S&P 500 (E-mini)", "idx"), "CME_MINI:NQ1!": ("NDX", "Nasdaq 100 (E-mini)", "idx"),
    "CBOT_MINI:YM1!": ("DJI", "Dow Jones (E-mini)", "idx"), "CME_MINI:RTY1!": ("RUT", "Russell 2000 (E-mini)", "idx"),
    "CBOE:VX1!": ("VIX", "VIX", "idx"),
    # taux
    "CBOT:ZT1!": ("US2Y", "Note US 2 ans", "rates"), "CBOT:ZF1!": ("US5Y", "Note US 5 ans", "rates"),
    "CBOT:ZN1!": ("US10Y", "Note US 10 ans", "rates"), "CBOT:ZB1!": ("US30Y", "Obligation US 30 ans", "rates"),
    # matières premières
    "COMEX:GC1!": ("GOLD", "Or", "cmd"), "COMEX:SI1!": ("SILVER", "Argent", "cmd"), "NYMEX:PL1!": ("PLATINUM", "Platine", "cmd"),
    "COMEX:HG1!": ("COPPER", "Cuivre", "cmd"), "NYMEX:CL1!": ("WTI", "Pétrole WTI", "cmd"), "NYMEX:BZ1!": ("BRENT", "Pétrole Brent", "cmd"),
    "NYMEX:NG1!": ("NATGAS", "Gaz naturel", "cmd"), "CBOT:ZW1!": ("WHEAT", "Blé", "cmd"), "CBOT:ZC1!": ("CORN", "Maïs", "cmd"),
    "CBOT:ZS1!": ("SOYBEAN", "Soja", "cmd"), "ICEUS:KC1!": ("COFFEE", "Café", "cmd"), "ICEUS:SB1!": ("SUGAR", "Sucre", "cmd"),
    "ICEUS:CC1!": ("COCOA", "Cacao", "cmd"),
}
ROLL_PCT = 25.0  # baisse d'OI au-delà de laquelle on parle de roulement


def _scan():
    r = httpx.post(SCAN, json={"symbols": {"tickers": list(FUTURES)}, "columns": ["close", "open_interest", "change", "volume"]},
                   timeout=25, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return {d["s"]: d["d"] for d in r.json().get("data", [])}


def reading(dp, doi_pct):
    if doi_pct is None or dp is None:
        return "—", "neu"
    if doi_pct <= -ROLL_PCT:
        return "Roulement de contrat", "neu"
    if abs(doi_pct) < 0.3:
        return "Positions stables", "neu"
    if dp >= 0 and doi_pct > 0:
        return "Nouveaux acheteurs", "pos"
    if dp < 0 and doi_pct > 0:
        return "Nouveaux vendeurs", "neg"
    if dp >= 0 and doi_pct < 0:
        return "Rachat de shorts", "pos"
    return "Liquidation de longs", "neg"


def refresh():
    """Une photo par jour (la dernière de la journée l'emporte) ; garde 90 jours."""
    data = _scan()
    hist = storage.load("flows_hist.json", {"days": {}})
    day = datetime.now(TZ).date().isoformat()
    hist["days"][day] = {t: {"close": d[0], "oi": d[1], "chg": d[2]} for t, d in data.items() if d and d[0] is not None}
    for d in sorted(hist["days"])[:-90]:
        hist["days"].pop(d)
    storage.save("flows_hist.json", hist)
    days = sorted(hist["days"])
    prev_day = days[-2] if len(days) > 1 else None
    prev = hist["days"].get(prev_day, {}) if prev_day else {}
    rows = []
    for t, (key, name, cls) in FUTURES.items():
        cur = hist["days"][day].get(t)
        if not cur:
            continue
        p = prev.get(t) or {}
        doi = (cur["oi"] - p["oi"]) if p.get("oi") and cur.get("oi") else None
        doi_pct = (doi / p["oi"] * 100) if doi is not None and p["oi"] else None
        dp = cur.get("chg")
        label, tone = reading(dp, doi_pct)
        # série d'OI pour la mini-tendance (20 derniers jours)
        series = [hist["days"][d][t]["oi"] for d in days[-20:] if t in hist["days"][d] and hist["days"][d][t].get("oi")]
        rows.append({"ticker": t, "key": key, "name": name, "class": cls, "price": cur["close"], "chg_pct": dp,
                     "oi": cur.get("oi"), "doi": doi, "doi_pct": round(doi_pct, 2) if doi_pct is not None else None,
                     "reading": label, "tone": tone, "oi_series": series})
    out = {"updated": time.time(), "day": day, "prev_day": prev_day, "rows": rows}
    storage.save("flows.json", out)
    return out


def latest():
    return storage.load("flows.json")
