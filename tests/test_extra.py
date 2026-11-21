"""Tests des correctifs du 21 novembre : macro (inflation), flux d'OI, flux de capitaux, dates de réunions."""
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["DATA_DIR"] = tempfile.mkdtemp()

from server import capflows, flows, macro, rates, storage  # noqa: E402


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
    assert out["prev_day"] is None, "OI inchangé : pas de nouvelle séance"
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


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
    print("TESTS EXTRA OK")
