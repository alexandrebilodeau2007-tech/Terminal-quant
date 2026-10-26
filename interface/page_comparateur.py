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
from interface import tradingview as tv, vue_graphiques
from interface.navigation import valeur_initiale
from sources.marche import ErreurDonnees, convertir_en_devise_base, telecharger_prix

FENETRE_GLISSANTE = 60  # jours de bourse (≈ 3 mois) pour la corrélation et le bêta glissants

EXEMPLES_FORMULES = {
    "Gold / silver ratio": "GC=F / SI=F",
    "WTI − Brent spread": "CL=F - BZ=F",
    "Stocks / bonds": "SPY / TLT",
    "Copper / gold (growth barometer)": "HG=F / GC=F",
    "Bitcoin in CAD": "BTC-USD * USDCAD=X",
    "Basket of 3 tech giants": "(AAPL + MSFT + NVDA) / 3",
}


def afficher(params: dict) -> None:
    titre("Comparator & formulas", "cmp", "CMP",
          "Two symbols side by side, ticker formulas and TradingView charts.")
    o1, o2, o3 = st.tabs([":material/compare_arrows: Two symbols", ":material/function: Formula",
                          ":material/candlestick_chart: TradingView charts"])
    with o1:
        _deux_symboles(params)
    with o2:
        _formule(params)
    with o3:
        _tradingview()


# ---------------------------------------------------------------- onglet 1
def _deux_symboles(params: dict) -> None:
    sous_titre("Compare two symbols", "cmp_deux")
    valeur_initiale("cmp_a", "MU", "cmd_cmp_a")
    valeur_initiale("cmp_b", "SOXX", "cmd_cmp_b")
    c1, c2, c3 = st.columns([2, 2, 2], vertical_alignment="bottom")
    a = c1.text_input("Symbol A (Yahoo)", key="cmp_a").strip().upper()
    b = c2.text_input("Symbol B (Yahoo)", key="cmp_b").strip().upper()
    convertir = c3.checkbox(f"Convert to {params['devise']}", key="cmp_conv")
    if not a or not b or a == b:
        st.info("Enter two different symbols (see the Directory, code TKR).")
        return
    try:
        with st.spinner("Downloading…"):
            prix = telecharger_prix((a, b), params["debut"], params["fin"])
            if convertir:
                prix, _ = convertir_en_devise_base(prix, params["devise"], TICKERS_TAUX)
    except ErreurDonnees as e:
        st.error(str(e))
        return
    prix = prix[[a, b]].dropna()
    if len(prix) < FENETRE_GLISSANTE + 5:
        st.warning("Not enough common dates between the two symbols.")
        return

    r = prix.pct_change().dropna()
    base100 = prix / prix.iloc[0] * 100
    ratio = (prix[a] / prix[b]).rename(f"{a} / {b}")
    correl = r[a].rolling(FENETRE_GLISSANTE).corr(r[b])
    beta_gliss = r[a].rolling(FENETRE_GLISSANTE).cov(r[b]) / r[b].rolling(FENETRE_GLISSANTE).var()

    stats = pd.DataFrame({
        s: {"Return over the period": prix[s].iloc[-1] / prix[s].iloc[0] - 1,
            "Annualized volatility": r[s].std() * np.sqrt(JOURS_BOURSE_PAR_AN),
            "Maximum drawdown": drawdown(r[s]).min()}
        for s in (a, b)
    }).T
    colonnes = st.columns(4)
    colonnes[0].metric("Correlation (period)", f"{r[a].corr(r[b]):.2f}", border=True)
    colonnes[1].metric(f"Beta of {a} vs {b}", f"{beta(r[a], r[b]):.2f}", border=True)
    colonnes[2].metric(f"Correlation {FENETRE_GLISSANTE} latest days", f"{correl.iloc[-1]:.2f}", border=True)
    colonnes[3].metric("Current ratio vs its mean", f"{ratio.iloc[-1] / ratio.mean() - 1:+.1%}", border=True)
    st.dataframe(stats.style.format("{:.2%}"), width="stretch")

    fig = go.Figure([go.Scatter(x=base100.index, y=base100[s], name=s) for s in (a, b)])
    st.plotly_chart(fig.update_layout(title="Performance rebased to 100", height=380), width="stretch")
    fig = go.Figure(go.Scatter(x=ratio.index, y=ratio, name=ratio.name))
    fig.add_hline(y=ratio.mean(), line_dash="dot", line_color="#8B98A9", annotation_text="mean")
    st.plotly_chart(fig.update_layout(title=f"Ratio {a} / {b} (rising = A outperforms B)", height=340),
                    width="stretch")
    fig = go.Figure([go.Scatter(x=correl.index, y=correl, name="Correlation"),
                     go.Scatter(x=beta_gliss.index, y=beta_gliss, name="Beta", yaxis="y2")])
    fig.update_layout(title=f"Rolling correlation and beta over {FENETRE_GLISSANTE} days", height=340,
                      yaxis={"title": "Correlation", "range": [-1, 1]},
                      yaxis2={"title": "Beta", "overlaying": "y", "side": "right", "showgrid": False})
    st.plotly_chart(fig, width="stretch")

    fichier = exporter_excel({"Price": prix, "Rebased to 100": base100, "Ratio": ratio.to_frame(),
                              "Rolling": pd.DataFrame({"Correlation": correl, "Beta": beta_gliss}),
                              "Statistics": stats},
                             {"Symbols": f"{a} vs {b}", "Period": f"{prix.index.min().date()} → {prix.index.max().date()}",
                              "Currency": params["devise"] if convertir else "original currencies",
                              "Rolling window": f"{FENETRE_GLISSANTE} days", "Source": "Yahoo Finance"})
    st.download_button("Export comparison (Excel)", fichier, key="cmp_export",
                       file_name=f"comparison_{a}_{b}.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 2
def _choisir_exemple(expression: str) -> None:
    st.session_state["cmp_formule"] = expression


def _formule(params: dict) -> None:
    sous_titre("Formula between tickers", "cmp_formule")
    st.caption("Examples (click to try):")
    colonnes = st.columns(3)
    for i, (nom, expr) in enumerate(EXEMPLES_FORMULES.items()):
        colonnes[i % 3].button(nom, key=f"cmp_ex_{i}", on_click=_choisir_exemple, args=(expr,), width="stretch")
    valeur_initiale("cmp_formule", "GC=F / SI=F")
    expression = st.text_input("Formula", key="cmp_formule",
                               help="Operators + - * / ** and parentheses. Put spaces around \"-\" between two tickers.")
    try:
        tickers = fm.tickers_de(expression)
    except fm.ErreurFormule as e:
        st.error(str(e))
        return
    try:
        with st.spinner("Downloading…"):
            prix = telecharger_prix(tuple(tickers), params["debut"], params["fin"])
        resultat = fm.calculer(expression, prix)
    except (ErreurDonnees, fm.ErreurFormule) as e:
        st.error(str(e))
        return
    if resultat.empty:
        st.warning("No date where every ticker has a price.")
        return

    passe = resultat.loc[: resultat.index.max() - pd.DateOffset(years=1)]
    ecart = resultat.std(ddof=1)
    metriques({"Last value": resultat.iloc[-1], "Mean": resultat.mean(),
               "Minimum": resultat.min(), "Maximum": resultat.max()}, "{:,.4g}")
    metriques({"z-score": (resultat.iloc[-1] - resultat.mean()) / ecart if ecart > 0 else np.nan,
               "1-year change": resultat.iloc[-1] / passe.iloc[-1] - 1 if not passe.empty and passe.iloc[-1] != 0 else np.nan},
              "{:+.2f}")
    fig = go.Figure([go.Scatter(x=resultat.index, y=resultat, name=expression),
                     go.Scatter(x=resultat.index, y=resultat.rolling(50).mean(), name="50-day moving average",
                                line={"dash": "dot", "width": 1})])
    fig.add_hline(y=resultat.mean(), line_dash="dot", line_color="#8B98A9", annotation_text="period mean")
    st.plotly_chart(fig.update_layout(title=expression, height=420), width="stretch")
    st.caption("Values computed in each ticker's quote currency, on dates where all have a price.")
    fichier = exporter_excel({"Formula": resultat.to_frame("Value"), "Prices used": prix[tickers]},
                             {"Formula": expression, "Tickers": ", ".join(tickers), "Source": "Yahoo Finance"})
    st.download_button("Export formula (Excel)", fichier, key="cmp_formule_export",
                       file_name="formula.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 3
CLE_REGLAGES = "tv_reglages"


def _reglages_session() -> dict:
    """Réglages de la visite en cours. Au premier passage : copie de la base
    commune (tradingview.toml), donc identique pour tous les visiteurs."""
    if CLE_REGLAGES not in st.session_state:
        st.session_state[CLE_REGLAGES] = tv.charger_base()
    return st.session_state[CLE_REGLAGES]


def _reinitialiser() -> None:
    """Rappel du bouton : revient aux réglages de base et vide les champs du panneau."""
    st.session_state[CLE_REGLAGES] = tv.charger_base()
    for cle in [k for k in st.session_state if str(k).startswith("tvr_")]:
        del st.session_state[cle]


def _panneau_reglages(base: dict) -> dict:
    """Panneau de réglages. Renvoie les réglages choisis (valeurs validées)."""
    aff, graphiques = base["display"], base["charts"]
    with st.expander("Display settings", icon=":material/tune:", expanded=False):
        c1, c2, c3 = st.columns(3)
        disposition = c1.radio("Number of charts", list(tv.DISPOSITIONS), format_func=tv.DISPOSITIONS.get,
                               index=list(tv.DISPOSITIONS).index(aff["layout"]), key="tvr_disposition")
        cle_h = "single_height" if disposition == 1 else "grid_height"
        hauteur = c2.slider("Height of each chart (pixels)", 400, 1400, aff[cle_h], 20, key=f"tvr_{cle_h}")
        intervalle = c3.selectbox("Interval", list(tv.INTERVALLES), format_func=tv.INTERVALLES.get,
                                  index=list(tv.INTERVALLES).index(aff["interval"]), key="tvr_intervalle")
        c4, c5 = st.columns([1, 2])
        style = c4.selectbox("Style", list(tv.STYLES), format_func=tv.STYLES.get,
                             index=list(tv.STYLES).index(aff["style"]), key="tvr_style")
        indicateurs = c5.multiselect("Indicators on load", list(tv.INDICATEURS), default=aff["indicators"],
                                     key="tvr_indicateurs")
        # Paramètres des indicateurs affichés (période du RSI, des moyennes, des bandes).
        parametres = {nom: dict(v) for nom, v in base["parameters"].items()}
        avec_parametres = [i for i in indicateurs if i in tv.PARAMETRES]
        if avec_parametres:
            st.markdown("**Indicator parameters**")
            champs = [(nom, cle, spec) for nom in avec_parametres for cle, spec in tv.PARAMETRES[nom].items()]
            colonnes_p = st.columns(min(len(champs), 4))
            for k, (nom, cle, (defaut, mini, maxi, libelle)) in enumerate(champs):
                pas = 1 if isinstance(defaut, int) else 0.1
                parametres[nom][cle] = colonnes_p[k % len(colonnes_p)].number_input(
                    libelle, mini, maxi, parametres[nom][cle], pas, key=f"tvr_p_{nom}_{cle}")
        st.markdown("**Colors**")
        colonnes_c = st.columns(len(tv.COULEURS))
        couleurs = {cle: colonnes_c[k].color_picker(libelle, base["colors"][cle], key=f"tvr_c_{cle}")
                    for k, (cle, (_, libelle)) in enumerate(tv.COULEURS.items())}
        st.caption("Indicator line colors (RSI, moving averages) cannot be set here: TradingView reserves this "
                   "for its paid version. You can change it on screen with the indicator's gear icon, but it is not saved.")
        o = st.columns(6)
        options = {
            "side_toolbar": o[0].toggle("Drawing tools", aff["side_toolbar"], key="tvr_lat"),
            "top_toolbar": o[1].toggle("Top toolbar", aff["top_toolbar"], key="tvr_haut"),
            "date_ranges": o[2].toggle("Date ranges", aff["date_ranges"], key="tvr_dates"),
            "legend": o[3].toggle("Legend", aff["legend"], key="tvr_legende"),
            "details_panel": o[4].toggle("Details panel", aff["details_panel"], key="tvr_details"),
            "hide_volume": o[5].toggle("Hide volume", aff["hide_volume"], key="tvr_volume"),
        }
        st.markdown("**Symbols** (TradingView format `EXCHANGE:SYMBOL`, see the TradingView column of the directory)")
        nouveaux = []
        colonnes = st.columns(2)
        for i in range(disposition):
            with colonnes[i % 2]:
                a, b = st.columns(2)
                symbole = a.text_input(f"Chart {i + 1}", graphiques[i]["symbol"], key=f"tvr_sym_{i}").strip()
                comparer = b.text_input(f"Compare with ({i + 1})", graphiques[i]["compare"], key=f"tvr_cmp_{i}").strip()
                nouveaux.append({"symbol": symbole, "compare": comparer})
        invalides = [v for g in nouveaux for v in g.values() if v and not tv.symbole_valide(v)]
        if invalides:
            st.error(f"Invalid symbol: {', '.join(invalides)}. Letters, digits and : . ! ^ only.")
    reglages = {"display": {**aff, "layout": disposition, cle_h: hauteur, "interval": intervalle,
                              "style": style, "indicators": indicateurs, **options},
                "parameters": parametres, "colors": couleurs,
                "charts": nouveaux + graphiques[disposition:]}
    return tv.valider(reglages)


def _tradingview() -> None:
    sous_titre("TradingView charts", "cmp_tv")
    base = _reglages_session()
    if base["display"]["allow_changes"]:
        reglages = _panneau_reglages(base)
        st.session_state[CLE_REGLAGES] = reglages
        c1, c2 = st.columns(2)
        c1.button("Back to base settings", on_click=_reinitialiser, icon=":material/restart_alt:",
                  width="stretch", key="tv_reset")
        c2.download_button("Export these settings as base (tradingview.toml)", tv.en_toml(reglages),
                           file_name="tradingview.toml", mime="text/plain", icon=":material/download:",
                           width="stretch", key="tv_export",
                           help="Replace the tradingview.toml file in the GitHub repository with this one: "
                                "every visitor will see these settings.")
    else:
        reglages = base
    # Fenêtre « graphiques seulement » : fenêtre popup à part, réglages du moment transmis dans l'adresse.
    components.html(vue_graphiques.bouton_ouvrir(f"./?view=charts&fs=1&cfg={tv.encoder(reglages)}"), height=44)
    st.caption("Opens a separate window with only the charts, using the settings above. One click there switches "
               "to full screen (no browser bar); move the mouse to the top of the window to show the **X**. "
               "Bookmark `?view=charts&layout=4` for a 4-chart grid with the base settings.")
    page, hauteur = tv.html_grille(reglages)
    components.html(page, height=hauteur)
    st.caption("In each chart: change the symbol, add indicators, draw, or open it in a large "
               "window (top-right button). These changes are not saved: on the next load, "
               "the base settings come back.")
    note_methodo(
        "- **Shared settings**: the base comes from the `tradingview.toml` file in the GitHub repository. Every visitor "
        "sees it on load; what a visitor changes only lasts for their visit.\n"
        "- **Change the base for everyone**: set the display here, click *Export these settings as base*, "
        "then replace `tradingview.toml` on GitHub. The app updates within one to two minutes. "
        "With `allow_changes = false`, the settings panel is hidden.\n"
        "- **TradingView offers no public data API**: the terminal embeds their free widget, which is used for "
        "display. Calculations (formulas, ratios, statistics, export) happen in the other two tabs.\n"
        "- **What the base can store** (verified live): chart style, interval, list of indicators, "
        "**indicator parameters** (RSI, moving average and Bollinger band periods), **candle colors**, "
        "background and grid colors, toolbars.\n"
        "- **What cannot be stored**: indicator line color and width (RSI, moving averages) and drawings. "
        "The free widgets ignore them; TradingView reserves them for its paid library and TradingView accounts.\n"
        "- **Futures and some indices cannot be displayed** in the free widget (message \"Symbol only available "
        "on TradingView\"): use `OANDA:XAUUSD` (gold), `OANDA:XAGUSD` (silver), `TVC:USOIL` (oil) "
        "or an ETF (`AMEX:SPY`, `TSX:XIU`).\n"
        "- Some real-time data requires a TradingView subscription; the widget then shows delayed data."
    )
