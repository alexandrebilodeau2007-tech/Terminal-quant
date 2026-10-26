"""
interface/composants.py — Petits éléments d'interface réutilisés par toutes les pages.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import UNIVERS
from interface.navigation import valeur_initiale

# Dictionnaire "Nom (TICKER) — famille" -> "TICKER" pour les listes déroulantes.
OPTIONS_UNIVERS = {
    f"{nom} ({ticker}) — {famille}": ticker
    for famille, actifs in UNIVERS.items()
    for nom, ticker in actifs.items()
}


def selecteur_tickers(cle: str, defaut: list[str], aide: str = "", cle_commande: str | None = None) -> list[str]:
    """Sélection d'actifs : liste du répertoire + champ libre pour n'importe
    quel ticker Yahoo (ex. "BRK-B, ^FTSE, BTC-USD").
    'cle' doit être unique par page (exigence de Streamlit).
    Si une commande a fourni des tickers (cle_commande), ils remplacent la sélection."""
    commande = st.session_state.pop(cle_commande, None) if cle_commande else None
    if commande:
        st.session_state[f"{cle}_liste"] = []
        st.session_state[f"{cle}_libre"] = commande
    valeur_initiale(f"{cle}_liste", [e for e, t in OPTIONS_UNIVERS.items() if t in defaut])
    valeur_initiale(f"{cle}_libre", "")
    choisis = st.multiselect("Actifs du répertoire (tape pour chercher)", list(OPTIONS_UNIVERS),
                             key=f"{cle}_liste", help=aide)
    libres = st.text_input("Autres tickers Yahoo (séparés par des virgules)", key=f"{cle}_libre",
                           placeholder="ex. BRK-B, ^FTSE, SU.TO")
    tickers = [OPTIONS_UNIVERS[c] for c in choisis]
    tickers += [t.strip().upper() for t in libres.split(",") if t.strip()]
    # dict.fromkeys : supprime les doublons en gardant l'ordre.
    return list(dict.fromkeys(tickers))


def tableau_pourcent(df: pd.DataFrame, decimales: int = 2, colonnes: list[str] | None = None, signe: bool = False):
    """Affiche un tableau avec certaines colonnes en % (NaN -> "N/A").
    signe=True : positifs en vert, négatifs en rouge (pour des rendements ;
    pas pour une volatilité ou un poids, toujours positifs)."""
    colonnes = colonnes if colonnes is not None else list(df.columns)
    formats = {c: f"{{:.{decimales}%}}" for c in colonnes}

    def couleur(v):
        if not isinstance(v, (int, float)) or pd.isna(v):
            return ""
        return "color: #2ECC71" if v > 0 else "color: #FF5C5C" if v < 0 else ""

    style = df.style.format(formats, na_rep="N/A")
    if signe:
        style = style.map(couleur, subset=colonnes)
    st.dataframe(style, width="stretch")


def metriques(valeurs: dict[str, float], format_: str = "{:.2%}", par_ligne: int = 4) -> None:
    """Affiche des indicateurs en grille de cartes."""
    elements = list(valeurs.items())
    for debut in range(0, len(elements), par_ligne):
        colonnes = st.columns(par_ligne)
        for col, (nom, val) in zip(colonnes, elements[debut:debut + par_ligne]):
            col.metric(nom, "N/A" if pd.isna(val) else format_.format(val), border=True)


def note_methodo(texte: str) -> None:
    """Encadré repliable qui explique la méthode et ses limites.
    Chaque page en a un : un terminal rigoureux montre ses hypothèses."""
    with st.expander("Méthode et limites", icon=":material/science:"):
        st.markdown(texte)
