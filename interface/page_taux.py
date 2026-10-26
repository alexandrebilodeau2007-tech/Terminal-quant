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
    for etiquette, date in (("Aujourd'hui", derniere), ("Il y a 1 an", derniere - pd.DateOffset(years=1)),
                            ("Il y a 2 ans", derniere - pd.DateOffset(years=2))):
        courbe = courbe_a_une_date(series, date)
        fig.add_trace(go.Scatter(x=courbe.index, y=courbe.values, mode="lines+markers",
                                 name=f"{etiquette} ({date.date()})"))
    fig.update_layout(title=titre, xaxis_title="Maturité (années)", yaxis_title="Rendement (%)",
                      xaxis_type="log", height=400)  # échelle log : lisibilité des maturités courtes
    st.plotly_chart(fig, width="stretch")


def afficher(params: dict) -> None:
    titre("Courbes & obligations", "taux", "YCRV", "Courbes des taux US (FRED) et canadienne (Banque du Canada), calculatrice obligataire.")
    debut = str((pd.Timestamp(params["fin"]) - pd.DateOffset(years=3)).date())
    onglet_us, onglet_ca, onglet_calc = st.tabs([":material/flag: États-Unis (FRED)", ":material/flag: Canada (Banque du Canada)",
                                                 ":material/calculate: Calculatrice obligataire"])

    # ------------------------------------------------------------ États-Unis
    with onglet_us:
        sous_titre("Courbe du Trésor américain", "taux_courbe")
        cle = cle_fred()
        if not cle:
            st.warning("Clé FRED absente. Ajoute FRED_API_KEY dans .streamlit/secrets.toml (voir README).")
        else:
            try:
                with st.spinner("Téléchargement FRED…"):
                    courbe_us = {m: serie_fred(code, debut, cle) for m, code in COURBE_FRED.items()}
                    ecarts = pd.DataFrame({nom: serie_fred(code, debut, cle) for nom, code in ECARTS_FRED.items()})
                _graphique_courbe(courbe_us, "Courbe des taux du Trésor américain")
                dernier = ecarts.ffill().iloc[-1]
                metriques({k: v for k, v in dernier.items()}, "{:.2f} pt", par_ligne=4)
                st.plotly_chart(px.line(ecarts, labels={"value": "Points de %", "index": "", "variable": ""},
                                        title="Pentes de courbe et écarts de crédit"), width="stretch")
            except requests.RequestException as e:
                st.error(f"FRED injoignable ou clé invalide : {e}")

    # ------------------------------------------------------------ Canada
    with onglet_ca:
        sous_titre("Courbe du gouvernement du Canada", "taux_courbe")
        try:
            with st.spinner("Téléchargement Banque du Canada…"):
                courbe_ca = {m: serie_bdc(code, debut) for m, code in COURBE_BDC.items()}
            _graphique_courbe(courbe_ca, "Courbe des obligations de référence du gouvernement du Canada")
            pente = (courbe_ca[10] - courbe_ca[2]).dropna()
            st.plotly_chart(px.area(pente, labels={"value": "Points de %", "index": ""},
                                    title="Pente 10 ans - 2 ans (Canada)").update_layout(showlegend=False),
                            width="stretch")
        except requests.RequestException as e:
            st.error(f"API Valet de la Banque du Canada injoignable : {e}")

    # ------------------------------------------------------------ Calculatrice
    with onglet_calc:
        sous_titre("Calculatrice obligataire", "taux_calc")
        c1, c2, c3, c4 = st.columns(4)
        nominal = c1.number_input("Nominal", 1.0, value=100.0)
        coupon = c2.number_input("Coupon annuel (%)", 0.0, 30.0, 4.0, 0.125) / 100
        annees = c3.number_input("Années à l'échéance", 0.5, 100.0, 10.0, 0.5)
        freq = c4.selectbox("Coupons par an", [2, 1, 4, 12], help="2 = semestriel (norme Canada/É.-U.)")
        mode = st.radio("Je connais…", ["le rendement", "le prix"], horizontal=True)
        if mode == "le rendement":
            ytm = st.number_input("Rendement à l'échéance (%)", -5.0, 50.0, 4.5, 0.05) / 100
        else:
            prix_marche = st.number_input("Prix du marché", 1.0, value=96.0)
            try:
                ytm = ob.rendement_a_echeance(prix_marche, nominal, coupon, annees, freq)
            except ValueError:
                st.error("Aucun rendement entre -50 % et 100 % ne correspond à ce prix.")
                return
            st.metric("Rendement à l'échéance calculé", f"{ytm:.3%}")

        mesures = ob.mesures_de_risque(nominal, coupon, ytm, annees, freq)
        metriques(mesures, "{:.4f}", par_ligne=5)

        # Scénarios : on compare l'approximation duration+convexité au
        # prix EXACT recalculé. L'écart montre la limite de l'approximation.
        lignes = []
        for pb in (-200, -100, -50, -25, 25, 50, 100, 200):
            choc = pb / 10_000
            approx = ob.choc_de_taux(mesures, choc)
            exact = ob.prix(nominal, coupon, ytm + choc, annees, freq) / mesures["Prix"] - 1
            lignes.append({"Choc (pb)": pb, "Duration seule": approx["Effet duration"],
                           "Duration + convexité": approx["Variation estimée (%)"], "Exact (réévaluation)": exact})
        st.markdown("**Chocs de taux parallèles — variation du prix**")
        st.dataframe(pd.DataFrame(lignes).set_index("Choc (pb)").style.format("{:.3%}"), width="stretch")

    note_methodo(
        "- **FRED** : rendements du Trésor à maturité constante (séries DGS). Écarts OAS ICE BofA.\n"
        "- **Banque du Canada** : obligations de référence 2, 3, 5, 7, 10 ans et long terme (affiché à 30 ans).\n"
        "- Courbe à une date = dernière observation disponible à cette date ou avant (aucune donnée future).\n"
        "- **Calculatrice** : évaluation à une date de coupon (pas d'intérêts courus) ; rendement composé selon la fréquence des coupons.\n"
        "- Obligations individuelles (CUSIP/ISIN) : pas de source gratuite fiable. Pour l'exposition obligataire "
        "dans un portefeuille, utiliser des FNB (section 2)."
    )
