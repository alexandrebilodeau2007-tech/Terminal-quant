"""
calculs/options_math.py — Black-Scholes-Merton, volatilité implicite et grecques.

Variables :
    S     : prix du sous-jacent         K : prix d'exercice (strike)
    T     : temps à l'échéance (années) r : taux sans risque (décimal, continu)
    q     : rendement du dividende      sigma : volatilité annuelle (décimal)

Rappel de la formule (call européen) :
    C = S e^(-qT) N(d1) - K e^(-rT) N(d2)
    d1 = [ln(S/K) + (r - q + sigma²/2) T] / (sigma racine(T)),   d2 = d1 - sigma racine(T)
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def _d1_d2(S, K, T, r, q, sigma):
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return d1, d1 - sigma * np.sqrt(T)


def prix_bsm(S, K, T, r, q, sigma, type_option: str) -> float:
    """Prix théorique d'un call ('call') ou d'un put ('put') européen."""
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    if type_option == "call":
        return S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1)


def grecques(S, K, T, r, q, sigma, type_option: str) -> dict[str, float]:
    """Sensibilités du prix de l'option, en unités lisibles :
        Delta : variation du prix pour +1 $ du sous-jacent
        Gamma : variation du delta pour +1 $ du sous-jacent
        Vega  : variation du prix pour +1 point de volatilité (ex. 20 % -> 21 %)
        Theta : variation du prix pour 1 JOUR qui passe (calendrier, /365)
        Rho   : variation du prix pour +1 point de taux
    """
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    densite = norm.pdf(d1)
    gamma = np.exp(-q * T) * densite / (S * sigma * np.sqrt(T))
    vega = S * np.exp(-q * T) * densite * np.sqrt(T) / 100
    terme_commun = -S * np.exp(-q * T) * densite * sigma / (2 * np.sqrt(T))
    if type_option == "call":
        delta = np.exp(-q * T) * norm.cdf(d1)
        theta = terme_commun - r * K * np.exp(-r * T) * norm.cdf(d2) + q * S * np.exp(-q * T) * norm.cdf(d1)
        rho = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    else:
        delta = -np.exp(-q * T) * norm.cdf(-d1)
        theta = terme_commun + r * K * np.exp(-r * T) * norm.cdf(-d2) - q * S * np.exp(-q * T) * norm.cdf(-d1)
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
    return {"Delta": delta, "Gamma": gamma, "Vega": vega, "Theta (per day)": theta / 365, "Rho": rho}


def volatilite_implicite(prix_marche, S, K, T, r, q, type_option: str) -> float:
    """Trouve la volatilité sigma qui rend le prix BSM égal au prix du marché.

    Contrôle d'arbitrage AVANT de chercher : un prix sous la valeur
    intrinsèque actualisée ou au-dessus du maximum théorique n'a pas de
    solution -> NaN (souvent signe d'une cotation périmée ou illiquide).
    """
    if not np.isfinite(prix_marche) or prix_marche <= 0 or T <= 0:
        return np.nan
    if type_option == "call":
        borne_basse = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0)
        borne_haute = S * np.exp(-q * T)
    else:
        borne_basse = max(K * np.exp(-r * T) - S * np.exp(-q * T), 0)
        borne_haute = K * np.exp(-r * T)
    if not borne_basse < prix_marche < borne_haute:
        return np.nan
    try:
        return brentq(lambda s: prix_bsm(S, K, T, r, q, s, type_option) - prix_marche, 1e-4, 5.0)
    except ValueError:  # pas de racine entre 0,01 % et 500 %
        return np.nan
