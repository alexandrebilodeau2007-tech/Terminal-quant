"""
sources/taux.py — Taux d'intérêt officiels : FRED (États-Unis) et Banque du Canada.

Deux sources OFFICIELLES et gratuites :
    - FRED : nécessite une clé API gratuite (voir README). La clé est lue
      dans .streamlit/secrets.toml, JAMAIS écrite dans le code.
    - Banque du Canada (API "Valet") : aucune clé requise.

Les taux sont renvoyés en POURCENTAGE (ex. 4.25 = 4,25 %).
"""

from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from config import CACHE_PRIX

URL_FRED = "https://api.stlouisfed.org/fred/series/observations"
URL_BDC = "https://www.bankofcanada.ca/valet/observations/{series}/json"
DELAI_REQUETE = 20  # secondes avant d'abandonner une requête (évite que l'app gèle)


def cle_fred() -> str | None:
    """Lit la clé FRED dans les secrets Streamlit. Renvoie None si absente,
    pour que l'interface affiche un message clair au lieu de planter."""
    try:
        return st.secrets.get("FRED_API_KEY") or None
    except Exception:  # aucun fichier secrets.toml
        return None


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def serie_fred(code: str, debut: str, cle: str) -> pd.Series:
    """Télécharge une série FRED (ex. "DGS10" = taux 10 ans US).

    FRED marque les jours sans donnée par "." -> on les transforme en NaN
    (valeur manquante) puis on les supprime.
    """
    parametres = {
        "series_id": code, "api_key": cle, "file_type": "json",
        "observation_start": debut,
    }
    reponse = requests.get(URL_FRED, params=parametres, timeout=DELAI_REQUETE)
    reponse.raise_for_status()  # lève une erreur si HTTP 400/500 (ex. mauvaise clé)
    observations = reponse.json().get("observations", [])
    serie = pd.Series(
        {pd.Timestamp(o["date"]): pd.to_numeric(o["value"], errors="coerce") for o in observations},
        name=code, dtype="float64",
    )
    return serie.dropna().sort_index()


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def serie_bdc(code: str, debut: str) -> pd.Series:
    """Télécharge une série de la Banque du Canada (ex. "BD.CDN.10YR.DQ.YLD").

    Format de réponse de l'API Valet :
        {"observations": [{"d": "2026-06-12", "BD.CDN.10YR.DQ.YLD": {"v": "3.40"}}, ...]}
    """
    reponse = requests.get(URL_BDC.format(series=code), params={"start_date": debut}, timeout=DELAI_REQUETE)
    reponse.raise_for_status()
    donnees = {}
    for obs in reponse.json().get("observations", []):
        valeur = obs.get(code, {}).get("v")
        if valeur not in (None, ""):
            donnees[pd.Timestamp(obs["d"])] = float(valeur)
    return pd.Series(donnees, name=code, dtype="float64").sort_index()


def courbe_a_une_date(series: dict[float, pd.Series], date: pd.Timestamp) -> pd.Series:
    """Construit la courbe des taux (maturité -> taux) à une date donnée.

    Pour chaque maturité, on prend la DERNIÈRE observation disponible à
    cette date ou avant (jamais après : pas de biais d'anticipation).
    """
    points = {}
    for maturite, serie in series.items():
        historique = serie.loc[:date]
        if not historique.empty:
            points[maturite] = historique.iloc[-1]
    return pd.Series(points).sort_index()
