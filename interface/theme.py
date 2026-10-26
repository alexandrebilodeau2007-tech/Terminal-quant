"""
interface/theme.py — Apparence « mini-Bloomberg » : CSS et gabarit des graphiques.

Les couleurs de base (fond, accent ambre) sont dans .streamlit/config.toml ;
ce fichier ajoute les polices, le bandeau de cotations et un gabarit Plotly
assorti pour que tous les graphiques aient la même allure.
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

AMBRE = "#FF9F1C"
VERT = "#2ECC71"
ROUGE = "#FF5C5C"
GRILLE = "#1F2A37"
TEXTE_DOUX = "#8B98A9"

# Palette des séries : ambre d'abord, puis des couleurs distinctes et lisibles sur fond sombre.
PALETTE = [AMBRE, "#4EA8DE", "#E5E5E5", "#2ECC71", "#C77DFF", "#FF5C5C", "#F7D154", "#56CFE1"]

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label {{ font-family: 'IBM Plex Sans', sans-serif; }}
/* Chiffres et tableaux en police à chasse fixe, comme sur un terminal */
[data-testid="stMetricValue"], [data-testid="stDataFrame"], code, .tq-mono {{ font-family: 'IBM Plex Mono', monospace !important; }}
[data-testid="stMetricValue"] {{ color: {AMBRE}; }}
.block-container, [data-testid="stMainBlockContainer"] {{ padding-top: 4.6rem !important; }}
/* Titres de section : code de fonction ambre + titre en capitales */
.tq-titre {{ font-family: 'IBM Plex Mono', monospace; font-weight: 600; letter-spacing: .02em;
             text-transform: uppercase; font-size: 1.35rem; margin: 0; padding: 0; }}
.tq-code {{ background: {AMBRE}; color: #0A0E14; padding: 2px 8px; border-radius: 3px; margin-right: 8px; }}
.tq-sous-titre {{ font-family: 'IBM Plex Mono', monospace; color: {AMBRE}; text-transform: uppercase;
                  font-size: .95rem; letter-spacing: .04em; margin: .6rem 0 0 0; }}
/* Bandeau de cotations */
.tq-bandeau {{ display: flex; gap: 0; overflow-x: auto; white-space: nowrap; border-top: 1px solid {GRILLE};
               border-bottom: 1px solid {GRILLE}; margin-bottom: .8rem; font-family: 'IBM Plex Mono', monospace; }}
.tq-cote {{ display: inline-block; padding: 6px 14px; border-right: 1px solid {GRILLE}; font-size: .82rem; }}
.tq-cote b {{ color: #E8E6E3; font-weight: 600; margin-right: 6px; }}
.tq-hausse {{ color: {VERT}; }} .tq-baisse {{ color: {ROUGE}; }} .tq-neutre {{ color: {TEXTE_DOUX}; }}
/* Tuiles de l'accueil */
.tq-tuile {{ border: 1px solid {GRILLE}; border-left: 3px solid {AMBRE}; padding: 10px 14px; border-radius: 4px;
             background: #0F151E; height: 100%; }}
.tq-tuile .tq-code {{ font-family: 'IBM Plex Mono', monospace; font-size: .8rem; }}
.tq-tuile p {{ color: {TEXTE_DOUX}; font-size: .86rem; margin: .4rem 0 0 0; }}
/* Bouton d'aide « ? » rond et discret */
[data-testid="stPopover"] button {{ border-radius: 50%; min-height: 2rem; width: 2rem; padding: 0;
                                     border: 1px solid {AMBRE}; color: {AMBRE}; }}
</style>
"""


def appliquer_theme() -> None:
    """À appeler une fois par exécution, au début de app.py."""
    st.markdown(CSS, unsafe_allow_html=True)

    # Gabarit Plotly : fond transparent (prend le fond de l'app), grille discrète, palette ambre.
    gabarit = go.layout.Template(pio.templates["plotly_dark"])
    gabarit.layout.update(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "IBM Plex Sans, sans-serif", "color": "#E8E6E3", "size": 12},
        colorway=PALETTE,
        xaxis={"gridcolor": GRILLE, "zerolinecolor": GRILLE},
        yaxis={"gridcolor": GRILLE, "zerolinecolor": GRILLE},
        legend={"bgcolor": "rgba(0,0,0,0)"},
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
    )
    pio.templates["terminal"] = gabarit
    pio.templates.default = "terminal"
