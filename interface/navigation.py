"""
interface/navigation.py — Liste des fonctions du terminal et barre de commande.

Chaque fonction a un CODE court, comme sur un terminal Bloomberg (FA, OPT, YCRV…).
La barre de commande de la barre latérale accepte ce code suivi d'arguments :
    FA AAPL          analyse fondamentale d'Apple
    OPT SPY          options de SPY
    CMP GC=F SI=F    comparer l'or et l'argent
    MKT AAPL MSFT    marchés avec ces tickers
    TKR or           répertoire filtré sur « or »
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Fonction:
    code: str          # code de commande (ex. "FA")
    titre: str         # titre affiché dans le menu
    groupe: str        # groupe du menu
    icone: str         # icône Material (Streamlit)
    module: str        # nom du module dans interface/
    description: str   # une ligne pour l'accueil


FONCTIONS: list[Fonction] = [
    Fonction("HOME", "Accueil", "Terminal", ":material/dashboard:", "page_accueil",
             "Vue d'ensemble des marchés et accès à toutes les fonctions"),
    Fonction("TKR", "Répertoire des tickers", "Terminal", ":material/list_alt:", "page_repertoire",
             "Tous les symboles par famille : actions, indices, commodités, forex, crypto…"),
    Fonction("MKT", "Marchés multi-actifs", "Marchés", ":material/public:", "page_marches",
             "Performance, volatilité et corrélations de plusieurs marchés"),
    Fonction("CMP", "Comparateur & formules", "Marchés", ":material/compare_arrows:", "page_comparateur",
             "Deux symboles face à face, formules entre tickers, graphique TradingView"),
    Fonction("PORT", "Portefeuille & risque", "Portefeuille", ":material/pie_chart:", "page_risque",
             "VaR, optimisation de Markowitz et niveau de risque d'un FNB"),
    Fonction("FA", "Analyse fondamentale", "Entreprises", ":material/account_balance:", "page_fondamental",
             "États financiers, ratios, DCF et carnet de thèse"),
    Fonction("OPT", "Options", "Dérivés", ":material/functions:", "page_options",
             "Chaîne d'options, volatilité implicite, grecques, Black-Scholes"),
    Fonction("YCRV", "Courbes & obligations", "Taux & crédit", ":material/show_chart:", "page_taux",
             "Courbes des taux US et Canada, calculatrice obligataire"),
    Fonction("SPRD", "Spreads de taux", "Taux & crédit", ":material/swap_vert:", "page_spreads",
             "Écarts entre taux, z-score historique, G-spread d'une obligation"),
]
PAR_CODE = {f.code: f for f in FONCTIONS}

# Clés d'état remplies par une commande, lues par la page cible au chargement.
# code -> liste des clés d'état qui reçoivent les arguments, dans l'ordre.
ARGUMENTS = {
    "FA": ["cmd_fd_ticker"],
    "OPT": ["cmd_opt_ticker"],
    "CMP": ["cmd_cmp_a", "cmd_cmp_b"],
    "MKT": ["cmd_marches_libre"],
    "TKR": ["cmd_rep_recherche"],
    "PORT": ["cmd_risque_libre"],
}


def executer_commande() -> None:
    """Rappel de la barre de commande : lit le texte, prépare la page cible.
    Le changement de page lui-même se fait dans app.py (st.switch_page)."""
    texte = st.session_state.get("commande", "").strip()
    st.session_state["commande"] = ""
    if not texte:
        return
    morceaux = texte.split()
    code, args = morceaux[0].upper(), morceaux[1:]
    if code not in PAR_CODE:
        st.session_state["_cmd_erreur"] = f"Code inconnu : {code}. Codes : {', '.join(PAR_CODE)}"
        return
    cles = ARGUMENTS.get(code, [])
    if code in ("MKT", "PORT") and args:
        st.session_state[cles[0]] = ", ".join(a.upper() for a in args)
    elif code == "TKR" and args:
        st.session_state[cles[0]] = " ".join(args)
    else:
        for cle, valeur in zip(cles, args):
            st.session_state[cle] = valeur.upper()
    st.session_state["_aller_a"] = code


def valeur_initiale(cle_widget: str, defaut, cle_commande: str | None = None) -> None:
    """Prépare la valeur d'un champ AVANT de le créer :
    une valeur envoyée par la barre de commande remplace la valeur actuelle,
    sinon on garde la valeur de la session (ou le défaut la première fois).
    Le champ doit ensuite être créé avec key=cle_widget et SANS paramètre value."""
    if cle_commande and cle_commande in st.session_state:
        st.session_state[cle_widget] = st.session_state.pop(cle_commande)
    st.session_state.setdefault(cle_widget, defaut)
