"""Positionnement institutionnel : rapport COT « Traders in Financial Futures » de la CFTC.

Catégories :
  - dealers        : banques / intermédiaires (souvent en contrepartie de leurs clients)
  - asset managers : fonds de pension, fonds communs, assureurs (investisseurs institutionnels)
  - leveraged      : hedge funds et CTA (argent spéculatif)
Données au mardi, publiées le vendredi 15 h 30 (heure de l'Est).
"""
import logging
import time

import httpx

from . import storage

log = logging.getLogger("cot")

CONTRACTS = {"099741": "EUR", "096742": "GBP", "097741": "JPY", "090741": "CAD", "232741": "AUD",
             "112741": "NZD", "092741": "CHF", "098662": "USD"}
SOCRATA = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
WEEKLY_TXT = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
GROUPS = {"dealer": "dealer_positions", "asset": "asset_mgr_positions", "lev": "lev_money_positions"}
LABELS = {"dealer": "Banques (dealers)", "asset": "Asset managers", "lev": "Hedge funds"}


def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def _pick(row, prefix, side):
    """Trouve la colonne long/short d'une catégorie, quel que soit le suffixe (_all, etc.)."""
    for k, v in row.items():
        kl = k.lower()
        if kl.startswith(prefix) and f"_{side}" in kl and "spread" not in kl and "change" not in kl and "pct" not in kl:
            return _num(v)
    return None


def _from_socrata():
    codes = ",".join(f"'{c}'" for c in CONTRACTS)
    params = {"$where": f"cftc_contract_market_code in({codes})",
              "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "500"}
    r = httpx.get(SOCRATA, params=params, timeout=30)
    r.raise_for_status()
    out = []
    for row in r.json():
        code = str(row.get("cftc_contract_market_code", "")).strip()
        if code not in CONTRACTS:
            continue
        rec = {"ccy": CONTRACTS[code], "date": str(row.get("report_date_as_yyyy_mm_dd", ""))[:10],
               "oi": _num(row.get("open_interest_all"))}
        for g, p in GROUPS.items():
            rec[g + "_long"], rec[g + "_short"] = _pick(row, p, "long"), _pick(row, p, "short")
        out.append(rec)
    return out


def _from_weekly_txt():
    """Secours : fichier texte de la semaine (colonnes fixes de la CFTC)."""
    import csv
    import io
    r = httpx.get(WEEKLY_TXT, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    out = []
    for c in csv.reader(io.StringIO(r.text)):
        if len(c) < 24:
            continue
        code = c[3].strip()
        if code not in CONTRACTS:
            continue
        n = [_num(x) for x in c]
        out.append({"ccy": CONTRACTS[code], "date": c[2].strip()[:10], "oi": n[7],
                    "dealer_long": n[8], "dealer_short": n[9], "asset_long": n[11], "asset_short": n[12],
                    "lev_long": n[14], "lev_short": n[15]})
    return out


def summarize(records):
    by = {}
    for r in records:
        by.setdefault(r["ccy"], []).append(r)
    rows = []
    for ccy in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"]:
        hist = sorted(by.get(ccy, []), key=lambda r: r["date"])
        if not hist:
            continue
        last = hist[-1]
        row = {"ccy": ccy, "date": last["date"], "oi": last.get("oi"), "groups": {}}
        for g in GROUPS:
            nets = [(h[g + "_long"] or 0) - (h[g + "_short"] or 0) for h in hist
                    if h.get(g + "_long") is not None and h.get(g + "_short") is not None]
            if not nets:
                continue
            L, S = last.get(g + "_long") or 0, last.get(g + "_short") or 0
            window = nets[-26:]
            lo, hi = min(window), max(window)
            row["groups"][g] = {
                "label": LABELS[g], "long": L, "short": S, "net": nets[-1],
                "pct_long": round(100 * L / (L + S)) if L + S else None,
                "change": nets[-1] - nets[-2] if len(nets) > 1 else None,
                "index": round(100 * (nets[-1] - lo) / (hi - lo)) if hi > lo else None,  # 0 = plus court en 6 mois, 100 = plus long
                "history": window,
            }
        rows.append(row)
    return rows


def refresh():
    err = None
    try:
        recs = _from_socrata()
        src = "CFTC (API publique)"
    except Exception as e:
        err, recs = e, []
    if not recs:
        recs = _from_weekly_txt()
        src = "CFTC (fichier hebdomadaire)"
    rows = summarize(recs)
    if not rows:
        raise RuntimeError(f"COT indisponible: {err}")
    out = {"updated": time.time(), "source": src, "rows": rows}
    storage.save("cot.json", out)
    return out


def latest():
    return storage.load("cot.json")
