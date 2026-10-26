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
    "ROE": "Bénéfice net / capitaux propres MOYENS. N/A si capitaux propres <= 0.",
    "ROA": "Bénéfice net / actif total MOYEN.",
    "Marge brute": "Bénéfice brut / revenus.",
    "Marge d'exploitation": "Résultat d'exploitation (EBIT) / revenus.",
    "Marge nette": "Bénéfice net / revenus.",
    "Rotation de l'actif": "Revenus / actif total moyen (DuPont).",
    "Levier financier": "Actif total moyen / capitaux propres moyens (DuPont).",
    "Ratio de liquidité générale": "Actif à court terme / passif à court terme.",
    "Ratio de liquidité immédiate": "(Actif à court terme - stocks) / passif à court terme.",
    "Ratio de trésorerie": "Trésorerie / passif à court terme.",
    "Dette LT / capitaux propres": "Dette à long terme / capitaux propres.",
    "Passif / actif": "Passif total / actif total.",
    "Couverture des intérêts": "EBIT / charges d'intérêts.",
    "Flux de trésorerie disponible (FCF)": "Flux d'exploitation - CAPEX.",
    "Croissance des revenus": "Variation annuelle des revenus.",
    "Croissance du bénéfice net": "Variation annuelle du bénéfice net. N/A si l'année précédente est <= 0.",
    "P/E": "Prix / BPA dilué du DERNIER exercice (pas TTM). N/A si BPA <= 0.",
    "P/B": "Capitalisation / capitaux propres du dernier exercice.",
    "P/S": "Capitalisation / revenus du dernier exercice.",
    "VE / EBIT": "(Capitalisation + dette LT - trésorerie) / EBIT. N/A si EBIT <= 0.",
    "Rendement FCF": "FCF du dernier exercice / capitalisation.",
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
    cp, actif = t["Capitaux propres"], t["Actif total"]
    cp_moy, actif_moy = _moyenne(cp), _moyenne(actif)
    bn, rev = t["Bénéfice net"], t["Revenus"]

    r = pd.DataFrame(index=t.index)
    # --- Rentabilité ---
    r["ROE"] = _div(bn, cp_moy.where(cp_moy > 0))           # .where(...) -> NaN si <= 0
    r["ROA"] = _div(bn, actif_moy)
    r["Marge brute"] = _div(t["Bénéfice brut"], rev)
    r["Marge d'exploitation"] = _div(t["Résultat d'exploitation (EBIT)"], rev)
    r["Marge nette"] = _div(bn, rev)
    # --- DuPont : ROE = marge nette x rotation de l'actif x levier ---
    r["Rotation de l'actif"] = _div(rev, actif_moy)
    r["Levier financier"] = _div(actif_moy, cp_moy.where(cp_moy > 0))
    # --- Liquidité ---
    r["Ratio de liquidité générale"] = _div(t["Actif à court terme"], t["Passif à court terme"])
    stocks = t["Stocks"].fillna(0)  # pas de stocks déclarés = 0 (ex. société de logiciels)
    r["Ratio de liquidité immédiate"] = _div(t["Actif à court terme"] - stocks, t["Passif à court terme"])
    r["Ratio de trésorerie"] = _div(t["Trésorerie"], t["Passif à court terme"])
    # --- Solvabilité ---
    r["Dette LT / capitaux propres"] = _div(t["Dette à long terme"], cp.where(cp > 0))
    r["Passif / actif"] = _div(t["Passif total"], actif)
    r["Couverture des intérêts"] = _div(t["Résultat d'exploitation (EBIT)"], t["Charges d'intérêts"].abs())
    # --- Flux et croissance ---
    r["Flux de trésorerie disponible (FCF)"] = t["Flux de trésorerie d'exploitation"] - t["Dépenses en immobilisations (CAPEX)"]
    r["Croissance des revenus"] = rev.pct_change(fill_method=None)
    bn_prec = bn.shift(1)
    r["Croissance du bénéfice net"] = _div(bn - bn_prec, bn_prec.where(bn_prec > 0))
    return r


def verifier_dupont(ratios: pd.DataFrame) -> pd.Series:
    """Contrôle de cohérence : marge nette x rotation x levier doit égaler le ROE.
    Un écart signale un problème de données (bon réflexe d'analyste)."""
    produit = ratios["Marge nette"] * ratios["Rotation de l'actif"] * ratios["Levier financier"]
    return (produit - ratios["ROE"]).abs()


def ratios_valorisation(t: pd.DataFrame, prix: float | None, actions: float | None) -> dict[str, float]:
    """Ratios de valorisation ACTUELS (prix d'aujourd'hui / chiffres du dernier exercice).
    Attention : prix et états financiers doivent être dans la même devise ;
    la vérification est faite dans l'interface avant l'appel."""
    if not prix or not actions:
        return {k: np.nan for k in ["Capitalisation", "P/E", "P/B", "P/S", "VE / EBIT", "Rendement FCF"]}
    dernier = t.iloc[-1]
    cap = prix * actions
    bpa = dernier["BPA dilué"]
    ebit = dernier["Résultat d'exploitation (EBIT)"]
    fcf = dernier["Flux de trésorerie d'exploitation"] - dernier["Dépenses en immobilisations (CAPEX)"]
    dette = 0 if pd.isna(dernier["Dette à long terme"]) else dernier["Dette à long terme"]
    tresorerie = 0 if pd.isna(dernier["Trésorerie"]) else dernier["Trésorerie"]
    ve = cap + dette - tresorerie
    return {
        "Capitalisation": cap,
        "Valeur d'entreprise (VE)": ve,
        "P/E": prix / bpa if pd.notna(bpa) and bpa > 0 else np.nan,
        "P/B": cap / dernier["Capitaux propres"] if dernier["Capitaux propres"] > 0 else np.nan,
        "P/S": cap / dernier["Revenus"] if dernier["Revenus"] > 0 else np.nan,
        "VE / EBIT": ve / ebit if pd.notna(ebit) and ebit > 0 else np.nan,
        "Rendement FCF": fcf / cap if pd.notna(fcf) else np.nan,
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
        raise ValueError("La croissance terminale doit être inférieure au WACC.")
    flux, fcf = [], fcf_depart
    for annee, g in enumerate(croissances, start=1):
        fcf = fcf * (1 + g)
        flux.append({"Année": annee, "Croissance": g, "FCF": fcf,
                     "Facteur d'actualisation": 1 / (1 + wacc) ** annee})
    tableau = pd.DataFrame(flux)
    tableau["FCF actualisé"] = tableau["FCF"] * tableau["Facteur d'actualisation"]

    n = len(croissances)
    valeur_terminale = tableau["FCF"].iloc[-1] * (1 + croissance_terminale) / (wacc - croissance_terminale)
    vt_actualisee = valeur_terminale / (1 + wacc) ** n
    valeur_entreprise = tableau["FCF actualisé"].sum() + vt_actualisee
    valeur_fonds_propres = valeur_entreprise - dette_nette
    return {
        "tableau": tableau,
        "Valeur terminale actualisée": vt_actualisee,
        "Valeur d'entreprise": valeur_entreprise,
        "Valeur des fonds propres": valeur_fonds_propres,
        "Valeur par action": valeur_fonds_propres / nb_actions,
        # Si > 75 %, la valeur dépend surtout d'une hypothèse lointaine : à signaler.
        "Poids de la valeur terminale": vt_actualisee / valeur_entreprise,
    }


def sensibilite_dcf(fcf_depart, croissances, dette_nette, nb_actions,
                    waccs: list[float], gs: list[float]) -> pd.DataFrame:
    """Tableau de sensibilité : valeur par action pour chaque couple (WACC, g).
    Montre à l'analyste à quel point sa conclusion dépend de ses hypothèses."""
    table = pd.DataFrame(index=[f"{w:.1%}" for w in waccs], columns=[f"{g:.1%}" for g in gs], dtype="float64")
    for w in waccs:
        for g in gs:
            try:
                table.loc[f"{w:.1%}", f"{g:.1%}"] = dcf(fcf_depart, croissances, w, g, dette_nette, nb_actions)["Valeur par action"]
            except ValueError:
                table.loc[f"{w:.1%}", f"{g:.1%}"] = np.nan
    table.index.name = "WACC \\ g"
    return table
