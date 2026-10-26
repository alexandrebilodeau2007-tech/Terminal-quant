"""
calculs/profil_risque.py — Niveau de risque d'un FNB, d'un titre ou d'un portefeuille.

Méthode de référence : la grille OFFICIELLE de l'ACVM (Autorités canadiennes en
valeurs mobilières, Règlement 81-102, annexe F), celle que les fonds canadiens
utilisent dans leur Aperçu du fonds :
    écart-type annualisé des rendements MENSUELS sur les 10 dernières années (120 mois)
        < 6 %   Faible
        6-11 %  Faible à moyen
        11-16 % Moyen
        16-20 % Moyen à élevé
        >= 20 % Élevé

Différences avec le calcul officiel (à mentionner dans une analyse) :
    - les prix Yahoo ajustés remplacent la valeur liquidative du fonds ;
    - un historique de moins de 10 ans donne un niveau INDICATIF (l'ACVM
      exige alors de compléter avec un indice de référence).

On ajoute des mesures complémentaires : bêta, VaR, drawdown, meilleur/pire mois.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from calculs.rendements import drawdown
from config import GRILLE_RISQUE_ACVM, JOURS_BOURSE_PAR_AN

MOIS_ACVM = 120


def niveau_acvm(ecart_type_annuel: float) -> tuple[int, str]:
    """Renvoie (rang de 1 à 5, libellé) pour un écart-type annualisé en DÉCIMAL (0.14 = 14 %)."""
    en_pourcent = ecart_type_annuel * 100
    for rang, (borne, libelle) in enumerate(GRILLE_RISQUE_ACVM, start=1):
        if en_pourcent < borne:
            return rang, libelle
    return len(GRILLE_RISQUE_ACVM), GRILLE_RISQUE_ACVM[-1][1]


def rendements_mensuels(prix: pd.Series) -> pd.Series:
    """Rendements mensuels à partir du dernier prix de chaque mois.
    Le mois en cours (incomplet) est retiré pour ne pas biaiser l'écart-type."""
    fin_de_mois = prix.dropna().resample("ME").last()
    if len(fin_de_mois) and prix.dropna().index.max() < fin_de_mois.index.max():
        fin_de_mois = fin_de_mois.iloc[:-1]
    return fin_de_mois.pct_change().dropna()


def ecart_type_acvm(prix: pd.Series) -> tuple[float, int]:
    """Écart-type annualisé des 120 derniers rendements mensuels (ou moins si
    l'historique est plus court). Retour : (écart-type en décimal, nombre de mois)."""
    r = rendements_mensuels(prix).tail(MOIS_ACVM)
    if len(r) < 12:
        return np.nan, len(r)
    return float(r.std(ddof=1) * np.sqrt(12)), len(r)


def beta(r_actif: pd.Series, r_reference: pd.Series) -> float:
    """Bêta = covariance(actif, référence) / variance(référence).
    Bêta 1,2 : quand la référence bouge de 1 %, l'actif bouge en moyenne de 1,2 %."""
    a, b = r_actif.align(r_reference, join="inner")
    if len(a) < 30 or b.var() == 0:
        return np.nan
    return float(np.cov(a, b, ddof=1)[0, 1] / b.var(ddof=1))


def profil(prix: pd.Series, prix_reference: pd.Series | None = None) -> dict:
    """Profil de risque complet d'une série de prix (FNB, titre ou portefeuille)."""
    sigma, nb_mois = ecart_type_acvm(prix)
    rang, libelle = niveau_acvm(sigma) if np.isfinite(sigma) else (0, "Historique insuffisant")
    r_quot = prix.dropna().pct_change().dropna()
    r_mens = rendements_mensuels(prix).tail(MOIS_ACVM)
    resultat = {
        "Niveau ACVM": libelle,
        "Rang (1 à 5)": rang,
        "Écart-type annualisé (mensuel, ACVM)": sigma,
        "Mois utilisés": nb_mois,
        "Historique complet (120 mois)": nb_mois >= MOIS_ACVM,
        "Volatilité annualisée (quotidienne)": float(r_quot.std(ddof=1) * np.sqrt(JOURS_BOURSE_PAR_AN)),
        "VaR historique 95 % (1 jour)": -float(np.quantile(r_quot, 0.05)),
        "Drawdown maximal": float(drawdown(r_quot).min()),
        "Pire mois": float(r_mens.min()) if len(r_mens) else np.nan,
        "Meilleur mois": float(r_mens.max()) if len(r_mens) else np.nan,
        "Mois positifs": float((r_mens > 0).mean()) if len(r_mens) else np.nan,
    }
    if prix_reference is not None:
        r_ref = prix_reference.dropna().pct_change().dropna()
        resultat["Bêta vs référence"] = beta(r_quot, r_ref)
        a, b = r_quot.align(r_ref, join="inner")
        resultat["Corrélation vs référence"] = float(a.corr(b)) if len(a) > 30 else np.nan
    return resultat


def valeur_portefeuille(prix: pd.DataFrame, poids: pd.Series) -> pd.Series:
    """Valeur d'un portefeuille rééquilibré chaque jour aux poids cibles (base 100).
    Sert à appliquer la même grille de risque qu'à un FNB."""
    r = prix.pct_change().dropna()
    r_port = r[poids.index] @ poids.values
    return 100 * (1 + r_port).cumprod()
