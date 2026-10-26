"""
calculs/rendements.py — Rendements et statistiques descriptives.

Rendement SIMPLE  : r = P(t) / P(t-1) - 1
    -> s'additionne entre ACTIFS : rendement du portefeuille = somme(poids x r).
Rendement LOG     : r = ln(P(t) / P(t-1))
    -> s'additionne dans le TEMPS : rendement sur 10 jours = somme des 10 log-rendements.
On utilise donc des rendements simples pour le portefeuille.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import JOURS_BOURSE_PAR_AN


def rendements_simples(prix: pd.DataFrame) -> pd.DataFrame:
    """Rendements quotidiens simples, calculés COLONNE PAR COLONNE sur les
    jours de cotation de chaque actif. Ainsi, si le TSX est fermé un jour où
    le NYSE est ouvert, le mouvement du TSX est attribué au jour de
    réouverture au lieu d'être perdu. La première ligne (sans veille) est retirée."""
    return prix.apply(lambda s: s.dropna().pct_change()).dropna(how="all")


def rendements_log(prix: pd.DataFrame) -> pd.DataFrame:
    """Rendements quotidiens logarithmiques."""
    return np.log(prix / prix.shift(1)).dropna(how="all")


def rendement_portefeuille(rendements: pd.DataFrame, poids: np.ndarray) -> pd.Series:
    """Rendement quotidien du portefeuille = produit matriciel rendements x poids.
    Hypothèse implicite : rééquilibrage QUOTIDIEN vers les poids cibles."""
    return pd.Series(rendements.values @ poids, index=rendements.index, name="Portefeuille")


def drawdown(rendements: pd.Series) -> pd.Series:
    """Baisse depuis le sommet précédent (en %), à chaque date.
    valeur = valeur cumulée ; sommet = maximum atteint jusqu'ici."""
    valeur = (1 + rendements).cumprod()
    sommet = valeur.cummax()
    return valeur / sommet - 1


def statistiques(rendements: pd.Series, taux_sans_risque: float = 0.0) -> dict[str, float]:
    """Statistiques annualisées d'une série de rendements quotidiens.

    taux_sans_risque : annuel, en décimal (0.04 = 4 %).
    Sharpe  = (rendement annualisé - taux sans risque) / volatilité annualisée
    Sortino = même chose, mais on ne pénalise que la volatilité des BAISSES.
    """
    n = JOURS_BOURSE_PAR_AN
    rend_annuel = rendements.mean() * n
    vol_annuelle = rendements.std(ddof=1) * np.sqrt(n)
    baisses = rendements[rendements < 0]
    vol_baisse = baisses.std(ddof=1) * np.sqrt(n) if len(baisses) > 1 else np.nan
    # Rendement composé réel sur la période (géométrique), plus honnête que la moyenne.
    annees = len(rendements) / n
    cagr = (1 + rendements).prod() ** (1 / annees) - 1 if annees > 0 else np.nan
    return {
        "Rendement annualisé (arithm.)": rend_annuel,
        "Rendement composé annuel (CAGR)": cagr,
        "Volatilité annualisée": vol_annuelle,
        "Ratio de Sharpe": (rend_annuel - taux_sans_risque) / vol_annuelle if vol_annuelle > 0 else np.nan,
        "Ratio de Sortino": (rend_annuel - taux_sans_risque) / vol_baisse if vol_baisse and vol_baisse > 0 else np.nan,
        "Drawdown maximal": drawdown(rendements).min(),
        "Asymétrie (skewness)": rendements.skew(),
        "Aplatissement excédentaire (kurtosis)": rendements.kurt(),
    }


def performance_periodes(prix: pd.DataFrame) -> pd.DataFrame:
    """Rendement de chaque actif sur 1 mois, 3 mois, début d'année et 1 an.
    On prend le dernier prix disponible à la date de départ ou avant."""
    fin = prix.index.max()
    periodes = {
        "1 mois": fin - pd.DateOffset(months=1),
        "3 mois": fin - pd.DateOffset(months=3),
        "Depuis 1er janv.": pd.Timestamp(year=fin.year, month=1, day=1) - pd.Timedelta(days=1),
        "1 an": fin - pd.DateOffset(years=1),
    }
    resultats = {}
    for nom, debut in periodes.items():
        base = prix.loc[:debut]
        resultats[nom] = (prix.ffill().iloc[-1] / base.ffill().iloc[-1] - 1) if not base.empty else np.nan
    return pd.DataFrame(resultats)
