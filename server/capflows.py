"""Flux de capitaux officiels : achats et ventes de titres par les investisseurs étrangers (et nationaux).

Ce sont surtout des institutions (assureurs, fonds de pension, banques centrales, gestionnaires d'actifs)
qui déplacent ces montants. Sources officielles, relayées par le calendrier TradingView :
- Japon (ministère des Finances, hebdomadaire) : achats d'obligations et d'actions japonaises par les étrangers,
  achats d'obligations et d'actions étrangères par les Japonais.
- États-Unis (Trésor, TIC, mensuel) : flux nets de long terme et flux totaux.
- Canada (Statistique Canada, mensuel) : achats de titres canadiens par les étrangers et de titres étrangers par les Canadiens.
- Suisse (BNS, mensuel) : réserves de change ; une hausse signale souvent des ventes de francs par la BNS.

« effet » = +1 si un chiffre positif soutient la devise (entrée de capitaux), −1 si c'est une sortie.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

from . import sources, storage

log = logging.getLogger("capflows")

# (pays, titre exact TradingView) : (clé, devise, libellé, effet sur la devise, fréquence, explication)
SERIES = {
    ("JP", "Bond Investment by Foreigners"): ("jp_bond_in", "JPY", "Obligations japonaises achetées par les étrangers", 1, "hebdo",
                                              "Entrée de capitaux : les étrangers achètent des yens pour acheter des JGB."),
    ("JP", "Stock Investment by Foreigners"): ("jp_stock_in", "JPY", "Actions japonaises achetées par les étrangers", 1, "hebdo",
                                               "Entrée de capitaux vers les actions japonaises."),
    ("JP", "Foreign Bond Investment"): ("jp_bond_out", "JPY", "Obligations étrangères achetées par les Japonais", -1, "hebdo",
                                        "Sortie de capitaux : assureurs et fonds de pension japonais vendent des yens pour acheter des obligations étrangères."),
    ("JP", "Foreign Stock Investment"): ("jp_stock_out", "JPY", "Actions étrangères achetées par les Japonais", -1, "hebdo",
                                         "Sortie de capitaux vers les actions étrangères."),
    ("US", "Net Long-term TIC Flows"): ("us_tic_lt", "USD", "Flux nets de long terme (TIC)", 1, "mensuel",
                                       "Achats nets de titres américains de long terme par les étrangers, moins les achats étrangers des Américains."),
    ("US", "Overall Net Capital Flows"): ("us_tic_all", "USD", "Flux nets de capitaux totaux (TIC)", 1, "mensuel",
                                          "Tous les flux, y compris court terme et bancaires."),
    ("US", "Foreign Bond Investment"): ("us_tbond_in", "USD", "Obligations du Trésor achetées par les étrangers", 1, "mensuel",
                                        "Demande étrangère pour la dette américaine."),
    ("CA", "Foreign Securities Purchases"): ("ca_in", "CAD", "Titres canadiens achetés par les étrangers", 1, "mensuel",
                                             "Entrée de capitaux au Canada."),
    ("CA", "Investment in Foreign Securities"): ("ca_out", "CAD", "Titres étrangers achetés par les Canadiens", -1, "mensuel",
                                                 "Sortie de capitaux du Canada."),
    ("CH", "Foreign Exchange Reserves"): ("ch_fx", "CHF", "Réserves de change de la BNS", 0, "mensuel",
                                          "Niveau des réserves. Une hausse marquée peut signaler que la BNS vend des francs ; la variation inclut aussi l'effet de change et de l'or."),
}
ORDER = ["JPY", "USD", "CAD", "CHF"]
# séries additionnées dans la synthèse (évite de compter deux fois les flux TIC)
SUMMARY_KEYS = {"JPY": ["jp_bond_in", "jp_stock_in", "jp_bond_out", "jp_stock_out"], "USD": ["us_tic_lt"], "CAD": ["ca_in", "ca_out"]}


def _row(e, meta):
    key, ccy, label, effect, freq, why = meta
    return {"date": e.get("date", "")[:10], "period": e.get("period"), "actual": e.get("actual"),
            "previous": e.get("previous"), "scale": e.get("scale") or "", "unit": e.get("unit") or ""}


def build(events: list[dict]) -> dict:
    """Regroupe les événements bruts TradingView par série et calcule les lectures."""
    by = {}
    for e in events:
        meta = SERIES.get((e.get("country"), e.get("title")))
        if not meta or e.get("actual") is None:
            continue
        by.setdefault(meta[0], {"meta": meta, "points": {}})
        p = _row(e, meta)
        by[meta[0]]["points"][p["date"] + str(p["period"])] = p
    series = []
    for (country, title), meta in SERIES.items():
        key, ccy, label, effect, freq, why = meta
        if key not in by:
            continue
        pts = sorted(by[key]["points"].values(), key=lambda p: p["date"])
        last = pts[-1]
        vals = [p["actual"] for p in pts]
        n = 4 if freq == "hebdo" else 3
        recent = vals[-n:]
        item = {"key": key, "ccy": ccy, "country": country, "title": title, "label": label, "effect": effect,
                "freq": freq, "why": why, "last": last, "unit": last["unit"], "scale": last["scale"],
                "history": pts[-12:], "window": n, "sum_recent": round(sum(recent), 2) if effect else None,
                "avg_recent": round(sum(recent) / len(recent), 2)}
        if effect:
            s = item["sum_recent"] * effect
            item["reading"] = "soutien" if s > 0 else "pression" if s < 0 else "neutre"
        else:  # réserves : on regarde la variation
            ch = vals[-1] - vals[-2] if len(vals) > 1 else None
            item["change"] = round(ch, 2) if ch is not None else None
            # la variation inclut l'effet de change et de l'or : c'est un indice, pas une preuve d'intervention
            item["reading"] = ("réserves en hausse" if ch and ch > 5 else "réserves en baisse" if ch and ch < -5 else "stable")
        series.append(item)
    # synthèse par devise (somme des flux récents dans le sens de la devise ; Japon seulement, séries hebdo comparables)
    summary = []
    for ccy in ORDER:
        its = [s for s in series if s["key"] in SUMMARY_KEYS.get(ccy, [])]
        if not its:
            continue
        net = round(sum(s["sum_recent"] * s["effect"] for s in its), 1)
        unit = its[0]["unit"] + its[0]["scale"]
        summary.append({"ccy": ccy, "net": net, "unit": unit, "window": its[0]["window"], "freq": its[0]["freq"],
                        "reading": "entrées nettes" if net > 0 else "sorties nettes" if net < 0 else "équilibre"})
    return {"series": series, "summary": summary}


def refresh(days=200):
    end = datetime.now(timezone.utc) + timedelta(days=1)
    start = end - timedelta(days=days)
    events, cur = [], start
    countries = sorted({c for c, _ in SERIES})
    while cur < end:
        nxt = min(cur + timedelta(days=60), end)
        events += sources.fetch_tradingview(cur, nxt, countries)
        cur = nxt
    out = build(events)
    if not out["series"]:
        raise RuntimeError("Flux de capitaux indisponibles")
    out["updated"] = time.time()
    storage.save("capflows.json", out)
    return out


def latest():
    return storage.load("capflows.json")
