"""
calculs/spreads.py — Écarts de taux (yield spreads).

Un spread = taux A - taux B, exprimé en POINTS DE BASE (pb) : 1 pb = 0,01 %.
    Exemple : Canada 10 ans à 3,20 %, US 10 ans à 4,10 %
              spread = (3,20 - 4,10) x 100 = -90 pb.

Trois familles de spreads couvertes par le terminal :
    1. Pente de courbe  : long terme - court terme du même pays (10 ans - 2 ans).
    2. Spread pays      : même maturité, deux pays (Canada 10 ans - US 10 ans).
    3. Spread de crédit : obligation d'entreprise - obligation d'État de même maturité
                          (G-spread, calculé par interpolation de la courbe d'État).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def spread_pb(taux_a: pd.Series, taux_b: pd.Series) -> pd.Series:
    """Spread A - B en points de base, sur les dates communes seulement.

    Les deux séries sont en % (4,10 = 4,10 %). Les calendriers peuvent
    différer (jours fériés US et canadiens) : on garde l'intersection, sans
    remplir les trous, pour ne jamais comparer deux dates différentes.
    """
    a, b = taux_a.dropna().align(taux_b.dropna(), join="inner")
    return ((a - b) * 100).rename("Spread (bp)")


def statistiques_spread(spread: pd.Series) -> dict[str, float]:
    """Où se situe le spread actuel par rapport à son historique ?

    z-score    = (actuel - moyenne) / écart-type. Au-delà de +2 ou sous -2,
                 le spread est inhabituellement large ou serré.
    percentile = % des observations historiques INFÉRIEURES au niveau actuel.
    """
    s = spread.dropna()
    if s.empty:
        return {}
    actuel, moyenne, ecart = float(s.iloc[-1]), float(s.mean()), float(s.std(ddof=1))
    return {
        "Current (bp)": actuel,
        "Mean (bp)": moyenne,
        "Std. dev. (bp)": ecart,
        "z-score": (actuel - moyenne) / ecart if ecart > 0 else np.nan,
        "Historical percentile": float((s < actuel).mean()),
        "Minimum (bp)": float(s.min()),
        "Maximum (bp)": float(s.max()),
        "1-year change (bp)": _variation(s, pd.DateOffset(years=1)),
    }


def _variation(s: pd.Series, decalage: pd.DateOffset) -> float:
    """Variation entre aujourd'hui et la dernière observation il y a 'decalage'."""
    passe = s.loc[: s.index.max() - decalage]
    return float(s.iloc[-1] - passe.iloc[-1]) if not passe.empty else np.nan


def interpoler_courbe(courbe: pd.Series, maturite: float) -> float:
    """Taux d'État interpolé linéairement à une maturité donnée (en années).

    courbe : index = maturités (années), valeurs = taux en %.
    En dehors des maturités disponibles, on prend le point le plus proche
    (aucune extrapolation : ce serait inventer un taux).
    """
    c = courbe.dropna().sort_index()
    if c.empty:
        return np.nan
    return float(np.interp(maturite, c.index.values.astype(float), c.values.astype(float)))


def g_spread(rendement_obligation: float, courbe_etat: pd.Series, maturite: float) -> dict[str, float]:
    """G-spread : rendement de l'obligation - rendement d'État interpolé, en pb.

    Exemple : obligation d'entreprise 7 ans à 5,30 % ; État 5 ans 4,00 % et
    10 ans 4,30 % -> État 7 ans interpolé = 4,00 + (7-5)/(10-5) x 0,30 = 4,12 %
    -> G-spread = (5,30 - 4,12) x 100 = 118 pb.
    Ce spread rémunère surtout le risque de défaut et la moindre liquidité.
    """
    etat = interpoler_courbe(courbe_etat, maturite)
    return {
        "Interpolated government yield (%)": etat,
        "G-spread (bp)": (rendement_obligation - etat) * 100,
    }
