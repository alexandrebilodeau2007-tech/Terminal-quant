"""
app.py — Point d'entrée du terminal.

Lancer :  streamlit run app.py

Architecture (couches qui ne se mélangent pas) :
    sources/    -> va chercher les données (Internet)
    calculs/    -> mathématiques pures (testées dans tests/)
    interface/  -> affichage Streamlit, une page par fonction
    export/     -> fichiers Excel
Ce fichier ne gère que : le thème, le bandeau, la barre latérale
(commande + paramètres globaux) et la navigation entre les fonctions.
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta

import streamlit as st

from config import AVERTISSEMENT
from interface.aide import aide
from interface.bandeau import afficher_bandeau
from interface.navigation import FONCTIONS, PAR_CODE, executer_commande
from interface.theme import appliquer_theme

# Doit être le PREMIER appel Streamlit du script.
st.set_page_config(page_title="Terminal quant", page_icon=":material/monitoring:", layout="wide")
appliquer_theme()

# ---------------------------------------------------------------- barre latérale
with st.sidebar:
    st.markdown("<div class='tq-titre' style='font-size:1.1rem'><span class='tq-code'>TQ</span>TERMINAL QUANT</div>",
                unsafe_allow_html=True)
    gauche, droite = st.columns([6, 1], vertical_alignment="bottom")
    gauche.text_input("Commande", key="commande", on_change=executer_commande,
                      placeholder="ex. FA AAPL · OPT SPY · CMP GC=F SI=F")
    with droite:
        aide("commande")
    if "_cmd_erreur" in st.session_state:
        st.error(st.session_state.pop("_cmd_erreur"))

    with st.expander("Paramètres globaux", expanded=False, icon=":material/tune:"):
        aujourd_hui = date.today()
        debut = st.date_input("Début", aujourd_hui - timedelta(days=5 * 365), max_value=aujourd_hui)
        fin = st.date_input("Fin", aujourd_hui, max_value=aujourd_hui)
        devise = st.selectbox("Devise de base", ["CAD", "USD"],
                              help="Devise dans laquelle les rendements de portefeuille sont mesurés.")
    if debut >= fin:
        st.error("La date de début doit précéder la date de fin.")
        st.stop()  # aucune page ne s'affiche avec des dates invalides
    st.caption(f"Période : {debut} → {fin} · Devise : {devise}")

# yfinance traite la date de fin comme EXCLUE : on ajoute un jour pour inclure "fin".
st.session_state["params"] = {"debut": str(debut), "fin": str(fin + timedelta(days=1)), "devise": devise}


# ---------------------------------------------------------------- navigation
def _page(fonction):
    """Crée la fonction d'affichage d'une page (importée seulement quand on l'ouvre)."""
    def afficher():
        afficher_bandeau()
        importlib.import_module(f"interface.{fonction.module}").afficher(st.session_state["params"])
    afficher.__name__ = f"page_{fonction.code.lower()}"  # nom unique exigé par st.Page
    return afficher


PAGES = {f.code: st.Page(_page(f), title=f"{f.titre}  ·  {f.code}", icon=f.icone,
                         url_path=f.code.lower(), default=(f.code == "HOME")) for f in FONCTIONS}
groupes: dict[str, list] = {}
for f in FONCTIONS:
    groupes.setdefault(f.groupe, []).append(PAGES[f.code])
navigation = st.navigation(groupes, position="top")  # menu horizontal, groupes en listes déroulantes

# Une commande a été tapée : on change de page (avant d'afficher la page courante).
cible = st.session_state.pop("_aller_a", None)
if cible in PAR_CODE:
    st.switch_page(PAGES[cible])

with st.sidebar:
    st.divider()
    st.caption(AVERTISSEMENT)

navigation.run()
