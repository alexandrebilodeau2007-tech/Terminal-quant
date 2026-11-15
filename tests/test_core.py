"""Tests hors-ligne : sources simulées (aucun accès réseau requis).
Lancer :  python -m pytest -q tests   (ou)   python tests/test_core.py
"""
import os, sys, tempfile, json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

import numpy as np, pandas as pd
from server import sources, calendar_data as cal, engine, push, weekly, seasonality, central_banks

NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)


def tv(id_, dt, country, title, imp, forecast, previous, actual=None, unit=None, scale=None, period="Oct 2026"):
    return {"id": id_, "date": dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "country": country, "title": title,
            "indicator": title, "importance": imp, "forecast": forecast, "previous": previous, "actual": actual,
            "unit": unit, "scale": scale, "period": period}


WEEK = [
    tv("1", NOW + timedelta(minutes=10), "US", "Core Inflation Rate YoY", 1, 3.0, 2.9, unit="%"),
    tv("2", NOW - timedelta(minutes=1), "CA", "Unemployment Rate", 1, 6.5, 6.5, unit="%"),
    tv("3", NOW + timedelta(days=1), "GB", "BoE Interest Rate Decision", 1, 3.75, 4.0, unit="%"),
    tv("4", NOW + timedelta(hours=5), "DE", "ZEW Economic Sentiment Index", 0, 40.0, 39.3),
    tv("5", NOW + timedelta(hours=6), "US", "Initial Jobless Claims", 0, 225, 230, scale="K"),
    tv("6", NOW - timedelta(hours=3), "US", "Non Farm Payrolls", 1, 65, 60, actual=165, scale="K"),
]
HISTORY = [
    tv("h1", NOW - timedelta(days=200), "US", "Fed Interest Rate Decision", 1, 4.25, 4.5, actual=4.25, unit="%"),
    tv("h2", NOW - timedelta(days=60), "US", "Fed Interest Rate Decision", 1, 4.0, 4.25, actual=4.0, unit="%"),
    tv("h3", NOW - timedelta(days=20), "US", "Inflation Rate YoY", 1, 3.0, 2.9, actual=3.1, unit="%"),
    tv("h4", NOW - timedelta(days=20), "US", "Core Inflation Rate YoY", 1, 3.0, 3.0, actual=3.2, unit="%"),
    tv("h5", NOW - timedelta(days=40), "JP", "BoJ Interest Rate Decision", 1, 0.75, 0.5, actual=0.75, unit="%"),
    tv("h6", NOW - timedelta(days=15), "JP", "Inflation Rate YoY", 1, 2.9, 2.7, actual=3.0, unit="%"),
    tv("h7", NOW - timedelta(days=30), "EU", "Deposit Facility Rate", 1, 2.0, 2.0, actual=2.0, unit="%"),
]
FF = [
    {"title": "ZEW Economic Sentiment", "country": "EUR", "date": (NOW + timedelta(hours=5)).isoformat(),
     "impact": "High", "forecast": "40.0", "previous": "39.3"},
    {"title": "RBA Gov Speaks", "country": "AUD", "date": (NOW + timedelta(days=2)).isoformat(),
     "impact": "Medium", "forecast": "", "previous": ""},
]
NEWS = [{"title": "Fed officials signal no rush to cut as inflation stays sticky", "link": "https://x", "time": NOW.isoformat(),
         "summary": "", "source": "InvestingLive"},
        {"title": "BOJ seen ready to hike again in December", "link": "https://y", "time": NOW.isoformat(),
         "summary": "", "source": "InvestingLive"}]

state = {"fast": False}


def fake_tv(start, end, countries):
    if (end - start) > timedelta(days=20):
        return [r for r in HISTORY if start <= cal.parse_time(r["date"]) < end]
    if (end - start) <= timedelta(minutes=10):  # fast poll : le chiffre canadien vient de sortir
        state["fast"] = True
        out = []
        for r in WEEK:
            if start <= cal.parse_time(r["date"]) <= end:
                r2 = dict(r)
                if r2["id"] == "2":
                    r2["actual"] = 6.9
                out.append(r2)
        return out
    return [r for r in WEEK if start <= cal.parse_time(r["date"]) < end]


sources.fetch_tradingview = fake_tv
sources.fetch_forexfactory = lambda which="thisweek": FF if which == "thisweek" else []
sources.fetch_news = lambda: NEWS
sources.fetch_financialjuice = lambda: [{"title": "ECB's Lagarde: Not in a hurry to cut rates", "link": "https://fj",
                                         "time": NOW.isoformat(), "summary": "", "source": "FinancialJuice"}]
SENT = []
push.send = lambda title, body, **kw: SENT.append((title, body, kw)) or 1


def test_pipeline():
    evs = engine.refresh_week()
    titles = {e["title"] for e in evs}
    assert "RBA Gov Speaks" in titles, "événement FF seul conservé"
    zew = next(e for e in evs if e["title"].startswith("ZEW"))
    assert zew["impact"] == "high" and "Forex Factory" in zew["sources"], "FF rehausse l'impact"
    nfp = next(e for e in evs if e["title"] == "Non Farm Payrolls")
    assert nfp["actual_str"] == "165K" and nfp["surprise"]["ccy_bias"] == "positif"
    claims = next(e for e in evs if "Jobless" in e["title"])
    claims["actual"] = 240; cal.decorate(claims)
    assert claims["surprise"]["ccy_bias"] == "négatif", "inverse pour les inscriptions au chômage"

    cal.refresh_history()
    engine.refresh_news()
    engine.refresh_fj()
    assert engine.news_items()[0]["source"] in ("FinancialJuice", "InvestingLive")
    ov = engine.overviews()
    usd, jpy = ov["USD"], ov["JPY"]
    assert usd["policy_rate"]["rate"] == 4.0 and usd["policy_rate"]["last_change_bp"] == -25
    assert jpy["stance"]["label"] == "Hawkish", jpy["stance"]
    print("USD", usd["stance"], "\nJPY", jpy["stance"])

    engine.check_alerts()
    kinds = [k["kind"] for _, _, k in SENT]
    assert "reminder" in kinds, SENT
    assert state["fast"], "fast poll lancé"
    rel = [t for t, b, k in SENT if k["kind"] == "release"]
    assert any("Unemployment" in t and "6.9%" in t for t in rel), rel
    for t, b, k in SENT:
        print("PUSH:", t, "|", b.replace("\n", " / "))
    n = len(SENT)
    engine.check_alerts()
    assert len([s for s in SENT[n:] if s[2]["kind"] != "release" or "Non Farm" not in s[0]]) == 0, "pas de doublon"

    rep = engine.generate_weekly(notify=True)
    assert rep["counts"]["red"] >= 3
    print("\nHEADLINE:", rep["headline"])
    print("GBP:", rep["per_currency"]["GBP"]["summary"])


def test_seasonality():
    idx = pd.bdate_range("2008-01-01", datetime.now().strftime("%Y-%m-%d"))
    rng = np.random.default_rng(1)
    seasonal = 1 + 0.0004 * np.sin(2 * np.pi * idx.dayofyear / 365)
    s = pd.Series(100 * np.cumprod(seasonal * (1 + rng.normal(0, 0.004, len(idx)))), index=idx)
    r = seasonality.analyze(s, 15, "03-01", "04-15")
    assert len(r["seasonal"]) == 366 and len(r["monthly"]) == 12 and r["window"]["n"] >= 14
    print("Fenêtre:", {k: r["window"][k] for k in ("avg", "median", "win_rate", "n")})


def test_api():
    from fastapi.testclient import TestClient
    from server.main import app
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"]
    assert len(c.get("/api/calendar").json()["events"]) >= 5
    assert len(c.get("/api/currencies").json()) == 9
    assert c.get("/api/currency/usd").json()["code"] == "USD"
    assert c.get("/api/weekly").json()["counts"]
    assert any(n["source"] == "FinancialJuice" for n in c.get("/api/news").json())
    assert c.get("/api/news?ccy=EUR&source=FinancialJuice").json()[0]["title"].startswith("ECB")
    assert len(c.get("/api/push/key").json()["key"]) > 80
    sub = {"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "x", "auth": "y"}}
    assert c.post("/api/push/subscribe", json={"subscription": sub}).json()["ok"]
    r = c.post("/api/push/prefs", json={"endpoint": sub["endpoint"], "prefs": {"currencies": ["USD"]}}).json()
    assert r["prefs"]["currencies"] == ["USD"]
    assert c.get("/").status_code == 200 and c.get("/sw.js").status_code == 200
    assert c.get("/manifest.webmanifest").status_code == 200


if __name__ == "__main__":
    test_pipeline(); test_seasonality(); test_api(); print("\nTOUS LES TESTS OK")
