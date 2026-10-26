"""
HOME — Page de lancement : marchés du jour, accès aux fonctions, état des sources.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from config import (MAX_ACTIFS_PORTEFEUILLE, MIN_ACTIFS_PORTEFEUILLE, MIN_OBSERVATIONS,
                    POIDS_MAX_DEFAUT, SOURCES_AUTORISEES)
from interface.aide import sous_titre, titre
from interface.bandeau import instantane
from interface.navigation import FONCTIONS
from sources.taux import cle_fred


def afficher(params: dict) -> None:
    titre("Terminal d'analyse quantitative", "accueil", "HOME",
          "Le terminal calcule. Toi, tu analyses et tu conclus.")

    # ------------------------------------------------ marchés du jour
    sous_titre("Marchés du jour", "accueil")
    try:
        cotes = instantane()
    except Exception:
        cotes = pd.DataFrame()
    if cotes.empty:
        st.info("Cotations momentanément indisponibles (Yahoo Finance). Le reste du terminal fonctionne.")
    else:
        # Grille HTML qui s'adapte à la largeur de l'écran (ordinateur, tablette, téléphone).
        cases = []
        for _, l in cotes.iterrows():
            classe = "tq-hausse" if l["Variation"] > 0 else "tq-baisse" if l["Variation"] < 0 else "tq-neutre"
            cases.append(f"<div class='tq-carte'><div class='tq-carte-nom'>{l['Marché']}</div>"
                         f"<div class='tq-carte-val'>{l['Dernier']:,.{int(l['Décimales'])}f}</div>"
                         f"<div class='{classe}'>{l['Variation']:+.2%}</div></div>")
        st.markdown(f"<div class='tq-grille'>{''.join(cases)}</div>", unsafe_allow_html=True)
        st.caption(f"Dernière séance disponible : {cotes['Date'].max().date()} · données différées (Yahoo Finance).")

    # ------------------------------------------------ fonctions
    sous_titre("Fonctions", "commande")
    st.caption("Clique sur une tuile, ou tape son code dans la barre de commande à gauche (ex. `FA AAPL`).")
    tuiles = "".join(
        f"<a class='tq-tuile' href='./{f.code.lower()}' target='_self'><span class='tq-code'>{f.code}</span>"
        f"<b>{f.titre}</b><p>{f.description}</p></a>"
        for f in FONCTIONS if f.code != "HOME")
    st.markdown(f"<div class='tq-grille tq-grille-large'>{tuiles}</div>", unsafe_allow_html=True)

    # ------------------------------------------------ par où commencer
    with st.expander("Par où commencer ?", icon=":material/school:", expanded=False):
        st.markdown(
            "1. **MKT** : regarde ce qui bouge sur les grands marchés.\n"
            "2. **YCRV** et **SPRD** : lis la courbe des taux et les spreads pour comprendre le contexte économique.\n"
            "3. **FA** : analyse une entreprise (ratios, DCF) et écris ta thèse dans le carnet.\n"
            "4. **OPT** : regarde ce que le marché des options anticipe pour cette entreprise.\n"
            "5. **PORT** : mesure l'effet de cette entreprise sur le risque d'un portefeuille.\n\n"
            "Chaque section a un bouton **?** qui explique la fonction avec un exemple."
        )

    # ------------------------------------------------ sources et balises
    with st.expander("État des sources de données", icon=":material/database:"):
        try:
            ua = st.secrets.get("SEC_USER_AGENT")
        except Exception:
            ua = None
        etat = {
            "Yahoo Finance (yfinance)": "Actif — aucune clé requise",
            "FRED (Fed de St. Louis)": "Actif" if cle_fred() else "Inactif — FRED_API_KEY manquante (taux US)",
            "SEC EDGAR": "Actif" if ua else "Inactif — SEC_USER_AGENT manquant (repli Yahoo en FA)",
            "Banque du Canada (Valet)": "Actif — aucune clé requise",
            "TradingView (widget)": "Affichage seulement — aucune donnée n'est extraite",
        }
        usages = {**SOURCES_AUTORISEES, "TradingView (widget)": "Graphique interactif intégré (section CMP)."}
        st.dataframe(pd.DataFrame({"Usage": usages, "État": etat}), width="stretch")

    with st.expander("Balises : ce que le terminal refuse de faire", icon=":material/shield:"):
        st.markdown(
            f"- Portefeuille : {MIN_ACTIFS_PORTEFEUILLE} à {MAX_ACTIFS_PORTEFEUILLE} actifs, "
            f"{MIN_OBSERVATIONS} observations communes minimum, poids max par défaut {POIDS_MAX_DEFAUT:.0%}, "
            "pas de vente à découvert.\n"
            "- Les taux (^TNX…) et indicateurs (^VIX) sont refusés comme actifs de portefeuille.\n"
            "- Aucune recommandation, aucune exécution d'ordre, aucune connexion à un courtier.\n"
            "- DCF : la valeur n'apparaît qu'après confirmation que les hypothèses sont celles de l'analyste.\n"
            "- Sources limitées à la liste ci-dessus. Aucun scraping de site.\n"
            "- Chaque export Excel inclut ses métadonnées (date, sources, paramètres)."
        )
