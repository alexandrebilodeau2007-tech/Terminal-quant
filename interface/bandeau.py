"""
interface/bandeau.py — Bandeau de cotations en haut de chaque page.

Affiche le dernier cours et la variation du jour des grands marchés.
Données Yahoo différées, mises en cache 10 minutes. Si Yahoo ne répond pas,
le bandeau disparaît simplement : il ne doit jamais bloquer le terminal.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from sources.marche import ErreurDonnees, telecharger_prix

# (libellé court, ticker Yahoo, nombre de décimales)
COTES = [
    ("S&P 500", "^GSPC", 0), ("NASDAQ", "^IXIC", 0), ("TSX", "^GSPTSE", 0), ("VIX", "^VIX", 2),
    ("US 10A", "^TNX", 2), ("USD/CAD", "USDCAD=X", 4), ("OR", "GC=F", 0), ("WTI", "CL=F", 2),
    ("BTC", "BTC-USD", 0), ("EUR/USD", "EURUSD=X", 4),
]


@st.cache_data(ttl=600, show_spinner=False)
def instantane() -> pd.DataFrame:
    """Dernier cours et variation du jour (en %) de chaque cote du bandeau."""
    fin = pd.Timestamp.today().normalize() + pd.Timedelta(days=1)
    prix = telecharger_prix(tuple(t for _, t, _ in COTES), str((fin - pd.Timedelta(days=12)).date()), str(fin.date()))
    lignes = []
    for libelle, ticker, dec in COTES:
        serie = prix[ticker].dropna() if ticker in prix else pd.Series(dtype=float)
        if len(serie) < 2:
            continue
        lignes.append({"Marché": libelle, "Ticker": ticker, "Dernier": serie.iloc[-1],
                       "Variation": serie.iloc[-1] / serie.iloc[-2] - 1, "Décimales": dec,
                       "Date": serie.index[-1]})
    return pd.DataFrame(lignes)


def afficher_bandeau() -> pd.DataFrame | None:
    """Dessine le bandeau ; renvoie les données (réutilisées par l'accueil) ou None."""
    try:
        donnees = instantane()
    except (ErreurDonnees, Exception):  # réseau, Yahoo indisponible : on n'affiche rien
        return None
    if donnees.empty:
        return None
    cellules = []
    for _, l in donnees.iterrows():
        classe = "tq-hausse" if l["Variation"] > 0 else "tq-baisse" if l["Variation"] < 0 else "tq-neutre"
        fleche = "▲" if l["Variation"] > 0 else "▼" if l["Variation"] < 0 else "■"
        cellules.append(f"<span class='tq-cote'><b>{l['Marché']}</b>{l['Dernier']:,.{int(l['Décimales'])}f} "
                        f"<span class='{classe}'>{fleche} {l['Variation']:+.2%}</span></span>")
    st.markdown(f"<div class='tq-bandeau'>{''.join(cellules)}</div>", unsafe_allow_html=True)
    return donnees
