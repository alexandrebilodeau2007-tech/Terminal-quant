"""
Section 1 — Marchés multi-actifs.

But : vue d'ensemble rapide de n'importe quel marché (actions, indices,
commodités, forex, obligations, taux) : performance, volatilité, corrélations.
"""

from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from calculs.rendements import performance_periodes, rendements_simples
from config import JOURS_BOURSE_PAR_AN, TICKERS_TAUX
from interface.aide import sous_titre, titre
from interface.composants import note_methodo, selecteur_tickers, tableau_pourcent
from sources.marche import (ErreurDonnees, convertir_en_devise_base, telecharger_ohlc,
                            telecharger_prix)


def afficher(params: dict) -> None:
    titre("Multi-asset markets", "marches", "MKT",
          "Stocks, indices, commodities, forex, crypto, bonds and rates — source: Yahoo Finance.")

    tickers = selecteur_tickers("marches", ["^GSPC", "^GSPTSE", "GC=F", "CL=F", "USDCAD=X", "TLT", "^TNX"],
                                cle_commande="cmd_marches_libre")
    convertir = st.checkbox(f"Convert prices to {params['devise']}", value=False,
                            help="Unchecked: each asset in its original currency (market view). "
                                 "Checked: the return experienced by an investor in your currency.")
    if not tickers:
        st.info("Pick at least one asset.")
        return

    try:
        with st.spinner("Downloading prices…"):
            prix = telecharger_prix(tuple(tickers), params["debut"], params["fin"])
            if convertir:
                prix, _ = convertir_en_devise_base(prix, params["devise"], TICKERS_TAUX)
    except ErreurDonnees as e:
        st.error(str(e))
        return

    # On sépare les TAUX (niveaux en %) des PRIX : les mettre sur le même
    # graphique "base 100" n'aurait aucun sens.
    col_taux = [t for t in prix.columns if t in TICKERS_TAUX]
    col_prix = [t for t in prix.columns if t not in TICKERS_TAUX]

    if col_prix:
        sous_titre("Performance", "marches_perf")
        tableau_pourcent(performance_periodes(prix[col_prix]), signe=True)

        # Base 100 : chaque série divisée par son premier prix x 100.
        # Permet de comparer des actifs aux prix très différents (ex. or vs USD/CAD).
        base100 = prix[col_prix].ffill()
        base100 = base100 / base100.bfill().iloc[0] * 100
        fig = px.line(base100, labels={"value": "Rebased to 100", "index": "", "variable": "Active"})
        st.plotly_chart(fig, width="stretch")

        sous_titre("Risk and correlations", "marches_risque")
        r = rendements_simples(prix[col_prix])
        vol = (r.std() * np.sqrt(JOURS_BOURSE_PAR_AN)).to_frame("Annualized volatility")
        # Volatilité sur les 3 derniers mois : montre si le risque actuel
        # est plus élevé ou plus faible que la moyenne de la période.
        vol["Volatility, latest 63 days"] = r.tail(63).std() * np.sqrt(JOURS_BOURSE_PAR_AN)
        tableau_pourcent(vol)

        if len(col_prix) > 1:
            # pairwise : chaque paire utilise ses dates communes (calendriers différents).
            correl = r.corr(min_periods=60)
            fig = px.imshow(correl, text_auto=".2f", zmin=-1, zmax=1, color_continuous_scale="RdBu",
                            aspect="auto", title="Correlation of daily returns")
            st.plotly_chart(fig, width="stretch")

    if col_taux:
        sous_titre("Rates and level indicators (%)", "marches_risque")
        st.plotly_chart(px.line(prix[col_taux], labels={"value": "%", "index": "", "variable": ""}),
                        width="stretch")

    sous_titre("Asset detail", "marches_detail")
    choix = st.selectbox("Active", tickers, key="marches_detail")
    try:
        ohlc = telecharger_ohlc(choix, params["debut"], params["fin"])
    except ErreurDonnees as e:
        st.error(str(e))
        return
    fig = go.Figure(go.Candlestick(x=ohlc.index, open=ohlc["Open"], high=ohlc["High"],
                                   low=ohlc["Low"], close=ohlc["Close"], name=choix))
    for fenetre in (50, 200):  # moyennes mobiles classiques
        fig.add_trace(go.Scatter(x=ohlc.index, y=ohlc["Close"].rolling(fenetre).mean(),
                                 name=f"MM {fenetre} j", line={"width": 1.2}))
    fig.update_layout(xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, width="stretch")

    note_methodo(
        "- Prices **adjusted** for dividends and splits.\n"
        "- Commodities: **continuous** futures (`=F`). When the contract rolls, an artificial "
        "price jump can appear: interpret returns around roll dates with caution.\n"
        "- Forex: `USDCAD=X` = number of CAD per 1 USD.\n"
        "- Rates (`^TNX`, etc.) are **levels**, not prices: they are excluded from returns and correlations.\n"
        "- Correlations computed on pairwise common dates, minimum 60 observations."
    )
