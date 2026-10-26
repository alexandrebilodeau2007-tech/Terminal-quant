"""
interface/vue_graphiques.py — Fenêtre « graphiques seulement » (adresse ?view=charts).

Affiche uniquement la grille TradingView, sur toute la fenêtre : pas de menu,
pas de barre latérale, pas de bandeau. Pensé pour être ouvert dans un onglet
ou une fenêtre à part (par ex. sur un second écran).

Paramètres d'adresse acceptés :
    view=charts      active cette vue (obligatoire)
    cfg=<texte>      réglages encodés par le bouton de l'onglet TradingView (optionnel)
    layout=1|2|4     force le nombre de graphiques (optionnel, ex. ?view=charts&layout=4)
Sans cfg, ce sont les réglages de BASE (tradingview.toml) qui s'appliquent.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from interface import tradingview as tv

# Masque tout ce qui n'est pas la grille et étire le cadre des graphiques sur 100 % de la fenêtre.
CSS_PLEIN_ECRAN = """
<style>
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], footer { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main { padding: 0 !important; overflow: hidden !important; }
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { height: 100vh !important; width: 100% !important; display: block; border: 0; }
</style>
"""


def reglages_depuis_adresse() -> dict:
    """Réglages de la fenêtre : ceux de l'adresse s'ils sont valides, sinon la base commune."""
    parametres = st.query_params
    reglages = None
    if "cfg" in parametres:
        brut = tv.decoder(parametres["cfg"])
        reglages = tv.valider(brut) if brut else None
    if reglages is None:
        reglages = tv.charger_base()
    disposition = parametres.get("layout")
    if disposition in ("1", "2", "4"):
        reglages["display"]["layout"] = int(disposition)
    return reglages


def afficher() -> None:
    st.markdown(CSS_PLEIN_ECRAN, unsafe_allow_html=True)
    page, hauteur = tv.html_grille(reglages_depuis_adresse(), plein_ecran=True)
    # La hauteur passée ici n'est qu'une valeur de départ : le CSS ci-dessus étire le cadre à 100vh.
    components.html(page, height=max(hauteur, 600))
