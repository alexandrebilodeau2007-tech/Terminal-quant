"""
calculs/formule.py — Formules sur des séries de prix, comme sur TradingView.

Exemples acceptés :
    GC=F / SI=F                    ratio or/argent
    CL=F - BZ=F                    écart WTI - Brent
    (AAPL + MSFT + NVDA) / 3       moyenne de trois actions
    SPY / TLT                      actions contre obligations
    BTC-USD * USDCAD=X             bitcoin converti en CAD

Règles :
    - Opérateurs : + - * / ** et parenthèses. Nombres autorisés (ex. 100 * GC=F / SI=F).
    - Le signe MOINS entre deux tickers doit être entouré d'espaces : "AAPL - MSFT".
      Sans espace, "BTC-USD" est lu comme un seul ticker (c'est le format Yahoo).

SÉCURITÉ : la formule n'est JAMAIS exécutée avec eval(). On la découpe en
morceaux (tickers, nombres, opérateurs), puis on la lit avec le module `ast`
en n'acceptant que les opérations arithmétiques. Toute autre construction
(appel de fonction, attribut, etc.) est refusée.
"""

from __future__ import annotations

import ast
import operator
import re

import pandas as pd

# Un ticker commence par une lettre ou ^ ; il peut contenir lettres, chiffres, . = ^
# et des tirets SUIVIS d'une lettre ou d'un chiffre (BTC-USD, BRK-B, GIB-A.TO).
MOTIF_TICKER = r"\^?[A-Za-z][A-Za-z0-9.=^]*(?:-[A-Za-z0-9][A-Za-z0-9.=^]*)*"
MOTIF_JETON = re.compile(rf"\s*(?:(?P<nombre>\d+(?:[.,]\d+)?)|(?P<ticker>{MOTIF_TICKER})|(?P<op>\*\*|[-+*/()]))")

OPERATEURS_BINAIRES = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                       ast.Div: operator.truediv, ast.Pow: operator.pow}


class ErreurFormule(Exception):
    """Formule invalide : message lisible pour l'utilisateur."""


def analyser(formule: str) -> tuple[str, dict[str, str]]:
    """Découpe la formule et remplace chaque ticker par une variable v0, v1…

    Retour : (expression Python sûre, {variable: ticker}).
    Ex. "GC=F / SI=F" -> ("v0 / v1", {"v0": "GC=F", "v1": "SI=F"})
    """
    position, morceaux, variables = 0, [], {}
    texte = formule.strip()
    if not texte:
        raise ErreurFormule("La formule est vide.")
    while position < len(texte):
        m = MOTIF_JETON.match(texte, position)
        if not m or m.end() == position:
            raise ErreurFormule(f"Caractère inattendu à la position {position + 1} : « {texte[position:position + 10]} »")
        if m.group("nombre"):
            morceaux.append(m.group("nombre").replace(",", "."))
        elif m.group("ticker"):
            ticker = m.group("ticker").upper()
            nom = next((k for k, v in variables.items() if v == ticker), None)
            if nom is None:
                nom = f"v{len(variables)}"
                variables[nom] = ticker
            morceaux.append(nom)
        else:
            morceaux.append(m.group("op"))
        position = m.end()
    if not variables:
        raise ErreurFormule("La formule doit contenir au moins un ticker.")
    return " ".join(morceaux), variables


def _evaluer(noeud, valeurs: dict[str, pd.Series]):
    """Parcourt l'arbre de l'expression en n'acceptant que l'arithmétique."""
    if isinstance(noeud, ast.Expression):
        return _evaluer(noeud.body, valeurs)
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in OPERATEURS_BINAIRES:
        return OPERATEURS_BINAIRES[type(noeud.op)](_evaluer(noeud.left, valeurs), _evaluer(noeud.right, valeurs))
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        v = _evaluer(noeud.operand, valeurs)
        return -v if isinstance(noeud.op, ast.USub) else v
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.Name) and noeud.id in valeurs:
        return valeurs[noeud.id]
    raise ErreurFormule("Construction non autorisée dans la formule (seuls + - * / ** et les parenthèses le sont).")


def calculer(formule: str, prix: pd.DataFrame) -> pd.Series:
    """Applique la formule aux prix (colonnes = tickers), date par date.

    Seules les dates où TOUS les tickers ont un prix sont gardées.
    Les divisions par zéro donnent NaN, retirées du résultat.
    """
    expression, variables = analyser(formule)
    manquants = [t for t in variables.values() if t not in prix.columns]
    if manquants:
        raise ErreurFormule(f"Prix manquants pour : {', '.join(manquants)}")
    commun = prix[list(variables.values())].dropna()
    valeurs = {nom: commun[ticker] for nom, ticker in variables.items()}
    try:
        arbre = ast.parse(expression, mode="eval")
    except SyntaxError as e:
        raise ErreurFormule("Formule mal construite (parenthèse ou opérateur en trop ?).") from e
    resultat = _evaluer(arbre, valeurs)
    if not isinstance(resultat, pd.Series):
        raise ErreurFormule("La formule ne dépend d'aucun prix.")
    resultat = resultat.replace([float("inf"), float("-inf")], float("nan")).dropna()
    return resultat.rename(formule.strip())


def tickers_de(formule: str) -> list[str]:
    """Liste des tickers d'une formule (pour savoir quoi télécharger)."""
    return list(analyser(formule)[1].values())
