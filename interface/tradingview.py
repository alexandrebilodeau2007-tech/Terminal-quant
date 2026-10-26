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

import base64
import json
import re
import zlib
import tomllib
from copy import deepcopy
from pathlib import Path

FICHIER_BASE = Path(__file__).resolve().parents[1] / "tradingview.toml"

# Indicateurs proposés : nom affiché -> identifiant TradingView (format officiel des widgets).
INDICATEURS = {
    "Simple moving average": "MASimple@tv-basicstudies",
    "Exponential moving average": "MAExp@tv-basicstudies",
    "Bollinger Bands": "BB@tv-basicstudies",
    "RSI": "RSI@tv-basicstudies",
    "Stochastic RSI": "StochasticRSI@tv-basicstudies",
    "Stochastic": "Stochastic@tv-basicstudies",
    "MACD": "MACD@tv-basicstudies",
    "ATR (average true range)": "ATR@tv-basicstudies",
    "Rate of change (ROC)": "ROC@tv-basicstudies",
    "VWAP": "VWAP@tv-basicstudies",
    "Ichimoku Cloud": "IchimokuCloud@tv-basicstudies",
    "Pivot points": "PivotPointsStandard@tv-basicstudies",
}
STYLES = {"1": "Candles", "9": "Hollow candles", "8": "Heikin Ashi", "0": "Bars", "2": "Line", "3": "Area"}
INTERVALLES = {"1": "1 min", "5": "5 min", "15": "15 min", "60": "1 hour", "240": "4 hours",
               "D": "Day", "W": "Week", "M": "Month"}
DISPOSITIONS = {1: "1 chart", 2: "2 side by side", 4: "4 in a grid (2 × 2)"}

# Paramètres réglables par indicateur : nom affiché -> {entrée TradingView: (défaut, min, max, libellé)}.
PARAMETRES = {
    "RSI": {"length": (14, 2, 100, "RSI period")},
    "Simple moving average": {"length": (50, 1, 500, "Simple MA period")},
    "Exponential moving average": {"length": (20, 1, 500, "Exponential MA period")},
    "Bollinger Bands": {"length": (20, 2, 200, "Bands period"), "mult": (2.0, 0.5, 5.0, "Standard deviations")},
}

# Couleurs réglables : clé -> (défaut, libellé).
# Vérifié en ligne : TradingView applique les couleurs des bougies, du fond et de la grille.
# Les couleurs des LIGNES d'indicateurs (RSI, moyennes) sont ignorées par les widgets gratuits
# (réservées à la bibliothèque payante) : elles ne sont donc pas proposées.
COULEURS = {
    "up": ("#2ECC71", "Up candle"),
    "down": ("#FF5C5C", "Down candle"),
    "background": ("#0A0E14", "Background"),
    "grid": ("#1F2A37", "Grid"),
}
COULEUR_SURE = re.compile(r"^#[0-9A-Fa-f]{6}$")

SYMBOLE_SUR = re.compile(r"^[A-Za-z0-9:._!^/*+\-() ]{1,60}$")

# Valeurs de secours si le fichier est absent ou incomplet.
DEFAUTS = {
    "display": {
        "layout": 1, "single_height": 820, "grid_height": 520, "interval": "D", "style": "1",
        "timezone": "America/Toronto", "indicators": [], "side_toolbar": True, "top_toolbar": True,
        "date_ranges": True, "legend": True, "details_panel": False, "hide_volume": False,
        "allow_changes": True,
    },
    "parameters": {nom: {cle: v[0] for cle, v in entrees.items()} for nom, entrees in PARAMETRES.items()},
    "colors": {cle: v[0] for cle, v in COULEURS.items()},
    "charts": [{"symbol": "OANDA:XAUUSD", "compare": "OANDA:XAGUSD"}, {"symbol": "AMEX:SPY", "compare": ""},
                   {"symbol": "TSX:RY", "compare": ""}, {"symbol": "TVC:USOIL", "compare": ""}],
}


def symbole_valide(symbole: str) -> bool:
    return bool(symbole) and bool(SYMBOLE_SUR.match(symbole))


def valider(reglages: dict) -> dict:
    """Complète avec les défauts et remplace toute valeur hors liste blanche.
    Un fichier mal rempli ne casse jamais la page : la valeur fautive est ignorée."""
    r = deepcopy(DEFAUTS)
    aff_in = reglages.get("display", {}) or {}
    aff = r["display"]
    if aff_in.get("layout") in DISPOSITIONS:
        aff["layout"] = aff_in["layout"]
    for cle in ("single_height", "grid_height"):
        if isinstance(aff_in.get(cle), int):
            aff[cle] = min(max(aff_in[cle], 400), 1400)
    if str(aff_in.get("interval")) in INTERVALLES:
        aff["interval"] = str(aff_in["interval"])
    if str(aff_in.get("style")) in STYLES:
        aff["style"] = str(aff_in["style"])
    if isinstance(aff_in.get("timezone"), str) and re.fullmatch(r"[A-Za-z_]+(/[A-Za-z_]+)*", aff_in["timezone"]):
        aff["timezone"] = aff_in["timezone"]
    if isinstance(aff_in.get("indicators"), list):
        aff["indicators"] = [i for i in aff_in["indicators"] if i in INDICATEURS]
    for cle in ("side_toolbar", "top_toolbar", "date_ranges", "legend",
                "details_panel", "hide_volume", "allow_changes"):
        if isinstance(aff_in.get(cle), bool):
            aff[cle] = aff_in[cle]
    for nom, entrees in (reglages.get("parameters") or {}).items():
        if nom not in PARAMETRES or not isinstance(entrees, dict):
            continue
        for cle, valeur in entrees.items():
            if cle in PARAMETRES[nom] and isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                defaut, mini, maxi, _ = PARAMETRES[nom][cle]
                valeur = min(max(valeur, mini), maxi)
                r["parameters"][nom][cle] = int(valeur) if isinstance(defaut, int) else float(valeur)
    for cle, valeur in (reglages.get("colors") or {}).items():
        if cle in COULEURS and isinstance(valeur, str) and COULEUR_SURE.match(valeur):
            r["colors"][cle] = valeur.upper()
    graphiques = reglages.get("charts")
    if isinstance(graphiques, list) and graphiques:
        propres = []
        for g in graphiques[:4]:
            symbole = str(g.get("symbol", "")).strip()
            comparer = str(g.get("compare", "")).strip()
            propres.append({"symbol": symbole if symbole_valide(symbole) else "AMEX:SPY",
                            "compare": comparer if symbole_valide(comparer) else ""})
        while len(propres) < 4:  # toujours 4 emplacements, pour passer à la grille sans erreur
            propres.append(DEFAUTS["charts"][len(propres)])
        r["charts"] = propres
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
    for nom in aff["indicators"]:
        if nom in parametres:
            etudes.append({"id": INDICATEURS[nom], "inputs": parametres[nom]})
        else:
            etudes.append(INDICATEURS[nom])
    return etudes


def config_widget(graphique: dict, aff: dict, parametres: dict | None = None, couleurs: dict | None = None) -> dict:
    """Configuration JSON d'UN widget « Advanced Chart »."""
    parametres = parametres if parametres is not None else DEFAUTS["parameters"]
    c = couleurs if couleurs is not None else DEFAUTS["colors"]
    config = {
        "autosize": True,
        "symbol": graphique["symbol"],
        "interval": aff["interval"],
        "timezone": aff["timezone"],
        "theme": "dark",
        "style": aff["style"],
        "locale": "en",
        "backgroundColor": _rgba(c["background"]),
        "gridColor": _rgba(c["grid"]),
        "allow_symbol_change": True,
        "hide_side_toolbar": not aff["side_toolbar"],
        "hide_top_toolbar": not aff["top_toolbar"],
        "withdateranges": aff["date_ranges"],
        "hide_legend": not aff["legend"],
        "details": aff["details_panel"],
        "hide_volume": aff["hide_volume"],
        "studies": _etudes(aff, parametres),
        # Couleurs des bougies et des indicateurs (clés du moteur de graphiques TradingView).
        "overrides": {
            "mainSeriesProperties.candleStyle.upColor": c["up"],
            "mainSeriesProperties.candleStyle.downColor": c["down"],
            "mainSeriesProperties.candleStyle.borderUpColor": c["up"],
            "mainSeriesProperties.candleStyle.borderDownColor": c["down"],
            "mainSeriesProperties.candleStyle.wickUpColor": c["up"],
            "mainSeriesProperties.candleStyle.wickDownColor": c["down"],
        },
        "calendar": False,
        "save_image": True,
        "show_popup_button": True,  # bouton pour ouvrir le graphique en grande fenêtre
        "popup_width": "1400",
        "popup_height": "850",
        "support_host": "https://www.tradingview.com",
    }
    if graphique.get("compare"):
        config["compareSymbols"] = [{"symbol": graphique["compare"], "position": "SameScale"}]
    return config


def html_grille(reglages: dict, plein_ecran: bool = False) -> tuple[str, int]:
    """Page HTML contenant 1, 2 ou 4 graphiques, et sa hauteur totale en pixels.

    Bibliothèque utilisée : tv.js (TradingView.widget). Contrairement au script
    « embed » plus récent, elle applique les PARAMÈTRES des indicateurs (RSI 9…)
    et les COULEURS des bougies — vérifié en ligne sur l'app.

    plein_ecran=True : la grille occupe 100 % de la fenêtre (vue « graphiques
    seulement ») ; chaque graphique prend une part égale de la hauteur."""
    aff = reglages["display"]
    n = aff["layout"]
    hauteur = aff["single_height"] if n == 1 else aff["grid_height"]
    colonnes = 1 if n == 1 else 2
    rangees = 1 if n <= 2 else 2
    ecart, legende = (4, 18) if plein_ecran else (8, 24)
    cadres, appels = [], []
    for i, g in enumerate(reglages["charts"][:n]):
        config = config_widget(g, aff, reglages["parameters"], reglages["colors"])
        config["container_id"] = f"tq_graphique_{i}"
        if plein_ecran:
            config["autosize"] = True  # le graphique suit la taille de son cadre (et de la fenêtre)
            taille = "flex:1;min-height:0"
            cadre = "height:100%;display:flex;flex-direction:column"
        else:
            config.pop("autosize", None)
            config.update({"width": "100%", "height": hauteur - legende})
            taille, cadre = "", f"height:{hauteur}px"  # cadre de hauteur FIXE : taille toujours connue
        cadres.append(
            f"<div style='{cadre}'><div id='tq_graphique_{i}' style='{taille}'></div>"
            f"<div style='font:11px sans-serif;color:#8B98A9;height:{legende}px;line-height:{legende}px'>"
            "<a href='https://www.tradingview.com/' rel='noopener nofollow' target='_blank' style='color:#FF9F1C'>"
            "Charts by TradingView</a></div></div>")
        # "<\/" : empêche toute fermeture prématurée de la balise <script> (défense en profondeur).
        appels.append(f"new TradingView.widget({json.dumps(config).replace('</', '<\\/')});")
    fond = reglages["colors"]["background"]
    if plein_ecran:
        lignes = f"grid-template-rows:repeat({rangees},minmax(0,1fr));height:100vh;box-sizing:border-box;padding:{ecart}px"
        style_page = f"html,body{{margin:0;padding:0;height:100%;overflow:hidden;background:{fond}}}"
    else:
        lignes = f"grid-auto-rows:{hauteur}px"
        style_page = f"html,body{{margin:0;padding:0;background:{fond}}}"
    page = (f"<style>{style_page}</style>"
            f"<div style='display:grid;grid-template-columns:repeat({colonnes},minmax(0,1fr));"
            f"{lignes};gap:{ecart}px;background:{fond}'>{''.join(cadres)}</div>"
            "<script src='https://s3.tradingview.com/tv.js'></script>"
            f"<script>{''.join(appels)}</script>")
    return page, rangees * hauteur + (rangees - 1) * ecart + 10


def encoder(reglages: dict) -> str:
    """Réglages -> texte compact pour l'adresse web (base64 « URL-safe » d'un JSON).
    Sert à ouvrir la fenêtre « graphiques seulement » avec les réglages du moment."""
    brut = json.dumps(reglages, separators=(",", ":"), ensure_ascii=True).encode()
    return base64.urlsafe_b64encode(zlib.compress(brut, 9)).decode().rstrip("=")


def decoder(texte: str) -> dict | None:
    """Inverse d'encoder(). Toute adresse invalide ou trafiquée renvoie None ;
    le résultat passe ensuite par valider() comme n'importe quel réglage."""
    try:
        brut = zlib.decompress(base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4)))
        if len(brut) > 20_000:  # garde-fou contre une adresse démesurée
            return None
        donnees = json.loads(brut)
        return donnees if isinstance(donnees, dict) else None
    except (ValueError, zlib.error, TypeError):
        return None


def en_toml(reglages: dict) -> str:
    """Réglages courants au format du fichier tradingview.toml (pour remplacer la base sur GitHub)."""
    aff = reglages["display"]

    def valeur(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, int):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
        return json.dumps(v, ensure_ascii=False)

    lignes = ["# BASE settings for the TradingView charts — exported from the terminal.",
              "# Replace the tradingview.toml file in the GitHub repository with this one.", "", "[display]"]
    lignes += [f"{cle} = {valeur(v)}" for cle, v in aff.items()]
    lignes += ["", "[parameters]"]
    for nom, entrees in reglages["parameters"].items():
        lignes.append(f"{json.dumps(nom, ensure_ascii=False)} = {{ " + ", ".join(f"{k} = {valeur(v)}" for k, v in entrees.items()) + " }")
    lignes += ["", "[colors]"] + [f"{cle} = {valeur(v)}" for cle, v in reglages["colors"].items()]
    for g in reglages["charts"]:
        lignes += ["", "[[charts]]", f"symbol = {valeur(g['symbol'])}", f"compare = {valeur(g['compare'])}"]
    return "\n".join(lignes) + "\n"
