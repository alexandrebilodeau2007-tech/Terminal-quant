"""Saisonnalité façon Seasonax : courbe saisonnière moyenne, stats mensuelles,
et analyse d'une fenêtre de dates (rendement moyen, médian, % d'années gagnantes)."""
import io
import logging
import time
from datetime import date

import numpy as np
import pandas as pd

from . import storage

log = logging.getLogger("seasonality")

SYMBOLS = {
    "DXY": ("DX-Y.NYB", "dx.f"), "EURUSD": ("EURUSD=X", "eurusd"), "GBPUSD": ("GBPUSD=X", "gbpusd"),
    "USDJPY": ("JPY=X", "usdjpy"), "USDCAD": ("CAD=X", "usdcad"), "AUDUSD": ("AUDUSD=X", "audusd"),
    "NZDUSD": ("NZDUSD=X", "nzdusd"), "USDCHF": ("CHF=X", "usdchf"), "USDCNH": ("CNH=X", "usdcnh"),
    "EURJPY": ("EURJPY=X", "eurjpy"), "GBPJPY": ("GBPJPY=X", "gbpjpy"), "EURGBP": ("EURGBP=X", "eurgbp"),
    "AUDJPY": ("AUDJPY=X", "audjpy"),
    "XAUUSD (Or)": ("GC=F", "xauusd"), "XAGUSD (Argent)": ("SI=F", "xagusd"), "WTI": ("CL=F", "cl.f"),
    "S&P 500": ("^GSPC", "^spx"), "Nasdaq 100": ("^NDX", "^ndx"), "Bitcoin": ("BTC-USD", "btcusd"),
}


def _download(symbol_key: str) -> pd.Series:
    cache_name = f"prices/{symbol_key.replace(' ', '_').replace('/', '_')}.csv"
    p = storage.path(cache_name)
    if p.exists() and time.time() - p.stat().st_mtime < 12 * 3600:
        s = pd.read_csv(p, index_col=0, parse_dates=True).iloc[:, 0]
        return s.dropna()
    yf_sym, stooq_sym = SYMBOLS[symbol_key]
    s = None
    try:
        import yfinance as yf
        df = yf.download(yf_sym, period="max", interval="1d", auto_adjust=True, progress=False)
        if df is not None and len(df):
            close = df["Close"]
            s = (close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close).dropna()
    except Exception as e:
        log.info("yfinance %s: %s", yf_sym, e)
    if s is None or len(s) < 500:
        try:
            import httpx
            r = httpx.get(f"https://stooq.com/q/d/l/?s={stooq_sym}&i=d", timeout=20)
            df = pd.read_csv(io.StringIO(r.text), parse_dates=["Date"], index_col="Date")
            s = df["Close"].dropna()
        except Exception as e:
            log.warning("stooq %s: %s", stooq_sym, e)
    if s is None or not len(s):
        raise RuntimeError(f"Pas de données pour {symbol_key}")
    s.index = pd.to_datetime(s.index).tz_localize(None)
    s.to_frame("close").to_csv(p)
    return s


def analyze(series: pd.Series, years: int = 15, start_md: str | None = None, end_md: str | None = None) -> dict:
    series = series.sort_index()
    series = series[~series.index.duplicated()]
    this_year = date.today().year
    first_year = max(series.index.min().year + 1, this_year - years)
    hist_years = [y for y in range(first_year, this_year) if (series.index.year == y).sum() > 150]

    # Courbe saisonnière : chaque année normalisée à 0 % au 1er janvier, par jour de l'année
    grid = np.arange(1, 367)
    paths = []
    for y in hist_years:
        s = series[series.index.year == y]
        doy = s.index.dayofyear.values
        cum = (s.values / s.values[0] - 1) * 100
        paths.append(pd.Series(cum, index=doy).reindex(grid).ffill().bfill().values)
    avg = np.nanmean(paths, axis=0) if paths else np.zeros(len(grid))
    cur = series[series.index.year == this_year]
    current = []
    if len(cur):
        cum = (cur.values / cur.values[0] - 1) * 100
        current = [{"doy": int(d), "v": round(float(v), 3)} for d, v in zip(cur.index.dayofyear, cum)]

    # Stats mensuelles
    monthly = series.resample("ME").last().pct_change().dropna() * 100
    monthly = monthly[monthly.index.year.isin(hist_years)]
    months = []
    for m in range(1, 13):
        v = monthly[monthly.index.month == m]
        months.append({"month": m, "avg": round(float(v.mean()), 3) if len(v) else None,
                       "median": round(float(v.median()), 3) if len(v) else None,
                       "win_rate": round(float((v > 0).mean() * 100), 1) if len(v) else None, "n": int(len(v))})

    out = {"years": hist_years, "seasonal": [round(float(x), 3) for x in avg], "current": current,
           "monthly": months, "last_price": round(float(series.iloc[-1]), 5),
           "last_date": series.index[-1].strftime("%Y-%m-%d")}

    if start_md and end_md:
        out["window"] = window_stats(series, hist_years, start_md, end_md)
    return out


def window_stats(series, hist_years, start_md, end_md):
    sm, sd = map(int, start_md.split("-"))
    em, ed = map(int, end_md.split("-"))
    rows = []
    for y in hist_years:
        try:
            a = pd.Timestamp(y, sm, sd)
            b = pd.Timestamp(y + (1 if (em, ed) < (sm, sd) else 0), em, ed)
        except ValueError:
            continue
        s = series[(series.index >= a) & (series.index <= b)]
        if len(s) < 2:
            continue
        rows.append({"year": y, "ret": round(float((s.iloc[-1] / s.iloc[0] - 1) * 100), 3),
                     "max_dd": round(float(((s / s.cummax()) - 1).min() * 100), 3)})
    rets = np.array([r["ret"] for r in rows]) if rows else np.array([])
    return {"start": start_md, "end": end_md, "per_year": rows,
            "avg": round(float(rets.mean()), 3) if len(rets) else None,
            "median": round(float(np.median(rets)), 3) if len(rets) else None,
            "win_rate": round(float((rets > 0).mean() * 100), 1) if len(rets) else None,
            "best": round(float(rets.max()), 3) if len(rets) else None,
            "worst": round(float(rets.min()), 3) if len(rets) else None, "n": int(len(rets))}


def run(symbol_key: str, years=15, start_md=None, end_md=None) -> dict:
    if symbol_key not in SYMBOLS:
        raise KeyError(symbol_key)
    res = analyze(_download(symbol_key), years, start_md, end_md)
    res["symbol"] = symbol_key
    return res
