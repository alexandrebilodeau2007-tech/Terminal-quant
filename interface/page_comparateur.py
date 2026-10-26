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
from interface import tradingview as tv
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
    aff, graphiques = base["affichage"], base["graphiques"]
    with st.expander("Réglages de l'affichage", icon=":material/tune:", expanded=False):
        c1, c2, c3 = st.columns(3)
        disposition = c1.radio("Nombre de graphiques", list(tv.DISPOSITIONS), format_func=tv.DISPOSITIONS.get,
                               index=list(tv.DISPOSITIONS).index(aff["disposition"]), key="tvr_disposition")
        cle_h = "hauteur_simple" if disposition == 1 else "hauteur_grille"
        hauteur = c2.slider("Hauteur de chaque graphique (pixels)", 400, 1400, aff[cle_h], 20, key=f"tvr_{cle_h}")
        intervalle = c3.selectbox("Intervalle", list(tv.INTERVALLES), format_func=tv.INTERVALLES.get,
                                  index=list(tv.INTERVALLES).index(aff["intervalle"]), key="tvr_intervalle")
        c4, c5 = st.columns([1, 2])
        style = c4.selectbox("Style", list(tv.STYLES), format_func=tv.STYLES.get,
                             index=list(tv.STYLES).index(aff["style"]), key="tvr_style")
        indicateurs = c5.multiselect("Indicateurs au chargement", list(tv.INDICATEURS), default=aff["indicateurs"],
                                     key="tvr_indicateurs")
        # Paramètres des indicateurs affichés (période du RSI, des moyennes, des bandes).
        parametres = {nom: dict(v) for nom, v in base["parametres"].items()}
        avec_parametres = [i for i in indicateurs if i in tv.PARAMETRES]
        if avec_parametres:
            st.markdown("**Paramètres des indicateurs**")
            champs = [(nom, cle, spec) for nom in avec_parametres for cle, spec in tv.PARAMETRES[nom].items()]
            colonnes_p = st.columns(min(len(champs), 4))
            for k, (nom, cle, (defaut, mini, maxi, libelle)) in enumerate(champs):
                pas = 1 if isinstance(defaut, int) else 0.1
                parametres[nom][cle] = colonnes_p[k % len(colonnes_p)].number_input(
                    libelle, mini, maxi, parametres[nom][cle], pas, key=f"tvr_p_{nom}_{cle}")
        st.markdown("**Couleurs**")
        colonnes_c = st.columns(len(tv.COULEURS))
        couleurs = {cle: colonnes_c[k].color_picker(libelle, base["couleurs"][cle], key=f"tvr_c_{cle}")
                    for k, (cle, (_, libelle)) in enumerate(tv.COULEURS.items())}
        st.caption("La couleur des lignes d'indicateurs (RSI, moyennes) n'est pas réglable ici : TradingView la réserve "
                   "à sa version payante. Elle se change à l'écran avec la roue dentée de l'indicateur, sans être enregistrée.")
        o = st.columns(6)
        options = {
            "barre_outils_laterale": o[0].toggle("Outils de dessin", aff["barre_outils_laterale"], key="tvr_lat"),
            "barre_outils_haut": o[1].toggle("Barre du haut", aff["barre_outils_haut"], key="tvr_haut"),
            "plages_de_dates": o[2].toggle("Plages de dates", aff["plages_de_dates"], key="tvr_dates"),
            "legende": o[3].toggle("Légende", aff["legende"], key="tvr_legende"),
            "panneau_details": o[4].toggle("Panneau détails", aff["panneau_details"], key="tvr_details"),
            "masquer_volume": o[5].toggle("Masquer le volume", aff["masquer_volume"], key="tvr_volume"),
        }
        st.markdown("**Symboles** (format TradingView `BOURSE:SYMBOLE`, voir la colonne TradingView du répertoire)")
        nouveaux = []
        colonnes = st.columns(2)
        for i in range(disposition):
            with colonnes[i % 2]:
                a, b = st.columns(2)
                symbole = a.text_input(f"Graphique {i + 1}", graphiques[i]["symbole"], key=f"tvr_sym_{i}").strip()
                comparer = b.text_input(f"Comparer avec ({i + 1})", graphiques[i]["comparer"], key=f"tvr_cmp_{i}").strip()
                nouveaux.append({"symbole": symbole, "comparer": comparer})
        invalides = [v for g in nouveaux for v in g.values() if v and not tv.symbole_valide(v)]
        if invalides:
            st.error(f"Symbole non valide : {', '.join(invalides)}. Lettres, chiffres et : . ! ^ seulement.")
    reglages = {"affichage": {**aff, "disposition": disposition, cle_h: hauteur, "intervalle": intervalle,
                              "style": style, "indicateurs": indicateurs, **options},
                "parametres": parametres, "couleurs": couleurs,
                "graphiques": nouveaux + graphiques[disposition:]}
    return tv.valider(reglages)


def _tradingview() -> None:
    sous_titre("Graphiques TradingView", "cmp_tv")
    base = _reglages_session()
    if base["affichage"]["permettre_modifications"]:
        reglages = _panneau_reglages(base)
        st.session_state[CLE_REGLAGES] = reglages
        c1, c2 = st.columns(2)
        c1.button("Revenir aux réglages de base", on_click=_reinitialiser, icon=":material/restart_alt:",
                  width="stretch", key="tv_reset")
        c2.download_button("Exporter ces réglages comme base (tradingview.toml)", tv.en_toml(reglages),
                           file_name="tradingview.toml", mime="text/plain", icon=":material/download:",
                           width="stretch", key="tv_export",
                           help="Remplace le fichier tradingview.toml du dépôt GitHub par celui-ci : "
                                "tous les visiteurs verront ces réglages.")
    else:
        reglages = base
    page, hauteur = tv.html_grille(reglages)
    components.html(page, height=hauteur)
    st.caption("Dans chaque graphique : change de symbole, ajoute des indicateurs, dessine, ou ouvre-le en grande "
               "fenêtre (bouton en haut à droite). Ces changements ne sont pas enregistrés : au prochain chargement, "
               "les réglages de base reviennent.")
    note_methodo(
        "- **Réglages communs** : la base vient du fichier `tradingview.toml` du dépôt GitHub. Tous les visiteurs "
        "la voient au chargement ; ce qu'un visiteur change ne vaut que pour sa visite.\n"
        "- **Changer la base pour tout le monde** : règle l'affichage ici, clique sur *Exporter ces réglages comme base*, "
        "puis remplace `tradingview.toml` sur GitHub. L'app se met à jour en une à deux minutes. "
        "Avec `permettre_modifications = false`, le panneau de réglages est masqué.\n"
        "- **TradingView n'offre pas d'API de données publique** : le terminal intègre leur widget gratuit, qui sert à "
        "l'affichage. Les calculs (formules, ratios, statistiques, export) se font dans les deux autres onglets.\n"
        "- **Ce qui s'enregistre dans la base** (vérifié en ligne) : style du graphique, intervalle, liste des indicateurs, "
        "**paramètres des indicateurs** (période du RSI, des moyennes, des bandes de Bollinger), **couleurs des bougies**, "
        "du fond et de la grille, barres d'outils.\n"
        "- **Ce qui ne s'enregistre pas** : la couleur et l'épaisseur des lignes d'indicateurs (RSI, moyennes) et les dessins. "
        "Les widgets gratuits les ignorent ; TradingView les réserve à sa bibliothèque payante et aux comptes TradingView.\n"
        "- **Contrats à terme et certains indices non affichables** dans le widget gratuit (message « Symbole disponible "
        "uniquement sur TradingView ») : utiliser `OANDA:XAUUSD` (or), `OANDA:XAGUSD` (argent), `TVC:USOIL` (pétrole) "
        "ou un FNB (`AMEX:SPY`, `TSX:XIU`).\n"
        "- Certaines données en temps réel exigent un abonnement TradingView ; le widget affiche alors des données différées."
    )
