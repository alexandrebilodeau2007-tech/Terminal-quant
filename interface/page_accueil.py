"""
HOME — Page de lancement : marchés du jour, accès aux fonctions, état des sources.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (MAX_ACTIFS_PORTEFEUILLE, MIN_ACTIFS_PORTEFEUILLE, MIN_OBSERVATIONS,
                    POIDS_MAX_DEFAUT, SOURCES_AUTORISEES)
from interface.aide import sous_titre, titre
from interface.bandeau import instantane
from interface.navigation import FONCTIONS
from sources.taux import cle_fred


def afficher(params: dict) -> None:
    titre("Quantitative analysis terminal", "accueil", "HOME",
          "The terminal computes. You analyze and conclude.")

    # ------------------------------------------------ marchés du jour
    sous_titre("Today's markets", "accueil")
    try:
        cotes = instantane()
    except Exception:
        cotes = pd.DataFrame()
    if cotes.empty:
        st.info("Quotes temporarily unavailable (Yahoo Finance). The rest of the terminal works.")
    else:
        # Grille HTML qui s'adapte à la largeur de l'écran (ordinateur, tablette, téléphone).
        cases = []
        for _, l in cotes.iterrows():
            classe = "tq-hausse" if l["Change"] > 0 else "tq-baisse" if l["Change"] < 0 else "tq-neutre"
            cases.append(f"<div class='tq-carte'><div class='tq-carte-nom'>{l['Market']}</div>"
                         f"<div class='tq-carte-val'>{l['Last']:,.{int(l['Decimals'])}f}</div>"
                         f"<div class='{classe}'>{l['Change']:+.2%}</div></div>")
        st.markdown(f"<div class='tq-grille'>{''.join(cases)}</div>", unsafe_allow_html=True)
        st.caption(f"Latest available session: {cotes['Date'].max().date()} · delayed data (Yahoo Finance).")

    # ------------------------------------------------ fonctions
    sous_titre("Functions", "commande")
    st.caption("Click a tile, or type its code in the command bar on the left (e.g. `FA AAPL`).")
    tuiles = "".join(
        f"<a class='tq-tuile' href='./{f.code.lower()}' target='_self'><span class='tq-code'>{f.code}</span>"
        f"<b>{f.titre}</b><p>{f.description}</p></a>"
        for f in FONCTIONS if f.code != "HOME")
    st.markdown(f"<div class='tq-grille tq-grille-large'>{tuiles}</div>", unsafe_allow_html=True)

    # ------------------------------------------------ par où commencer
    with st.expander("Where to start?", icon=":material/school:", expanded=False):
        st.markdown(
            "1. **MKT**: see what is moving across major markets.\n"
            "2. **YCRV** and **SPRD**: read the yield curve and spreads to understand the economic backdrop.\n"
            "3. **FA**: analyze a company (ratios, DCF) and write your thesis in the notebook.\n"
            "4. **OPT**: see what the options market expects for that company.\n"
            "5. **PORT**: measure that company's effect on a portfolio's risk.\n\n"
            "Every section has a **?** button that explains the function with an example."
        )

    # ------------------------------------------------ sources et balises
    with st.expander("Data source status", icon=":material/database:"):
        try:
            ua = st.secrets.get("SEC_USER_AGENT")
        except Exception:
            ua = None
        etat = {
            "Yahoo Finance (yfinance)": "Active — no key required",
            "FRED (St. Louis Fed)": "Active" if cle_fred() else "Inactive — FRED_API_KEY missing (US rates)",
            "SEC EDGAR": "Active" if ua else "Inactive — SEC_USER_AGENT missing (Yahoo fallback in FA)",
            "Bank of Canada (Valet)": "Active — no key required",
            "TradingView (widget)": "Display only — no data is extracted",
        }
        usages = {**SOURCES_AUTORISEES, "TradingView (widget)": "Embedded interactive chart (CMP function)."}
        st.dataframe(pd.DataFrame({"Use": usages, "Status": etat}), width="stretch")

    with st.expander("Guardrails: what the terminal refuses to do", icon=":material/shield:"):
        st.markdown(
            f"- Portfolio: {MIN_ACTIFS_PORTEFEUILLE} to {MAX_ACTIFS_PORTEFEUILLE} assets, "
            f"{MIN_OBSERVATIONS} common observations minimum, default max weight {POIDS_MAX_DEFAUT:.0%}, "
            "no short selling.\n"
            "- Rates (^TNX…) and indicators (^VIX) are rejected as portfolio assets.\n"
            "- No recommendations, no order execution, no broker connection.\n"
            "- DCF: the value only appears after the analyst confirms the assumptions are their own.\n"
            "- Sources limited to the list above. No website scraping.\n"
            "- Every Excel export includes its metadata (date, sources, parameters)."
        )
