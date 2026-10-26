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


# ---------------------------------------------------------------- spreads
from calculs import formule, profil_risque, spreads  # noqa: E402


def test_spread_en_points_de_base():
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    ca = pd.Series([3.20, 3.25, 3.30], index=idx)
    us = pd.Series([4.10, 4.15], index=idx[:2])          # une date manquante côté US
    s = spreads.spread_pb(ca, us)
    assert len(s) == 2                                    # dates communes seulement
    assert s.iloc[0] == pytest.approx(-90.0)


def test_statistiques_spread_zscore():
    s = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0], index=pd.bdate_range("2026-01-01", periods=5))
    st_ = spreads.statistiques_spread(s)
    assert st_["Actuel (pb)"] == 50.0
    assert st_["z-score"] == pytest.approx((50 - 30) / s.std(ddof=1))
    assert st_["Percentile historique"] == pytest.approx(0.8)


def test_g_spread_interpolation():
    """Exemple du docstring : État 5 ans 4,00 %, 10 ans 4,30 % -> 7 ans 4,12 % -> 118 pb."""
    courbe = pd.Series({2: 3.80, 5: 4.00, 10: 4.30})
    g = spreads.g_spread(5.30, courbe, 7)
    assert g["Taux d'État interpolé (%)"] == pytest.approx(4.12)
    assert g["G-spread (pb)"] == pytest.approx(118.0)


def test_interpolation_sans_extrapolation():
    courbe = pd.Series({2: 3.0, 10: 4.0})
    assert spreads.interpoler_courbe(courbe, 30) == pytest.approx(4.0)


# ---------------------------------------------------------------- formules
@pytest.fixture
def prix_formule():
    idx = pd.bdate_range("2026-01-01", periods=3)
    return pd.DataFrame({"GC=F": [2000.0, 2100.0, 2200.0], "SI=F": [25.0, 26.0, 27.5],
                         "BTC-USD": [100.0, 110.0, 120.0], "USDCAD=X": [1.35, 1.36, 1.37]}, index=idx)


def test_formule_ratio(prix_formule):
    r = formule.calculer("GC=F / SI=F", prix_formule)
    assert r.iloc[0] == pytest.approx(80.0)


def test_formule_ticker_avec_tiret(prix_formule):
    r = formule.calculer("BTC-USD * USDCAD=X", prix_formule)
    assert r.iloc[-1] == pytest.approx(120 * 1.37)


def test_formule_priorite_et_parentheses(prix_formule):
    r = formule.calculer("(GC=F - SI=F * 10) / 2", prix_formule)
    assert r.iloc[0] == pytest.approx((2000 - 250) / 2)


@pytest.mark.parametrize("mauvaise", ["__import__('os')", "GC=F.__class__", "abs(GC=F)", "", "2 + 3", "GC=F / (SI=F"])
def test_formule_refuse_le_code(mauvaise, prix_formule):
    with pytest.raises(formule.ErreurFormule):
        formule.calculer(mauvaise, prix_formule)


def test_formule_division_par_zero(prix_formule):
    prix_formule.loc[prix_formule.index[1], "SI=F"] = 0.0
    assert len(formule.calculer("GC=F / SI=F", prix_formule)) == 2


# ---------------------------------------------------------------- niveau de risque ACVM
@pytest.mark.parametrize("sigma,attendu", [(0.05, "Faible"), (0.06, "Faible à moyen"), (0.159, "Moyen"),
                                           (0.16, "Moyen à élevé"), (0.20, "Élevé"), (0.45, "Élevé")])
def test_grille_acvm(sigma, attendu):
    assert profil_risque.niveau_acvm(sigma)[1] == attendu


def test_ecart_type_acvm_mensuel():
    """Rendements mensuels alternant +3 % / -1 % : écart-type connu, annualisé par racine(12)."""
    mois = pd.date_range("2016-01-31", periods=121, freq="ME")
    r = np.tile([0.03, -0.01], 60)
    prix = pd.Series(100 * np.concatenate([[1], np.cumprod(1 + r)]), index=mois)
    sigma, n = profil_risque.ecart_type_acvm(prix)
    assert n == 120
    assert sigma == pytest.approx(pd.Series(r).std(ddof=1) * np.sqrt(12))


def test_beta_connu():
    rng = np.random.default_rng(7)
    ref = pd.Series(rng.normal(0, 0.01, 2000), index=pd.bdate_range("2018-01-01", periods=2000))
    actif = 1.5 * ref + pd.Series(rng.normal(0, 0.002, 2000), index=ref.index)
    assert profil_risque.beta(actif, ref) == pytest.approx(1.5, abs=0.02)


# ---------------------------------------------------------------- TradingView (réglages partagés)
import json as _json  # noqa: E402
import tomllib  # noqa: E402

from interface import tradingview as tv  # noqa: E402


def test_base_tradingview_valide():
    """Le fichier du dépôt se charge et respecte les listes blanches."""
    base = tv.charger_base()
    assert base["affichage"]["disposition"] in tv.DISPOSITIONS
    assert all(i in tv.INDICATEURS for i in base["affichage"]["indicateurs"])
    assert len(base["graphiques"]) == 4


def test_valider_rejette_les_valeurs_hors_liste():
    r = tv.valider({"affichage": {"disposition": 3, "style": "99", "intervalle": "2D", "hauteur_simple": 99999,
                                  "indicateurs": ["RSI", "<script>"], "legende": "oui"},
                    "graphiques": [{"symbole": "</script><script>alert(1)</script>", "comparer": "COMEX:SI1!"}]})
    assert r["affichage"]["disposition"] == 1 and r["affichage"]["style"] == "1"
    assert r["affichage"]["intervalle"] == "D" and r["affichage"]["hauteur_simple"] == 1400
    assert r["affichage"]["indicateurs"] == ["RSI"] and r["affichage"]["legende"] is True
    assert r["graphiques"][0]["symbole"] == "AMEX:SPY"          # symbole dangereux remplacé
    assert r["graphiques"][0]["comparer"] == "COMEX:SI1!"


def test_grille_quatre_graphiques():
    base = tv.charger_base()
    base["affichage"]["disposition"] = 4
    page, hauteur = tv.html_grille(base)
    assert page.count("new TradingView.widget(") == 4 and page.count("tv.js") == 1
    assert hauteur == 2 * base["affichage"]["hauteur_grille"] + 8 + 10
    assert page.count("<script") == 2          # tv.js + un seul bloc d'appels, rien d'injecté


def test_aucune_injection_possible():
    r = tv.valider({"graphiques": [{"symbole": "AMEX:SPY", "comparer": "</script><script>alert(1)</script>"}]})
    page, _ = tv.html_grille(r)
    assert "alert(1)" not in page


def test_config_widget_indicateurs_et_comparaison():
    base = tv.charger_base()
    base["affichage"]["indicateurs"] = ["RSI", "MACD"]
    cfg = tv.config_widget({"symbole": "NASDAQ:AAPL", "comparer": "NASDAQ:MSFT"}, base["affichage"])
    # RSI a des paramètres -> objet {id, inputs} ; MACD n'en a pas -> identifiant seul
    assert cfg["studies"] == [{"id": "RSI@tv-basicstudies", "inputs": {"length": 14}}, "MACD@tv-basicstudies"]
    assert cfg["overrides"]["mainSeriesProperties.candleStyle.upColor"] == "#2ECC71"
    assert cfg["compareSymbols"] == [{"symbol": "NASDAQ:MSFT", "position": "SameScale"}]
    _json.dumps(cfg)  # sérialisable


def test_parametres_et_couleurs_valides():
    r = tv.valider({"parametres": {"RSI": {"length": 9}, "Bandes de Bollinger": {"mult": 99}, "Inconnu": {"x": 1}},
                    "couleurs": {"hausse": "#00ff00", "baisse": "red;}</style>", "rsi": "#123456"}})
    assert r["parametres"]["RSI"]["length"] == 9
    assert r["parametres"]["Bandes de Bollinger"]["mult"] == 5.0      # borné au maximum
    assert "Inconnu" not in r["parametres"]
    assert r["couleurs"]["hausse"] == "#00FF00"
    assert r["couleurs"]["baisse"] == "#FF5C5C"                       # valeur dangereuse refusée
    assert "rsi" not in r["couleurs"]                                 # couleur non prise en charge


def test_export_toml_relu_a_l_identique():
    base = tv.charger_base()
    base["affichage"]["disposition"] = 2
    base["affichage"]["indicateurs"] = ["Bandes de Bollinger"]
    base["parametres"]["RSI"]["length"] = 9
    base["couleurs"]["hausse"] = "#00FF00"
    relu = tv.valider(tomllib.loads(tv.en_toml(base)))
    assert relu == base
