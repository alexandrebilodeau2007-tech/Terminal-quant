"""
SPRD — Spreads de taux (yield spreads).

Trois onglets :
    1. Tableau de bord : les spreads les plus suivis, avec leur position historique (z-score).
    2. Entre deux taux : n'importe quel couple de taux, tracé dans le temps.
    3. G-spread : écart entre une obligation d'entreprise et la courbe d'État du jour.
Sources : FRED (taux US, clé requise) et Banque du Canada (aucune clé).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from calculs import spreads as sp
from config import COURBE_BDC, COURBE_FRED, SERIES_TAUX, SPREADS_PREDEFINIS
from export.excel import exporter_excel
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from sources.taux import cle_fred, courbe_a_une_date, serie_bdc, serie_fred


def _serie(nom: str, debut: str) -> pd.Series:
    """Télécharge une série de SERIES_TAUX par son nom affiché.
    Lève ValueError si la série US est demandée sans clé FRED."""
    source, code = SERIES_TAUX[nom]
    if source == "FRED":
        cle = cle_fred()
        if not cle:
            raise ValueError("clé FRED absente")
        return serie_fred(code, debut, cle).rename(nom)
    return serie_bdc(code, debut).rename(nom)


def _disponibles() -> list[str]:
    """Séries utilisables : sans clé FRED, seules les séries canadiennes le sont."""
    return [n for n, (src, _) in SERIES_TAUX.items() if src == "BDC" or cle_fred()]


def _graphique_spread(spread: pd.Series, titre_graphique: str) -> go.Figure:
    """Spread en pb avec sa moyenne et une bande de ±2 écarts-types :
    au-delà de la bande, le spread est historiquement extrême."""
    moyenne, ecart = spread.mean(), spread.std(ddof=1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=spread.index, y=[moyenne + 2 * ecart] * len(spread), line={"width": 0},
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=spread.index, y=[moyenne - 2 * ecart] * len(spread), line={"width": 0},
                             fill="tonexty", fillcolor="rgba(255,159,28,0.08)", name="Moyenne ± 2 écarts-types",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread (pb)", line={"width": 2}))
    fig.add_hline(y=moyenne, line_dash="dot", line_color="#8B98A9", annotation_text="moyenne")
    fig.add_hline(y=0, line_color="#1F2A37")
    fig.update_layout(title=titre_graphique, yaxis_title="Points de base", height=420)
    return fig


def afficher(params: dict) -> None:
    titre("Spreads de taux", "spr", "SPRD",
          "Écarts entre taux en points de base (1 pb = 0,01 %) · FRED et Banque du Canada.")
    if not cle_fred():
        st.info("Sans clé FRED, seuls les taux canadiens sont disponibles. Ajoute FRED_API_KEY dans les Secrets "
                "pour les taux américains et les écarts de crédit.")
    onglet_tdb, onglet_deux, onglet_g = st.tabs([":material/dashboard: Tableau de bord",
                                                 ":material/compare_arrows: Entre deux taux",
                                                 ":material/request_quote: G-spread d'une obligation"])
    with onglet_tdb:
        _tableau_de_bord(params)
    with onglet_deux:
        _entre_deux(params)
    with onglet_g:
        _g_spread()
    note_methodo(
        "- **Spread** = taux A − taux B, en points de base, sur les dates communes aux deux séries (aucun remplissage).\n"
        "- **z-score** = (actuel − moyenne) / écart-type sur la période choisie. Il dépend de la période : "
        "une période courte donne une « normale » courte.\n"
        "- **Écarts de crédit FRED** (ICE BofA OAS) : déjà des spreads contre le Trésor, ajustés des options.\n"
        "- **G-spread** : interpolation linéaire de la courbe d'État du dernier jour disponible, sans extrapolation "
        "au-delà des maturités publiées.\n"
        "- **Canada long terme** : obligation de référence longue de la Banque du Canada (environ 30 ans)."
    )


# ---------------------------------------------------------------- onglet 1
def _tableau_de_bord(params: dict) -> None:
    sous_titre("Spreads les plus suivis", "spr_pred")
    lignes, series = [], {}
    with st.spinner("Calcul des spreads…"):
        for nom, (a, b) in SPREADS_PREDEFINIS.items():
            try:
                s = sp.spread_pb(_serie(a, params["debut"]), _serie(b, params["debut"]))
            except (ValueError, requests.RequestException):
                continue  # série indisponible (clé FRED absente ou source injoignable)
            if s.empty:
                continue
            series[nom] = s
            stats = sp.statistiques_spread(s)
            lignes.append({"Spread": nom, **{k: stats[k] for k in ("Actuel (pb)", "Moyenne (pb)", "z-score",
                                                                   "Percentile historique", "Variation sur 1 an (pb)")}})
    if not lignes:
        st.warning("Aucun spread disponible pour le moment.")
        return
    tableau = pd.DataFrame(lignes).set_index("Spread")
    st.dataframe(tableau.style.format({"Actuel (pb)": "{:.0f}", "Moyenne (pb)": "{:.0f}", "z-score": "{:+.2f}",
                                       "Percentile historique": "{:.0%}", "Variation sur 1 an (pb)": "{:+.0f}"},
                                      na_rep="N/A")
                 .map(lambda v: "color:#FF9F1C;font-weight:600" if isinstance(v, float) and abs(v) >= 2 else "",
                      subset=["z-score"]), width="stretch")
    st.caption("z-score en ambre : spread à plus de 2 écarts-types de sa moyenne, donc historiquement extrême.")
    choix = st.selectbox("Spread à tracer", list(series), key="spr_tdb_choix")
    st.plotly_chart(_graphique_spread(series[choix], choix), width="stretch")
    fichier = exporter_excel({"Tableau de bord": tableau, **{n[:31]: s.to_frame() for n, s in series.items()}},
                             {"Période": f"{params['debut']} → {params['fin']}", "Sources": "FRED, Banque du Canada",
                              "Unité": "points de base (pb)"})
    st.download_button("Exporter les spreads (Excel)", fichier, key="spr_tdb_export",
                       file_name="spreads_tableau_de_bord.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 2
def _entre_deux(params: dict) -> None:
    sous_titre("Spread entre deux taux au choix", "spr_deux")
    noms = _disponibles()
    c1, c2 = st.columns(2)
    a = c1.selectbox("Taux A", noms, index=noms.index("Canada 10 ans") if "Canada 10 ans" in noms else 0, key="spr_a")
    defaut_b = "US 10 ans" if "US 10 ans" in noms else ("Canada 2 ans" if "Canada 2 ans" in noms else noms[0])
    b = c2.selectbox("Taux B", noms, index=noms.index(defaut_b), key="spr_b")
    if a == b:
        st.info("Choisis deux taux différents.")
        return
    try:
        with st.spinner("Téléchargement des taux…"):
            serie_a, serie_b = _serie(a, params["debut"]), _serie(b, params["debut"])
    except (ValueError, requests.RequestException) as e:
        st.error(f"Série indisponible : {e}")
        return
    spread = sp.spread_pb(serie_a, serie_b)
    if spread.empty:
        st.warning("Aucune date commune entre les deux séries.")
        return
    stats = sp.statistiques_spread(spread)
    metriques({k: stats[k] for k in ("Actuel (pb)", "Moyenne (pb)", "Minimum (pb)", "Maximum (pb)")}, "{:.0f}")
    metriques({"z-score": stats["z-score"], "Variation sur 1 an (pb)": stats["Variation sur 1 an (pb)"]}, "{:+.2f}")
    st.caption(f"Le niveau actuel est supérieur à {stats['Percentile historique']:.0%} des observations depuis "
               f"{spread.index.min().date()}.")
    st.plotly_chart(_graphique_spread(spread, f"{a} − {b}"), width="stretch")
    niveaux = go.Figure([go.Scatter(x=serie_a.index, y=serie_a, name=a), go.Scatter(x=serie_b.index, y=serie_b, name=b)])
    st.plotly_chart(niveaux.update_layout(title="Niveaux des deux taux (%)", yaxis_title="%", height=340), width="stretch")
    fichier = exporter_excel({"Spread": spread.to_frame(), "Taux": pd.concat([serie_a, serie_b], axis=1),
                              "Statistiques": pd.Series(stats, name="Valeur").to_frame()},
                             {"Spread": f"{a} − {b}", "Unité": "points de base", "Sources": "FRED, Banque du Canada"})
    st.download_button("Exporter (Excel)", fichier, key="spr_deux_export", file_name="spread.xlsx",
                       icon=":material/download:")


# ---------------------------------------------------------------- onglet 3
def _g_spread() -> None:
    sous_titre("G-spread d'une obligation d'entreprise", "spr_gspread")
    c1, c2, c3 = st.columns(3)
    pays = c1.radio("Courbe d'État", ["Canada", "États-Unis"], horizontal=True, key="g_pays")
    maturite = c2.number_input("Années à l'échéance", 0.25, 30.0, 7.0, 0.25, key="g_mat")
    rendement = c3.number_input("Rendement à l'échéance de l'obligation (%)", 0.0, 30.0, 5.30, 0.05, key="g_ytm",
                                help="Le YTM se calcule dans YCRV → Calculatrice obligataire à partir du prix.")
    debut = str((pd.Timestamp.today() - pd.DateOffset(months=1)).date())
    try:
        if pays == "Canada":
            courbes = {m: serie_bdc(code, debut) for m, code in COURBE_BDC.items()}
        else:
            cle = cle_fred()
            if not cle:
                st.warning("Clé FRED absente : choisis la courbe du Canada.")
                return
            courbes = {m: serie_fred(code, debut, cle) for m, code in COURBE_FRED.items()}
    except requests.RequestException as e:
        st.error(f"Courbe indisponible : {e}")
        return
    date = max(s.index.max() for s in courbes.values() if not s.empty)
    courbe = courbe_a_une_date(courbes, date)
    resultat = sp.g_spread(rendement, courbe, maturite)
    metriques({"Taux d'État interpolé": resultat["Taux d'État interpolé (%)"] / 100,
               "Rendement de l'obligation": rendement / 100}, "{:.3%}", par_ligne=3)
    st.metric("G-spread", f"{resultat['G-spread (pb)']:.0f} pb", border=True)
    st.caption(f"Courbe du {date.date()}. Un G-spread plus élevé signale une prime de risque de crédit plus forte.")
    fig = go.Figure([go.Scatter(x=courbe.index, y=courbe.values, mode="lines+markers", name=f"Courbe {pays}"),
                     go.Scatter(x=[maturite], y=[rendement], mode="markers", name="Ton obligation",
                                marker={"size": 13, "symbol": "diamond"})])
    fig.add_shape(type="line", x0=maturite, x1=maturite, y0=resultat["Taux d'État interpolé (%)"], y1=rendement,
                  line={"dash": "dot", "color": "#FF9F1C"})
    fig.update_layout(title="Obligation comparée à la courbe d'État", xaxis_title="Maturité (années)",
                      yaxis_title="Rendement (%)", height=400)
    st.plotly_chart(fig, width="stretch")
