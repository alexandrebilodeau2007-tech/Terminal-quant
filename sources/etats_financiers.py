"""
sources/etats_financiers.py — États financiers annuels standardisés.

Stratégie de source (dans cet ordre) :
    1. SEC EDGAR (officiel) : sociétés qui déposent à la SEC (10-K, 20-F, 40-F).
       Données XBRL, normes US GAAP ou IFRS.
    2. Yahoo Finance (repli) : sociétés non inscrites à la SEC (ex. plusieurs
       titres du TSX). Moins fiable : on l'indique clairement à l'écran.

Le résultat est TOUJOURS le même format, quelle que soit la source :
    tableau : index = dates de fin d'exercice, colonnes = postes standardisés
              (Revenus, Bénéfice net, Capitaux propres, ...)
Ainsi, le module de calcul des ratios n'a pas besoin de savoir d'où viennent
les chiffres.

Règle EDGAR : la SEC exige un en-tête "User-Agent" avec ton nom et ton
courriel, et limite à 10 requêtes/seconde. On fait 2 requêtes par société.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from config import CACHE_FONDAMENTAUX

URL_TICKERS_SEC = "https://www.sec.gov/files/company_tickers.json"
URL_FAITS_SEC = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
FORMULAIRES_ANNUELS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
NB_ANNEES = 6  # on garde les 6 derniers exercices

# ---------------------------------------------------------------------------
# Dictionnaire des postes : nom standard -> (type, concepts US GAAP, concepts IFRS)
#   type "duree"   = flux sur l'exercice (ex. revenus de l'année)
#   type "instant" = photo à la date du bilan (ex. actif total au 31 déc.)
#   type "action"  = montant par action (BPA)
# Plusieurs concepts par poste : les entreprises n'utilisent pas toutes la
# même étiquette XBRL, et elles en changent parfois (ex. normes de 2018 sur
# les revenus). On essaie dans l'ordre et on combine.
# ---------------------------------------------------------------------------
POSTES = {
    "Revenue": ("duree",
        ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
         "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"],
        ["Revenue", "RevenueFromContractsWithCustomers"]),
    "Gross profit": ("duree", ["GrossProfit"], ["GrossProfit"]),
    "Operating income (EBIT)": ("duree", ["OperatingIncomeLoss"],
        ["ProfitLossFromOperatingActivities"]),
    "Net income": ("duree", ["NetIncomeLoss", "ProfitLoss"],
        ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"]),
    "Interest expense": ("duree", ["InterestExpense", "InterestExpenseNonoperating"],
        ["FinanceCosts", "InterestExpense"]),
    "Diluted EPS": ("action", ["EarningsPerShareDiluted"], ["DilutedEarningsLossPerShare"]),
    "Operating cash flow": ("duree",
        ["NetCashProvidedByUsedInOperatingActivities"], ["CashFlowsFromUsedInOperatingActivities"]),
    "Capital expenditures (CAPEX)": ("duree",
        ["PaymentsToAcquirePropertyPlantAndEquipment"],
        ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"]),
    "Total assets": ("instant", ["Assets"], ["Assets"]),
    "Current assets": ("instant", ["AssetsCurrent"], ["CurrentAssets"]),
    "Current liabilities": ("instant", ["LiabilitiesCurrent"], ["CurrentLiabilities"]),
    "Total liabilities": ("instant", ["Liabilities"], ["Liabilities"]),
    "Inventory": ("instant", ["InventoryNet"], ["Inventories"]),
    "Cash": ("instant",
        ["CashAndCashEquivalentsAtCarryingValue",
         "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        ["CashAndCashEquivalents"]),
    "Long-term debt": ("instant", ["LongTermDebtNoncurrent", "LongTermDebt"],
        ["NoncurrentPortionOfNoncurrentBorrowings", "LongtermBorrowings"]),
    "Shareholders' equity": ("instant",
        ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        ["EquityAttributableToOwnersOfParent", "Equity"]),
}

# Équivalences pour le repli Yahoo Finance (noms de lignes de yfinance).
POSTES_YAHOO = {
    "Revenue": ["Total Revenue", "Operating Revenue"],
    "Gross profit": ["Gross Profit"],
    "Operating income (EBIT)": ["Operating Income", "EBIT"],
    "Net income": ["Net Income Common Stockholders", "Net Income"],
    "Interest expense": ["Interest Expense", "Interest Expense Non Operating"],
    "Diluted EPS": ["Diluted EPS"],
    "Operating cash flow": ["Operating Cash Flow"],
    "Capital expenditures (CAPEX)": ["Capital Expenditure"],
    "Total assets": ["Total Assets"],
    "Current assets": ["Current Assets"],
    "Current liabilities": ["Current Liabilities"],
    "Total liabilities": ["Total Liabilities Net Minority Interest"],
    "Inventory": ["Inventory"],
    "Cash": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "Long-term debt": ["Long Term Debt"],
    "Shareholders' equity": ["Stockholders Equity", "Common Stock Equity"],
}


@dataclass
class EtatsFinanciers:
    """Conteneur du résultat : les chiffres + leur provenance.
    Garder la provenance avec les chiffres est une règle de rigueur :
    l'export Excel l'indique dans l'onglet Métadonnées."""
    tableau: pd.DataFrame
    source: str
    devise: str
    nom: str
    notes: list[str] = field(default_factory=list)


class ErreurFondamentaux(Exception):
    """Aucune source n'a pu fournir d'états financiers exploitables."""


# ===========================================================================
# 1. SEC EDGAR
# ===========================================================================

@st.cache_data(ttl=CACHE_FONDAMENTAUX, show_spinner=False)
def _table_tickers_sec(user_agent: str) -> dict[str, tuple[int, str]]:
    """Télécharge la correspondance ticker -> (CIK, nom) publiée par la SEC.
    Le CIK est l'identifiant unique d'une société à la SEC."""
    reponse = requests.get(URL_TICKERS_SEC, headers={"User-Agent": user_agent}, timeout=20)
    reponse.raise_for_status()
    return {v["ticker"].upper(): (int(v["cik_str"]), v["title"]) for v in reponse.json().values()}


@st.cache_data(ttl=CACHE_FONDAMENTAUX, show_spinner=False)
def _faits_sec(cik: int, user_agent: str) -> dict:
    """Télécharge TOUS les faits XBRL déposés par la société (un seul fichier JSON)."""
    reponse = requests.get(URL_FAITS_SEC.format(cik=cik), headers={"User-Agent": user_agent}, timeout=30)
    reponse.raise_for_status()
    return reponse.json()


def _choisir_unite(unites: dict, type_poste: str) -> str | None:
    """Choisit l'unité monétaire. Priorité au USD ; sinon la première devise
    trouvée (ex. CAD pour une société canadienne qui dépose en IFRS)."""
    cles = list(unites.keys())
    if type_poste == "action":
        candidates = [c for c in cles if c.endswith("/shares")]
        return next((c for c in candidates if c.startswith("USD")), candidates[0] if candidates else None)
    if "USD" in cles:
        return "USD"
    devises = [c for c in cles if len(c) == 3 and c.isupper()]
    return devises[0] if devises else None


def _serie_concept(faits: dict, taxonomie: str, concept: str, type_poste: str) -> tuple[pd.Series, str | None]:
    """Extrait les valeurs ANNUELLES d'un concept XBRL.

    Filtres appliqués :
        - formulaire annuel seulement (10-K, 20-F, 40-F) et période "FY" ;
        - pour un flux : la période doit durer ~1 an (350 à 380 jours),
          sinon on prendrait un trimestre présenté dans le 10-K ;
        - si une valeur a été retraitée (déposée deux fois pour la même
          date), on garde la PLUS RÉCENTE (date de dépôt "filed").
    """
    bloc = faits.get("facts", {}).get(taxonomie, {}).get(concept)
    if not bloc:
        return pd.Series(dtype="float64"), None
    unite = _choisir_unite(bloc.get("units", {}), type_poste)
    if unite is None:
        return pd.Series(dtype="float64"), None

    retenus = {}  # date de fin -> (date de dépôt, valeur)
    for entree in bloc["units"][unite]:
        if entree.get("form") not in FORMULAIRES_ANNUELS or entree.get("fp") != "FY":
            continue
        fin = pd.Timestamp(entree["end"])
        if type_poste in ("duree", "action"):
            if "start" not in entree:
                continue
            jours = (fin - pd.Timestamp(entree["start"])).days
            if not 350 <= jours <= 380:
                continue
        depot = entree.get("filed", "")
        if fin not in retenus or depot > retenus[fin][0]:
            retenus[fin] = (depot, float(entree["val"]))
    serie = pd.Series({d: v for d, (_, v) in retenus.items()}, dtype="float64").sort_index()
    return serie, unite


def _etats_sec(ticker: str, user_agent: str) -> EtatsFinanciers:
    """Construit le tableau standardisé à partir d'EDGAR."""
    table = _table_tickers_sec(user_agent)
    # La SEC écrit "BRK-B" ; Yahoo écrit "BRK-B" aussi, mais on normalise les points.
    cle = ticker.upper().replace(".", "-")
    if cle not in table:
        raise ErreurFondamentaux(f"{ticker} is not registered with the SEC.")
    cik, nom = table[cle]
    faits = _faits_sec(cik, user_agent)

    # Taxonomie : US GAAP pour la majorité, IFRS pour certains émetteurs étrangers.
    taxonomie = "us-gaap" if "us-gaap" in faits.get("facts", {}) else "ifrs-full"
    index_concepts = 1 if taxonomie == "us-gaap" else 2

    series, devise, notes = {}, None, []
    for poste, definition in POSTES.items():
        type_poste, concepts = definition[0], definition[index_concepts]
        combinee = pd.Series(dtype="float64")
        for concept in concepts:
            serie, unite = _serie_concept(faits, taxonomie, concept, type_poste)
            if serie.empty:
                continue
            if type_poste != "action" and devise is None:
                devise = unite
            # combine_first : garde la valeur déjà trouvée (concept prioritaire)
            # et complète seulement les années manquantes.
            combinee = serie if combinee.empty else combinee.combine_first(serie)
        series[poste] = (type_poste, combinee)

    # Dates d'ancrage = fins d'exercice, déduites des flux (revenus, bénéfice net).
    ancres = sorted(set(series["Net income"][1].index) | set(series["Revenue"][1].index))
    if not ancres:
        raise ErreurFondamentaux("No annual fiscal year found in EDGAR.")
    ancres = ancres[-NB_ANNEES:]

    tableau = pd.DataFrame(index=pd.DatetimeIndex(ancres, name="Fiscal year end"))
    for poste, (type_poste, serie) in series.items():
        valeurs = []
        for ancre in ancres:
            if serie.empty:
                valeurs.append(float("nan"))
                continue
            # Tolérance de 10 jours : la date du bilan peut différer de
            # quelques jours de la fin de période des flux (exercices de 52/53 semaines).
            ecarts = (serie.index - ancre).days
            proches = serie[abs(ecarts) <= 10]
            valeurs.append(proches.iloc[-1] if not proches.empty else float("nan"))
        tableau[poste] = valeurs

    manquants = [p for p in POSTES if tableau[p].isna().all()]
    if manquants:
        notes.append("Items missing from XBRL filings: " + ", ".join(manquants))
    return EtatsFinanciers(tableau, f"SEC EDGAR ({taxonomie})", devise or "USD", nom, notes)


# ===========================================================================
# 2. Repli Yahoo Finance
# ===========================================================================

def _etats_yahoo(ticker: str) -> EtatsFinanciers:
    """Construit le tableau standardisé à partir de yfinance.
    yfinance renvoie 3 tableaux (résultats, bilan, flux) avec les postes en
    lignes et les années en colonnes : on les empile puis on transpose."""
    t = yf.Ticker(ticker)
    brut = pd.concat([t.financials, t.balance_sheet, t.cashflow])
    if brut is None or brut.empty:
        raise ErreurFondamentaux(f"No financial statements available for {ticker}.")
    brut = brut[~brut.index.duplicated()]  # un poste peut apparaître dans 2 tableaux

    tableau = pd.DataFrame(index=pd.DatetimeIndex(sorted(pd.to_datetime(brut.columns)), name="Fiscal year end"))
    for poste, noms in POSTES_YAHOO.items():
        trouve = next((n for n in noms if n in brut.index), None)
        if trouve is None:
            tableau[poste] = float("nan")
            continue
        ligne = brut.loc[trouve]
        ligne.index = pd.to_datetime(ligne.index)
        tableau[poste] = pd.to_numeric(ligne, errors="coerce").reindex(tableau.index)

    # yfinance présente le CAPEX en négatif (sortie de fonds) ; EDGAR en positif.
    # On harmonise en POSITIF pour que FCF = FTE - CAPEX soit identique partout.
    tableau["Capital expenditures (CAPEX)"] = tableau["Capital expenditures (CAPEX)"].abs()

    try:
        infos = t.info
        devise = infos.get("financialCurrency") or "USD"
        nom = infos.get("longName") or ticker
    except Exception:
        devise, nom = "USD", ticker
    notes = ["Unofficial fallback source (Yahoo). Check key figures in the annual report or on SEDAR+."]
    return EtatsFinanciers(tableau.tail(NB_ANNEES), "Yahoo Finance (fallback)", devise, nom, notes)


# ===========================================================================
# 3. Point d'entrée unique
# ===========================================================================

@st.cache_data(ttl=CACHE_FONDAMENTAUX, show_spinner=False)
def obtenir_etats_financiers(ticker: str, user_agent: str | None) -> EtatsFinanciers:
    """Essaie EDGAR, puis Yahoo. Le motif de l'échec d'EDGAR est conservé
    dans les notes pour que l'analyste sache pourquoi le repli a été utilisé."""
    raison = "SEC_USER_AGENT header missing from secrets"
    if user_agent:
        try:
            return _etats_sec(ticker, user_agent)
        except ErreurFondamentaux as e:
            raison = str(e)
        except requests.RequestException as e:
            raison = f"EDGAR unreachable ({e.__class__.__name__})"
    etats = _etats_yahoo(ticker)
    etats.notes.insert(0, f"EDGAR not used: {raison}.")
    return etats


@st.cache_data(ttl=3600, show_spinner=False)
def donnees_de_marche(ticker: str) -> dict:
    """Prix actuel, nombre d'actions et devise de cotation (pour la valorisation)."""
    fi = yf.Ticker(ticker).fast_info
    def lire(*cles):
        for c in cles:
            try:
                v = fi[c]
                if v is not None:
                    return v
            except Exception:
                continue
        return None
    return {
        "prix": lire("last_price", "lastPrice"),
        "actions": lire("shares"),
        "devise": lire("currency"),
    }
