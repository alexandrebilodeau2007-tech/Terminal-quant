"""
PORT — Portefeuille & risque. Deux onglets :

ONGLET 1 « Optimisation & VaR » — déroulement :
    1. Choix des actifs et des paramètres  ->  2. Données (converties, alignées, validées)
    3. Rendements attendus (historiques OU saisis par l'analyste)
    4. Optimisation (variance minimale, Sharpe maximal, ou poids manuels)
    5. Risque du portefeuille retenu (VaR, CVaR, backtest)  ->  6. Export Excel

ONGLET 2 « Niveau de risque » : classement officiel ACVM d'un FNB, d'un titre
ou d'un portefeuille personnalisé (écart-type des rendements mensuels sur 10 ans).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculs import optimisation as opt
from calculs import profil_risque as pr
from calculs import risque
from calculs.rendements import drawdown, rendement_portefeuille, rendements_simples, statistiques
from config import (FENETRE_BACKTEST_VAR, MAX_ACTIFS_PORTEFEUILLE, MIN_ACTIFS_PORTEFEUILLE,
                    MIN_OBSERVATIONS, POIDS_MAX_DEFAUT, TICKERS_TAUX)
from export.excel import exporter_excel
from config import GRILLE_RISQUE_ACVM
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo, selecteur_tickers, tableau_pourcent
from interface.navigation import valeur_initiale
from sources.marche import (ErreurDonnees, aligner_calendriers, convertir_en_devise_base,
                            infos_fonds, telecharger_prix)


def _valider(tickers: list[str]) -> str | None:
    """Applique les balises. Renvoie un message d'erreur, ou None si tout est valide."""
    if not MIN_ACTIFS_PORTEFEUILLE <= len(tickers) <= MAX_ACTIFS_PORTEFEUILLE:
        return f"Choose between {MIN_ACTIFS_PORTEFEUILLE} and {MAX_ACTIFS_PORTEFEUILLE} assets (currently {len(tickers)})."
    taux = [t for t in tickers if t in TICKERS_TAUX]
    if taux:
        return f"{', '.join(taux)}: these are rates or indicators, not investable assets. Use a bond ETF (e.g. TLT, XBB.TO)."
    return None


def afficher(params: dict) -> None:
    titre("Portfolio & risk", "port", "PORT",
          "VaR / CVaR, Kupiec backtest, Markowitz optimization and official risk level (CSA).")
    onglet_opt, onglet_niveau = st.tabs([":material/insights: Optimization & VaR",
                                         ":material/speed: Risk level (ETF / portfolio)"])
    with onglet_opt:
        _onglet_optimisation(params)
    with onglet_niveau:
        _onglet_niveau(params)


def _onglet_optimisation(params: dict) -> None:
    sous_titre("Assets and parameters", "port_opt")
    # ------------------------------------------------------------ 1. Paramètres
    tickers = selecteur_tickers("risque", ["AAPL", "MSFT", "RY.TO", "GC=F", "TLT"],
                                aide=f"{MIN_ACTIFS_PORTEFEUILLE} to {MAX_ACTIFS_PORTEFEUILLE} investable assets.",
                                cle_commande="cmd_risque_libre")
    c1, c2, c3, c4 = st.columns(4)
    confiance = c1.selectbox("Confidence level", [0.95, 0.99], format_func=lambda x: f"{x:.0%}")
    horizon = c2.selectbox("Horizon (trading days)", [1, 5, 10, 21])
    poids_max = c3.slider("Maximum weight per asset", 0.10, 1.00, POIDS_MAX_DEFAUT, 0.05)
    rf = c4.number_input("Annual risk-free rate (%)", 0.0, 20.0, 3.0, 0.25,
                         help="3-month T-bill in your base currency (see YCRV).") / 100
    methode_cov = st.radio("Covariance", ["ledoit-wolf", "echantillon"], horizontal=True,
                           format_func=lambda m: "Ledoit-Wolf (recommended)" if m == "ledoit-wolf" else "Sample")

    erreur = _valider(tickers)
    if erreur:
        st.warning(erreur)
        return

    # ------------------------------------------------------------ 2. Données
    try:
        with st.spinner("Downloading and converting prices…"):
            prix_bruts = telecharger_prix(tuple(tickers), params["debut"], params["fin"])
            prix_conv, devises = convertir_en_devise_base(prix_bruts, params["devise"], TICKERS_TAUX)
            prix, retirees = aligner_calendriers(prix_conv)
    except ErreurDonnees as e:
        st.error(str(e))
        return

    st.caption(f"Original currencies: {devises} → everything is converted to **{params['devise']}**. "
               f"{retirees} date(s) without a price for every asset removed.")
    if len(prix) < MIN_OBSERVATIONS:
        st.error(f"Only {len(prix)} common observations; minimum required: {MIN_OBSERVATIONS}. "
                 "Extend the period or remove the most recent asset.")
        return
    rend = rendements_simples(prix).dropna()

    # ------------------------------------------------------------ 3. Rendements attendus
    sous_titre("Expected returns (μ)", "port_mu")
    st.markdown("The historical mean is **pre-filled for reference**. "
                "Replace it with **your** assumptions: it is the parameter that drives the optimization the most.")
    mu_hist = opt.rendements_attendus_historiques(rend)
    edition = st.data_editor(
        pd.DataFrame({"Historical (%)": mu_hist * 100, "Chosen assumption (%)": mu_hist * 100}).round(2),
        disabled=["Historical (%)"], width="stretch", key="risque_mu")
    mu = edition["Chosen assumption (%)"].astype(float) / 100
    source_mu = "historical" if np.allclose(mu.values, mu_hist.round(4).values, atol=1e-4) else "analyst"
    cov = opt.covariance_annualisee(rend, methode_cov)

    # ------------------------------------------------------------ 4. Optimisation
    sous_titre("Markowitz optimization", "port_opt")
    try:
        p_minvar = opt.variance_minimale(mu, cov, poids_max, rf)
        p_sharpe = opt.sharpe_maximal(mu, cov, poids_max, rf)
        frontiere = opt.frontiere_efficiente(mu, cov, poids_max, rf)
    except opt.ErreurOptimisation as e:
        st.error(str(e))
        return

    # Poids manuels : point de départ équipondéré, modifiable.
    with st.expander("Manual weights (your own portfolio)"):
        manuels = st.data_editor(pd.DataFrame({"Weight (%)": np.full(len(tickers), 100 / len(tickers))},
                                              index=prix.columns).round(2), key="risque_manuels")
        w_man = manuels["Weight (%)"].astype(float).values / 100
        if abs(w_man.sum() - 1) > 1e-6 or (w_man < 0).any():
            st.warning(f"Manual weights must be positive and total 100% (currently {w_man.sum():.2%}).")
            w_man = None

    portefeuilles = {"Minimum variance": p_minvar, "Maximum Sharpe": p_sharpe}
    if w_man is not None:
        r_, v_, s_ = opt.performance(w_man, mu.values, cov.values, rf)
        portefeuilles["Manual"] = opt.Resultat(pd.Series(w_man, index=prix.columns), r_, v_, s_)

    poids_tous = pd.DataFrame({nom: p.poids for nom, p in portefeuilles.items()})
    resume = pd.DataFrame({nom: {"Expected return": p.rendement, "Volatility": p.volatilite,
                                 "Sharpe": p.sharpe} for nom, p in portefeuilles.items()}).T
    col_g, col_d = st.columns(2)
    with col_g:
        tableau_pourcent(poids_tous, 1)
        st.dataframe(resume.style.format({"Expected return": "{:.2%}", "Volatility": "{:.2%}", "Sharpe": "{:.2f}"}),
                     width="stretch")
    with col_d:
        fig = go.Figure()
        if not frontiere.empty:
            fig.add_trace(go.Scatter(x=frontiere["Volatility"], y=frontiere["Return"], mode="lines",
                                     name="Efficient frontier"))
        vols_actifs = np.sqrt(np.diag(cov.values))
        fig.add_trace(go.Scatter(x=vols_actifs, y=mu.values, mode="markers+text", text=list(mu.index),
                                 textposition="top center", name="Assets"))
        for nom, p in portefeuilles.items():
            fig.add_trace(go.Scatter(x=[p.volatilite], y=[p.rendement], mode="markers",
                                     marker={"size": 13, "symbol": "star"}, name=nom))
        fig.update_layout(xaxis_title="Annualized volatility", yaxis_title="Expected return",
                          xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=420)
        st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------ 5. Risque
    sous_titre("Portfolio risk (VaR / CVaR)", "port_var")
    choix = st.radio("Portfolio analyzed", list(portefeuilles), horizontal=True)
    w = portefeuilles[choix].poids.values
    r_port = rendement_portefeuille(rend, w)

    contrib = opt.contributions_au_risque(portefeuilles[choix].poids, cov)
    st.plotly_chart(px.bar(pd.DataFrame({"Weight": portefeuilles[choix].poids, "Risk contribution": contrib}),
                           barmode="group", labels={"value": "", "index": ""}).update_layout(yaxis_tickformat=".0%", height=320),
                    width="stretch")

    stats_port = statistiques(r_port, rf)
    metriques({k: v for k, v in stats_port.items() if "Ratio" not in k and "Skew" not in k and "kurtosis" not in k})
    metriques({k: v for k, v in stats_port.items() if "Ratio" in k or "Skew" in k or "kurtosis" in k}, "{:.2f}")

    table_var = risque.tableau_var(r_port, rend, w, confiance, horizon)
    st.markdown(f"**VaR and CVaR — {confiance:.0%}, {horizon} day(s)** (losses as % of portfolio value)")
    tableau_pourcent(table_var)

    # Histogramme des rendements avec les seuils de VaR.
    fig = px.histogram(risque.rendements_sur_horizon(r_port, horizon), nbins=100,
                       labels={"value": f"Return over {horizon} j"})
    for methode, ligne in table_var.iterrows():
        fig.add_vline(x=-ligne["VaR"], line_dash="dash", annotation_text=methode, annotation_font_size=10)
    fig.update_layout(showlegend=False, xaxis_tickformat=".1%", height=380)
    st.plotly_chart(fig, width="stretch")

    sous_titre("1-day historical VaR backtest (Kupiec test)", "port_kupiec")
    kupiec = risque.backtest_kupiec(r_port, confiance, FENETRE_BACKTEST_VAR)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Observed exceptions", kupiec["exceptions"])
    k2.metric("Expected exceptions", f"{kupiec['expected exceptions']:.0f}")
    k3.metric("p-value", f"{kupiec['p-value']:.3f}")
    k4.metric("Statistical verdict", "Rejected" if kupiec["model rejected (5%)"] else "Not rejected")
    serie = kupiec["serie"]
    fig = go.Figure([
        go.Scatter(x=serie.index, y=serie["r"], mode="lines", name="Return", line={"width": 0.8}),
        go.Scatter(x=serie.index, y=-serie["var"], mode="lines", name="-Rolling VaR"),
        go.Scatter(x=serie.index[serie["exception"]], y=serie.loc[serie["exception"], "r"], mode="markers",
                   name="Exception", marker={"color": "red", "size": 5}),
    ])
    fig.update_layout(yaxis_tickformat=".1%", height=360)
    st.plotly_chart(fig, width="stretch")

    st.plotly_chart(px.area(drawdown(r_port), labels={"value": "Drawdown", "index": ""}, title="Drawdown")
                    .update_layout(showlegend=False, yaxis_tickformat=".0%", height=300), width="stretch")

    # ------------------------------------------------------------ 6. Export
    kupiec_resume = pd.DataFrame({k: [v] for k, v in kupiec.items() if k != "serie"}).T.rename(columns={0: "Value"})
    fichier = exporter_excel(
        {
            "Weight": poids_tous, "Portfolio summary": resume,
            "μ assumptions": edition, "Annualized covariance": cov,
            "VaR-CVaR": table_var, "Statistics": pd.Series(stats_port, name=choix).to_frame(),
            "Kupiec backtest": kupiec_resume, "Efficient frontier": frontiere,
            "Prices (base currency)": prix, "Returns": rend,
        },
        {
            "Assets": ", ".join(tickers), "Period": f"{prix.index.min().date()} → {prix.index.max().date()}",
            "Observations": len(rend), "Base currency": params["devise"],
            "Original currencies": str(devises), "Confidence": confiance, "Horizon (days)": horizon,
            "Max weight": poids_max, "Risk-free rate": rf, "Covariance": methode_cov,
            "Source of μ": source_mu, "Portfolio analyzed (VaR)": choix,
            "Price source": "Yahoo Finance (yfinance), adjusted prices",
        },
    )
    st.download_button("Export to Excel", fichier, file_name=f"portfolio_risk_{params['fin']}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    note_methodo(
        "- Daily **simple returns**, portfolio **rebalanced daily** to target weights.\n"
        "- **Horizon > 1 day**: historical = compounded returns over (overlapping) rolling windows; "
        "parametric = μ×h and σ×√h (assumes independent returns, false in a crisis).\n"
        "- **Monte Carlo**: multivariate normal, 10,000 scenarios, fixed seed (reproducible). "
        "Same tail limitations as the parametric method.\n"
        "- **Cornish-Fisher**: adjusts the normal with observed skewness and kurtosis.\n"
        "- **Kupiec**: only tests the FREQUENCY of exceptions, not their clustering over time (Christoffersen test).\n"
        "- **Markowitz**: very sensitive to μ. The minimum-variance portfolio does not use μ and is therefore more robust. "
        "Long-only, capped weights, SciPy convergence checked."
    )


# =====================================================================
# ONGLET 2 — Niveau de risque (méthode ACVM)
# =====================================================================

REFERENCES = {"S&P/TSX Composite (^GSPTSE)": "^GSPTSE", "S&P 500 (^GSPC)": "^GSPC",
              "iShares S&P/TSX 60 (XIU.TO)": "XIU.TO", "None": None}


def _jauge(rang: int) -> None:
    """Jauge horizontale à 5 cases, la case du niveau obtenu mise en évidence."""
    cases = []
    for i, (_, libelle) in enumerate(GRILLE_RISQUE_ACVM, start=1):
        actif = i == rang
        style = ("background:#FF9F1C;color:#0A0E14;font-weight:600" if actif
                 else "background:#131A24;color:#8B98A9")
        cases.append(f"<div style='flex:1;padding:10px 4px;text-align:center;{style};"
                     f"border:1px solid #1F2A37;font-size:.85rem'>{libelle}</div>")
    st.markdown(f"<div style='display:flex;gap:4px;margin:.4rem 0 .8rem 0'>{''.join(cases)}</div>",
                unsafe_allow_html=True)


def _graphique_glissant(prix: pd.Series) -> go.Figure:
    """Écart-type annualisé sur 36 mois glissants, avec les seuils de la grille ACVM :
    montre si le niveau de risque a changé dans le temps."""
    r = pr.rendements_mensuels(prix)
    glissant = r.rolling(36).std(ddof=1) * np.sqrt(12)
    fig = go.Figure(go.Scatter(x=glissant.index, y=glissant, name="36-month std. dev.", line={"width": 2}))
    for borne, libelle in GRILLE_RISQUE_ACVM[:-1]:
        fig.add_hline(y=borne / 100, line_dash="dot", line_color="#8B98A9",
                      annotation_text=f"{borne} %", annotation_position="right")
    fig.update_layout(title="Annualized std. dev. over rolling 36 months (CSA thresholds dotted)",
                      yaxis_tickformat=".0%", height=360, showlegend=False)
    return fig


def _onglet_niveau(params: dict) -> None:
    sous_titre("Risk level under the Canadian method (CSA)", "port_niveau")
    st.caption("Fixed 10-year period ending at the global end date (independent of the start date), "
               "as the official method requires.")
    mode = st.radio("What do you want to assess?", ["An ETF or a security", "My portfolio (several assets)"],
                    horizontal=True, key="niv_mode")
    reference_nom = st.selectbox("Benchmark index (for beta and correlation)", list(REFERENCES), key="niv_ref")
    reference = REFERENCES[reference_nom]

    fin = pd.Timestamp(params["fin"])
    debut = str((fin - pd.DateOffset(years=10, months=1)).date())

    # ------------------------------------------------ séries de prix à évaluer
    if mode == "An ETF or a security":
        valeur_initiale("niv_ticker", "XEQT.TO")
        ticker = st.text_input("Yahoo ticker of the ETF or security", key="niv_ticker",
                               help="E.g. XEQT.TO, VFV.TO, XBB.TO, SPY, QQQ, AAPL.").strip().upper()
        if not ticker:
            return
        a_telecharger = tuple(dict.fromkeys([ticker] + ([reference] if reference else [])))
        try:
            with st.spinner("Downloading 10 years of prices…"):
                prix = telecharger_prix(a_telecharger, debut, params["fin"])
        except ErreurDonnees as e:
            st.error(str(e))
            return
        serie, nom, composition = prix[ticker].dropna(), ticker, None
    else:
        tickers = selecteur_tickers("niv_port", ["XIU.TO", "VFV.TO", "XBB.TO"])
        if not 1 <= len(tickers) <= MAX_ACTIFS_PORTEFEUILLE:
            st.info(f"Choose 1 to {MAX_ACTIFS_PORTEFEUILLE} assets.")
            return
        taux = [t for t in tickers if t in TICKERS_TAUX]
        if taux:
            st.warning(f"{', '.join(taux)}: rates or indicators, not investable assets.")
            return
        poids_df = st.data_editor(pd.DataFrame({"Weight (%)": np.full(len(tickers), round(100 / len(tickers), 2))},
                                               index=tickers), key=f"niv_poids_{'_'.join(tickers)}")
        poids = poids_df["Weight (%)"].astype(float) / 100
        if abs(poids.sum() - 1) > 0.005 or (poids < 0).any():
            st.warning(f"Weights must be positive and total 100% (currently {poids.sum():.2%}).")
            return
        try:
            with st.spinner("Downloading and converting 10 years of prices…"):
                bruts = telecharger_prix(tuple(dict.fromkeys(tickers + ([reference] if reference else []))),
                                         debut, params["fin"])
                convertis, _ = convertir_en_devise_base(bruts[tickers], params["devise"], TICKERS_TAUX)
                communs, _ = aligner_calendriers(convertis)
        except ErreurDonnees as e:
            st.error(str(e))
            return
        prix = bruts
        serie = pr.valeur_portefeuille(communs, poids / poids.sum())
        nom, composition = f"Portfolio ({params['devise']})", None
        st.caption(f"Portfolio rebalanced daily, prices converted to {params['devise']}, "
                   f"common history since {communs.index.min().date()}.")

    ref_serie = prix[reference].dropna() if reference and reference in prix else None
    resultat = pr.profil(serie, ref_serie)

    # ------------------------------------------------ résultat principal
    if resultat["Rank (1 to 5)"] == 0:
        st.error("Less than 12 months of history: risk level cannot be computed.")
        return
    st.markdown(f"#### {nom}: risk level **{resultat['CSA risk level']}**")
    _jauge(resultat["Rank (1 to 5)"])
    if not resultat["Full history (120 months)"]:
        st.warning(f"Only {resultat['Months used']} months of history (120 required). **Indicative** level: "
                   "the official method fills the history with a reference index.")

    metriques({"Annualized std. dev. (CSA method)": resultat["Annualized std. dev. (monthly, CSA)"],
               "Volatility (daily returns)": resultat["Annualized volatility (daily)"],
               "Historical VaR 95% (1 day)": resultat["Historical VaR 95% (1 day)"],
               "Maximum drawdown": resultat["Maximum drawdown"]})
    metriques({"Worst month": resultat["Worst month"], "Best month": resultat["Best month"],
               "Positive months": resultat["Positive months"]}, "{:.2%}")
    if ref_serie is not None:
        metriques({"Beta vs benchmark": resultat.get("Beta vs benchmark"),
                   "Correlation vs benchmark": resultat.get("Correlation vs benchmark")}, "{:.2f}")
    st.caption(f"Computed on {resultat['Months used']} monthly returns.")

    st.plotly_chart(_graphique_glissant(serie), width="stretch")

    # ------------------------------------------------ composition du FNB (si Yahoo la fournit)
    if mode == "An ETF or a security":
        composition = infos_fonds(nom)
        if composition:
            with st.expander("Fund composition (Yahoo Finance)", icon=":material/donut_large:"):
                if "principaux_titres" in composition:
                    st.markdown("**Top holdings**")
                    st.dataframe(composition["principaux_titres"], width="stretch")
                if "secteurs" in composition:
                    secteurs = pd.Series(composition["secteurs"], dtype=float).sort_values(ascending=False)
                    secteurs = secteurs[secteurs > 0]
                    if not secteurs.empty:
                        st.plotly_chart(px.bar(secteurs, orientation="h", title="Weight by sector",
                                               labels={"value": "", "index": ""})
                                        .update_layout(xaxis_tickformat=".0%", showlegend=False, height=360),
                                        width="stretch")

    # ------------------------------------------------ export
    resume = pd.Series({k: v for k, v in resultat.items()}, name="Value").to_frame()
    fichier = exporter_excel({"Risk profile": resume, "Monthly returns": pr.rendements_mensuels(serie).to_frame("Return"),
                              "Value": serie.to_frame("Value")},
                             {"Assessed": nom, "Method": "CSA, NI 81-102, Appendix F (10-year monthly std. dev., annualized)",
                              "Benchmark": reference_nom, "End of period": params["fin"],
                              "Source": "Yahoo Finance, adjusted prices (approximation of NAV)"})
    st.download_button("Export the risk profile (Excel)", fichier, key="niv_export",
                       file_name=f"risk_level_{nom.split()[0]}.xlsx", icon=":material/download:",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    note_methodo(
        "- **Official method** (CSA, NI 81-102, Appendix F): standard deviation of the latest 120 "
        "monthly returns, annualized by √12, classified in the 6 / 11 / 16 / 20% grid.\n"
        "- **Approximation**: adjusted Yahoo prices instead of the fund's NAV; the current month, "
        "being incomplete, is excluded.\n"
        "- **Less than 10 years of history**: indicative level. The official method fills in with a reference index.\n"
        "- A manager may **raise** the official level if reasonable: the published level may therefore be "
        "higher than the one computed here.\n"
        "- **Beta**: sensitivity to the benchmark's moves (daily returns)."
    )
