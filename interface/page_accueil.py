"""
Page d'accueil — plan du terminal, état des sources et balises actives.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (MAX_ACTIFS_PORTEFEUILLE, MIN_ACTIFS_PORTEFEUILLE, MIN_OBSERVATIONS,
                    POIDS_MAX_DEFAUT, SOURCES_AUTORISEES)
from sources.taux import cle_fred


def afficher(params: dict) -> None:
    st.title("Terminal d'analyse quantitative")
    st.markdown(
        "| Section | Rôle |\n|---|---|\n"
        "| **1 · Marchés multi-actifs** | Performance, volatilité et corrélations : actions, indices, commodités, forex, obligations, taux |\n"
        "| **2 · Risque & Portefeuille** | VaR / CVaR (4 méthodes), backtest de Kupiec, optimisation de Markowitz |\n"
        "| **3 · Analyse fondamentale** | États financiers, ratios, DCF avec **tes** hypothèses, carnet de thèse, export Excel |\n"
        "| **4 · Options** | Chaîne, smile de volatilité, grecques, calculatrice Black-Scholes |\n"
        "| **5 · Taux & Obligations** | Courbes US et Canada, écarts de crédit, calculatrice obligataire |"
    )

    st.subheader("État des sources")
    try:
        ua = st.secrets.get("SEC_USER_AGENT")
    except Exception:
        ua = None
    etat = {
        "Yahoo Finance (yfinance)": "Actif — aucune clé requise",
        "FRED (Fed de St. Louis)": "Actif" if cle_fred() else "Inactif — FRED_API_KEY manquante (section 5 US)",
        "SEC EDGAR": "Actif" if ua else "Inactif — SEC_USER_AGENT manquant (repli Yahoo en section 3)",
        "Banque du Canada (Valet)": "Actif — aucune clé requise",
    }
    st.dataframe(pd.DataFrame({"Usage": SOURCES_AUTORISEES, "État": etat}), width="stretch")

    st.subheader("Balises actives")
    st.markdown(
        f"- Portefeuille : {MIN_ACTIFS_PORTEFEUILLE} à {MAX_ACTIFS_PORTEFEUILLE} actifs, "
        f"{MIN_OBSERVATIONS} observations communes minimum, poids max par défaut {POIDS_MAX_DEFAUT:.0%}, "
        "pas de vente à découvert.\n"
        "- Les taux (^TNX…) sont refusés comme actifs de portefeuille.\n"
        "- Aucune recommandation, aucune exécution d'ordre, aucune connexion à un courtier.\n"
        "- DCF : la valeur n'apparaît qu'après confirmation que les hypothèses sont celles de l'analyste.\n"
        "- Seules les 4 sources ci-dessus sont appelées. Aucun scraping de site.\n"
        "- Chaque export Excel inclut ses métadonnées (date, sources, paramètres)."
    )
