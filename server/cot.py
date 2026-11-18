"""Positionnement institutionnel : rapports COT de la CFTC (hebdomadaires).

- « Traders in Financial Futures » (devises, indices, taux) :
    dealers (banques), asset managers (fonds de pension, assureurs), leveraged (hedge funds / CTA)
- « Disaggregated » (matières premières) :
    producteurs / négociants (couverture), swap dealers (banques), managed money (fonds spéculatifs)
Données au mardi, publiées le vendredi 15 h 30 (heure de l'Est).
"""
import logging
import time
from datetime import date, timedelta

import httpx

from . import storage

log = logging.getLogger("cot")

TFF = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
DISAGG = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"

# code CFTC : (clé, nom affiché, classe, rapport)
ASSETS = {
    # devises (clé = code devise, gardée pour la compatibilité)
    "098662": ("USD", "Dollar US (DXY)", "fx", "tff"), "099741": ("EUR", "Euro", "fx", "tff"),
    "096742": ("GBP", "Livre sterling", "fx", "tff"), "097741": ("JPY", "Yen", "fx", "tff"),
    "090741": ("CAD", "Dollar canadien", "fx", "tff"), "232741": ("AUD", "Dollar australien", "fx", "tff"),
    "112741": ("NZD", "Dollar néo-zélandais", "fx", "tff"), "092741": ("CHF", "Franc suisse", "fx", "tff"),
    # indices boursiers
    "13874A": ("SPX", "S&P 500 (E-mini)", "idx", "tff"), "209742": ("NDX", "Nasdaq 100 (E-mini)", "idx", "tff"),
    "124603": ("DJI", "Dow Jones (E-mini)", "idx", "tff"), "239742": ("RUT", "Russell 2000 (E-mini)", "idx", "tff"),
    "1170E1": ("VIX", "VIX", "idx", "tff"),
    # taux
    "042601": ("US2Y", "Note US 2 ans", "rates", "tff"), "044601": ("US5Y", "Note US 5 ans", "rates", "tff"),
    "043602": ("US10Y", "Note US 10 ans", "rates", "tff"), "020601": ("US30Y", "Obligation US 30 ans", "rates", "tff"),
    # matières premières
    "088691": ("GOLD", "Or", "cmd", "dis"), "084691": ("SILVER", "Argent", "cmd", "dis"),
    "076651": ("PLATINUM", "Platine", "cmd", "dis"), "085692": ("COPPER", "Cuivre", "cmd", "dis"),
    "067651": ("WTI", "Pétrole WTI", "cmd", "dis"), "06765T": ("BRENT", "Pétrole Brent", "cmd", "dis"),
    "023651": ("NATGAS", "Gaz naturel", "cmd", "dis"), "111659": ("RBOB", "Essence RBOB", "cmd", "dis"),
    "001602": ("WHEAT", "Blé", "cmd", "dis"), "002602": ("CORN", "Maïs", "cmd", "dis"),
    "005602": ("SOYBEAN", "Soja", "cmd", "dis"), "083731": ("COFFEE", "Café", "cmd", "dis"),
    "080732": ("SUGAR", "Sucre", "cmd", "dis"), "073732": ("COCOA", "Cacao", "cmd", "dis"),
}
CLASSES = {"fx": "Devises", "idx": "Indices boursiers", "rates": "Taux", "cmd": "Matières premières"}
# groupe : (préfixe CFTC, libellé)
GROUPS_TFF = {"dealer": ("dealer_positions", "Banques (dealers)"), "asset": ("asset_mgr_positions", "Asset managers"),
              "lev": ("lev_money_positions", "Hedge funds")}
GROUPS_DIS = {"prod": ("prod_merc_positions", "Producteurs"), "swap": ("swap_positions", "Banques (swap dealers)"),
              "mm": ("m_money_positions", "Managed money (fonds)")}
SPEC = {"tff": "lev", "dis": "mm"}  # groupe spéculatif suivi pour la lecture
# compatibilité avec l'ancien format (devises)
CONTRACTS = {c: a[0] for c, a in ASSETS.items() if a[2] == "fx"}
LABELS = {k: v[1] for k, v in GROUPS_TFF.items()}


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def _pick(row, prefix, side):
    """Colonne « tous contrats » d'une catégorie (gère swap__positions_short_all, etc.)."""
    norm = {k.lower().replace("__", "_"): v for k, v in row.items()}
    for k in (f"{prefix}_{side}_all", f"{prefix}_{side}"):
        if k in norm:
            return _num(norm[k])
    return None


def _fetch(url, codes, groups, report):
    since = (date.today() - timedelta(days=400)).isoformat()
    q = ",".join(f"'{c}'" for c in codes)
    params = {"$where": f"cftc_contract_market_code in({q}) AND report_date_as_yyyy_mm_dd >= '{since}'",
              "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "5000"}
    r = httpx.get(url, params=params, timeout=40)
    r.raise_for_status()
    out = []
    for row in r.json():
        code = str(row.get("cftc_contract_market_code", "")).strip()
        if code not in ASSETS or ASSETS[code][3] != report:
            continue
        key, name, cls, rep = ASSETS[code]
        rec = {"key": key, "ccy": key, "name": name, "class": cls, "report": rep,
               "date": str(row.get("report_date_as_yyyy_mm_dd", ""))[:10], "oi": _num(row.get("open_interest_all"))}
        for g, (p, _) in groups.items():
            rec[g + "_long"], rec[g + "_short"] = _pick(row, p, "long"), _pick(row, p, "short")
        out.append(rec)
    return out


def _from_socrata():
    tff = [c for c, a in ASSETS.items() if a[3] == "tff"]
    dis = [c for c, a in ASSETS.items() if a[3] == "dis"]
    return _fetch(TFF, tff, GROUPS_TFF, "tff") + _fetch(DISAGG, dis, GROUPS_DIS, "dis")


def summarize(records):
    by = {}
    for r in records:
        by.setdefault(r["key"], []).append(r)
    rows = []
    order = [a[0] for a in ASSETS.values()]
    for key in order:
        hist = sorted(by.get(key, []), key=lambda r: r["date"])
        if not hist:
            continue
        last = hist[-1]
        rep = last.get("report", "tff")
        groups = GROUPS_TFF if rep == "tff" else GROUPS_DIS
        row = {"key": key, "ccy": key, "name": last.get("name", key), "class": last.get("class", "fx"), "report": rep,
               "spec": SPEC[rep], "date": last["date"], "oi": last.get("oi"), "groups": {}}
        for g, (_, label) in groups.items():
            nets = [(h[g + "_long"] or 0) - (h[g + "_short"] or 0) for h in hist
                    if h.get(g + "_long") is not None and h.get(g + "_short") is not None]
            if not nets:
                continue
            L, S = last.get(g + "_long") or 0, last.get(g + "_short") or 0
            window = nets[-26:]
            lo, hi = min(window), max(window)
            row["groups"][g] = {
                "label": label, "long": L, "short": S, "net": nets[-1],
                "pct_long": round(100 * L / (L + S)) if L + S else None,
                "change": nets[-1] - nets[-2] if len(nets) > 1 else None,
                "index": round(100 * (nets[-1] - lo) / (hi - lo)) if hi > lo else None,  # 0 = plus court en 6 mois, 100 = plus long
                "index_1y": (lambda w: round(100 * (nets[-1] - min(w)) / (max(w) - min(w))) if max(w) > min(w) else None)(nets[-52:]),
                "history": window,
            }
        rows.append(row)
    return rows


def refresh():
    recs = _from_socrata()
    rows = summarize(recs)
    if not rows:
        raise RuntimeError("COT indisponible")
    out = {"updated": time.time(), "source": "CFTC (API publique)", "classes": CLASSES, "rows": rows}
    storage.save("cot.json", out)
    return out


def latest():
    return storage.load("cot.json")
