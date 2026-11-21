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
    tv("7", NOW - timedelta(minutes=1), "GB", "BoE Gov Bailey Speaks", 1, None, None),
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
    {"title": "RBA Gov Speaks", "country": "AUD", "date": (NOW + timedelta(hours=3)).isoformat(),
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
    assert "live" in kinds, "notification en direct pour un discours"
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


def test_cot():
    from server import cot
    rows = [{"cftc_contract_market_code": "099741", "report_date_as_yyyy_mm_dd": f"2026-11-{d:02d}T00:00:00.000",
             "open_interest_all": "700000", "dealer_positions_long_all": "50000", "dealer_positions_short_all": "200000",
             "asset_mgr_positions_long": "400000", "asset_mgr_positions_short": "100000",
             "lev_money_positions_long": str(60000 + d * 1000), "lev_money_positions_short": "90000",
             "lev_money_positions_spread": "1"} for d in (3, 10)]
    class R:
        def raise_for_status(self): pass
        def json(self): return rows
    import httpx
    orig = httpx.get
    httpx.get = lambda *a, **k: R()
    try:
        out = cot.refresh()
    finally:
        httpx.get = orig
    eur = out["rows"][0]
    assert eur["ccy"] == "EUR" and eur["date"] == "2026-11-10"
    lev = eur["groups"]["lev"]
    assert lev["net"] == -20000 and lev["change"] == 7000 and lev["index"] == 100, lev
    assert eur["groups"]["dealer"]["pct_long"] == 20


def test_rates():
    from server import rates
    prices = {"CBOT:ZQX2026": 96.12, "CBOT:ZQZ2026": 95.935, "CBOT:ZQF2027": 95.83, "CBOT:ZQG2027": 95.675, "CBOT:ZQH2027": 95.595,
              "CBOT:ZQJ2027": 95.5, "CBOT:ZQK2027": 95.43, "CBOT:ZQM2027": 95.365, "CBOT:ZQN2027": 95.335, "CBOT:ZQQ2027": 95.305,
              "CBOT:ZQU2027": 95.295, "CBOT:ZQV2027": 95.285, "CBOT:ZQX2027": 95.305, "CBOT:ZQZ2027": 95.32,
              "TMX:CRAU2026": 97.4, "TMX:CRAZ2026": 97.29, "TMX:CRAH2027": 97.05, "TMX:CRAM2027": 96.88, "TMX:CRAU2027": 96.755, "TMX:CRAZ2027": 96.665}
    rows, curve = rates.fed(prices, 4.0)
    assert rows and rows[0]["hike"] + rows[0]["hold"] + rows[0]["cut"] == 100 and curve
    rows, curve = rates.quarterly("CAD", prices, 2.5)
    assert rows and all(r["rate"] > 2.5 for r in rows), rows[:2]
    rates._scan = lambda t: prices
    out = rates.refresh({"USD": 4.0, "CAD": 2.5, "EUR": 2.0})
    assert out["banks"]["USD"]["ok"] and out["banks"]["CAD"]["ok"] and not out["banks"]["AUD"]["ok"]
    assert out["banks"]["EUR"]["ok"] is False  # pas de prix Euribor fournis


def test_news_notify():
    from server import engine, push, storage
    sent = []
    orig = push.send
    push.send = lambda *a, **k: sent.append((a, k)) or 1
    try:
        storage.save("news_sent.json", {"keys": [], "seeded": False})
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        old = [{"title": f"Vieux {i}", "link": f"https://x/{i}", "time": (now - timedelta(minutes=i)).isoformat(), "source": "InvestingLive"} for i in range(5)]
        engine.notify_news(old)  # premier passage : rien n'est envoyé
        assert sent == []
        new = [{"title": "Nouveau", "link": "https://x/new", "time": now.isoformat(), "source": "InvestingLive", "summary": "Résumé"},
               {"title": "FJ flash", "link": "https://fj/1", "time": now.isoformat(), "source": "FinancialJuice"}]
        engine.notify_news(old + new)
        assert len(sent) == 2 and sent[0][1]["kind"] in ("news_il", "news_fj"), sent
        engine.notify_news(old + new)  # pas de doublon
        assert len(sent) == 2
        # accumulation : les anciennes ne disparaissent pas quand le flux change
        storage.save("news.json", {"items": []})
        engine._merge_news("news.json", old)
        engine._merge_news("news.json", new)
        assert len(storage.load("news.json")["items"]) == 7
    finally:
        push.send = orig


def test_flows_live():
    from server import flows, market, storage
    snaps = [{"CME:6E1!": [1.10, 800000, 0.2, 1], "COMEX:GC1!": [3800, 200000, -1.0, 1], "CME_MINI:ES1!": [7000, 2000000, 0.5, 1]},
             {"CME:6E1!": [1.11, 820000, 0.5, 1], "COMEX:GC1!": [3780, 210000, -0.5, 1], "CME_MINI:ES1!": [7050, 1000000, 0.7, 1]}]
    storage.save("flows_hist.json", {"days": {"2000-01-01": {t: {"close": d[0], "oi": d[1], "chg": d[2]} for t, d in snaps[0].items()}}})
    flows._scan = lambda: snaps[1]
    out = flows.refresh()
    by = {r["ticker"]: r for r in out["rows"]}
    assert by["CME:6E1!"]["reading"] == "Nouveaux acheteurs", by["CME:6E1!"]
    assert by["COMEX:GC1!"]["reading"] == "Nouveaux vendeurs"
    assert by["CME_MINI:ES1!"]["reading"] == "Roulement de contrat"
    assert flows.reading(1, -2)[0] == "Rachat de shorts" and flows.reading(-1, -2)[0] == "Liquidation de longs"
    orig = market._get
    market._get = lambda url, params, ttl: {"EURUSD=X": {"timestamp": [1, 2, 3], "close": [1.1, 1.2, None], "chartPreviousClose": 1.0}}
    try:
        q = market.live(["EURUSD"])["quotes"]["EURUSD"]
        assert q["price"] == 1.2 and q["t"] == 2
    finally:
        market._get = orig


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
    mx = c.get("/api/macro").json()
    assert len(mx["rows"]) == 9 and mx["columns"][0]["key"] == "rate"
    usd = next(r for r in mx["rows"] if r["code"] == "USD")
    assert usd["rate"]["value"] == 4.0 and usd["cpi"]["str"] == "3.1%", usd
    d = c.get("/api/dashboard").json()
    assert "upcoming" in d and len(d["stances"]) == 9
    assert c.get("/api/sentiment").json()["configured"] is False
    sub = {"endpoint": "https://web.push.apple.com/abc", "keys": {"p256dh": "x", "auth": "y"}}
    assert c.post("/api/push/subscribe", json={"subscription": sub}).json()["ok"]
    r = c.post("/api/push/prefs", json={"endpoint": sub["endpoint"], "prefs": {"currencies": ["USD"]}}).json()
    assert r["prefs"]["currencies"] == ["USD"]
    # calendrier style Forex Factory
    from server import fiches, indicators
    fiches.set_items([{"id": "nfp", "title": "NFP", "group": "Retardé (lagging)", "match": r"non.?farm", "img": "nfp.png"},
                      {"id": "core-cpi", "title": "Core CPI", "group": "Retardé (lagging)", "match": r"core cpi", "img": "c.png"},
                      {"id": "cpi", "title": "CPI", "group": "Retardé (lagging)", "match": r"\bcpi\b", "img": "x.png"}],
                     {"nfp.png": b"PNG"})
    assert fiches.match("Core CPI m/m") == "core-cpi" and fiches.match("CPI y/y") == "cpi"
    full = c.get("/api/calendar?impacts=high,medium,low,holiday&range=thisweek").json()
    assert full["categories"] == indicators.CATEGORIES
    nfp = next(e for e in full["events"] if e["title"] == "Non Farm Payrolls")
    assert nfp["category"] == "Emploi" and nfp["fiche"] == "nfp", nfp
    assert len(full["events"]) >= len(c.get("/api/calendar").json()["events"])
    nxt = c.get("/api/calendar?range=nextweek").json()
    assert nxt["range"] == "nextweek" and "events" in nxt
    d = c.get("/api/event?ccy=USD&title=Non Farm Payrolls").json()
    assert d["category"] == "Emploi" and d["usual_effect"].startswith("Réel >") and d["fiche"] == "nfp"
    assert d["history"] and d["history"][0]["actual"] == "165K", d["history"][:2]
    j = c.get("/api/event?ccy=USD&title=Initial Jobless Claims").json()
    assert j["usual_effect"].startswith("Réel <")
    assert c.get("/api/fiches").json()["items"][0]["id"] == "nfp"
    assert c.get("/api/fiches/img/nfp.png").content == b"PNG"
    from server import rates as _r
    _r._scan = lambda t: {}
    rr = c.post("/api/rates/refresh")
    assert rr.status_code == 200 and "USD" in rr.json()["banks"], rr.text[:300]
    assert c.get("/").status_code == 200 and c.get("/sw.js").status_code == 200
    assert c.get("/manifest.webmanifest").status_code == 200


if __name__ == "__main__":
    test_pipeline(); test_seasonality(); test_cot(); test_rates(); test_news_notify(); test_flows_live(); test_api(); print("\nTOUS LES TESTS OK")
