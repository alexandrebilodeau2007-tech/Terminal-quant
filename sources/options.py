"""
sources/options.py — Chaînes d'options via Yahoo Finance.

Limites à connaître (et à écrire dans ton analyse) :
    - Données DIFFÉRÉES (~15 min) et sans historique : seulement la chaîne
      du moment.
    - Surtout des options sur actions/FNB américains. Pas d'options sur
      contrats à terme de commodités, très peu sur le TSX.
    - Les options sur actions US sont de type AMÉRICAIN (exerçables avant
      l'échéance). Black-Scholes suppose une option EUROPÉENNE : c'est une
      approximation, raisonnable pour les calls sans dividende important.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from config import CACHE_OPTIONS


@st.cache_data(ttl=CACHE_OPTIONS, show_spinner=False)
def echeances(ticker: str) -> list[str]:
    """Liste des dates d'échéance disponibles (format AAAA-MM-JJ)."""
    return list(yf.Ticker(ticker).options)


@st.cache_data(ttl=CACHE_OPTIONS, show_spinner=False)
def chaine(ticker: str, echeance: str) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Renvoie (calls, puts, prix du sous-jacent).

    Ajoute une colonne "prix_milieu" = (bid + ask) / 2.
    Pourquoi le milieu ? Le "dernier prix" (lastPrice) peut dater de
    plusieurs heures ; le milieu de la fourchette reflète mieux la valeur
    actuelle. Si bid ou ask vaut 0 (option illiquide), on met NaN plutôt
    que d'inventer un prix.
    """
    t = yf.Ticker(ticker)
    oc = t.option_chain(echeance)
    spot = float(t.fast_info["last_price"])

    def preparer(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        valide = (df["bid"] > 0) & (df["ask"] > 0) & (df["ask"] >= df["bid"])
        df["prix_milieu"] = np.where(valide, (df["bid"] + df["ask"]) / 2, np.nan)
        # Écart relatif de la fourchette : indicateur de liquidité.
        df["ecart_fourchette_%"] = np.where(valide, (df["ask"] - df["bid"]) / df["prix_milieu"] * 100, np.nan)
        return df

    return preparer(oc.calls), preparer(oc.puts), spot
