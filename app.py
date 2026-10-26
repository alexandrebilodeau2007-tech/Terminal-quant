"""
app.py — Point d'entrée du terminal.

Lancer :  streamlit run app.py

Architecture (3 couches qui ne se mélangent pas) :
    sources/    -> va chercher les données (Internet)
    calculs/    -> mathématiques pures (testées dans tests/)
    interface/  -> affichage Streamlit, une page par section
    export/     -> fichiers Excel
Ce fichier ne fait que la navigation et les paramètres globaux.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from config import AVERTISSEMENT
from interface import page_accueil, page_fondamental, page_marches, page_options, page_risque, page_taux

# Doit être le PREMIER appel Streamlit du script.
st.set_page_config(page_title="Terminal quant", layout="wide")

SECTIONS = {
    "Accueil": page_accueil,
    "1 · Marchés multi-actifs": page_marches,
    "2 · Risque & Portefeuille": page_risque,
    "3 · Analyse fondamentale": page_fondamental,
    "4 · Options": page_options,
    "5 · Taux & Obligations": page_taux,
}

# ---------------------------------------------------------------- barre latérale
with st.sidebar:
    st.title("Terminal quant")
    section = st.radio("Section", list(SECTIONS), label_visibility="collapsed")

    st.divider()
    st.subheader("Paramètres globaux")
    aujourd_hui = date.today()
    debut = st.date_input("Début", aujourd_hui - timedelta(days=5 * 365), max_value=aujourd_hui)
    fin = st.date_input("Fin", aujourd_hui, max_value=aujourd_hui)
    devise = st.selectbox("Devise de base", ["CAD", "USD"],
                          help="Devise dans laquelle les rendements de portefeuille sont mesurés.")
    if debut >= fin:
        st.error("La date de début doit précéder la date de fin.")
        st.stop()  # arrête l'exécution : aucune page ne s'affiche avec des dates invalides

    st.divider()
    st.caption(AVERTISSEMENT)

# yfinance traite la date de fin comme EXCLUE : on ajoute un jour pour inclure "fin".
params = {
    "debut": str(debut),
    "fin": str(fin + timedelta(days=1)),
    "devise": devise,
}

SECTIONS[section].afficher(params)
