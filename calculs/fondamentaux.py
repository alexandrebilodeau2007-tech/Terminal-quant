"""
calculs/fondamentaux.py — Ratios financiers et outil de DCF.

PHILOSOPHIE DE CE MODULE (balise importante) :
    Le terminal CALCULE, l'analyste CONCLUT.
    - Aucune fonction ici ne produit de recommandation (acheter/vendre),
      de "note" ou de "cible" automatique.
    - Le DCF ne contient AUCUNE hypothèse par défaut cachée : croissance,
      coût du capital (WACC) et croissance terminale sont saisis par l'analyste.

Règles de rigueur :
    - Chaque ratio a une définition écrite (DEFINITIONS) exportée dans Excel.
    - Un ratio sans signification économique renvoie NaN (affiché "N/A") :
      ROE avec capitaux propres négatifs, P/E avec bénéfice négatif, etc.
    - Les ratios de rentabilité utilisent les MOYENNES de bilan
      (début + fin d'exercice) / 2, car le bénéfice est gagné sur toute l'année.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFINITIONS = {
    "ROE": "Net income / AVERAGE shareholders' equity. N/A if equity <= 0.",
    "ROA": "Net income / AVERAGE total assets.",
    "Gross margin": "Gross profit / revenue.",
    "Operating margin": "Operating income (EBIT) / revenue.",
    "Net margin": "Net income / revenue.",
    "Asset turnover": "Revenue / average total assets (DuPont).",
    "Financial leverage": "Average total assets / average equity (DuPont).",
    "Current ratio": "Current assets / current liabilities.",
    "Quick ratio": "(Current assets - inventory) / current liabilities.",
    "Cash ratio": "Cash / current liabilities.",
    "LT debt / equity": "Long-term debt / shareholders' equity.",
    "Liabilities / assets": "Total liabilities / total assets.",
    "Interest coverage": "EBIT / interest expense.",
    "Free cash flow (FCF)": "Operating cash flow - CAPEX.",
    "Revenue growth": "Year-over-year change in revenue.",
    "Net income growth": "Year-over-year change in net income. N/A if the prior year is <= 0.",
    "P/E": "Price / diluted EPS of the LATEST fiscal year (not TTM). N/A if EPS <= 0.",
    "P/B": "Market cap / equity of the latest fiscal year.",
    "P/S": "Market cap / revenue of the latest fiscal year.",
    "EV / EBIT": "(Market cap + LT debt - cash) / EBIT. N/A if EBIT <= 0.",
    "FCF yield": "Latest fiscal-year FCF / market cap.",
}


def _div(a, b):
    """Division sécurisée : NaN si le dénominateur est nul ou manquant
    (au lieu d'une erreur ou d'un 'infini' trompeur)."""
    a = pd.Series(a, dtype="float64") if not isinstance(a, pd.Series) else a.astype("float64")
    b = pd.Series(b, dtype="float64") if not isinstance(b, pd.Series) else b.astype("float64")
    return a / b.replace(0, np.nan)


def _moyenne(serie: pd.Series) -> pd.Series:
    """Moyenne (début + fin) / 2. Pour le PREMIER exercice, le début est
    inconnu : on garde NaN plutôt que d'utiliser la fin seule, pour ne pas
    mélanger deux définitions dans la même colonne."""
    return (serie + serie.shift(1)) / 2


def calculer_ratios(t: pd.DataFrame) -> pd.DataFrame:
    """Calcule les ratios annuels à partir du tableau standardisé
    (index = fins d'exercice, colonnes = postes)."""
    cp, actif = t["Shareholders' equity"], t["Total assets"]
    cp_moy, actif_moy = _moyenne(cp), _moyenne(actif)
    bn, rev = t["Net income"], t["Revenue"]

    r = pd.DataFrame(index=t.index)
    # --- Rentabilité ---
    r["ROE"] = _div(bn, cp_moy.where(cp_moy > 0))           # .where(...) -> NaN si <= 0
    r["ROA"] = _div(bn, actif_moy)
    r["Gross margin"] = _div(t["Gross profit"], rev)
    r["Operating margin"] = _div(t["Operating income (EBIT)"], rev)
    r["Net margin"] = _div(bn, rev)
    # --- DuPont : ROE = marge nette x rotation de l'actif x levier ---
    r["Asset turnover"] = _div(rev, actif_moy)
    r["Financial leverage"] = _div(actif_moy, cp_moy.where(cp_moy > 0))
    # --- Liquidité ---
    r["Current ratio"] = _div(t["Current assets"], t["Current liabilities"])
    stocks = t["Inventory"].fillna(0)  # pas de stocks déclarés = 0 (ex. société de logiciels)
    r["Quick ratio"] = _div(t["Current assets"] - stocks, t["Current liabilities"])
    r["Cash ratio"] = _div(t["Cash"], t["Current liabilities"])
    # --- Solvabilité ---
    r["LT debt / equity"] = _div(t["Long-term debt"], cp.where(cp > 0))
    r["Liabilities / assets"] = _div(t["Total liabilities"], actif)
    r["Interest coverage"] = _div(t["Operating income (EBIT)"], t["Interest expense"].abs())
    # --- Flux et croissance ---
    r["Free cash flow (FCF)"] = t["Operating cash flow"] - t["Capital expenditures (CAPEX)"]
    r["Revenue growth"] = rev.pct_change(fill_method=None)
    bn_prec = bn.shift(1)
    r["Net income growth"] = _div(bn - bn_prec, bn_prec.where(bn_prec > 0))
    return r


def verifier_dupont(ratios: pd.DataFrame) -> pd.Series:
    """Contrôle de cohérence : marge nette x rotation x levier doit égaler le ROE.
    Un écart signale un problème de données (bon réflexe d'analyste)."""
    produit = ratios["Net margin"] * ratios["Asset turnover"] * ratios["Financial leverage"]
    return (produit - ratios["ROE"]).abs()


def ratios_valorisation(t: pd.DataFrame, prix: float | None, actions: float | None) -> dict[str, float]:
    """Ratios de valorisation ACTUELS (prix d'aujourd'hui / chiffres du dernier exercice).
    Attention : prix et états financiers doivent être dans la même devise ;
    la vérification est faite dans l'interface avant l'appel."""
    if not prix or not actions:
        return {k: np.nan for k in ["Market cap", "P/E", "P/B", "P/S", "EV / EBIT", "FCF yield"]}
    dernier = t.iloc[-1]
    cap = prix * actions
    bpa = dernier["Diluted EPS"]
    ebit = dernier["Operating income (EBIT)"]
    fcf = dernier["Operating cash flow"] - dernier["Capital expenditures (CAPEX)"]
    dette = 0 if pd.isna(dernier["Long-term debt"]) else dernier["Long-term debt"]
    tresorerie = 0 if pd.isna(dernier["Cash"]) else dernier["Cash"]
    ve = cap + dette - tresorerie
    return {
        "Market cap": cap,
        "Enterprise value (EV)": ve,
        "P/E": prix / bpa if pd.notna(bpa) and bpa > 0 else np.nan,
        "P/B": cap / dernier["Shareholders' equity"] if dernier["Shareholders' equity"] > 0 else np.nan,
        "P/S": cap / dernier["Revenue"] if dernier["Revenue"] > 0 else np.nan,
        "EV / EBIT": ve / ebit if pd.notna(ebit) and ebit > 0 else np.nan,
        "FCF yield": fcf / cap if pd.notna(fcf) else np.nan,
    }


# ===========================================================================
# DCF : TOUTES les hypothèses viennent de l'analyste
# ===========================================================================

def dcf(fcf_depart: float, croissances: list[float], wacc: float, croissance_terminale: float,
        dette_nette: float, nb_actions: float) -> dict:
    """Valeur intrinsèque par actions selon un DCF à 2 étapes.

    Étape 1 : FCF projetés année par année avec les croissances saisies.
    Étape 2 : valeur terminale de Gordon = FCF_final x (1+g) / (WACC - g).
    Valeur des fonds propres = somme des flux actualisés - dette nette.

    Balise : g doit être < WACC, sinon la formule de Gordon donne une valeur
    infinie ou négative (absurde) -> on refuse.
    """
    if croissance_terminale >= wacc:
        raise ValueError("Terminal growth must be lower than the WACC.")
    flux, fcf = [], fcf_depart
    for annee, g in enumerate(croissances, start=1):
        fcf = fcf * (1 + g)
        flux.append({"Year": annee, "Growth": g, "FCF": fcf,
                     "Discount factor": 1 / (1 + wacc) ** annee})
    tableau = pd.DataFrame(flux)
    tableau["Discounted FCF"] = tableau["FCF"] * tableau["Discount factor"]

    n = len(croissances)
    valeur_terminale = tableau["FCF"].iloc[-1] * (1 + croissance_terminale) / (wacc - croissance_terminale)
    vt_actualisee = valeur_terminale / (1 + wacc) ** n
    valeur_entreprise = tableau["Discounted FCF"].sum() + vt_actualisee
    valeur_fonds_propres = valeur_entreprise - dette_nette
    return {
        "tableau": tableau,
        "Discounted terminal value": vt_actualisee,
        "Enterprise value": valeur_entreprise,
        "Equity value": valeur_fonds_propres,
        "Value per share": valeur_fonds_propres / nb_actions,
        # Si > 75 %, la valeur dépend surtout d'une hypothèse lointaine : à signaler.
        "Terminal value weight": vt_actualisee / valeur_entreprise,
    }


def sensibilite_dcf(fcf_depart, croissances, dette_nette, nb_actions,
                    waccs: list[float], gs: list[float]) -> pd.DataFrame:
    """Tableau de sensibilité : valeur par action pour chaque couple (WACC, g).
    Montre à l'analyste à quel point sa conclusion dépend de ses hypothèses."""
    table = pd.DataFrame(index=[f"{w:.1%}" for w in waccs], columns=[f"{g:.1%}" for g in gs], dtype="float64")
    for w in waccs:
        for g in gs:
            try:
                table.loc[f"{w:.1%}", f"{g:.1%}"] = dcf(fcf_depart, croissances, w, g, dette_nette, nb_actions)["Value per share"]
            except ValueError:
                table.loc[f"{w:.1%}", f"{g:.1%}"] = np.nan
    table.index.name = "WACC \\ g"
    return table
