"""
calculs/obligations.py — Prix, rendement à l'échéance, duration et convexité.

Hypothèse simplificatrice (à écrire dans ton analyse) :
    l'évaluation se fait à une DATE DE COUPON (pas d'intérêts courus).
    Pour une date quelconque, il faudrait ajouter les intérêts courus et la
    convention de calcul des jours (Act/Act, 30/360...).

Notations :
    nominal     : valeur remboursée à l'échéance (ex. 100)
    taux_coupon : coupon annuel en décimal (0.04 = 4 %)
    rendement   : rendement à l'échéance annuel (YTM), en décimal
    annees      : années restantes jusqu'à l'échéance
    frequence   : coupons par année (2 = semestriel, norme au Canada et aux É.-U.)
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def _flux(nominal: float, taux_coupon: float, annees: float, frequence: int) -> tuple[np.ndarray, np.ndarray]:
    """Renvoie (périodes, flux). Ex. 2 ans semestriel : périodes 1,2,3,4 ;
    flux = coupon, coupon, coupon, coupon + nominal."""
    n = int(round(annees * frequence))
    if n < 1:
        raise ValueError("Maturity must be at least one coupon period.")
    periodes = np.arange(1, n + 1)
    flux = np.full(n, nominal * taux_coupon / frequence)
    flux[-1] += nominal
    return periodes, flux


def prix(nominal: float, taux_coupon: float, rendement: float, annees: float, frequence: int = 2) -> float:
    """Prix = somme des flux actualisés au rendement périodique (y / fréquence)."""
    t, f = _flux(nominal, taux_coupon, annees, frequence)
    return float(np.sum(f / (1 + rendement / frequence) ** t))


def rendement_a_echeance(prix_marche: float, nominal: float, taux_coupon: float, annees: float,
                         frequence: int = 2) -> float:
    """Trouve le rendement y tel que prix(y) = prix du marché.
    Méthode de Brent : cherche la racine entre -50 % et +100 %. Garantie de
    converger si la solution est dans l'intervalle (le prix décroît avec y)."""
    return brentq(lambda y: prix(nominal, taux_coupon, y, annees, frequence) - prix_marche, -0.5, 1.0)


def mesures_de_risque(nominal: float, taux_coupon: float, rendement: float, annees: float,
                      frequence: int = 2) -> dict[str, float]:
    """Duration de Macaulay, duration modifiée, convexité et DV01.

    Duration de Macaulay = moyenne pondérée du temps des flux (en années).
    Duration modifiée    = Macaulay / (1 + y/f) -> variation % du prix pour +1 point de taux.
    Convexité            = courbure : corrige l'approximation de la duration pour les gros chocs.
    DV01                 = variation du prix (en $) pour +0,01 % de taux.
    """
    t, f = _flux(nominal, taux_coupon, annees, frequence)
    y = rendement / frequence
    actualises = f / (1 + y) ** t
    p = actualises.sum()
    temps_annees = t / frequence
    macaulay = float(np.sum(temps_annees * actualises) / p)
    modifiee = macaulay / (1 + y)
    convexite = float(np.sum(actualises * t * (t + 1)) / (p * (1 + y) ** 2 * frequence**2))
    return {
        "Price": p,
        "Macaulay duration (years)": macaulay,
        "Modified duration": modifiee,
        "Convexity": convexite,
        "DV01 ($ per 1 bp)": modifiee * p * 0.0001,
    }


def choc_de_taux(mesures: dict, choc: float) -> dict[str, float]:
    """Variation de prix estimée pour un choc de taux (ex. +0.01 = +100 pb).
    ΔP/P ≈ -Dmod x Δy + ½ x Convexité x Δy²"""
    effet_duration = -mesures["Modified duration"] * choc
    effet_convexite = 0.5 * mesures["Convexity"] * choc**2
    return {
        "Duration effect": effet_duration,
        "Convexity effect": effet_convexite,
        "Estimated change (%)": effet_duration + effet_convexite,
    }
