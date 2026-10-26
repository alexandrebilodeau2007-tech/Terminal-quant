"""
calculs/optimisation.py — Optimisation de portefeuille de Markowitz (SciPy).

Le problème de Markowitz :
    minimiser   w' Σ w              (variance du portefeuille)
    sous        somme(w) = 1        (100 % investi)
                0 <= w_i <= w_max   (pas de vente à découvert, poids plafonné)
                w' μ = cible        (pour la frontière efficiente)

Le grand piège : μ (rendements attendus). Les moyennes historiques sont très
bruitées et l'optimiseur les "croit" aveuglément, d'où des portefeuilles
extrêmes. Contre-mesures intégrées ici :
    - plafond de poids par actif ;
    - covariance de Ledoit-Wolf (shrinkage), plus stable que l'échantillon ;
    - possibilité pour l'ANALYSTE de saisir ses propres rendements attendus
      (c'est lui qui porte la thèse, pas l'historique).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import LedoitWolf

from config import JOURS_BOURSE_PAR_AN


class ErreurOptimisation(Exception):
    """L'optimiseur n'a pas convergé ou le problème est impossible."""


@dataclass
class Resultat:
    """Résultat d'une optimisation : poids + performance attendue."""
    poids: pd.Series
    rendement: float
    volatilite: float
    sharpe: float


def covariance_annualisee(rendements: pd.DataFrame, methode: str = "ledoit-wolf") -> pd.DataFrame:
    """Matrice de covariance annualisée.
    'echantillon' : covariance classique.
    'ledoit-wolf' : rapproche la matrice d'une cible simple pour réduire
                    l'erreur d'estimation (recommandé dès 5+ actifs)."""
    if methode == "ledoit-wolf":
        cov = LedoitWolf().fit(rendements.values).covariance_
    else:
        cov = rendements.cov().values
    return pd.DataFrame(cov * JOURS_BOURSE_PAR_AN, index=rendements.columns, columns=rendements.columns)


def rendements_attendus_historiques(rendements: pd.DataFrame) -> pd.Series:
    """Moyenne historique annualisée : point de départ, PAS une prévision."""
    return rendements.mean() * JOURS_BOURSE_PAR_AN


def performance(poids: np.ndarray, mu: np.ndarray, cov: np.ndarray, rf: float) -> tuple[float, float, float]:
    """(rendement, volatilité, Sharpe) d'un vecteur de poids."""
    rendement = float(poids @ mu)
    volatilite = float(np.sqrt(poids @ cov @ poids))
    sharpe = (rendement - rf) / volatilite if volatilite > 0 else np.nan
    return rendement, volatilite, sharpe


def _verifier_faisabilite(n: int, poids_max: float) -> None:
    """Avec n actifs plafonnés à poids_max, on ne peut pas atteindre 100 %
    si n x poids_max < 1 (ex. 2 actifs à 40 % max = 80 % au mieux)."""
    if n * poids_max < 1 - 1e-9:
        raise ErreurOptimisation(
            f"Impossible: {n} assets x {poids_max:.0%} max = {n * poids_max:.0%} < 100 %. "
            "Add assets or raise the cap."
        )


def _resoudre(objectif, n: int, poids_max: float, contraintes_sup: list | None = None) -> np.ndarray:
    """Appelle SciPy (méthode SLSQP, adaptée aux contraintes d'égalité et
    de bornes) et VÉRIFIE la convergence. Ne jamais utiliser un résultat
    sans vérifier result.success : SciPy renvoie des poids même en cas d'échec."""
    contraintes = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]
    contraintes += contraintes_sup or []
    bornes = [(0.0, poids_max)] * n
    depart = np.full(n, 1 / n)  # point de départ : équipondéré
    res = minimize(objectif, depart, method="SLSQP", bounds=bornes, constraints=contraintes,
                   options={"maxiter": 1000, "ftol": 1e-12})
    if not res.success:
        raise ErreurOptimisation(f"The optimizer did not converge: {res.message}")
    poids = np.clip(res.x, 0, None)   # supprime les -1e-12 numériques
    return poids / poids.sum()        # renormalise exactement à 100 %


def _emballer(poids, noms, mu, cov, rf) -> Resultat:
    r, v, s = performance(poids, mu, cov, rf)
    return Resultat(pd.Series(poids, index=noms, name="Weight"), r, v, s)


def variance_minimale(mu: pd.Series, cov: pd.DataFrame, poids_max: float, rf: float) -> Resultat:
    """Portefeuille le moins volatil possible (n'utilise PAS μ : plus robuste)."""
    n = len(mu)
    _verifier_faisabilite(n, poids_max)
    S = cov.values
    w = _resoudre(lambda w: w @ S @ w, n, poids_max)
    return _emballer(w, mu.index, mu.values, S, rf)


def sharpe_maximal(mu: pd.Series, cov: pd.DataFrame, poids_max: float, rf: float) -> Resultat:
    """Portefeuille tangent : meilleur rendement excédentaire par unité de risque.
    On MINIMISE le Sharpe négatif (SciPy ne sait que minimiser)."""
    n = len(mu)
    _verifier_faisabilite(n, poids_max)
    m, S = mu.values, cov.values
    def sharpe_negatif(w):
        vol = np.sqrt(w @ S @ w)
        return -(w @ m - rf) / vol if vol > 0 else 1e6
    w = _resoudre(sharpe_negatif, n, poids_max)
    return _emballer(w, mu.index, m, S, rf)


def rendement_maximal_atteignable(mu: pd.Series, poids_max: float) -> float:
    """Rendement le plus élevé possible avec les plafonds : on remplit les
    actifs au meilleur μ jusqu'à poids_max chacun (solution exacte, sans optimiseur)."""
    restant, total = 1.0, 0.0
    for valeur in mu.sort_values(ascending=False).values:
        part = min(poids_max, restant)
        total += part * valeur
        restant -= part
        if restant <= 1e-12:
            break
    return total


def frontiere_efficiente(mu: pd.Series, cov: pd.DataFrame, poids_max: float, rf: float,
                         nb_points: int = 30) -> pd.DataFrame:
    """Pour une série de rendements cibles entre celui de la variance minimale
    et le maximum atteignable, trouve la volatilité minimale.
    Les points où l'optimiseur échoue sont simplement ignorés."""
    m, S = mu.values, cov.values
    r_min = variance_minimale(mu, cov, poids_max, rf).rendement
    r_max = rendement_maximal_atteignable(mu, poids_max)
    points = []
    for cible in np.linspace(r_min, r_max, nb_points):
        contrainte = [{"type": "eq", "fun": lambda w, c=cible: w @ m - c}]
        try:
            w = _resoudre(lambda w: w @ S @ w, len(m), poids_max, contrainte)
        except ErreurOptimisation:
            continue
        r, v, s = performance(w, m, S, rf)
        points.append({"Return": r, "Volatility": v, "Sharpe": s, **dict(zip(mu.index, w))})
    return pd.DataFrame(points)


def contributions_au_risque(poids: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Part de chaque actif dans la variance totale (somme = 100 %).
    Contribution_i = w_i x (Σ w)_i / (w' Σ w).
    Utile : un actif à 20 % du poids peut porter 50 % du risque."""
    w = poids.values
    variance = w @ cov.values @ w
    return pd.Series(w * (cov.values @ w) / variance, index=poids.index, name="Risk contribution")
