"""
Section 5 — Taux & Obligations.

    - Courbe des taux US (FRED) et canadienne (Banque du Canada), aujourd'hui
      vs il y a 1 an : pente, inversion.
    - Écarts de crédit (IG, High Yield) et pentes de courbe (FRED).
    - Calculatrice obligataire : prix <-> rendement, duration, convexité,
      DV01 et scénarios de chocs de taux.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from calculs import obligations as ob
from config import COURBE_BDC, COURBE_FRED, ECARTS_FRED
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from sources.taux import cle_fred, courbe_a_une_date, serie_bdc, serie_fred


def _graphique_courbe(series: dict[float, pd.Series], titre: str) -> None:
    """Trace la courbe des taux à 3 dates : dernière, -1 an, -2 ans."""
    derniere = max(s.index.max() for s in series.values() if not s.empty)
    fig = go.Figure()
    for etiquette, date in (("Today", derniere), ("1 year ago", derniere - pd.DateOffset(years=1)),
                            ("2 years ago", derniere - pd.DateOffset(years=2))):
        courbe = courbe_a_une_date(series, date)
        fig.add_trace(go.Scatter(x=courbe.index, y=courbe.values, mode="lines+markers",
                                 name=f"{etiquette} ({date.date()})"))
    fig.update_layout(title=titre, xaxis_title="Maturity (years)", yaxis_title="Yield (%)",
                      xaxis_type="log", height=400)  # échelle log : lisibilité des maturités courtes
    st.plotly_chart(fig, width="stretch")


def afficher(params: dict) -> None:
    titre("Curves & bonds", "taux", "YCRV", "US (FRED) and Canadian (Bank of Canada) yield curves, bond calculator.")
    debut = str((pd.Timestamp(params["fin"]) - pd.DateOffset(years=3)).date())
    onglet_us, onglet_ca, onglet_calc = st.tabs([":material/flag: United States (FRED)", ":material/flag: Canada (Bank of Canada)",
                                                 ":material/calculate: Bond calculator"])

    # ------------------------------------------------------------ États-Unis
    with onglet_us:
        sous_titre("US Treasury curve", "taux_courbe")
        cle = cle_fred()
        if not cle:
            st.warning("FRED key missing. Add FRED_API_KEY to .streamlit/secrets.toml (see README).")
        else:
            try:
                with st.spinner("Downloading from FRED…"):
                    courbe_us = {m: serie_fred(code, debut, cle) for m, code in COURBE_FRED.items()}
                    ecarts = pd.DataFrame({nom: serie_fred(code, debut, cle) for nom, code in ECARTS_FRED.items()})
                _graphique_courbe(courbe_us, "US Treasury yield curve")
                dernier = ecarts.ffill().iloc[-1]
                metriques({k: v for k, v in dernier.items()}, "{:.2f} pt", par_ligne=4)
                st.plotly_chart(px.line(ecarts, labels={"value": "Percentage points", "index": "", "variable": ""},
                                        title="Curve slopes and credit spreads"), width="stretch")
            except requests.RequestException as e:
                st.error(f"FRED unreachable or invalid key: {e}")

    # ------------------------------------------------------------ Canada
    with onglet_ca:
        sous_titre("Government of Canada curve", "taux_courbe")
        try:
            with st.spinner("Downloading from the Bank of Canada…"):
                courbe_ca = {m: serie_bdc(code, debut) for m, code in COURBE_BDC.items()}
            _graphique_courbe(courbe_ca, "Government of Canada benchmark bond curve")
            pente = (courbe_ca[10] - courbe_ca[2]).dropna()
            st.plotly_chart(px.area(pente, labels={"value": "Percentage points", "index": ""},
                                    title="10y - 2y slope (Canada)").update_layout(showlegend=False),
                            width="stretch")
        except requests.RequestException as e:
            st.error(f"Bank of Canada Valet API unreachable: {e}")

    # ------------------------------------------------------------ Calculatrice
    with onglet_calc:
        sous_titre("Bond calculator", "taux_calc")
        c1, c2, c3, c4 = st.columns(4)
        nominal = c1.number_input("Face value", 1.0, value=100.0)
        coupon = c2.number_input("Annual coupon (%)", 0.0, 30.0, 4.0, 0.125) / 100
        annees = c3.number_input("Years to maturity", 0.5, 100.0, 10.0, 0.5)
        freq = c4.selectbox("Coupons per year", [2, 1, 4, 12], help="2 = semi-annual (Canada/US standard)")
        mode = st.radio("I know…", ["the yield", "the price"], horizontal=True)
        if mode == "the yield":
            ytm = st.number_input("Yield to maturity (%)", -5.0, 50.0, 4.5, 0.05) / 100
        else:
            prix_marche = st.number_input("Market price", 1.0, value=96.0)
            try:
                ytm = ob.rendement_a_echeance(prix_marche, nominal, coupon, annees, freq)
            except ValueError:
                st.error("No yield between -50% and 100% matches this price.")
                return
            st.metric("Computed yield to maturity", f"{ytm:.3%}")

        mesures = ob.mesures_de_risque(nominal, coupon, ytm, annees, freq)
        metriques(mesures, "{:.4f}", par_ligne=5)

        # Scénarios : on compare l'approximation duration+convexité au
        # prix EXACT recalculé. L'écart montre la limite de l'approximation.
        lignes = []
        for pb in (-200, -100, -50, -25, 25, 50, 100, 200):
            choc = pb / 10_000
            approx = ob.choc_de_taux(mesures, choc)
            exact = ob.prix(nominal, coupon, ytm + choc, annees, freq) / mesures["Price"] - 1
            lignes.append({"Shock (bp)": pb, "Duration only": approx["Duration effect"],
                           "Duration + convexity": approx["Estimated change (%)"], "Exact (repricing)": exact})
        st.markdown("**Parallel rate shocks — price change**")
        st.dataframe(pd.DataFrame(lignes).set_index("Shock (bp)").style.format("{:.3%}"), width="stretch")

    note_methodo(
        "- **FRED**: constant-maturity Treasury yields (DGS series). ICE BofA OAS spreads.\n"
        "- **Bank of Canada**: 2, 3, 5, 7, 10-year and long-term benchmark bonds (shown at 30 years).\n"
        "- Curve at a date = latest observation available on or before that date (no future data).\n"
        "- **Calculator**: valued on a coupon date (no accrued interest); yield compounded at the coupon frequency.\n"
        "- Individual bonds (CUSIP/ISIN): no reliable free source. For bond exposure "
        "in a portfolio, use ETFs (PORT function)."
    )
