"""
config.py — Paramètres globaux et BALISES (garde-fous) du terminal.

Pourquoi un fichier séparé ?
    Toutes les règles et limites sont centralisées ici. Si tu veux changer
    une règle (ex. le poids maximum par actif), tu la changes à UN seul
    endroit et tout le terminal suit. C'est aussi ce qu'un évaluateur
    regarde en premier pour comprendre tes choix méthodologiques.
"""

# ---------------------------------------------------------------------------
# 1. Conventions de calcul
# ---------------------------------------------------------------------------

# Nombre de jours de bourse par année. Sert à annualiser les rendements
# (moyenne x 252) et la volatilité (écart-type x racine(252)).
JOURS_BOURSE_PAR_AN = 252

# Graine aléatoire fixe : la simulation Monte Carlo donne le même résultat
# à chaque exécution. Indispensable pour qu'une analyse soit reproductible.
GRAINE_ALEATOIRE = 42

# ---------------------------------------------------------------------------
# 2. Balises (limites que le terminal refuse de dépasser)
# ---------------------------------------------------------------------------

MIN_ACTIFS_PORTEFEUILLE = 2      # sous 2 actifs, une "diversification" n'a pas de sens
MAX_ACTIFS_PORTEFEUILLE = 20     # au-delà, la matrice de covariance devient trop instable
MIN_OBSERVATIONS = 500           # ~2 ans de données quotidiennes, minimum pour une VaR crédible
POIDS_MAX_DEFAUT = 0.40          # aucun actif ne peut dépasser 40 % (évite les solutions "tout sur un")
FENETRE_BACKTEST_VAR = 250       # fenêtre glissante (≈ 1 an) pour le backtest de la VaR
NB_SIMULATIONS_MC = 10_000       # nombre de scénarios Monte Carlo

# Les ventes à découvert sont interdites (poids >= 0). C'est une balise
# volontaire : le terminal est un outil d'analyse, pas un outil de levier.
VENTE_A_DECOUVERT_PERMISE = False

# ---------------------------------------------------------------------------
# 3. Cache (durée de vie des données en mémoire, en secondes)
# ---------------------------------------------------------------------------
# Évite de re-télécharger les mêmes données à chaque clic, et respecte
# les sources (moins de requêtes = moins de risque d'être bloqué).
CACHE_PRIX = 60 * 60             # 1 h pour les prix
CACHE_FONDAMENTAUX = 24 * 60 * 60  # 24 h pour les états financiers (changent 4 fois/an)
CACHE_OPTIONS = 15 * 60          # 15 min pour les chaînes d'options

# ---------------------------------------------------------------------------
# 4. Sources de données AUTORISÉES (liste fermée)
# ---------------------------------------------------------------------------
# Le terminal n'utilise QUE ces 4 sources. Aucune autre n'est appelée.
SOURCES_AUTORISEES = {
    "Yahoo Finance (yfinance)": "Prix multi-actifs, chaînes d'options, états financiers hors É.-U. "
                                "— non officiel, usage personnel, données différées.",
    "FRED (Fed de St. Louis)": "Courbe des taux US, écarts de crédit, taux sans risque — officiel, clé gratuite.",
    "SEC EDGAR": "États financiers officiels des sociétés américaines (XBRL) — officiel, sans clé.",
    "Banque du Canada (Valet)": "Courbe des taux canadienne, taux directeur, USD/CAD officiel — officiel, sans clé.",
}

# ---------------------------------------------------------------------------
# 5. Univers d'actifs (tiré du répertoire des tickers, voir repertoire.py)
# ---------------------------------------------------------------------------
# UNIVERS = {famille: {nom: ticker Yahoo}}. La famille "Options" est exclue :
# ses sous-jacents figurent déjà dans les autres familles.
from repertoire import FAMILLES_NON_INVESTISSABLES, INDICATEURS_NON_INVESTISSABLES, REPERTOIRE  # noqa: E402

UNIVERS = {
    famille: {nom: yahoo for nom, yahoo, _tv, _note in lignes}
    for famille, lignes in REPERTOIRE.items()
    if not famille.startswith("Options")
}

# Tickers qui représentent un TAUX ou un indicateur (en %), pas un prix.
# On ne peut pas "acheter" ^TNX : ses variations ne sont pas des rendements.
# Balise : ils sont refusés dans le module de portefeuille.
TICKERS_TAUX = {
    yahoo for famille in FAMILLES_NON_INVESTISSABLES for _n, yahoo, _t, _no in REPERTOIRE[famille]
} | INDICATEURS_NON_INVESTISSABLES

# ---------------------------------------------------------------------------
# 6. Séries FRED et Banque du Canada utilisées
# ---------------------------------------------------------------------------
COURBE_FRED = {  # maturité (en années) -> code de série FRED
    1 / 12: "DGS1MO", 0.25: "DGS3MO", 0.5: "DGS6MO", 1: "DGS1", 2: "DGS2",
    3: "DGS3", 5: "DGS5", 7: "DGS7", 10: "DGS10", 20: "DGS20", 30: "DGS30",
}
ECARTS_FRED = {
    "Pente 10 ans - 2 ans": "T10Y2Y",
    "Pente 10 ans - 3 mois": "T10Y3M",
    "Écart crédit IG (OAS)": "BAMLC0A0CM",
    "Écart crédit High Yield (OAS)": "BAMLH0A0HYM2",
}

# Séries de taux disponibles dans la section Spreads : nom affiché -> (source, code).
# Toutes en % ; un spread entre deux d'entre elles est affiché en points de base.
SERIES_TAUX = {
    "US 3 mois": ("FRED", "DGS3MO"),
    "US 2 ans": ("FRED", "DGS2"),
    "US 5 ans": ("FRED", "DGS5"),
    "US 10 ans": ("FRED", "DGS10"),
    "US 30 ans": ("FRED", "DGS30"),
    "US 10 ans réel (TIPS)": ("FRED", "DFII10"),
    "Inflation anticipée 10 ans US (point mort)": ("FRED", "T10YIE"),
    "Écart crédit IG US (OAS)": ("FRED", "BAMLC0A0CM"),
    "Écart crédit BBB US (OAS)": ("FRED", "BAMLC0A4CBBB"),
    "Écart crédit High Yield US (OAS)": ("FRED", "BAMLH0A0HYM2"),
    "Canada 2 ans": ("BDC", "BD.CDN.2YR.DQ.YLD"),
    "Canada 5 ans": ("BDC", "BD.CDN.5YR.DQ.YLD"),
    "Canada 10 ans": ("BDC", "BD.CDN.10YR.DQ.YLD"),
    "Canada long terme": ("BDC", "BD.CDN.LONG.DQ.YLD"),
}

# Spreads prêts à l'emploi : nom -> (série A, série B). Spread = A - B.
SPREADS_PREDEFINIS = {
    "Pente US 10 ans - 2 ans": ("US 10 ans", "US 2 ans"),
    "Pente US 10 ans - 3 mois": ("US 10 ans", "US 3 mois"),
    "Pente Canada 10 ans - 2 ans": ("Canada 10 ans", "Canada 2 ans"),
    "Canada 10 ans - US 10 ans": ("Canada 10 ans", "US 10 ans"),
    "Canada 2 ans - US 2 ans": ("Canada 2 ans", "US 2 ans"),
    "Inflation : nominal 10 ans - réel 10 ans US": ("US 10 ans", "US 10 ans réel (TIPS)"),
    "High Yield - IG (prime de risque des moins bien notées)": ("Écart crédit High Yield US (OAS)", "Écart crédit IG US (OAS)"),
}

# Grille officielle de classement du risque des fonds au Canada (ACVM, Règlement
# 81-102, annexe F) : écart-type annualisé des rendements MENSUELS sur 10 ans.
# (borne supérieure exclue en %, niveau)
GRILLE_RISQUE_ACVM = [
    (6, "Faible"),
    (11, "Faible à moyen"),
    (16, "Moyen"),
    (20, "Moyen à élevé"),
    (float("inf"), "Élevé"),
]
COURBE_BDC = {  # maturité (en années) -> code de série Banque du Canada
    2: "BD.CDN.2YR.DQ.YLD", 3: "BD.CDN.3YR.DQ.YLD", 5: "BD.CDN.5YR.DQ.YLD",
    7: "BD.CDN.7YR.DQ.YLD", 10: "BD.CDN.10YR.DQ.YLD", 30: "BD.CDN.LONG.DQ.YLD",
}

# ---------------------------------------------------------------------------
# 7. Avertissement affiché partout
# ---------------------------------------------------------------------------
AVERTISSEMENT = (
    "Outil d'analyse personnel et éducatif. Ce n'est pas un conseil financier. "
    "Le terminal calcule ; la thèse d'investissement et la décision restent celles de l'analyste. "
    "La VaR n'est pas une perte maximale. Les données Yahoo sont différées et non officielles."
)
