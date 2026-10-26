"""
sources/marche.py — Prix historiques multi-actifs via Yahoo Finance (yfinance).

Couvre : actions (US, TSX, international), FNB, indices, commodités
(contrats à terme continus), forex et taux.

Règles de rigueur appliquées ici :
    1. Prix AJUSTÉS (dividendes + fractionnements) -> rendements corrects.
    2. Conversion de tous les prix dans UNE devise de base (CAD ou USD),
       sinon on mélange des rendements en dollars US et canadiens.
    3. Alignement explicite des calendriers (TSX et NYSE n'ont pas les mêmes
       jours fériés) : on garde seulement les dates communes, sans inventer
       de données.

Limites connues (à mentionner dans ton analyse) :
    - yfinance n'est PAS une API officielle : elle peut casser sans préavis.
    - Les contrats à terme "=F" sont des séries continues : au changement
      d'échéance (roll), il peut y avoir un saut de prix artificiel.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
import yfinance as yf

from config import CACHE_PRIX

# Devise déduite du suffixe du ticker, utilisée si Yahoo ne répond pas.
# Ex. "RY.TO" -> se termine par ".TO" -> CAD.
DEVISE_PAR_SUFFIXE = {
    ".TO": "CAD", ".V": "CAD", ".NE": "CAD", ".CN": "CAD",
    ".L": "GBp", ".PA": "EUR", ".DE": "EUR", ".AS": "EUR",
    ".T": "JPY", ".HK": "HKD", ".SW": "CHF", ".AX": "AUD",
}


class ErreurDonnees(Exception):
    """Erreur levée quand les données sont absentes ou insuffisantes.
    On utilise une erreur dédiée pour l'afficher proprement dans l'interface
    au lieu de faire planter l'application."""


def _extraire_colonne(brut: pd.DataFrame, colonne: str, tickers: list[str]) -> pd.DataFrame:
    """yf.download renvoie des colonnes à deux niveaux (Champ, Ticker) pour
    plusieurs tickers, et parfois un seul niveau pour un seul ticker.
    Cette fonction gère les deux cas et renvoie un tableau Date x Ticker."""
    if isinstance(brut.columns, pd.MultiIndex):
        tableau = brut[colonne]
    else:
        tableau = brut[[colonne]].rename(columns={colonne: tickers[0]})
    if isinstance(tableau, pd.Series):
        tableau = tableau.to_frame(name=tickers[0])
    return tableau


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def telecharger_prix(tickers: tuple[str, ...], debut: str, fin: str) -> pd.DataFrame:
    """Télécharge les prix de clôture AJUSTÉS de plusieurs tickers.

    Paramètres
        tickers : tuple (et non liste) car le cache Streamlit exige des
                  arguments "hashables" (non modifiables).
        debut, fin : dates au format "AAAA-MM-JJ".

    Retour
        DataFrame : index = dates, colonnes = tickers, valeurs = prix en
        devise LOCALE (la conversion se fait dans convertir_en_devise_base).
    """
    liste = list(tickers)
    brut = yf.download(
        liste, start=debut, end=fin,
        auto_adjust=True,   # prix ajustés pour dividendes et fractionnements
        progress=False,     # pas de barre de progression dans la console
        threads=True,
    )
    if brut is None or brut.empty:
        raise ErreurDonnees("No data received from Yahoo Finance. Check the tickers.")

    prix = _extraire_colonne(brut, "Close", liste)
    prix.index = pd.to_datetime(prix.index).tz_localize(None)  # enlève le fuseau horaire

    # Tickers entièrement vides = ticker invalide ou délisté.
    vides = [t for t in prix.columns if prix[t].dropna().empty]
    if vides:
        raise ErreurDonnees(f"Ticker(s) without data: {', '.join(vides)}")
    return prix.sort_index()


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def telecharger_ohlc(ticker: str, debut: str, fin: str) -> pd.DataFrame:
    """Télécharge Ouverture / Haut / Bas / Clôture / Volume d'un seul actif
    (pour le graphique en chandeliers)."""
    brut = yf.download(ticker, start=debut, end=fin, auto_adjust=True, progress=False)
    if brut is None or brut.empty:
        raise ErreurDonnees(f"No data for {ticker}.")
    if isinstance(brut.columns, pd.MultiIndex):
        brut.columns = brut.columns.get_level_values(0)  # garde seulement le nom du champ
    brut.index = pd.to_datetime(brut.index).tz_localize(None)
    return brut[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def devise_du_ticker(ticker: str) -> str:
    """Trouve la devise de cotation d'un ticker.
    1) On demande à Yahoo (fast_info).  2) Sinon on déduit du suffixe.
    3) Sinon on suppose USD (marché américain)."""
    try:
        devise = yf.Ticker(ticker).fast_info.get("currency")
        if devise:
            return devise
    except Exception:
        pass  # Yahoo n'a pas répondu : on passe au plan B
    for suffixe, devise in DEVISE_PAR_SUFFIXE.items():
        if ticker.upper().endswith(suffixe):
            return devise
    return "USD"


def convertir_en_devise_base(prix: pd.DataFrame, devise_base: str, tickers_taux: set[str]) -> tuple[pd.DataFrame, dict]:
    """Convertit chaque colonne de prix dans la devise de base.

    Exemple : AAPL est en USD, devise de base = CAD.
        prix_AAPL_en_CAD = prix_AAPL_en_USD x (CAD par USD) le même jour.
    Le taux de change "USDCAD=X" de Yahoo donne justement des CAD par USD.

    Les taux d'intérêt (^TNX, etc.) sont des pourcentages, pas des prix :
    on ne les convertit jamais.

    Retour : (prix convertis, dictionnaire {ticker: devise d'origine})
    """
    resultat = prix.copy()
    devises = {}
    for ticker in prix.columns:
        if ticker in tickers_taux:
            devises[ticker] = "%"
            continue
        devise = devise_du_ticker(ticker)
        devises[ticker] = devise

        # Cas spécial : Londres cote en PENCE (GBp) -> on divise par 100.
        if devise == "GBp":
            resultat[ticker] = resultat[ticker] / 100
            devise = "GBP"

        if devise == devise_base:
            continue  # rien à convertir

        paire = f"{devise}{devise_base}=X"  # ex. "USDCAD=X" = CAD par USD
        taux = telecharger_prix((paire,), str(prix.index.min().date()), str((prix.index.max() + pd.Timedelta(days=1)).date()))[paire]
        # reindex : aligne le taux de change sur les dates des prix ;
        # ffill : si le marché des changes n'a pas de cotation ce jour-là,
        # on reprend la dernière connue (jamais une valeur future).
        taux = taux.reindex(resultat.index).ffill()
        resultat[ticker] = resultat[ticker] * taux
    return resultat, devises


def aligner_calendriers(prix: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Garde seulement les dates où TOUS les actifs ont un prix.

    Pourquoi ? La covariance exige des observations simultanées. Remplir
    les trous par zéro ou par interpolation inventerait des données.
    Retour : (prix alignés, nombre de dates supprimées) -> on affiche ce
    nombre pour que l'analyste sache ce qui a été retiré.
    """
    avant = len(prix)
    propre = prix.dropna(how="any")
    return propre, avant - len(propre)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def infos_fonds(ticker: str) -> dict:
    """Composition d'un FNB (principaux titres, secteurs, classes d'actifs) via Yahoo.

    Renvoie un dictionnaire vide si le ticker n'est pas un fonds ou si Yahoo
    ne fournit pas ces données (fréquent pour certains FNB canadiens).
    Chaque élément est lu séparément : une partie manquante n'empêche pas les autres.
    """
    resultat = {}
    try:
        fonds = yf.Ticker(ticker).funds_data
    except Exception:
        return resultat
    for cle, attribut in (("principaux_titres", "top_holdings"), ("secteurs", "sector_weightings"),
                          ("classes_actifs", "asset_classes"), ("description", "description")):
        try:
            valeur = getattr(fonds, attribut)
        except Exception:
            continue
        if valeur is None or (hasattr(valeur, "empty") and valeur.empty) or (isinstance(valeur, (dict, str)) and not valeur):
            continue
        resultat[cle] = valeur
    return resultat
