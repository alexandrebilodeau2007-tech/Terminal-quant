"""Tests des correctifs du 21 novembre : macro (inflation), flux d'OI, flux de capitaux, dates de réunions."""
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

from server import capflows, fjdetail, flows, macro, rates, storage  # noqa: E402


def test_inflation_matchers():
    f = {k: m for k, _, m in macro.INDICATORS}
    assert f["cpi"]("inflation rate yoy")
    assert not f["cpi"]("inflation rate yoy s.a"), "le Canada désaisonnalisé (3,09 %) ne doit pas remplacer 3,1 %"
    assert not f["cpi"]("quarterly inflation rate yoy"), "Australie : le mensuel est le chiffre principal"
    assert not f["cpi"]("rba trimmed mean cpi yoy") and f["core"]("rba trimmed mean cpi yoy")
    assert f["core"]("core inflation rate yoy") and not f["core"]("core inflation rate mom")


def test_nz_quarterly_fallback():
    ev = [{"country": "NZ", "title": "Inflation Rate QoQ", "actual": 0.7, "actual_str": "0.7%", "previous_str": "1.5%",
           "period": "Q3 2026", "time": "2026-10-21T00:00:00+00:00"}]
    row = next(r for r in macro.table(ev, {})["rows"] if r["code"] == "NZD")
    assert row["cpi"]["str"] == "0.7% t/t"


def test_meetings_are_sorted_and_future_safe():
    for ccy, ms in rates.MEETINGS.items():
        assert ms == sorted(ms), ccy
        assert all(date.fromisoformat(m) for m in ms)
    assert rates.MEETINGS["NZD"][0] == "2026-12-09", "pas de réunion RBNZ le 25 novembre"
    assert "2027-11-17" in rates.MEETINGS["USD"] and "2027-12-08" not in rates.MEETINGS["USD"]


def test_flows_one_snapshot_per_session():
    snaps = iter([
        {"CME:6J1!": [0.0063, 100, 0.5, 1]},
        {"CME:6J1!": [0.0064, 100, 0.7, 1]},  # OI identique : même séance (fin de semaine)
        {"CME:6J1!": [0.0065, 110, 0.2, 1]},  # nouvel OI publié
    ])
    flows._scan = lambda: next(snaps)
    storage.save("flows_hist.json", {"days": {}})
    flows.refresh()
    hist = storage.load("flows_hist.json")
    first_day = sorted(hist["days"])[0]
    # simule le lendemain
    hist["days"] = {"2026-11-19": hist["days"][first_day]}
    storage.save("flows_hist.json", hist)
    out = flows.refresh()
    assert out["prev_day"] is None and out["rows"][0]["doi_pct"] is None, "OI inchangé : pas de nouvelle séance"
    assert out["rows"][0]["price"] == 0.0064, "prix mis à jour quand même"
    out = flows.refresh()
    r = out["rows"][0]
    assert out["prev_day"] == "2026-11-19" and r["doi_pct"] == 10.0 and r["reading"] == "Nouveaux acheteurs"


def test_capflows_build():
    ev = [
        {"country": "JP", "title": "Bond Investment by Foreigners", "date": f"2026-11-{d:02d}T23:50:00Z", "actual": a,
         "previous": None, "scale": "B", "unit": "¥", "period": f"W{d}"} for d, a in [(4, 100), (11, 200), (18, 300)]
    ] + [
        {"country": "JP", "title": "Foreign Bond Investment", "date": "2026-11-18T23:50:00Z", "actual": -50,
         "previous": None, "scale": "B", "unit": "¥", "period": "W18"},
        {"country": "US", "title": "Net Long-term TIC Flows", "date": "2026-11-18T21:00:00Z", "actual": -20,
         "previous": 10, "scale": "B", "unit": "$", "period": "Sep"},
        {"country": "XX", "title": "Ignorée", "date": "2026-11-18T21:00:00Z", "actual": 1},
    ]
    out = capflows.build(ev)
    s = {x["key"]: x for x in out["series"]}
    assert s["jp_bond_in"]["sum_recent"] == 600 and s["jp_bond_in"]["reading"] == "soutien"
    assert s["jp_bond_out"]["reading"] == "soutien", "les Japonais vendent des obligations étrangères = rapatriement"
    jpy = next(x for x in out["summary"] if x["ccy"] == "JPY")
    assert jpy["net"] == 650 and jpy["reading"] == "entrées nettes"
    usd = next(x for x in out["summary"] if x["ccy"] == "USD")
    assert usd["reading"] == "sorties nettes"


def test_flows_per_contract_timing():
    """CME et ICE publient l'OI à des heures différentes : on compare chaque contrat à sa dernière valeur différente."""
    snaps = iter([{"CME:6E1!": [1.1, 500, 0.1, 1], "ICEUS:DX1!": [100, 50, 0.1, 1]},
                  {"CME:6E1!": [1.1, 500, 0.2, 1], "ICEUS:DX1!": [100, 55, 0.2, 1]}])
    flows._scan = lambda: next(snaps)
    storage.save("flows_hist.json", {"days": {"2026-11-18": {"CME:6E1!": {"close": 1.1, "oi": 450, "chg": 0}, "ICEUS:DX1!": {"close": 100, "oi": 49, "chg": 0}},
                                              "2026-11-19": {"CME:6E1!": {"close": 1.1, "oi": 500, "chg": 0}, "ICEUS:DX1!": {"close": 100, "oi": 50, "chg": 0}}}})
    flows.refresh()
    out = flows.refresh()
    r = {x["key"]: x for x in out["rows"]}
    assert r["EUR"]["doi_pct"] == round(50 / 450 * 100, 2), "EUR comparé au 18 (OI pas encore mis à jour)"
    assert r["USD"]["doi_pct"] == 10.0


def test_fj_detail_parse():
    page = ('<meta property="og:title" content="Monday FX Option Expiries" />'
            '<meta property="og:description" content="&lt;div&gt;&lt;ul&gt;&lt;li&gt;&lt;strong&gt;USD/JPY: &lt;/strong&gt;159.25 ($1.43b)&lt;/li&gt;'
            '&lt;li&gt;EUR/USD: 1.1325 (EU864.7m)&lt;/li&gt;&lt;/ul&gt;&lt;/div&gt;" />'
            '<meta property="og:image" content="https://www.financialjuice.com/assets/images/need-to-know.jpg" />')
    d = fjdetail.parse(page)
    assert d["title"] == "Monday FX Option Expiries"
    assert d["lines"] == ["USD/JPY: 159.25 ($1.43b)", "EUR/USD: 1.1325 (EU864.7m)"] and d["image"] == ""
    d = fjdetail.parse('<meta property="og:description" content="" /><meta property="og:image" content="https://www.financialjuice.com/images/9861333.png" />')
    assert d["lines"] == [] and d["image"].endswith("9861333.png")
    assert fjdetail.news_id("https://www.financialjuice.com/News/9862406/Monday-FX.aspx?xy=rss") == "9862406"
    assert fjdetail.news_id("https://evil.com/News/1/x.aspx") is None
    assert fjdetail.clean_url("https://www.financialjuice.com/News/9862406/Monday-FX.aspx?xy=rss").endswith("Monday-FX.aspx")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
    print("TESTS EXTRA OK")
