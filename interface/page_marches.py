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
    titre("Marchés multi-actifs", "marches", "MKT",
          "Actions, indices, commodités, forex, crypto, obligations et taux — source : Yahoo Finance.")

    tickers = selecteur_tickers("marches", ["^GSPC", "^GSPTSE", "GC=F", "CL=F", "USDCAD=X", "TLT", "^TNX"],
                                cle_commande="cmd_marches_libre")
    convertir = st.checkbox(f"Convertir les prix en {params['devise']}", value=False,
                            help="Décoché : chaque actif dans sa devise d'origine (lecture du marché). "
                                 "Coché : rendement vécu par un investisseur dans ta devise.")
    if not tickers:
        st.info("Choisis au moins un actif.")
        return

    try:
        with st.spinner("Téléchargement des prix…"):
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
        fig = px.line(base100, labels={"value": "Base 100", "index": "", "variable": "Actif"})
        st.plotly_chart(fig, width="stretch")

        sous_titre("Risque et corrélations", "marches_risque")
        r = rendements_simples(prix[col_prix])
        vol = (r.std() * np.sqrt(JOURS_BOURSE_PAR_AN)).to_frame("Volatilité annualisée")
        # Volatilité sur les 3 derniers mois : montre si le risque actuel
        # est plus élevé ou plus faible que la moyenne de la période.
        vol["Volatilité 63 derniers jours"] = r.tail(63).std() * np.sqrt(JOURS_BOURSE_PAR_AN)
        tableau_pourcent(vol)

        if len(col_prix) > 1:
            # pairwise : chaque paire utilise ses dates communes (calendriers différents).
            correl = r.corr(min_periods=60)
            fig = px.imshow(correl, text_auto=".2f", zmin=-1, zmax=1, color_continuous_scale="RdBu",
                            aspect="auto", title="Corrélation des rendements quotidiens")
            st.plotly_chart(fig, width="stretch")

    if col_taux:
        sous_titre("Taux et indicateurs de niveau (%)", "marches_risque")
        st.plotly_chart(px.line(prix[col_taux], labels={"value": "%", "index": "", "variable": ""}),
                        width="stretch")

    sous_titre("Détail d'un actif", "marches_detail")
    choix = st.selectbox("Actif", tickers, key="marches_detail")
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
        "- Prix **ajustés** pour dividendes et fractionnements.\n"
        "- Commodités : contrats à terme **continus** (`=F`). Au changement d'échéance, un saut "
        "de prix artificiel peut apparaître : les rendements autour des dates de roll sont à interpréter avec prudence.\n"
        "- Forex : `USDCAD=X` = nombre de CAD pour 1 USD.\n"
        "- Les taux (`^TNX`, etc.) sont des **niveaux**, pas des prix : ils sont exclus des rendements et corrélations.\n"
        "- Corrélations calculées par paires de dates communes, minimum 60 observations."
    )
