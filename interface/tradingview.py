"""
interface/tradingview.py — Widgets TradingView : réglages de base partagés et grille de graphiques.

Principe :
    - Les réglages de BASE viennent du fichier tradingview.toml du dépôt : ils sont
      identiques pour tous les visiteurs.
    - Un visiteur peut les modifier pour sa visite (session) ; il peut aussi exporter
      ses réglages en TOML pour remplacer la base sur GitHub.

Sécurité : tout ce qui entre dans la page passe par une liste blanche (styles,
intervalles, indicateurs) ou un filtre (symboles), puis est sérialisé en JSON.
Aucun texte saisi ne peut injecter de code dans la page.
"""

from __future__ import annotations

import json
import re
import tomllib
from copy import deepcopy
from pathlib import Path

FICHIER_BASE = Path(__file__).resolve().parents[1] / "tradingview.toml"

# Indicateurs proposés : nom affiché -> identifiant TradingView (format officiel des widgets).
INDICATEURS = {
    "Moyenne mobile simple": "MASimple@tv-basicstudies",
    "Moyenne mobile exponentielle": "MAExp@tv-basicstudies",
    "Bandes de Bollinger": "BB@tv-basicstudies",
    "RSI": "RSI@tv-basicstudies",
    "RSI stochastique": "StochasticRSI@tv-basicstudies",
    "Stochastique": "Stochastic@tv-basicstudies",
    "MACD": "MACD@tv-basicstudies",
    "ATR (volatilité moyenne)": "ATR@tv-basicstudies",
    "Taux de variation (ROC)": "ROC@tv-basicstudies",
    "VWAP": "VWAP@tv-basicstudies",
    "Nuage d'Ichimoku": "IchimokuCloud@tv-basicstudies",
    "Points pivots": "PivotPointsStandard@tv-basicstudies",
}
STYLES = {"1": "Chandeliers", "9": "Chandeliers creux", "8": "Heikin Ashi", "0": "Barres", "2": "Ligne", "3": "Aire"}
INTERVALLES = {"1": "1 min", "5": "5 min", "15": "15 min", "60": "1 heure", "240": "4 heures",
               "D": "Jour", "W": "Semaine", "M": "Mois"}
DISPOSITIONS = {1: "1 graphique", 2: "2 côte à côte", 4: "4 en grille (2 × 2)"}

# Paramètres réglables par indicateur : nom affiché -> {entrée TradingView: (défaut, min, max, libellé)}.
PARAMETRES = {
    "RSI": {"length": (14, 2, 100, "Période du RSI")},
    "Moyenne mobile simple": {"length": (50, 1, 500, "Période de la moyenne simple")},
    "Moyenne mobile exponentielle": {"length": (20, 1, 500, "Période de la moyenne exponentielle")},
    "Bandes de Bollinger": {"length": (20, 2, 200, "Période des bandes"), "mult": (2.0, 0.5, 5.0, "Écarts-types")},
}

# Couleurs réglables : clé -> (défaut, libellé).
COULEURS = {
    "hausse": ("#2ECC71", "Bougie haussière"),
    "baisse": ("#FF5C5C", "Bougie baissière"),
    "rsi": ("#FF9F1C", "Ligne du RSI"),
    "moyenne": ("#4EA8DE", "Moyennes mobiles"),
    "fond": ("#0A0E14", "Fond"),
    "grille": ("#1F2A37", "Grille"),
}
COULEUR_SURE = re.compile(r"^#[0-9A-Fa-f]{6}$")

SYMBOLE_SUR = re.compile(r"^[A-Za-z0-9:._!^/*+\-() ]{1,60}$")

# Valeurs de secours si le fichier est absent ou incomplet.
DEFAUTS = {
    "affichage": {
        "disposition": 1, "hauteur_simple": 820, "hauteur_grille": 520, "intervalle": "D", "style": "1",
        "fuseau": "America/Toronto", "indicateurs": [], "barre_outils_laterale": True, "barre_outils_haut": True,
        "plages_de_dates": True, "legende": True, "panneau_details": False, "masquer_volume": False,
        "permettre_modifications": True,
    },
    "parametres": {nom: {cle: v[0] for cle, v in entrees.items()} for nom, entrees in PARAMETRES.items()},
    "couleurs": {cle: v[0] for cle, v in COULEURS.items()},
    "graphiques": [{"symbole": "OANDA:XAUUSD", "comparer": "OANDA:XAGUSD"}, {"symbole": "AMEX:SPY", "comparer": ""},
                   {"symbole": "TSX:RY", "comparer": ""}, {"symbole": "TVC:USOIL", "comparer": ""}],
}


def symbole_valide(symbole: str) -> bool:
    return bool(symbole) and bool(SYMBOLE_SUR.match(symbole))


def valider(reglages: dict) -> dict:
    """Complète avec les défauts et remplace toute valeur hors liste blanche.
    Un fichier mal rempli ne casse jamais la page : la valeur fautive est ignorée."""
    r = deepcopy(DEFAUTS)
    if reglages.get("_essai_tvjs") is True:
        r["_essai_tvjs"] = True
    aff_in = reglages.get("affichage", {}) or {}
    aff = r["affichage"]
    if aff_in.get("disposition") in DISPOSITIONS:
        aff["disposition"] = aff_in["disposition"]
    for cle in ("hauteur_simple", "hauteur_grille"):
        if isinstance(aff_in.get(cle), int):
            aff[cle] = min(max(aff_in[cle], 400), 1400)
    if str(aff_in.get("intervalle")) in INTERVALLES:
        aff["intervalle"] = str(aff_in["intervalle"])
    if str(aff_in.get("style")) in STYLES:
        aff["style"] = str(aff_in["style"])
    if isinstance(aff_in.get("fuseau"), str) and re.fullmatch(r"[A-Za-z_]+(/[A-Za-z_]+)*", aff_in["fuseau"]):
        aff["fuseau"] = aff_in["fuseau"]
    if isinstance(aff_in.get("indicateurs"), list):
        aff["indicateurs"] = [i for i in aff_in["indicateurs"] if i in INDICATEURS]
    for cle in ("barre_outils_laterale", "barre_outils_haut", "plages_de_dates", "legende",
                "panneau_details", "masquer_volume", "permettre_modifications"):
        if isinstance(aff_in.get(cle), bool):
            aff[cle] = aff_in[cle]
    for nom, entrees in (reglages.get("parametres") or {}).items():
        if nom not in PARAMETRES or not isinstance(entrees, dict):
            continue
        for cle, valeur in entrees.items():
            if cle in PARAMETRES[nom] and isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                defaut, mini, maxi, _ = PARAMETRES[nom][cle]
                valeur = min(max(valeur, mini), maxi)
                r["parametres"][nom][cle] = int(valeur) if isinstance(defaut, int) else float(valeur)
    for cle, valeur in (reglages.get("couleurs") or {}).items():
        if cle in COULEURS and isinstance(valeur, str) and COULEUR_SURE.match(valeur):
            r["couleurs"][cle] = valeur.upper()
    graphiques = reglages.get("graphiques")
    if isinstance(graphiques, list) and graphiques:
        propres = []
        for g in graphiques[:4]:
            symbole = str(g.get("symbole", "")).strip()
            comparer = str(g.get("comparer", "")).strip()
            propres.append({"symbole": symbole if symbole_valide(symbole) else "AMEX:SPY",
                            "comparer": comparer if symbole_valide(comparer) else ""})
        while len(propres) < 4:  # toujours 4 emplacements, pour passer à la grille sans erreur
            propres.append(DEFAUTS["graphiques"][len(propres)])
        r["graphiques"] = propres
    return r


def charger_base(chemin: Path = FICHIER_BASE) -> dict:
    """Lit tradingview.toml (les réglages communs à tous les visiteurs)."""
    try:
        with open(chemin, "rb") as f:
            return valider(tomllib.load(f))
    except (OSError, tomllib.TOMLDecodeError):
        return deepcopy(DEFAUTS)


def _rgba(hexa: str) -> str:
    """#0A0E14 -> rgba(10, 14, 20, 1) (format attendu par le widget pour le fond et la grille)."""
    return f"rgba({int(hexa[1:3], 16)}, {int(hexa[3:5], 16)}, {int(hexa[5:7], 16)}, 1)"


def _etudes(aff: dict, parametres: dict) -> list:
    """Indicateurs : un identifiant seul, ou {id, inputs} quand l'indicateur a des paramètres."""
    etudes = []
    for nom in aff["indicateurs"]:
        if nom in parametres:
            etudes.append({"id": INDICATEURS[nom], "inputs": parametres[nom]})
        else:
            etudes.append(INDICATEURS[nom])
    return etudes


def config_widget(graphique: dict, aff: dict, parametres: dict | None = None, couleurs: dict | None = None) -> dict:
    """Configuration JSON d'UN widget « Advanced Chart »."""
    parametres = parametres if parametres is not None else DEFAUTS["parametres"]
    c = couleurs if couleurs is not None else DEFAUTS["couleurs"]
    config = {
        "autosize": True,
        "symbol": graphique["symbole"],
        "interval": aff["intervalle"],
        "timezone": aff["fuseau"],
        "theme": "dark",
        "style": aff["style"],
        "locale": "fr",
        "backgroundColor": _rgba(c["fond"]),
        "gridColor": _rgba(c["grille"]),
        "allow_symbol_change": True,
        "hide_side_toolbar": not aff["barre_outils_laterale"],
        "hide_top_toolbar": not aff["barre_outils_haut"],
        "withdateranges": aff["plages_de_dates"],
        "hide_legend": not aff["legende"],
        "details": aff["panneau_details"],
        "hide_volume": aff["masquer_volume"],
        "studies": _etudes(aff, parametres),
        # Couleurs des bougies et des indicateurs (clés du moteur de graphiques TradingView).
        "overrides": {
            "mainSeriesProperties.candleStyle.upColor": c["hausse"],
            "mainSeriesProperties.candleStyle.downColor": c["baisse"],
            "mainSeriesProperties.candleStyle.borderUpColor": c["hausse"],
            "mainSeriesProperties.candleStyle.borderDownColor": c["baisse"],
            "mainSeriesProperties.candleStyle.wickUpColor": c["hausse"],
            "mainSeriesProperties.candleStyle.wickDownColor": c["baisse"],
        },
        "studies_overrides": {
            "relative strength index.plot.color": c["rsi"],
            "moving average.plot.color": c["moyenne"],
            "moving average exponential.plot.color": c["moyenne"],
        },
        "calendar": False,
        "save_image": True,
        "show_popup_button": True,  # bouton pour ouvrir le graphique en grande fenêtre
        "popup_width": "1400",
        "popup_height": "850",
        "support_host": "https://www.tradingview.com",
    }
    if graphique.get("comparer"):
        config["compareSymbols"] = [{"symbol": graphique["comparer"], "position": "SameScale"}]
    return config


def _essai(i: int, cfg: dict) -> dict:
    """TEMPORAIRE : variantes pour identifier les options acceptées par le widget."""
    simples = [e["id"] if isinstance(e, dict) else e for e in cfg["studies"]]
    if i == 0:   # paramètres d'indicateurs + couleurs des bougies, sans couleurs d'indicateurs
        cfg.pop("studies_overrides")
    elif i == 1:   # indicateurs avec paramètres, sans couleurs
        cfg.pop("overrides"); cfg.pop("studies_overrides")
    elif i == 2:  # couleurs des bougies seulement
        cfg["studies"] = simples; cfg.pop("studies_overrides")
    elif i == 3:  # couleurs des indicateurs seulement
        cfg["studies"] = simples; cfg.pop("overrides")
    return cfg


def html_grille(reglages: dict) -> tuple[str, int]:
    """Page HTML contenant 1, 2 ou 4 widgets, et sa hauteur totale en pixels."""
    aff = reglages["affichage"]
    n = aff["disposition"]
    hauteur = aff["hauteur_simple"] if n == 1 else aff["hauteur_grille"]
    colonnes = 1 if n == 1 else 2
    rangees = 1 if n <= 2 else 2
    ecart = 8
    blocs = []
    for i_essai, g in enumerate(reglages["graphiques"][:n]):
        # Cadre extérieur de hauteur FIXE : le script TradingView réécrit le style de son
        # propre conteneur (height:100 %), il lui faut donc un parent dont la hauteur est connue.
        blocs.append(f"""
  <div class="tq-cadre" style="height:{hauteur}px">
    <div class="tradingview-widget-container" style="height:100%;width:100%">
      <div class="tradingview-widget-container__widget" style="height:calc(100% - 24px);width:100%"></div>
      <div class="tradingview-widget-copyright" style="font:11px sans-serif;color:#8B98A9;height:24px;line-height:24px">
        <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank" style="color:#FF9F1C">Graphiques par TradingView</a></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
      {json.dumps(_essai(i_essai, config_widget(g, aff, reglages["parametres"], reglages["couleurs"])))}
      </script>
    </div>
  </div>""")
    if reglages.get("_essai_tvjs"):  # TEMPORAIRE : ancienne bibliothèque tv.js
        cfg = config_widget(reglages["graphiques"][0], aff, reglages["parametres"], reglages["couleurs"])
        cfg.update({"container_id": "tv_essai", "width": "100%", "height": hauteur})
        cfg.pop("autosize", None)
        page = (f"<style>html,body{{margin:0;padding:0;background:#0A0E14}}</style><div id='tv_essai' style='height:{hauteur}px'></div>"
                "<script src='https://s3.tradingview.com/tv.js'></script>"
                f"<script>new TradingView.widget({json.dumps(cfg)});</script>")
        return page, hauteur + 10
    page = ("<style>html,body{margin:0;padding:0;background:#0A0E14}</style>"
            f"<div style='display:grid;grid-template-columns:repeat({colonnes},minmax(0,1fr));"
            f"grid-auto-rows:{hauteur}px;gap:{ecart}px;background:{reglages["couleurs"]["fond"]}'>{''.join(blocs)}</div>")
    return page, rangees * hauteur + (rangees - 1) * ecart + 10


def en_toml(reglages: dict) -> str:
    """Réglages courants au format du fichier tradingview.toml (pour remplacer la base sur GitHub)."""
    aff = reglages["affichage"]

    def valeur(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
        return json.dumps(v, ensure_ascii=False)

    lignes = ["# Réglages de BASE des graphiques TradingView — exportés depuis le terminal.",
              "# Remplacer le fichier tradingview.toml du dépôt GitHub par celui-ci.", "", "[affichage]"]
    lignes += [f"{cle} = {valeur(v)}" for cle, v in aff.items()]
    lignes += ["", "[parametres]"]
    for nom, entrees in reglages["parametres"].items():
        lignes.append(f"{json.dumps(nom, ensure_ascii=False)} = {{ " + ", ".join(f"{k} = {valeur(v)}" for k, v in entrees.items()) + " }")
    lignes += ["", "[couleurs]"] + [f"{cle} = {valeur(v)}" for cle, v in reglages["couleurs"].items()]
    for g in reglages["graphiques"]:
        lignes += ["", "[[graphiques]]", f"symbole = {valeur(g['symbole'])}", f"comparer = {valeur(g['comparer'])}"]
    return "\n".join(lignes) + "\n"
