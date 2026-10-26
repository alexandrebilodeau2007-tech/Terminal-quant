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
            raise ValueError("FRED key missing")
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
                             fill="tonexty", fillcolor="rgba(255,159,28,0.08)", name="Mean ± 2 std. devs.",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=spread.index, y=spread, name="Spread (bp)", line={"width": 2, "color": "#FF9F1C"}))
    fig.add_hline(y=moyenne, line_dash="dot", line_color="#8B98A9", annotation_text="mean")
    fig.add_hline(y=0, line_color="#1F2A37")
    fig.update_layout(title=titre_graphique, yaxis_title="Basis points", height=420)
    return fig


def afficher(params: dict) -> None:
    titre("Yield spreads", "spr", "SPRD",
          "Spreads between yields in basis points (1 bp = 0.01%) · FRED and Bank of Canada.")
    if not cle_fred():
        st.info("Without a FRED key, only Canadian yields are available. Add FRED_API_KEY to the Secrets "
                "for US yields and credit spreads.")
    onglet_tdb, onglet_deux, onglet_g = st.tabs([":material/dashboard: Dashboard",
                                                 ":material/compare_arrows: Between two yields",
                                                 ":material/request_quote: Bond G-spread"])
    with onglet_tdb:
        _tableau_de_bord(params)
    with onglet_deux:
        _entre_deux(params)
    with onglet_g:
        _g_spread()
    note_methodo(
        "- **Spread** = yield A − yield B, in basis points, on dates common to both series (no filling).\n"
        "- **z-score** = (current − mean) / std. dev. over the chosen period. It depends on the period: "
        "a short period gives a short-term \"normal\".\n"
        "- **FRED credit spreads** (ICE BofA OAS): already spreads over Treasuries, option-adjusted.\n"
        "- **G-spread**: linear interpolation of the latest available government curve, without extrapolation "
        "beyond the published maturities.\n"
        "- **Canada long-term**: Bank of Canada long benchmark bond (about 30 years)."
    )


# ---------------------------------------------------------------- onglet 1
def _tableau_de_bord(params: dict) -> None:
    sous_titre("Most-watched spreads", "spr_pred")
    lignes, series = [], {}
    with st.spinner("Computing spreads…"):
        for nom, (a, b) in SPREADS_PREDEFINIS.items():
            try:
                s = sp.spread_pb(_serie(a, params["debut"]), _serie(b, params["debut"]))
            except (ValueError, requests.RequestException):
                continue  # série indisponible (clé FRED absente ou source injoignable)
            if s.empty:
                continue
            series[nom] = s
            stats = sp.statistiques_spread(s)
            lignes.append({"Spread": nom, **{k: stats[k] for k in ("Current (bp)", "Mean (bp)", "z-score",
                                                                   "Historical percentile", "1-year change (bp)")}})
    if not lignes:
        st.warning("No spread available right now.")
        return
    tableau = pd.DataFrame(lignes).set_index("Spread")
    st.dataframe(tableau.style.format({"Current (bp)": "{:.0f}", "Mean (bp)": "{:.0f}", "z-score": "{:+.2f}",
                                       "Historical percentile": "{:.0%}", "1-year change (bp)": "{:+.0f}"},
                                      na_rep="N/A")
                 .map(lambda v: "color:#FF9F1C;font-weight:600" if isinstance(v, float) and abs(v) >= 2 else "",
                      subset=["z-score"]), width="stretch")
    st.caption("z-score in amber: spread more than 2 std. devs. from its mean, i.e. historically extreme.")
    choix = st.selectbox("Spread to plot", list(series), key="spr_tdb_choix")
    st.plotly_chart(_graphique_spread(series[choix], choix), width="stretch")
    fichier = exporter_excel({"Dashboard": tableau, **{n[:31]: s.to_frame() for n, s in series.items()}},
                             {"Period": f"{params['debut']} → {params['fin']}", "Sources": "FRED, Bank of Canada",
                              "Unit": "basis points (bp)"})
    st.download_button("Export spreads (Excel)", fichier, key="spr_tdb_export",
                       file_name="spreads_dashboard.xlsx", icon=":material/download:")


# ---------------------------------------------------------------- onglet 2
def _entre_deux(params: dict) -> None:
    sous_titre("Spread between any two yields", "spr_deux")
    noms = _disponibles()
    c1, c2 = st.columns(2)
    a = c1.selectbox("Yield A", noms, index=noms.index("Canada 10-year") if "Canada 10-year" in noms else 0, key="spr_a")
    defaut_b = "US 10-year" if "US 10-year" in noms else ("Canada 2-year" if "Canada 2-year" in noms else noms[0])
    b = c2.selectbox("Yield B", noms, index=noms.index(defaut_b), key="spr_b")
    if a == b:
        st.info("Choose two different yields.")
        return
    try:
        with st.spinner("Downloading yields…"):
            serie_a, serie_b = _serie(a, params["debut"]), _serie(b, params["debut"])
    except (ValueError, requests.RequestException) as e:
        st.error(f"Series unavailable: {e}")
        return
    spread = sp.spread_pb(serie_a, serie_b)
    if spread.empty:
        st.warning("No common date between the two series.")
        return
    stats = sp.statistiques_spread(spread)
    metriques({k: stats[k] for k in ("Current (bp)", "Mean (bp)", "Minimum (bp)", "Maximum (bp)")}, "{:.0f}")
    metriques({"z-score": stats["z-score"], "1-year change (bp)": stats["1-year change (bp)"]}, "{:+.2f}")
    st.caption(f"The current level is above {stats['Historical percentile']:.0%} of observations since "
               f"{spread.index.min().date()}.")
    st.plotly_chart(_graphique_spread(spread, f"{a} − {b}"), width="stretch")
    niveaux = go.Figure([go.Scatter(x=serie_a.index, y=serie_a, name=a), go.Scatter(x=serie_b.index, y=serie_b, name=b)])
    st.plotly_chart(niveaux.update_layout(title="Levels of the two yields (%)", yaxis_title="%", height=340), width="stretch")
    fichier = exporter_excel({"Spread": spread.to_frame(), "Yields": pd.concat([serie_a, serie_b], axis=1),
                              "Statistics": pd.Series(stats, name="Value").to_frame()},
                             {"Spread": f"{a} − {b}", "Unit": "basis points", "Sources": "FRED, Bank of Canada"})
    st.download_button("Export (Excel)", fichier, key="spr_deux_export", file_name="spread.xlsx",
                       icon=":material/download:")


# ---------------------------------------------------------------- onglet 3
def _g_spread() -> None:
    sous_titre("G-spread of a corporate bond", "spr_gspread")
    c1, c2, c3 = st.columns(3)
    pays = c1.radio("Government curve", ["Canada", "United States"], horizontal=True, key="g_pays")
    maturite = c2.number_input("Years to maturity", 0.25, 30.0, 7.0, 0.25, key="g_mat")
    rendement = c3.number_input("Bond yield to maturity (%)", 0.0, 30.0, 5.30, 0.05, key="g_ytm",
                                help="YTM can be computed from the price in YCRV → Bond calculator.")
    debut = str((pd.Timestamp.today() - pd.DateOffset(months=1)).date())
    try:
        if pays == "Canada":
            courbes = {m: serie_bdc(code, debut) for m, code in COURBE_BDC.items()}
        else:
            cle = cle_fred()
            if not cle:
                st.warning("FRED key missing: choose the Canadian curve.")
                return
            courbes = {m: serie_fred(code, debut, cle) for m, code in COURBE_FRED.items()}
    except requests.RequestException as e:
        st.error(f"Curve unavailable: {e}")
        return
    date = max(s.index.max() for s in courbes.values() if not s.empty)
    courbe = courbe_a_une_date(courbes, date)
    resultat = sp.g_spread(rendement, courbe, maturite)
    metriques({"Interpolated government yield": resultat["Interpolated government yield (%)"] / 100,
               "Bond yield": rendement / 100}, "{:.3%}", par_ligne=3)
    st.metric("G-spread", f"{resultat['G-spread (bp)']:.0f} pb", border=True)
    st.caption(f"Curve of {date.date()}. A higher G-spread signals a larger credit risk premium.")
    fig = go.Figure([go.Scatter(x=courbe.index, y=courbe.values, mode="lines+markers", name=f"Curve {pays}"),
                     go.Scatter(x=[maturite], y=[rendement], mode="markers", name="Your bond",
                                marker={"size": 13, "symbol": "diamond"})])
    fig.add_shape(type="line", x0=maturite, x1=maturite, y0=resultat["Interpolated government yield (%)"], y1=rendement,
                  line={"dash": "dot", "color": "#FF9F1C"})
    fig.update_layout(title="Bond compared with the government curve", xaxis_title="Maturity (years)",
                      yaxis_title="Yield (%)", height=400)
    st.plotly_chart(fig, width="stretch")
