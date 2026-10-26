"""
interface/composants.py — Petits éléments d'interface réutilisés par toutes les sections.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import UNIVERS

# Dictionnaire "Nom (TICKER)" -> "TICKER" pour la liste déroulante.
OPTIONS_UNIVERS = {
    f"{nom} ({ticker}) — {categorie}": ticker
    for categorie, actifs in UNIVERS.items()
    for nom, ticker in actifs.items()
}


def selecteur_tickers(cle: str, defaut: list[str], aide: str = "") -> list[str]:
    """Sélection d'actifs : liste prédéfinie + champ libre pour n'importe
    quel ticker Yahoo (ex. "BRK-B, ^FTSE, BTC-USD").
    'cle' doit être unique par page (exigence de Streamlit)."""
    etiquettes_defaut = [e for e, t in OPTIONS_UNIVERS.items() if t in defaut]
    choisis = st.multiselect("Actifs prédéfinis", list(OPTIONS_UNIVERS), default=etiquettes_defaut,
                             key=f"{cle}_liste", help=aide)
    libres = st.text_input("Autres tickers Yahoo (séparés par des virgules)", key=f"{cle}_libre",
                           placeholder="ex. BRK-B, ^FTSE, SU.TO")
    tickers = [OPTIONS_UNIVERS[c] for c in choisis]
    tickers += [t.strip().upper() for t in libres.split(",") if t.strip()]
    # dict.fromkeys : supprime les doublons en gardant l'ordre.
    return list(dict.fromkeys(tickers))


def tableau_pourcent(df: pd.DataFrame, decimales: int = 2, colonnes: list[str] | None = None):
    """Affiche un tableau avec certaines colonnes en % (NaN -> "N/A")."""
    colonnes = colonnes if colonnes is not None else list(df.columns)
    formats = {c: f"{{:.{decimales}%}}" for c in colonnes}
    st.dataframe(df.style.format(formats, na_rep="N/A"), width="stretch")


def metriques(valeurs: dict[str, float], format_: str = "{:.2%}", par_ligne: int = 4) -> None:
    """Affiche des indicateurs en grille de cartes."""
    elements = list(valeurs.items())
    for debut in range(0, len(elements), par_ligne):
        colonnes = st.columns(par_ligne)
        for col, (nom, val) in zip(colonnes, elements[debut:debut + par_ligne]):
            col.metric(nom, "N/A" if pd.isna(val) else format_.format(val))


def note_methodo(texte: str) -> None:
    """Encadré repliable qui explique la méthode et ses limites.
    Chaque section en a un : un terminal rigoureux montre ses hypothèses."""
    with st.expander("Méthode et limites"):
        st.markdown(texte)
