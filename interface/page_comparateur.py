"""
CMP — Comparateur & formules.

Trois onglets :
    1. Deux symboles : base 100, ratio, corrélation et bêta glissants.
    2. Formule : expression entre tickers (GC=F / SI=F, CL=F - BZ=F…), calculée par le terminal.
    3. TradingView : graphique interactif officiel (widget gratuit), affichage seulement.
Les onglets 1 et 2 utilisent Yahoo Finance et sont exportables ; le widget
TradingView n'extrait aucune donnée (il ne fait qu'afficher le graphique).
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from calculs import formule as fm
from calculs.profil_risque import beta
from calculs.rendements import drawdown
from config import JOURS_BOURSE_PAR_AN, TICKERS_TAUX
from export.excel import exporter_excel
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from interface.navigation import valeur_initiale
from sources.marche import ErreurDonnees, convertir_en_devise_base, telecharger_prix

FENETRE_GLISSANTE = 60  # jours de bourse (≈ 3 mois) pour la corrélation et le bêta glissants

EXEMPLES_FORMULES = {
    "Ratio or / argent": "GC=F / SI=F",
    "Écart WTI − Brent": "CL=F - BZ=F",
    "Actions / obligations": "SPY / TLT",
    "Cuivre / or (baromètre de croissance)": "HG=F / GC=F",
    "Bitcoin en CAD": "BTC-USD * USDCAD=X",
    "Panier de 3 géants tech": "(AAPL + MSFT + NVDA) / 3",
}


def afficher(params: dict) -> None:
    titre("Comparateur & formules", "cmp", "CMP",
          "Deux symboles face à face, formules entre tickers et graphique TradingView.")
    o1, o2, o3 = st.tabs([":material/compare_arrows: Deux symboles", ":material/function: Formule",
                          ":material/candlestick_chart: Graphique TradingView"])
    with o1:
        _deux_symboles(params)
    with o2:
        _formule(params)
    with o3:
        _tradingview()


# ---------------------------------------------------------------- onglet 1
def _deux_symboles(params: dict) -> None:
    sous_titre("Comparer deux symboles", "cmp_deux")
    valeur_initiale("cmp_a", "MU", "cmd_cmp_a")
    valeur_initiale("cmp_b", "SOXX", "cmd_cmp_b")
    c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    a = c1.text_input("Symbole A (Yahoo)", key="cmp_a").strip().upper()
    b = c2.text_input("Symbole B (Yahoo)", key="cmp_b").strip().upper()
    convertir = c3.checkbox(f"Convertir en {params['devise']}", key="cmp_conv")
    if not a or not b or a == b:
        st.info("Entre deux symboles différents (voir le Répertoire, code TKR).")
        return
    try:
        with st.spinner("Téléchargement…"):
            prix = telecharger_prix((a, b), params["debut"], params["fin"])
            if convertir:
                prix, _ = convertir_en_devise_base(prix, params["devise"], TICKERS_TAUX)
    except ErreurDonnees as e:
        st.error(str(e))
        return
    prix = prix[[a, b]].dropna()
    if len(prix) < FENETRE_GLISSANTE + 5:
        st.warning("Pas assez de dates communes entre les deux symboles.")
        return

    r = prix.pct_change().dropna()
    base100 = prix / prix.iloc[0] * 100
    ratio = (prix[a] / prix[b]).rename(f"{a} / {b}")
    correl = r[a].rolling(FENETRE_GLISSANTE).corr(r[b])
    beta_gliss = r[a].rolling(FENETRE_GLISSANTE).cov(r[b]) / r[b].rolling(FENETRE_GLISSANTE).var()

    stats = pd.DataFrame({
        s: {"Rendement sur la période": prix[s].iloc[-1] / prix[s].iloc[0] - 1,
            "Volatilité annualisée": r[s].std() * np.sqrt(JOURS_BOURSE_PAR_AN),
            "Drawdown maximal": drawdown(r[s]).min()}
        for s in (a, b)
    }).T
    colonnes = st.columns(4)
    colonnes[0].metric("Corrélation (période)", f"{r[a].corr(r[b]):.2f}", border=True)
    colonnes[1].metric(f"Bêta de {a} vs {b}", f"{beta(r[a], r[b]):.2f}", border=True)
    colonnes[2].metric(f"Corrélation {FENETRE_GLISSANTE} derniers jours", f"{correl.iloc[-1]:.2f}", border=True)
    colonnes[3].metric("Ratio actuel vs sa moyenne", f"{ratio.iloc[-1] / ratio.mean() - 1:+.1%}", border=True)
    st.dataframe(stats.style.format("{:.2%}"), width="stretch")

    fig = go.Figure([go.Scatter(x=base100.index, y=base100[s], name=s) for s in (a, b)])
    st.plotly_chart(fig.update_layout(title="Performance en base 100", height=380), width="stretch")
    fig = go.Figure(go.Scatter(x=ratio.index, y=ratio, name=ratio.name))
    fig.add_hline(y=ratio.mean(), line_dash="dot", line_color="#8B98A9", annotation_text="moyenne")
    st.plotly_chart(fig.update_layout(title=f"Ratio {a} / {b} (monte = A fait mieux que B)", height=340),
                    width="stretch")
    fig = go.Figure([go.Scatter(x=correl.index, y=correl, name="Corrélation"),
                     go.Scatter(x=beta_gliss.index, y=beta_gliss, name="Bêta", yaxis="y2")])
    fig.update_layout(title=f"Corrélation et bêta glissants sur {FENETRE_GLISSANTE} jours", height=340,
                      yaxis={"title": "Corrélation", "range": [-1, 1]},
                      yaxis2={"title": "Bêta", "overlaying": "y", "side": "right", "showgrid": False})
    st.plotly_chart(fig, width="stretch")

    fichier = exporter_excel({"Prix": prix, "Base 100": base100, "Ratio": ratio.to_frame(),
                              "Glissant": pd.DataFrame({"Corrélation": correl, "Bêta": beta_gliss}),
                              "Statistiques": stats},
                             {"Symboles": f"{a} vs {b}", "Période": f"{prix.index.min().date()} → {prix.index.max().date()}",
                              "Devise": params["devise"] if convertir else "devises d'origine",
                              "Fenêtre glissante": f"{FENETRE_GLISSANTE} jours", "Source": "Yahoo Finance"})
    st.download_button("Exporter la comparaison (Excel)", fichier, key="cmp_export",
                       file_name=f"comparaison_{a}_{b}.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 2
def _choisir_exemple(expression: str) -> None:
    st.session_state["cmp_formule"] = expression


def _formule(params: dict) -> None:
    sous_titre("Formule entre tickers", "cmp_formule")
    st.caption("Exemples (clique pour essayer) :")
    colonnes = st.columns(3)
    for i, (nom, expr) in enumerate(EXEMPLES_FORMULES.items()):
        colonnes[i % 3].button(nom, key=f"cmp_ex_{i}", on_click=_choisir_exemple, args=(expr,), width="stretch")
    valeur_initiale("cmp_formule", "GC=F / SI=F")
    expression = st.text_input("Formule", key="cmp_formule",
                               help="Opérateurs + - * / ** et parenthèses. Espaces autour du « - » entre deux tickers.")
    try:
        tickers = fm.tickers_de(expression)
    except fm.ErreurFormule as e:
        st.error(str(e))
        return
    try:
        with st.spinner("Téléchargement…"):
            prix = telecharger_prix(tuple(tickers), params["debut"], params["fin"])
        resultat = fm.calculer(expression, prix)
    except (ErreurDonnees, fm.ErreurFormule) as e:
        st.error(str(e))
        return
    if resultat.empty:
        st.warning("Aucune date où tous les tickers ont un prix.")
        return

    passe = resultat.loc[: resultat.index.max() - pd.DateOffset(years=1)]
    ecart = resultat.std(ddof=1)
    metriques({"Dernière valeur": resultat.iloc[-1], "Moyenne": resultat.mean(),
               "Minimum": resultat.min(), "Maximum": resultat.max()}, "{:,.4g}")
    metriques({"z-score": (resultat.iloc[-1] - resultat.mean()) / ecart if ecart > 0 else np.nan,
               "Variation sur 1 an": resultat.iloc[-1] / passe.iloc[-1] - 1 if not passe.empty and passe.iloc[-1] != 0 else np.nan},
              "{:+.2f}")
    fig = go.Figure([go.Scatter(x=resultat.index, y=resultat, name=expression),
                     go.Scatter(x=resultat.index, y=resultat.rolling(50).mean(), name="Moyenne mobile 50 j",
                                line={"dash": "dot", "width": 1})])
    fig.add_hline(y=resultat.mean(), line_dash="dot", line_color="#8B98A9", annotation_text="moyenne de la période")
    st.plotly_chart(fig.update_layout(title=expression, height=420), width="stretch")
    st.caption("Valeurs calculées dans la devise de cotation de chaque ticker, aux dates où tous ont un prix.")
    fichier = exporter_excel({"Formule": resultat.to_frame("Valeur"), "Prix utilisés": prix[tickers]},
                             {"Formule": expression, "Tickers": ", ".join(tickers), "Source": "Yahoo Finance"})
    st.download_button("Exporter la formule (Excel)", fichier, key="cmp_formule_export",
                       file_name="formule.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 3
SYMBOLE_TV_SUR = re.compile(r"^[A-Za-z0-9:._!^/*+\-() ]{1,60}$")


def _widget_tradingview(symbole: str, comparaison: str | None, intervalle: str) -> str:
    """Code HTML du widget officiel « Advanced Chart » de TradingView.
    La configuration est sérialisée en JSON (jamais concaténée) et les symboles
    sont filtrés : aucun texte saisi ne peut injecter de code dans la page."""
    config = {
        "autosize": True, "symbol": symbole, "interval": intervalle, "timezone": "America/Toronto",
        "theme": "dark", "style": "1", "locale": "fr", "allow_symbol_change": True, "calendar": False,
        "backgroundColor": "rgba(10, 14, 20, 1)", "gridColor": "rgba(31, 42, 55, 1)",
        "support_host": "https://www.tradingview.com",
    }
    if comparaison:
        config["compareSymbols"] = [{"symbol": comparaison, "position": "SameScale"}]
    return f"""
<div class="tradingview-widget-container" style="height:100%;width:100%">
  <div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div>
  <div class="tradingview-widget-copyright" style="font:12px sans-serif;color:#8B98A9">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank" style="color:#FF9F1C">
    Graphiques par TradingView</a></div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
  {json.dumps(config)}
  </script>
</div>"""


def _tradingview() -> None:
    sous_titre("Graphique TradingView", "cmp_tv")
    c1, c2, c3 = st.columns([2, 2, 1])
    symbole = c1.text_input("Symbole TradingView", "COMEX:GC1!", key="tv_symbole",
                            help="Format BOURSE:SYMBOLE. Voir la colonne « Symbole TradingView » du Répertoire.").strip()
    comparaison = c2.text_input("Comparer avec (optionnel)", "COMEX:SI1!", key="tv_comparaison").strip()
    intervalle = c3.selectbox("Intervalle", ["D", "W", "M", "60", "15"], key="tv_intervalle",
                              format_func=lambda i: {"D": "Jour", "W": "Semaine", "M": "Mois",
                                                     "60": "1 heure", "15": "15 min"}[i])
    for valeur in (symbole, comparaison):
        if valeur and not SYMBOLE_TV_SUR.match(valeur):
            st.error(f"Symbole non valide : « {valeur} ». Utilise lettres, chiffres et : . ! ^ seulement.")
            return
    if not symbole:
        return
    components.html(_widget_tradingview(symbole, comparaison or None, intervalle), height=620)
    st.caption("Tu peux changer de symbole, ajouter des indicateurs et dessiner directement dans le graphique. "
               "Ce graphique est fourni par TradingView ; le terminal n'en extrait aucune donnée.")
    note_methodo(
        "- **TradingView n'offre pas d'API de données publique** : le terminal intègre leur widget gratuit, "
        "qui sert à l'affichage. Les calculs (formules, ratios, statistiques, export) se font dans les deux autres "
        "onglets, à partir de Yahoo Finance.\n"
        "- Les symboles TradingView diffèrent de ceux de Yahoo : `COMEX:GC1!` (or) contre `GC=F`, `TSX:RY` contre `RY.TO`.\n"
        "- Certaines données en temps réel exigent un abonnement TradingView ; le widget affiche alors des données différées."
    )
