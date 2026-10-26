"""
tests/test_calculs.py — Tests des calculs sur des valeurs connues.

Lancer :  python -m pytest tests/ -v
Principe : chaque calcul est comparé à un résultat connu (manuel, manuel de
finance ou méthode numérique indépendante). Si tu modifies une formule et
qu'un test casse, tu sais immédiatement que quelque chose a changé.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permet "import calculs"

from calculs import fondamentaux, obligations, optimisation, options_math, rendements, risque


# ---------------------------------------------------------------- données fictives
@pytest.fixture
def rend_actifs():
    """3 actifs, 1 000 jours, loi normale avec corrélations connues."""
    rng = np.random.default_rng(0)
    cov = np.array([[1.0, 0.3, 0.1], [0.3, 1.0, 0.2], [0.1, 0.2, 1.0]]) * 0.0001
    data = rng.multivariate_normal([0.0005, 0.0003, 0.0002], cov, size=1000)
    return pd.DataFrame(data, columns=["A", "B", "C"], index=pd.bdate_range("2020-01-01", periods=1000))


# ---------------------------------------------------------------- rendements
def test_rendement_simple():
    prix = pd.DataFrame({"X": [100, 110, 99]})
    r = rendements.rendements_simples(prix)["X"].tolist()
    assert r == pytest.approx([0.10, -0.10])


def test_drawdown():
    r = pd.Series([0.10, -0.50, 0.20])  # 100 -> 110 -> 55 -> 66
    assert rendements.drawdown(r).min() == pytest.approx(-0.50)


# ---------------------------------------------------------------- VaR
def test_var_parametrique_normale():
    """Pour mu = 0 et sigma = 1 %, la VaR 95 % = 1,645 x 1 %."""
    r = pd.Series(np.random.default_rng(1).normal(0, 0.01, 200_000))
    assert risque.var_parametrique(r, 0.95) == pytest.approx(0.01645, rel=0.02)
    # CVaR normale 95 % = sigma x pdf(1,645) / 0,05 ≈ 2,063 x sigma
    assert risque.cvar_parametrique(r, 0.95) == pytest.approx(0.02063, rel=0.02)


def test_historique_converge_vers_parametrique():
    r = pd.Series(np.random.default_rng(2).normal(0, 0.01, 200_000))
    assert risque.var_historique(r, 0.99) == pytest.approx(risque.var_parametrique(r, 0.99), rel=0.03)


def test_cvar_superieure_a_var():
    r = pd.Series(np.random.default_rng(3).standard_t(4, 5000) * 0.01)
    assert risque.cvar_historique(r, 0.95) > risque.var_historique(r, 0.95)


def test_cornish_fisher_queues_epaisses():
    """Avec des queues épaisses (loi de Student), la VaR 99 % Cornish-Fisher
    doit dépasser la VaR normale."""
    r = pd.Series(np.random.default_rng(4).standard_t(4, 20_000) * 0.01)
    assert risque.var_cornish_fisher(r, 0.99) > risque.var_parametrique(r, 0.99)


def test_kupiec_modele_correct():
    """Sur des données normales i.i.d., la VaR historique ne doit pas être rejetée."""
    r = pd.Series(np.random.default_rng(5).normal(0, 0.01, 3000))
    res = risque.backtest_kupiec(r, 0.95, 250)
    assert res["observations"] == 3000 - 250
    assert not res["modèle rejeté (5 %)"]


def test_monte_carlo_reproductible(rend_actifs):
    w = np.array([0.4, 0.3, 0.3])
    a = risque.simuler_portefeuille(rend_actifs, w, n_sim=2000)
    b = risque.simuler_portefeuille(rend_actifs, w, n_sim=2000)
    assert np.allclose(a, b)  # même graine -> même résultat


# ---------------------------------------------------------------- Markowitz
def test_variance_minimale_contraintes(rend_actifs):
    mu = optimisation.rendements_attendus_historiques(rend_actifs)
    cov = optimisation.covariance_annualisee(rend_actifs, "echantillon")
    res = optimisation.variance_minimale(mu, cov, poids_max=0.5, rf=0.0)
    assert res.poids.sum() == pytest.approx(1.0)
    assert (res.poids >= -1e-9).all() and (res.poids <= 0.5 + 1e-6).all()


def test_variance_minimale_deux_actifs_formule_fermee():
    """2 actifs non corrélés : w1 = s2² / (s1² + s2²) (résultat analytique)."""
    mu = pd.Series([0.05, 0.08], index=["A", "B"])
    cov = pd.DataFrame([[0.04, 0.0], [0.0, 0.09]], index=mu.index, columns=mu.index)
    res = optimisation.variance_minimale(mu, cov, poids_max=1.0, rf=0.0)
    assert res.poids["A"] == pytest.approx(0.09 / 0.13, abs=1e-4)


def test_sharpe_max_superieur(rend_actifs):
    mu = optimisation.rendements_attendus_historiques(rend_actifs)
    cov = optimisation.covariance_annualisee(rend_actifs)
    vm = optimisation.variance_minimale(mu, cov, 0.6, 0.02)
    sm = optimisation.sharpe_maximal(mu, cov, 0.6, 0.02)
    assert sm.sharpe >= vm.sharpe - 1e-6


def test_infaisable():
    mu = pd.Series([0.05, 0.08], index=["A", "B"])
    cov = pd.DataFrame(np.eye(2) * 0.04, index=mu.index, columns=mu.index)
    with pytest.raises(optimisation.ErreurOptimisation):
        optimisation.variance_minimale(mu, cov, poids_max=0.4, rf=0)


def test_contributions_somment_a_un(rend_actifs):
    cov = optimisation.covariance_annualisee(rend_actifs)
    w = pd.Series([0.5, 0.3, 0.2], index=cov.index)
    assert optimisation.contributions_au_risque(w, cov).sum() == pytest.approx(1.0)


# ---------------------------------------------------------------- obligations
def test_obligation_au_pair():
    """Coupon = rendement -> prix = nominal."""
    assert obligations.prix(100, 0.05, 0.05, 10, 2) == pytest.approx(100.0)


def test_ytm_inverse_du_prix():
    p = obligations.prix(100, 0.04, 0.0537, 7, 2)
    assert obligations.rendement_a_echeance(p, 100, 0.04, 7, 2) == pytest.approx(0.0537, abs=1e-8)


def test_duration_zero_coupon():
    """Zéro-coupon : la duration de Macaulay = l'échéance."""
    m = obligations.mesures_de_risque(100, 0.0, 0.05, 5, 2)
    assert m["Duration de Macaulay (ans)"] == pytest.approx(5.0)


def test_duration_convexite_numeriques():
    """Compare duration et convexité analytiques aux dérivées numériques du prix."""
    y, h = 0.045, 1e-5
    p0 = obligations.prix(100, 0.06, y, 12, 2)
    p_haut, p_bas = obligations.prix(100, 0.06, y + h, 12, 2), obligations.prix(100, 0.06, y - h, 12, 2)
    m = obligations.mesures_de_risque(100, 0.06, y, 12, 2)
    assert m["Duration modifiée"] == pytest.approx(-(p_haut - p_bas) / (2 * h * p0), rel=1e-5)
    assert m["Convexité"] == pytest.approx((p_haut + p_bas - 2 * p0) / (h**2 * p0), rel=1e-3)


# ---------------------------------------------------------------- options
def test_bsm_valeur_manuel():
    """Exemple classique (Hull) : S=42, K=40, r=10 %, sigma=20 %, T=0,5 -> call ≈ 4,76, put ≈ 0,81."""
    assert options_math.prix_bsm(42, 40, 0.5, 0.10, 0, 0.20, "call") == pytest.approx(4.76, abs=0.01)
    assert options_math.prix_bsm(42, 40, 0.5, 0.10, 0, 0.20, "put") == pytest.approx(0.81, abs=0.01)


def test_parite_call_put():
    """C - P = S e^(-qT) - K e^(-rT)"""
    S, K, T, r, q, s = 100, 95, 0.75, 0.04, 0.01, 0.3
    c = options_math.prix_bsm(S, K, T, r, q, s, "call")
    p = options_math.prix_bsm(S, K, T, r, q, s, "put")
    assert c - p == pytest.approx(S * np.exp(-q * T) - K * np.exp(-r * T))


def test_vol_implicite_retrouve_sigma():
    prix = options_math.prix_bsm(100, 110, 0.5, 0.04, 0.0, 0.27, "call")
    assert options_math.volatilite_implicite(prix, 100, 110, 0.5, 0.04, 0.0, "call") == pytest.approx(0.27, abs=1e-6)


def test_vol_implicite_prix_impossible():
    """Un call sous sa valeur intrinsèque n'a pas de volatilité implicite."""
    assert np.isnan(options_math.volatilite_implicite(1.0, 100, 80, 0.5, 0.04, 0, "call"))


def test_delta_numerique():
    h = 1e-4
    haut = options_math.prix_bsm(100 + h, 100, 1, 0.03, 0, 0.25, "call")
    bas = options_math.prix_bsm(100 - h, 100, 1, 0.03, 0, 0.25, "call")
    assert options_math.grecques(100, 100, 1, 0.03, 0, 0.25, "call")["Delta"] == pytest.approx((haut - bas) / (2 * h), rel=1e-5)


# ---------------------------------------------------------------- fondamentaux
@pytest.fixture
def etats():
    idx = pd.to_datetime(["2023-12-31", "2024-12-31", "2025-12-31"])
    return pd.DataFrame({
        "Revenus": [1000, 1100, 1210], "Bénéfice brut": [400, 450, 500],
        "Résultat d'exploitation (EBIT)": [200, 220, 250], "Bénéfice net": [100, 120, 150],
        "Charges d'intérêts": [20, 20, 25], "BPA dilué": [1.0, 1.2, 1.5],
        "Flux de trésorerie d'exploitation": [180, 200, 230],
        "Dépenses en immobilisations (CAPEX)": [50, 60, 70],
        "Actif total": [2000, 2200, 2400], "Actif à court terme": [600, 650, 700],
        "Passif à court terme": [300, 320, 350], "Passif total": [1200, 1300, 1400],
        "Stocks": [100, 110, 120], "Trésorerie": [150, 160, 200],
        "Dette à long terme": [500, 500, 450], "Capitaux propres": [800, 900, 1000],
    }, index=idx)


def test_roe_moyen(etats):
    r = fondamentaux.calculer_ratios(etats)
    assert np.isnan(r["ROE"].iloc[0])                      # pas de bilan d'ouverture
    assert r["ROE"].iloc[-1] == pytest.approx(150 / 950)   # 150 / ((900 + 1000) / 2)


def test_dupont_coherent(etats):
    r = fondamentaux.calculer_ratios(etats)
    assert fondamentaux.verifier_dupont(r).dropna().max() < 1e-12


def test_liquidite(etats):
    r = fondamentaux.calculer_ratios(etats)
    assert r["Ratio de liquidité générale"].iloc[-1] == pytest.approx(2.0)
    assert r["Ratio de liquidité immédiate"].iloc[-1] == pytest.approx((700 - 120) / 350)


def test_roe_capitaux_negatifs(etats):
    etats.loc[:, "Capitaux propres"] = [-100, -50, -10]
    assert fondamentaux.calculer_ratios(etats)["ROE"].isna().all()


def test_pe_et_pe_negatif(etats):
    v = fondamentaux.ratios_valorisation(etats, prix=30.0, actions=100)
    assert v["P/E"] == pytest.approx(20.0)
    etats.loc[etats.index[-1], "BPA dilué"] = -0.5
    assert np.isnan(fondamentaux.ratios_valorisation(etats, 30.0, 100)["P/E"])


def test_dcf_gordon_simple():
    """Sans phase explicite de croissance différente : 1 an à g puis Gordon à g
    -> VE = FCF0 (1+g) / (WACC - g)  (perpétuité croissante)."""
    res = fondamentaux.dcf(100, [0.03], wacc=0.08, croissance_terminale=0.03, dette_nette=0, nb_actions=1)
    assert res["Valeur d'entreprise"] == pytest.approx(100 * 1.03 / 0.05)


def test_dcf_refuse_g_superieur_wacc():
    with pytest.raises(ValueError):
        fondamentaux.dcf(100, [0.05], wacc=0.05, croissance_terminale=0.06, dette_nette=0, nb_actions=1)
