"""
calculs/risque.py — Value at Risk (VaR), CVaR et backtest de Kupiec.

Convention : la VaR et la CVaR sont renvoyées comme des PERTES POSITIVES.
    VaR 95 % 1 jour = 0.021 signifie : "dans 95 % des jours, la perte ne
    devrait pas dépasser 2,1 %". Ça ne dit RIEN sur les 5 % de pires jours.
    C'est le rôle de la CVaR (Expected Shortfall) : la perte MOYENNE
    dans ces 5 % de pires jours.

Quatre méthodes, chacune avec ses hypothèses :
    1. Historique      : aucune hypothèse de loi, mais suppose que le passé
                         récent représente le futur.
    2. Paramétrique    : suppose une loi normale -> sous-estime les queues épaisses.
    3. Cornish-Fisher  : corrige la normale avec l'asymétrie et l'aplatissement observés.
    4. Monte Carlo     : simule 10 000 scénarios (loi normale multivariée,
                         donc mêmes limites que la paramétrique, mais extensible).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from config import GRAINE_ALEATOIRE, NB_SIMULATIONS_MC


def rendements_sur_horizon(rendements: pd.Series, horizon: int) -> pd.Series:
    """Rendements composés sur 'horizon' jours (fenêtres glissantes).
    On additionne les log-rendements puis on revient en rendement simple.
    Note : les fenêtres se chevauchent, donc les observations ne sont pas
    indépendantes (à garder en tête pour les grands horizons)."""
    if horizon == 1:
        return rendements
    log_r = np.log1p(rendements)
    return np.expm1(log_r.rolling(horizon).sum()).dropna()


# ---------------------------------------------------------------------------
# 1. Historique
# ---------------------------------------------------------------------------
def var_historique(rendements: pd.Series, confiance: float, horizon: int = 1) -> float:
    """VaR = - quantile (1 - confiance) des rendements observés."""
    r = rendements_sur_horizon(rendements, horizon)
    return -float(np.quantile(r, 1 - confiance))


def cvar_historique(rendements: pd.Series, confiance: float, horizon: int = 1) -> float:
    """CVaR = - moyenne des rendements inférieurs ou égaux au seuil de la VaR."""
    r = rendements_sur_horizon(rendements, horizon)
    seuil = np.quantile(r, 1 - confiance)
    return -float(r[r <= seuil].mean())


# ---------------------------------------------------------------------------
# 2. Paramétrique (loi normale)
# ---------------------------------------------------------------------------
def var_parametrique(rendements: pd.Series, confiance: float, horizon: int = 1) -> float:
    """VaR = -(mu x h + z x sigma x racine(h)), z = quantile normal (négatif).
    Le passage à h jours par racine(h) suppose des rendements indépendants."""
    mu, sigma = rendements.mean(), rendements.std(ddof=1)
    z = stats.norm.ppf(1 - confiance)          # ex. -1.645 pour 95 %
    return -(mu * horizon + z * sigma * np.sqrt(horizon))


def cvar_parametrique(rendements: pd.Series, confiance: float, horizon: int = 1) -> float:
    """CVaR normale : -(mu x h - sigma x racine(h) x densité(z) / (1 - confiance))."""
    mu, sigma = rendements.mean(), rendements.std(ddof=1)
    z = stats.norm.ppf(1 - confiance)
    return -(mu * horizon - sigma * np.sqrt(horizon) * stats.norm.pdf(z) / (1 - confiance))


# ---------------------------------------------------------------------------
# 3. Cornish-Fisher (VaR "modifiée")
# ---------------------------------------------------------------------------
def var_cornish_fisher(rendements: pd.Series, confiance: float, horizon: int = 1) -> float:
    """Ajuste le quantile normal z avec S (asymétrie) et K (kurtosis excédentaire) :
        z_cf = z + (z²-1)S/6 + (z³-3z)K/24 - (2z³-5z)S²/36
    Si les rendements ont des queues épaisses (K > 0), la VaR augmente."""
    mu, sigma = rendements.mean(), rendements.std(ddof=1)
    S, K = rendements.skew(), rendements.kurt()
    z = stats.norm.ppf(1 - confiance)
    z_cf = z + (z**2 - 1) * S / 6 + (z**3 - 3 * z) * K / 24 - (2 * z**3 - 5 * z) * S**2 / 36
    return -(mu * horizon + z_cf * sigma * np.sqrt(horizon))


# ---------------------------------------------------------------------------
# 4. Monte Carlo
# ---------------------------------------------------------------------------
def simuler_portefeuille(rendements_actifs: pd.DataFrame, poids: np.ndarray, horizon: int = 1,
                         n_sim: int = NB_SIMULATIONS_MC) -> np.ndarray:
    """Simule n_sim rendements du portefeuille sur 'horizon' jours.

    Étapes :
        1. Estimer la moyenne et la covariance quotidiennes des actifs.
        2. Tirer des rendements quotidiens corrélés (loi normale multivariée).
        3. Les composer sur l'horizon, puis appliquer les poids.
    La graine fixe rend le résultat reproductible.
    """
    generateur = np.random.default_rng(GRAINE_ALEATOIRE)
    mu = rendements_actifs.mean().values
    cov = rendements_actifs.cov().values
    tirages = generateur.multivariate_normal(mu, cov, size=(n_sim, horizon))  # (n_sim, horizon, n_actifs)
    composes = np.prod(1 + tirages, axis=1) - 1                              # (n_sim, n_actifs)
    return composes @ poids


def var_cvar_monte_carlo(simulations: np.ndarray, confiance: float) -> tuple[float, float]:
    """VaR et CVaR à partir des rendements simulés."""
    seuil = np.quantile(simulations, 1 - confiance)
    return -float(seuil), -float(simulations[simulations <= seuil].mean())


# ---------------------------------------------------------------------------
# Tableau comparatif
# ---------------------------------------------------------------------------
def tableau_var(rendements_port: pd.Series, rendements_actifs: pd.DataFrame, poids: np.ndarray,
                confiance: float, horizon: int) -> pd.DataFrame:
    """Calcule VaR et CVaR selon les 4 méthodes dans un seul tableau.
    Comparer les méthodes EST l'analyse : un grand écart entre historique et
    paramétrique signale des queues épaisses."""
    sims = simuler_portefeuille(rendements_actifs, poids, horizon)
    var_mc, cvar_mc = var_cvar_monte_carlo(sims, confiance)
    lignes = {
        "Historical": (var_historique(rendements_port, confiance, horizon),
                       cvar_historique(rendements_port, confiance, horizon)),
        "Parametric (normal)": (var_parametrique(rendements_port, confiance, horizon),
                                   cvar_parametrique(rendements_port, confiance, horizon)),
        "Cornish-Fisher": (var_cornish_fisher(rendements_port, confiance, horizon), np.nan),
        "Monte Carlo (multivariate normal)": (var_mc, cvar_mc),
    }
    return pd.DataFrame(lignes, index=["VaR", "CVaR"]).T


# ---------------------------------------------------------------------------
# Backtest de Kupiec : la VaR historique a-t-elle été dépassée trop souvent ?
# ---------------------------------------------------------------------------
def backtest_kupiec(rendements: pd.Series, confiance: float, fenetre: int) -> dict:
    """Test de proportion des défaillances (POF) de Kupiec (1995).

    Méthode :
        Chaque jour t, on calcule la VaR historique avec les 'fenetre' jours
        PRÉCÉDENTS (aucune donnée future) puis on regarde si la perte du jour t
        l'a dépassée (= une "exception").
    Hypothèse testée : le taux d'exceptions observé = 1 - confiance.
        LR = -2 ln[(1-p)^(T-x) p^x] + 2 ln[(1-x/T)^(T-x) (x/T)^x]   ~ khi² à 1 d.l.
    p-value < 0,05 -> on REJETTE le modèle : la VaR est mal calibrée.
    """
    p = 1 - confiance
    # shift(1) : la VaR du jour t n'utilise que les données jusqu'à t-1.
    var_glissante = -rendements.rolling(fenetre).quantile(p).shift(1)
    donnees = pd.DataFrame({"r": rendements, "var": var_glissante}).dropna()
    exceptions = donnees["r"] < -donnees["var"]
    T, x = len(donnees), int(exceptions.sum())
    if T == 0:
        return {"observations": 0}

    def log_vrais(prob: float) -> float:
        # Gère les cas limites 0 et 1 (log(0) indéfini) : 0 x log(0) = 0 par convention.
        a = (T - x) * np.log(1 - prob) if prob < 1 else (0.0 if x == T else -np.inf)
        b = x * np.log(prob) if prob > 0 else (0.0 if x == 0 else -np.inf)
        return a + b

    lr = -2 * (log_vrais(p) - log_vrais(x / T))
    p_value = 1 - stats.chi2.cdf(lr, df=1)
    return {
        "observations": T,
        "exceptions": x,
        "expected exceptions": T * p,
        "observed rate": x / T,
        "expected rate": p,
        "LR statistic": lr,
        "p-value": p_value,
        "model rejected (5%)": bool(p_value < 0.05),
        "serie": donnees.assign(exception=exceptions),
    }
