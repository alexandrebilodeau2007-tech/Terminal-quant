"""
Section 2 — Risque & Portefeuille : VaR / CVaR et optimisation de Markowitz.

Déroulement :
    1. Choix des actifs et des paramètres  ->  2. Données (converties, alignées, validées)
    3. Rendements attendus (historiques OU saisis par l'analyste)
    4. Optimisation (variance minimale, Sharpe maximal, ou poids manuels)
    5. Risque du portefeuille retenu (VaR, CVaR, backtest)  ->  6. Export Excel
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculs import optimisation as opt
from calculs import risque
from calculs.rendements import drawdown, rendement_portefeuille, rendements_simples, statistiques
from config import (FENETRE_BACKTEST_VAR, MAX_ACTIFS_PORTEFEUILLE, MIN_ACTIFS_PORTEFEUILLE,
                    MIN_OBSERVATIONS, POIDS_MAX_DEFAUT, TICKERS_TAUX)
from export.excel import exporter_excel
from interface.composants import metriques, note_methodo, selecteur_tickers, tableau_pourcent
from sources.marche import (ErreurDonnees, aligner_calendriers, convertir_en_devise_base,
                            telecharger_prix)


def _valider(tickers: list[str]) -> str | None:
    """Applique les balises. Renvoie un message d'erreur, ou None si tout est valide."""
    if not MIN_ACTIFS_PORTEFEUILLE <= len(tickers) <= MAX_ACTIFS_PORTEFEUILLE:
        return f"Choisis entre {MIN_ACTIFS_PORTEFEUILLE} et {MAX_ACTIFS_PORTEFEUILLE} actifs (actuellement {len(tickers)})."
    taux = [t for t in tickers if t in TICKERS_TAUX]
    if taux:
        return f"{', '.join(taux)} : ce sont des taux ou indicateurs, pas des actifs investissables. Utilise un FNB obligataire (ex. TLT, XBB.TO)."
    return None


def afficher(params: dict) -> None:
    st.header("2 · Risque & Portefeuille")
    st.caption("VaR / CVaR (4 méthodes), backtest de Kupiec et optimisation de Markowitz (SciPy).")

    # ------------------------------------------------------------ 1. Paramètres
    tickers = selecteur_tickers("risque", ["AAPL", "MSFT", "RY.TO", "GC=F", "TLT"],
                                aide=f"{MIN_ACTIFS_PORTEFEUILLE} à {MAX_ACTIFS_PORTEFEUILLE} actifs investissables.")
    c1, c2, c3, c4 = st.columns(4)
    confiance = c1.selectbox("Niveau de confiance", [0.95, 0.99], format_func=lambda x: f"{x:.0%}")
    horizon = c2.selectbox("Horizon (jours de bourse)", [1, 5, 10, 21])
    poids_max = c3.slider("Poids maximum par actif", 0.10, 1.00, POIDS_MAX_DEFAUT, 0.05)
    rf = c4.number_input("Taux sans risque annuel (%)", 0.0, 20.0, 3.0, 0.25,
                         help="Bon du Trésor 3 mois dans ta devise de base (voir section 5).") / 100
    methode_cov = st.radio("Covariance", ["ledoit-wolf", "echantillon"], horizontal=True,
                           format_func=lambda m: "Ledoit-Wolf (recommandé)" if m == "ledoit-wolf" else "Échantillon")

    erreur = _valider(tickers)
    if erreur:
        st.warning(erreur)
        return

    # ------------------------------------------------------------ 2. Données
    try:
        with st.spinner("Téléchargement et conversion des prix…"):
            prix_bruts = telecharger_prix(tuple(tickers), params["debut"], params["fin"])
            prix_conv, devises = convertir_en_devise_base(prix_bruts, params["devise"], TICKERS_TAUX)
            prix, retirees = aligner_calendriers(prix_conv)
    except ErreurDonnees as e:
        st.error(str(e))
        return

    st.caption(f"Devises d'origine : {devises} → tout est converti en **{params['devise']}**. "
               f"{retirees} date(s) sans prix pour tous les actifs retirée(s).")
    if len(prix) < MIN_OBSERVATIONS:
        st.error(f"Seulement {len(prix)} observations communes ; minimum requis : {MIN_OBSERVATIONS}. "
                 "Allonge la période ou retire l'actif le plus récent.")
        return
    rend = rendements_simples(prix).dropna()

    # ------------------------------------------------------------ 3. Rendements attendus
    st.subheader("Rendements attendus (μ)")
    st.markdown("La moyenne historique est **pré-remplie à titre indicatif**. "
                "Remplace-la par **tes** hypothèses : c'est le paramètre qui influence le plus l'optimisation.")
    mu_hist = opt.rendements_attendus_historiques(rend)
    edition = st.data_editor(
        pd.DataFrame({"Historique (%)": mu_hist * 100, "Hypothèse retenue (%)": mu_hist * 100}).round(2),
        disabled=["Historique (%)"], width="stretch", key="risque_mu")
    mu = edition["Hypothèse retenue (%)"].astype(float) / 100
    source_mu = "historique" if np.allclose(mu.values, mu_hist.round(4).values, atol=1e-4) else "analyste"
    cov = opt.covariance_annualisee(rend, methode_cov)

    # ------------------------------------------------------------ 4. Optimisation
    st.subheader("Optimisation de Markowitz")
    try:
        p_minvar = opt.variance_minimale(mu, cov, poids_max, rf)
        p_sharpe = opt.sharpe_maximal(mu, cov, poids_max, rf)
        frontiere = opt.frontiere_efficiente(mu, cov, poids_max, rf)
    except opt.ErreurOptimisation as e:
        st.error(str(e))
        return

    # Poids manuels : point de départ équipondéré, modifiable.
    with st.expander("Poids manuels (ton propre portefeuille)"):
        manuels = st.data_editor(pd.DataFrame({"Poids (%)": np.full(len(tickers), 100 / len(tickers))},
                                              index=prix.columns).round(2), key="risque_manuels")
        w_man = manuels["Poids (%)"].astype(float).values / 100
        if abs(w_man.sum() - 1) > 1e-6 or (w_man < 0).any():
            st.warning(f"Les poids manuels doivent être positifs et totaliser 100 % (actuellement {w_man.sum():.2%}).")
            w_man = None

    portefeuilles = {"Variance minimale": p_minvar, "Sharpe maximal": p_sharpe}
    if w_man is not None:
        r_, v_, s_ = opt.performance(w_man, mu.values, cov.values, rf)
        portefeuilles["Manuel"] = opt.Resultat(pd.Series(w_man, index=prix.columns), r_, v_, s_)

    poids_tous = pd.DataFrame({nom: p.poids for nom, p in portefeuilles.items()})
    resume = pd.DataFrame({nom: {"Rendement attendu": p.rendement, "Volatilité": p.volatilite,
                                 "Sharpe": p.sharpe} for nom, p in portefeuilles.items()}).T
    col_g, col_d = st.columns(2)
    with col_g:
        tableau_pourcent(poids_tous, 1)
        st.dataframe(resume.style.format({"Rendement attendu": "{:.2%}", "Volatilité": "{:.2%}", "Sharpe": "{:.2f}"}),
                     width="stretch")
    with col_d:
        fig = go.Figure()
        if not frontiere.empty:
            fig.add_trace(go.Scatter(x=frontiere["Volatilité"], y=frontiere["Rendement"], mode="lines",
                                     name="Frontière efficiente"))
        vols_actifs = np.sqrt(np.diag(cov.values))
        fig.add_trace(go.Scatter(x=vols_actifs, y=mu.values, mode="markers+text", text=list(mu.index),
                                 textposition="top center", name="Actifs"))
        for nom, p in portefeuilles.items():
            fig.add_trace(go.Scatter(x=[p.volatilite], y=[p.rendement], mode="markers",
                                     marker={"size": 13, "symbol": "star"}, name=nom))
        fig.update_layout(xaxis_title="Volatilité annualisée", yaxis_title="Rendement attendu",
                          xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=420)
        st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------ 5. Risque
    st.subheader("Risque du portefeuille")
    choix = st.radio("Portefeuille analysé", list(portefeuilles), horizontal=True)
    w = portefeuilles[choix].poids.values
    r_port = rendement_portefeuille(rend, w)

    contrib = opt.contributions_au_risque(portefeuilles[choix].poids, cov)
    st.plotly_chart(px.bar(pd.DataFrame({"Poids": portefeuilles[choix].poids, "Contribution au risque": contrib}),
                           barmode="group", labels={"value": "", "index": ""}).update_layout(yaxis_tickformat=".0%", height=320),
                    width="stretch")

    stats_port = statistiques(r_port, rf)
    metriques({k: v for k, v in stats_port.items() if "Ratio" not in k and "Asym" not in k and "Aplat" not in k})
    metriques({k: v for k, v in stats_port.items() if "Ratio" in k or "Asym" in k or "Aplat" in k}, "{:.2f}")

    table_var = risque.tableau_var(r_port, rend, w, confiance, horizon)
    st.markdown(f"**VaR et CVaR — {confiance:.0%}, {horizon} jour(s)** (pertes en % de la valeur du portefeuille)")
    tableau_pourcent(table_var)

    # Histogramme des rendements avec les seuils de VaR.
    fig = px.histogram(risque.rendements_sur_horizon(r_port, horizon), nbins=100,
                       labels={"value": f"Rendement sur {horizon} j"})
    for methode, ligne in table_var.iterrows():
        fig.add_vline(x=-ligne["VaR"], line_dash="dash", annotation_text=methode, annotation_font_size=10)
    fig.update_layout(showlegend=False, xaxis_tickformat=".1%", height=380)
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Backtest de la VaR historique 1 jour (test de Kupiec)**")
    kupiec = risque.backtest_kupiec(r_port, confiance, FENETRE_BACKTEST_VAR)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Exceptions observées", kupiec["exceptions"])
    k2.metric("Exceptions attendues", f"{kupiec['exceptions attendues']:.0f}")
    k3.metric("p-value", f"{kupiec['p-value']:.3f}")
    k4.metric("Verdict statistique", "Rejeté" if kupiec["modèle rejeté (5 %)"] else "Non rejeté")
    serie = kupiec["serie"]
    fig = go.Figure([
        go.Scatter(x=serie.index, y=serie["r"], mode="lines", name="Rendement", line={"width": 0.8}),
        go.Scatter(x=serie.index, y=-serie["var"], mode="lines", name="-VaR glissante"),
        go.Scatter(x=serie.index[serie["exception"]], y=serie.loc[serie["exception"], "r"], mode="markers",
                   name="Exception", marker={"color": "red", "size": 5}),
    ])
    fig.update_layout(yaxis_tickformat=".1%", height=360)
    st.plotly_chart(fig, width="stretch")

    st.plotly_chart(px.area(drawdown(r_port), labels={"value": "Drawdown", "index": ""}, title="Drawdown")
                    .update_layout(showlegend=False, yaxis_tickformat=".0%", height=300), width="stretch")

    # ------------------------------------------------------------ 6. Export
    kupiec_resume = pd.DataFrame({k: [v] for k, v in kupiec.items() if k != "serie"}).T.rename(columns={0: "Valeur"})
    fichier = exporter_excel(
        {
            "Poids": poids_tous, "Résumé portefeuilles": resume,
            "Hypothèses μ": edition, "Covariance annualisée": cov,
            "VaR-CVaR": table_var, "Statistiques": pd.Series(stats_port, name=choix).to_frame(),
            "Backtest Kupiec": kupiec_resume, "Frontière efficiente": frontiere,
            "Prix (devise base)": prix, "Rendements": rend,
        },
        {
            "Actifs": ", ".join(tickers), "Période": f"{prix.index.min().date()} → {prix.index.max().date()}",
            "Observations": len(rend), "Devise de base": params["devise"],
            "Devises d'origine": str(devises), "Confiance": confiance, "Horizon (jours)": horizon,
            "Poids max": poids_max, "Taux sans risque": rf, "Covariance": methode_cov,
            "Source de μ": source_mu, "Portefeuille analysé (VaR)": choix,
            "Source des prix": "Yahoo Finance (yfinance), prix ajustés",
        },
    )
    st.download_button("Exporter vers Excel", fichier, file_name=f"risque_portefeuille_{params['fin']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    note_methodo(
        "- **Rendements simples** quotidiens, portefeuille **rééquilibré chaque jour** aux poids cibles.\n"
        "- **Horizon > 1 jour** : historique = rendements composés sur fenêtres glissantes (qui se chevauchent) ; "
        "paramétrique = μ×h et σ×√h (suppose des rendements indépendants, faux en crise).\n"
        "- **Monte Carlo** : loi normale multivariée, 10 000 scénarios, graine fixe (reproductible). "
        "Mêmes limites que la paramétrique sur les queues.\n"
        "- **Cornish-Fisher** : corrige la normale avec l'asymétrie et le kurtosis observés.\n"
        "- **Kupiec** : teste uniquement la FRÉQUENCE des exceptions, pas leur regroupement dans le temps (test de Christoffersen).\n"
        "- **Markowitz** : très sensible à μ. Le portefeuille de variance minimale n'utilise pas μ et est donc plus robuste. "
        "Long-only, poids plafonnés, convergence de SciPy vérifiée."
    )
