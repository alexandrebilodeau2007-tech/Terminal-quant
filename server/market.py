"""Données de marché (Yahoo Finance) : chandelles OHLC, force des devises, matrice de performance.

Tout est mis en cache quelques dizaines de secondes pour ménager Yahoo.
"""
import logging
import math
import time
from datetime import datetime, timezone

import httpx

log = logging.getLogger("market")
YF = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"}
_cache: dict = {}

# Symboles proposés dans l'application → symbole Yahoo
SYMBOLS = {
    # Devises
    "DXY": ("DX-Y.NYB", "Indice dollar"), "EURUSD": ("EURUSD=X", "EUR/USD"), "GBPUSD": ("GBPUSD=X", "GBP/USD"),
    "USDJPY": ("USDJPY=X", "USD/JPY"), "USDCAD": ("USDCAD=X", "USD/CAD"), "AUDUSD": ("AUDUSD=X", "AUD/USD"),
    "NZDUSD": ("NZDUSD=X", "NZD/USD"), "USDCHF": ("USDCHF=X", "USD/CHF"), "USDCNH": ("USDCNH=X", "USD/CNH"),
    "EURJPY": ("EURJPY=X", "EUR/JPY"), "GBPJPY": ("GBPJPY=X", "GBP/JPY"), "EURGBP": ("EURGBP=X", "EUR/GBP"),
    "AUDJPY": ("AUDJPY=X", "AUD/JPY"), "EURCHF": ("EURCHF=X", "EUR/CHF"), "CADJPY": ("CADJPY=X", "CAD/JPY"),
    "AUDNZD": ("AUDNZD=X", "AUD/NZD"), "EURAUD": ("EURAUD=X", "EUR/AUD"), "GBPCAD": ("GBPCAD=X", "GBP/CAD"),
    "EURCAD": ("EURCAD=X", "EUR/CAD"), "AUDCAD": ("AUDCAD=X", "AUD/CAD"), "NZDJPY": ("NZDJPY=X", "NZD/JPY"),
    "CHFJPY": ("CHFJPY=X", "CHF/JPY"), "GBPAUD": ("GBPAUD=X", "GBP/AUD"), "GBPCHF": ("GBPCHF=X", "GBP/CHF"),
    # Matières premières
    "GOLD": ("GC=F", "Or"), "SILVER": ("SI=F", "Argent"), "COPPER": ("HG=F", "Cuivre"), "PLATINUM": ("PL=F", "Platine"),
    "WTI": ("CL=F", "Pétrole WTI"), "BRENT": ("BZ=F", "Pétrole Brent"), "NATGAS": ("NG=F", "Gaz naturel"),
    "WHEAT": ("ZW=F", "Blé"), "CORN": ("ZC=F", "Maïs"), "SOYBEAN": ("ZS=F", "Soja"), "COFFEE": ("KC=F", "Café"),
    "SUGAR": ("SB=F", "Sucre"), "COCOA": ("CC=F", "Cacao"), "LUMBER": ("LBR=F", "Bois d'œuvre"),
    # Indices boursiers
    "SPX": ("^GSPC", "S&P 500"), "NDX": ("^NDX", "Nasdaq 100"), "DJI": ("^DJI", "Dow Jones"), "RUT": ("^RUT", "Russell 2000"),
    "TSX": ("^GSPTSE", "TSX (Canada)"), "DAX": ("^GDAXI", "DAX (Allemagne)"), "FTSE": ("^FTSE", "FTSE 100 (R.-U.)"),
    "CAC": ("^FCHI", "CAC 40 (France)"), "STOXX50": ("^STOXX50E", "Euro Stoxx 50"), "NIKKEI": ("^N225", "Nikkei 225"),
    "ASX200": ("^AXJO", "ASX 200"), "HSI": ("^HSI", "Hang Seng"), "SMI": ("^SSMI", "SMI (Suisse)"), "VIX": ("^VIX", "VIX"),
    # Taux
    "US10Y": ("^TNX", "Rendement US 10 ans"), "US2Y": ("2YY=F", "Rendement US 2 ans"), "US30Y": ("^TYX", "Rendement US 30 ans"),
    "US5Y": ("^FVX", "Rendement US 5 ans"),
    # Crypto
    "BTC": ("BTC-USD", "Bitcoin"), "ETH": ("ETH-USD", "Ethereum"),
}
CCYS = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
# paire Yahoo, devise, +1 si la devise est la base (XXX/USD), -1 si elle est la cotée (USD/XXX)
VS_USD = [("EURUSD=X", "EUR", 1), ("GBPUSD=X", "GBP", 1), ("USDJPY=X", "JPY", -1), ("AUDUSD=X", "AUD", 1),
          ("USDCAD=X", "CAD", -1), ("USDCHF=X", "CHF", -1), ("NZDUSD=X", "NZD", 1)]

# intervalle app → (intervalle Yahoo, portée)
INTERVALS = {"1": ("1m", "5d"), "5": ("5m", "1mo"), "15": ("15m", "2mo"), "60": ("60m", "1y"),
             "240": ("60m", "2y"), "D": ("1d", "10y"), "W": ("1wk", "max")}


def _get(url, params, ttl):
    key = (url, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    r = httpx.get(url, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    data = r.json()
    _cache[key] = (time.time(), data)
    if len(_cache) > 400:
        for k in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
            _cache.pop(k, None)
    return data


def yahoo(sym, interval, rng, ttl=60):
    d = _get(YF.format(sym=sym), {"interval": interval, "range": rng, "includePrePost": "false"}, ttl)
    res = d["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": (q.get("volume") or [0] * len(ts))[i] or 0})
    meta = res.get("meta", {})
    return bars, meta


def _aggregate(bars, hours):
    out = []
    for b in bars:
        bucket = b["t"] - (b["t"] % (hours * 3600))
        if out and out[-1]["t"] == bucket:
            x = out[-1]
            x["h"], x["l"], x["c"], x["v"] = max(x["h"], b["h"]), min(x["l"], b["l"]), b["c"], x["v"] + b["v"]
        else:
            out.append({**b, "t": bucket})
    return out


def ohlc(symbol, interval):
    code = symbol.upper()
    ysym = SYMBOLS.get(code, (code, code))[0]
    yi, rng = INTERVALS.get(interval, INTERVALS["60"])
    bars, meta = yahoo(ysym, yi, rng, ttl=30 if yi.endswith("m") else 120)
    if interval == "240":
        bars = _aggregate(bars, 4)
    return {"symbol": code, "name": SYMBOLS.get(code, (code, code))[1], "yahoo": ysym, "interval": interval,
            "price": meta.get("regularMarketPrice"), "prev_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
            "decimals": meta.get("priceHint", 2), "bars": bars}


def quote_table(codes):
    out = []
    for code in codes:
        ysym, name = SYMBOLS.get(code, (code, code))
        try:
            bars, meta = yahoo(ysym, "5m", "1d", ttl=60)
            price = meta.get("regularMarketPrice") or (bars[-1]["c"] if bars else None)
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            out.append({"code": code, "name": name, "price": price, "prev": prev,
                        "chg": (price - prev) if price and prev else None,
                        "chg_pct": (price / prev - 1) * 100 if price and prev else None,
                        "decimals": meta.get("priceHint", 2)})
        except Exception as e:
            out.append({"code": code, "name": name, "error": str(e)[:80]})
    return out


# ---------- prix en direct (pour le temps réel) ----------
def live_prices():
    """Dernier prix de chaque paire majeure (cache 8 s), récupérés en parallèle."""
    from concurrent.futures import ThreadPoolExecutor

    def one(item):
        ysym = item[0]
        try:
            bars, meta = yahoo(ysym, "1m", "1d", ttl=8)
            return ysym, meta.get("regularMarketPrice") or (bars[-1]["c"] if bars else None)
        except Exception:
            return ysym, None
    with ThreadPoolExecutor(7) as ex:
        return dict(ex.map(one, VS_USD))


def _prefetch(specs):
    """Charge en parallèle les historiques Yahoo nécessaires (remplit le cache)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda a: _safe(yahoo, *a), specs))


def _safe(f, *a):
    try:
        return f(*a)
    except Exception:
        return None


# ---------- force des devises (style « Currency Strength ») ----------
WINDOWS = {"td": ("5m", "1d", 0), "8h": ("5m", "1d", 8 * 3600), "1d": ("5m", "5d", 24 * 3600), "tw": ("15m", "5d", 0),
           "5d": ("15m", "1mo", 5 * 86400), "7d": ("30m", "1mo", 7 * 86400), "1m": ("60m", "3mo", 30 * 86400)}


def strength(window="1d"):
    yi, rng, span = WINDOWS.get(window, WINDOWS["1d"])
    _prefetch([(y, yi, rng, 60) for y, _, _ in VS_USD])
    live = live_prices()
    series = {}
    for ysym, ccy, sign in VS_USD:
        bars, _ = yahoo(ysym, yi, rng, ttl=60)
        series[ccy] = (sign, {b["t"]: b["c"] for b in bars})
    now = time.time()
    live_t = int(now)
    if window == "td":
        start = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    elif window == "tw":
        d = datetime.fromtimestamp(now, timezone.utc)
        start = (d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) - ((d.weekday() + 1) % 7) * 86400
        start -= 2 * 3600  # ouverture de Sydney dimanche soir (approx.)
    else:
        start = now - span
    common = None
    for _, (_, m) in series.items():
        ts = {t for t in m if t >= start}
        common = ts if common is None else common & ts
    ts = sorted(common or [])
    if ts and all(live.get(y) for y, _, _ in VS_USD) and live_t > ts[-1]:
        for ysym, ccy, _ in VS_USD:
            series[ccy][1][live_t] = live[ysym]
        ts.append(live_t)
    if len(ts) < 2:
        return {"window": window, "times": [], "series": {}, "latest": {}}
    t0 = ts[0]
    logs = {ccy: [sign * math.log(m[t] / m[t0]) for t in ts] for ccy, (sign, m) in series.items()}
    logs["USD"] = [0.0] * len(ts)
    out = {}
    for i in range(len(ts)):
        mean = sum(logs[c][i] for c in CCYS) / len(CCYS)
        for c in CCYS:
            out.setdefault(c, []).append(round((logs[c][i] - mean) * 10000, 1))  # en points de base
    return {"window": window, "times": ts, "series": out, "latest": {c: out[c][-1] for c in CCYS}, "asof": now}


# ---------- performance des paires et matrice (style Koyfin / PMT) ----------
PERIODS = ["1D", "5D", "MTD", "1M", "3M", "QTD", "YTD", "1Y"]


def _daily_closes():
    out = {}
    _prefetch([(y, "1d", "2y", 300) for y, _, _ in VS_USD])
    lp = live_prices()
    for ysym, ccy, sign in VS_USD:
        bars, meta = yahoo(ysym, "1d", "2y", ttl=300)
        closes = {}
        for b in bars:
            d = datetime.fromtimestamp(b["t"], timezone.utc).date().isoformat()
            closes[d] = b["c"]
        live = lp.get(ysym) or meta.get("regularMarketPrice")
        if live:
            closes[datetime.now(timezone.utc).date().isoformat()] = live
        out[ccy] = (sign, closes)
    return out


def _ref_date(period, dates):
    today = datetime.now(timezone.utc).date()
    if period == "1D":
        return dates[-2] if len(dates) > 1 else dates[0]
    if period == "5D":
        return dates[-6] if len(dates) > 5 else dates[0]
    if period == "MTD":
        target = today.replace(day=1).isoformat()
    elif period == "QTD":
        target = today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1).isoformat()
    elif period == "YTD":
        target = today.replace(month=1, day=1).isoformat()
    elif period == "1M":
        target = (today - __import__("datetime").timedelta(days=30)).isoformat()
    elif period == "3M":
        target = (today - __import__("datetime").timedelta(days=91)).isoformat()
    else:
        target = (today - __import__("datetime").timedelta(days=365)).isoformat()
    before = [d for d in dates if d < target]
    return before[-1] if before else dates[0]


def performance(period="1D"):
    data = _daily_closes()
    dates = sorted(set.intersection(*[set(c.keys()) for _, c in data.values()]))
    if not dates:
        return {"period": period, "matrix": [], "pairs": []}
    ref = _ref_date(period, dates)
    last = dates[-1]
    # valeur de chaque devise en USD
    usd_now, usd_ref = {"USD": 1.0}, {"USD": 1.0}
    for ccy, (sign, closes) in data.items():
        usd_now[ccy] = closes[last] if sign > 0 else 1 / closes[last]
        usd_ref[ccy] = closes[ref] if sign > 0 else 1 / closes[ref]
    matrix = []
    for base in CCYS:
        row = {"ccy": base, "cells": {}}
        for quote in CCYS:
            if base == quote:
                row["cells"][quote] = None
            else:
                now_ = usd_now[base] / usd_now[quote]
                ref_ = usd_ref[base] / usd_ref[quote]
                row["cells"][quote] = round((now_ / ref_ - 1) * 100, 2)
        row["avg"] = round(sum(v for v in row["cells"].values() if v is not None) / (len(CCYS) - 1), 2)
        matrix.append(row)
    matrix.sort(key=lambda r: -r["avg"])
    pairs = []
    for b, q in [("EUR", "USD"), ("GBP", "USD"), ("USD", "JPY"), ("USD", "CAD"), ("AUD", "USD"), ("NZD", "USD"), ("USD", "CHF"),
                 ("EUR", "GBP"), ("EUR", "JPY"), ("GBP", "JPY"), ("AUD", "JPY"), ("EUR", "CHF"), ("AUD", "NZD"), ("CAD", "JPY")]:
        now_ = usd_now[b] / usd_now[q]
        ref_ = usd_ref[b] / usd_ref[q]
        pairs.append({"pair": b + q, "price": round(now_, 5), "chg_pct": round((now_ / ref_ - 1) * 100, 2)})
    return {"period": period, "ref_date": ref, "date": last, "matrix": matrix, "pairs": pairs, "ccys": CCYS, "asof": time.time()}


def normalized(period="1D"):
    """Courbes normalisées (% depuis la référence) pour les 7 majeures, style Koyfin."""
    yi, rng = {"1D": ("5m", "5d"), "5D": ("15m", "1mo"), "1M": ("60m", "3mo"), "3M": ("1d", "1y"),
               "YTD": ("1d", "2y"), "1Y": ("1d", "2y"), "MTD": ("60m", "3mo"), "QTD": ("1d", "1y")}.get(period, ("5m", "5d"))
    pairs = {"EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "USDCAD": "USDCAD=X",
             "AUDUSD": "AUDUSD=X", "NZDUSD": "NZDUSD=X", "USDCHF": "USDCHF=X"}
    _prefetch([(y, yi, rng, 60) for y in pairs.values()])
    series = {p: {b["t"]: b["c"] for b in yahoo(y, yi, rng, ttl=60)[0]} for p, y in pairs.items()}
    daily = _daily_closes()
    dates = sorted(set.intersection(*[set(c.keys()) for _, c in daily.values()]))
    ref = _ref_date(period, dates)
    start = datetime.fromisoformat(ref).replace(tzinfo=timezone.utc).timestamp() + 86400 * (0 if period in ("1D", "5D") else 0)
    if period == "1D":
        start = time.time() - 86400
    common = None
    for m in series.values():
        ts = {t for t in m if t >= start}
        common = ts if common is None else common & ts
    ts = sorted(common or [])
    lp = live_prices()
    live_t = int(time.time())
    if ts and all(lp.get(y) for y in pairs.values()) and live_t > ts[-1]:
        for p, y in pairs.items():
            series[p][live_t] = lp[y]
        ts.append(live_t)
    if not ts:
        return {"period": period, "times": [], "series": {}}
    out = {p: [round((m[t] / m[ts[0]] - 1) * 100, 3) for t in ts] for p, m in series.items()}
    return {"period": period, "times": ts, "series": out}
