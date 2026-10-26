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
    "Yahoo Finance (yfinance)": "Multi-asset prices, option chains, non-US financial statements "
                                "— unofficial, personal use, delayed data.",
    "FRED (St. Louis Fed)": "US yield curve, credit spreads, risk-free rate — official, free key.",
    "SEC EDGAR": "Official financial statements of US-listed companies (XBRL) — official, no key.",
    "Bank of Canada (Valet)": "Canadian yield curve, policy rate, official USD/CAD — official, no key.",
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
    "10y - 2y slope": "T10Y2Y",
    "10y - 3m slope": "T10Y3M",
    "IG credit spread (OAS)": "BAMLC0A0CM",
    "High Yield credit spread (OAS)": "BAMLH0A0HYM2",
}

# Séries de taux disponibles dans la section Spreads : nom affiché -> (source, code).
# Toutes en % ; un spread entre deux d'entre elles est affiché en points de base.
SERIES_TAUX = {
    "US 3-month": ("FRED", "DGS3MO"),
    "US 2-year": ("FRED", "DGS2"),
    "US 5-year": ("FRED", "DGS5"),
    "US 10-year": ("FRED", "DGS10"),
    "US 30-year": ("FRED", "DGS30"),
    "US 10-year real (TIPS)": ("FRED", "DFII10"),
    "US 10-year breakeven inflation": ("FRED", "T10YIE"),
    "US IG credit spread (OAS)": ("FRED", "BAMLC0A0CM"),
    "US BBB credit spread (OAS)": ("FRED", "BAMLC0A4CBBB"),
    "US High Yield credit spread (OAS)": ("FRED", "BAMLH0A0HYM2"),
    "Canada 2-year": ("BDC", "BD.CDN.2YR.DQ.YLD"),
    "Canada 5-year": ("BDC", "BD.CDN.5YR.DQ.YLD"),
    "Canada 10-year": ("BDC", "BD.CDN.10YR.DQ.YLD"),
    "Canada long-term": ("BDC", "BD.CDN.LONG.DQ.YLD"),
}

# Spreads prêts à l'emploi : nom -> (série A, série B). Spread = A - B.
SPREADS_PREDEFINIS = {
    "US 10y - 2y slope": ("US 10-year", "US 2-year"),
    "US 10y - 3m slope": ("US 10-year", "US 3-month"),
    "Canada 10y - 2y slope": ("Canada 10-year", "Canada 2-year"),
    "Canada 10y - US 10y": ("Canada 10-year", "US 10-year"),
    "Canada 2y - US 2y": ("Canada 2-year", "US 2-year"),
    "Inflation: US 10y nominal - 10y real": ("US 10-year", "US 10-year real (TIPS)"),
    "High Yield - IG (risk premium of lower-rated issuers)": ("US High Yield credit spread (OAS)", "US IG credit spread (OAS)"),
}

# Grille officielle de classement du risque des fonds au Canada (ACVM, Règlement
# 81-102, annexe F) : écart-type annualisé des rendements MENSUELS sur 10 ans.
# (borne supérieure exclue en %, niveau)
GRILLE_RISQUE_ACVM = [
    (6, "Low"),
    (11, "Low to medium"),
    (16, "Medium"),
    (20, "Medium to high"),
    (float("inf"), "High"),
]
COURBE_BDC = {  # maturité (en années) -> code de série Banque du Canada
    2: "BD.CDN.2YR.DQ.YLD", 3: "BD.CDN.3YR.DQ.YLD", 5: "BD.CDN.5YR.DQ.YLD",
    7: "BD.CDN.7YR.DQ.YLD", 10: "BD.CDN.10YR.DQ.YLD", 30: "BD.CDN.LONG.DQ.YLD",
}

# ---------------------------------------------------------------------------
# 7. Avertissement affiché partout
# ---------------------------------------------------------------------------
AVERTISSEMENT = (
    "Personal and educational analysis tool. This is not financial advice. "
    "The terminal computes; the investment thesis and the decision remain the analyst's. "
    "VaR is not a maximum loss. Yahoo data is delayed and unofficial."
)
