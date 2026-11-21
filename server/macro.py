"""Tableau macro comparatif : une ligne par devise, une colonne par indicateur (dernier chiffre publié)."""
from .countries import CURRENCIES
from .calendar_data import _num

# (clé, libellé, fonction de reconnaissance du titre)
INDICATORS = [
    # « s.a » = version désaisonnalisée (ex. Canada 3,09 %) et « quarterly » = version trimestrielle (Australie) :
    # on garde le chiffre principal publié chaque mois
    ("cpi", "Inflation a/a", lambda t: ("inflation rate yoy" in t or "cpi y/y" in t or "cpi yoy" in t)
     and not any(w in t for w in ("core", "s.a", "quarterly", "expectation", "trimmed", "median", "common"))),
    ("core", "Inflation core a/a", lambda t: (("core" in t and ("inflation" in t or "cpi" in t or "pce" in t)) or "trimmed mean cpi" in t)
     and ("yoy" in t or "y/y" in t) and "s.a" not in t),
    ("unemp", "Chômage", lambda t: t.startswith("unemployment rate")),
    ("gdp_yoy", "PIB a/a", lambda t: "gdp growth rate yoy" in t or "gdp annual growth" in t),
    ("gdp_qoq", "PIB t/t", lambda t: ("gdp growth rate" in t and "yoy" not in t) or "gdp growth rate qoq" in t),
    ("pmi_m", "PMI manuf.", lambda t: "manufacturing pmi" in t or t == "ism manufacturing pmi"),
    ("pmi_s", "PMI services", lambda t: "services pmi" in t or "non-manufacturing pmi" in t or "ism services" in t),
    ("retail", "Ventes détail m/m", lambda t: "retail sales mom" in t or "retail sales m/m" in t),
]


def table(events: list[dict], overviews: dict) -> dict:
    rows = []
    for ccy, d in CURRENCIES.items():
        country = d["countries"][0]
        evs = [e for e in events if e["country"] == country and e.get("actual") is not None]
        row = {"code": ccy, "flag": d["flag"], "name": d["name"], "bank": d["bank"]}
        for key, _, match in INDICATORS:
            hit = None
            for e in evs:
                if match(e["title"].lower()):
                    hit = e
            row[key] = ({"value": _num(hit["actual"]), "str": hit["actual_str"], "prev": hit["previous_str"],
                         "period": hit.get("period"), "bias": (hit.get("surprise") or {}).get("ccy_bias")}
                        if hit else None)
        if row["cpi"] is None:
            q = None
            for e in evs:
                t = e["title"].lower()
                if ("inflation rate qoq" in t or "cpi q/q" in t) and "core" not in t:
                    q = e
            if q:
                row["cpi"] = {"value": _num(q["actual"]), "str": f'{q["actual_str"]} t/t', "prev": q["previous_str"],
                              "period": q.get("period"), "bias": (q.get("surprise") or {}).get("ccy_bias")}
        ov = overviews.get(ccy, {})
        pr = ov.get("policy_rate") or {}
        row["rate"] = {"value": pr.get("rate"), "str": f"{pr['rate']:g}%" if pr.get("rate") is not None else "—",
                       "change": pr.get("last_change_bp")}
        st = ov.get("stance") or {}
        row["stance"] = {"label": st.get("label", "—"), "score": st.get("score", 0)}
        rows.append(row)
    cols = [("rate", "Taux directeur")] + [(k, l) for k, l, _ in INDICATORS] + [("stance", "Ton BC")]
    return {"columns": [{"key": k, "label": l} for k, l in cols], "rows": rows}
