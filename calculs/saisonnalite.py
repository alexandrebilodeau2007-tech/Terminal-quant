"""
calculs/saisonnalite.py — Saisonnalité : courbe annuelle moyenne, fenêtres saisonnières,
statistiques, tests de significativité, recherche des meilleures fenêtres (screener),
études d'événements, rendements mensuels et par jour de semaine.

Mathématiques pures : aucune connexion Internet, aucun Streamlit -> testable.

CONVENTIONS (à connaître pour interpréter les chiffres)
    1. Calendrier de 365 jours (année non bissextile de référence) : le 29 février
       est fusionné avec le 28. Jour 0 = 1er janvier, jour 364 = 31 décembre.
    2. Les jours sans cotation (fins de semaine, fériés) prennent le DERNIER cours
       connu (report avant). Aucune donnée n'est inventée : le cours ne bouge pas
       ces jours-là.
    3. Une fenêtre « du jour A au jour B » achète à la clôture de la VEILLE de A
       et vend à la clôture de B : le mouvement du jour A est donc compris. C'est
       la même convention que la courbe saisonnière (valeur du jour = variation
       cumulée jusqu'à ce jour inclus).
    4. Si B est avant A dans le calendrier (ex. 15 nov. -> 10 janv.), la fenêtre
       chevauche le Nouvel An et se termine l'année suivante. L'année affichée
       est celle du DÉBUT.
    5. Position « short » (vendeuse) : rendement = −(rendement long). Les frais
       d'emprunt, de transaction et les dividendes à payer ne sont pas comptés.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from scipy import stats as sps

JOURS_AN = 365
REFERENCE = pd.date_range("2001-01-01", "2001-12-31", freq="D")   # année de référence non bissextile
ETIQUETTES = [d.strftime("%b %d") for d in REFERENCE]              # "Jan 01" … "Dec 31"
JOURS_BOURSE_AN = 252

CYCLES = {
    "All years": None,
    "US election years (2024, 2020…)": 0,
    "Post-election years (2025, 2021…)": 1,
    "Midterm years (2026, 2022…)": 2,
    "Pre-election years (2027, 2023…)": 3,
    "Odd years": "odd",
    "Even years": "even",
}


# =========================================================================== outils de dates
def jour_de_l_annee(d: date | pd.Timestamp) -> int:
    """Date -> jour 0..364 du calendrier de référence (29 février -> 28 février)."""
    mois, jour = d.month, d.day
    if mois == 2 and jour == 29:
        jour = 28
    return (date(2001, mois, jour) - date(2001, 1, 1)).days


def date_du_jour(annee: int, jour: int) -> date:
    """Jour 0..364 d'une année donnée -> vraie date (le 28 février reste le 28 février)."""
    ref = REFERENCE[jour]
    return date(annee, ref.month, ref.day)


def duree_calendaire(debut: int, fin: int) -> int:
    """Nombre de jours civils de la fenêtre, bornes incluses (gère le chevauchement du Nouvel An)."""
    return fin - debut + 1 if fin >= debut else JOURS_AN - debut + fin + 1


def filtrer_annees(annees: list[int], cycle=None, exclure: list[int] | None = None) -> list[int]:
    """Filtre de cycle présidentiel américain (année % 4), années paires/impaires, exclusions."""
    garde = list(annees)
    if cycle == "odd":
        garde = [a for a in garde if a % 2 == 1]
    elif cycle == "even":
        garde = [a for a in garde if a % 2 == 0]
    elif isinstance(cycle, int):
        garde = [a for a in garde if a % 4 == cycle]
    exclure = set(exclure or [])
    return [a for a in garde if a not in exclure]


# =========================================================================== grille calendaire
def grille_calendaire(prix: pd.Series) -> pd.DataFrame:
    """Série de prix (jours de bourse) -> tableau Année x Jour (0..364) de prix de clôture.

    Chaque case = dernier cours connu à la fin de ce jour civil. Avant la première
    cotation et après la dernière, la case est vide (NaN) : rien n'est extrapolé."""
    s = pd.Series(prix, dtype="float64").dropna()
    if s.empty:
        return pd.DataFrame(columns=range(JOURS_AN), dtype="float64")
    s.index = pd.to_datetime(s.index).normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    quotidien = s.resample("D").last().ffill()
    quotidien = quotidien[~((quotidien.index.month == 2) & (quotidien.index.day == 29))]
    tableau = pd.DataFrame({"annee": quotidien.index.year,
                            "jour": [jour_de_l_annee(d) for d in quotidien.index],
                            "prix": quotidien.values})
    grille = tableau.pivot(index="annee", columns="jour", values="prix")
    return grille.reindex(columns=range(JOURS_AN))


def annees_completes(grille: pd.DataFrame) -> list[int]:
    """Années entières utilisables pour la courbe : les 365 jours ET la clôture du 31 déc. précédent."""
    complets = [a for a in grille.index if grille.loc[a].notna().all()]
    return [a for a in complets if (a - 1) in grille.index and pd.notna(grille.loc[a - 1, JOURS_AN - 1])]


def _etendue(grille: pd.DataFrame, annees: list[int]) -> np.ndarray:
    """Matrice (années x 731) : [clôture du 31 déc. précédent, jours 0..364 de l'année, jours 0..364 de l'année suivante].
    Position p = 1 + jour pour l'année ; 366 + jour pour l'année suivante ; 0 = veille du 1er janvier."""
    lignes = []
    for a in annees:
        veille = grille.loc[a - 1, JOURS_AN - 1] if (a - 1) in grille.index else np.nan
        courante = grille.loc[a].to_numpy(dtype=float) if a in grille.index else np.full(JOURS_AN, np.nan)
        suivante = grille.loc[a + 1].to_numpy(dtype=float) if (a + 1) in grille.index else np.full(JOURS_AN, np.nan)
        lignes.append(np.concatenate([[veille], courante, suivante]))
    return np.array(lignes) if lignes else np.empty((0, 2 * JOURS_AN + 1))


def _positions(debut: int, fin: int) -> tuple[int, int]:
    """Positions d'entrée (clôture de la veille du début) et de sortie dans la matrice étendue."""
    return debut, (1 + fin) if fin >= debut else (1 + JOURS_AN + fin)


# =========================================================================== courbe saisonnière
def chemins_annuels(grille: pd.DataFrame, annees: list[int]) -> pd.DataFrame:
    """Variation cumulée depuis le 31 décembre précédent, pour chaque année (lignes) et chaque jour (colonnes)."""
    if not annees:
        return pd.DataFrame(columns=range(JOURS_AN), dtype="float64")
    ext = _etendue(grille, annees)
    chemins = ext[:, 1:1 + JOURS_AN] / ext[:, [0]] - 1
    return pd.DataFrame(chemins, index=annees, columns=range(JOURS_AN))


def courbe_saisonniere(grille: pd.DataFrame, annees: list[int], detendance: bool = False,
                       mediane: bool = False) -> pd.Series:
    """Année type : moyenne (ou médiane) des chemins annuels, en variation cumulée (0,05 = +5 %).

    detendance=True retire la tendance de fond : on soustrait une droite qui va de 0
    au niveau final, si bien que la courbe finit à 0 et ne montre que la forme
    saisonnière (utile pour un actif qui a beaucoup monté, où tout semble haussier)."""
    chemins = chemins_annuels(grille, annees)
    if chemins.empty:
        return pd.Series(np.nan, index=range(JOURS_AN))
    courbe = chemins.median() if mediane else chemins.mean()
    if detendance:
        courbe = courbe - courbe.iloc[-1] * (np.arange(1, JOURS_AN + 1) / JOURS_AN)
    return courbe


def chemin_annee_en_cours(grille: pd.DataFrame, annee: int, detendance_pente: float | None = None) -> pd.Series:
    """Variation cumulée de l'année en cours (partielle), même base que la courbe saisonnière."""
    if annee not in grille.index or (annee - 1) not in grille.index:
        return pd.Series(dtype="float64")
    base = grille.loc[annee - 1, JOURS_AN - 1]
    chemin = grille.loc[annee] / base - 1
    if detendance_pente is not None:
        chemin = chemin - detendance_pente * (np.arange(1, JOURS_AN + 1) / JOURS_AN)
    return chemin.dropna()


# =========================================================================== fenêtre saisonnière
def annees_fenetre(grille: pd.DataFrame, debut: int, fin: int) -> list[int]:
    """Années pour lesquelles la fenêtre est entièrement connue (entrée ET sortie)."""
    candidates = [a for a in grille.index if (a - 1) in grille.index or debut > 0]
    if not candidates:
        return []
    ext = _etendue(grille, candidates)
    p0, p1 = _positions(debut, fin)
    ok = ~np.isnan(ext[:, p0]) & ~np.isnan(ext[:, p1])
    return [a for a, v in zip(candidates, ok) if v]


def rendements_fenetre(grille: pd.DataFrame, debut: int, fin: int, annees: list[int], short: bool = False) -> pd.DataFrame:
    """Une ligne par année : dates, prix d'entrée et de sortie, rendement, hausse et baisse maximales pendant la fenêtre."""
    colonnes = ["Start", "End", "Start price", "End price", "Return", "Max rise", "Max drop"]
    if not annees:
        return pd.DataFrame(columns=colonnes)
    ext = _etendue(grille, annees)
    p0, p1 = _positions(debut, fin)
    lignes = []
    for a, rangee in zip(annees, ext):
        entree, sortie = rangee[p0], rangee[p1]
        if np.isnan(entree) or np.isnan(sortie):
            continue
        trajet = rangee[p0:p1 + 1] / entree - 1
        r = sortie / entree - 1
        hausse, baisse = np.nanmax(trajet), np.nanmin(trajet)
        if short:
            r, hausse, baisse = -r, -baisse, -hausse   # pour une vente à découvert, une baisse du prix est un gain
        annee_fin = a if fin >= debut else a + 1
        lignes.append({"Year": a, "Start": date_du_jour(a, debut), "End": date_du_jour(annee_fin, fin),
                       "Start price": entree, "End price": sortie, "Return": r, "Max rise": hausse, "Max drop": baisse})
    return pd.DataFrame(lignes).set_index("Year") if lignes else pd.DataFrame(columns=colonnes)


def rendements_quotidiens_fenetres(prix: pd.Series, table: pd.DataFrame, debut: int) -> pd.Series:
    """Rendements quotidiens (jours de bourse) compris dans les fenêtres de chaque année, mis bout à bout.
    Sert à la volatilité, au ratio de Sharpe et au ratio de Sortino."""
    s = pd.Series(prix, dtype="float64").dropna()
    s.index = pd.to_datetime(s.index).normalize()
    r = s.pct_change().dropna()
    morceaux = []
    for _, ligne in table.iterrows():
        entree = pd.Timestamp(ligne["Start"]) - pd.Timedelta(days=1)   # clôture de la veille du début
        sortie = pd.Timestamp(ligne["End"])
        morceaux.append(r[(r.index > entree) & (r.index <= sortie)])
    return pd.concat(morceaux) if morceaux else pd.Series(dtype="float64")


def jours_de_bourse_moyens(prix: pd.Series, table: pd.DataFrame) -> float:
    s = pd.Series(prix).dropna()
    idx = pd.to_datetime(s.index).normalize()
    comptes = [((idx > pd.Timestamp(l["Start"]) - pd.Timedelta(days=1)) & (idx <= pd.Timestamp(l["End"]))).sum()
               for _, l in table.iterrows()]
    return float(np.mean(comptes)) if comptes else float("nan")


def statistiques_fenetre(table: pd.DataFrame, jours_calendaires: int, quotidiens: pd.Series | None = None,
                         jours_bourse: float | None = None) -> dict:
    """Statistiques d'une fenêtre saisonnière, à partir des rendements annuels de la fenêtre."""
    r = table["Return"].astype(float) if not table.empty else pd.Series(dtype="float64")
    n = len(r)
    gains, pertes = r[r > 0], r[r < 0]
    moyenne = r.mean() if n else np.nan
    res = {
        "Years": n,
        "Annualized return": (1 + moyenne) ** (JOURS_AN / jours_calendaires) - 1 if n and moyenne > -1 else np.nan,
        "Average return": moyenne,
        "Median return": r.median() if n else np.nan,
        "Gains": len(gains),
        "Losses": len(pertes),
        "Hit rate": len(gains) / n if n else np.nan,
        "Average profit": gains.mean() if len(gains) else np.nan,
        "Average loss": pertes.mean() if len(pertes) else np.nan,
        "Max profit": r.max() if n else np.nan,
        "Max loss": r.min() if n else np.nan,
        "Standard deviation": r.std(ddof=1) if n > 1 else np.nan,
        "Calendar days": jours_calendaires,
        "Trading days": jours_bourse if jours_bourse is not None else np.nan,
    }
    q = quotidiens.dropna() if quotidiens is not None else pd.Series(dtype="float64")
    if len(q) > 2 and q.std() > 0:
        res["Volatility"] = q.std() * np.sqrt(JOURS_BOURSE_AN)
        res["Sharpe ratio"] = q.mean() / q.std() * np.sqrt(JOURS_BOURSE_AN)
        bas = np.sqrt((np.minimum(q, 0) ** 2).mean())
        res["Sortino ratio"] = q.mean() / bas * np.sqrt(JOURS_BOURSE_AN) if bas > 0 else np.nan
    else:
        res["Volatility"] = res["Sharpe ratio"] = res["Sortino ratio"] = np.nan
    return res


def significativite(table: pd.DataFrame) -> dict:
    """Le résultat peut-il être dû au hasard ?
    - test t de Student : la moyenne des rendements est-elle différente de 0 ?
    - test binomial : le taux de réussite est-il différent de 50 % (pile ou face) ?
    Avec peu d'années (10-15), il faut un effet fort pour être significatif."""
    r = table["Return"].astype(float).dropna() if not table.empty else pd.Series(dtype="float64")
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return {"t-statistic": np.nan, "p-value (mean)": np.nan, "p-value (hit rate)": np.nan}
    t = sps.ttest_1samp(r, 0.0)
    b = sps.binomtest(int((r > 0).sum()), n, 0.5)
    return {"t-statistic": float(t.statistic), "p-value (mean)": float(t.pvalue), "p-value (hit rate)": float(b.pvalue)}


def comparaison_toutes_fenetres(grille: pd.DataFrame, annees: list[int], debut: int, fin: int,
                                short: bool = False) -> dict:
    """Compare la fenêtre choisie à TOUTES les fenêtres de même durée de l'année (365 départs possibles).
    Une fenêtre trouvée en cherchant la meilleure a forcément l'air bonne : ce rang dit à quel point
    elle se distingue d'un départ pris au hasard, et quel rendement « normal » on aurait eu sur cette durée."""
    duree = duree_calendaire(debut, fin)
    ext = _etendue(grille, annees)
    if ext.size == 0:
        return {"Percentile vs all windows": np.nan, "Average of all windows": np.nan, "Excess vs typical window": np.nan}
    r = ext[:, duree:duree + JOURS_AN] / ext[:, :JOURS_AN] - 1          # (années, 365 départs)
    if short:
        r = -r
    moyennes = np.nanmean(r, axis=0)
    choisie = moyennes[debut]
    return {"Percentile vs all windows": float((moyennes < choisie).mean()),
            "Average of all windows": float(np.nanmean(moyennes)),
            "Excess vs typical window": float(choisie - np.nanmean(moyennes))}


def profit_cumule(table: pd.DataFrame) -> pd.Series:
    """Valeur de 1 $ investi uniquement pendant la fenêtre, chaque année (rendements composés)."""
    if table.empty:
        return pd.Series(dtype="float64")
    return (1 + table["Return"].astype(float).sort_index()).cumprod()


# =========================================================================== screener
@dataclass
class CriteresScreener:
    annees: int = 15
    jours_min: int = 10
    jours_max: int = 60
    taux_min: float = 0.80
    sens: str = "Both"                    # "Long", "Short" ou "Both"
    debut_dans: int | None = None         # ne garder que les fenêtres qui commencent dans N jours
    aujourd_hui: date | None = None
    tri: str = "Annualized return"        # ou "Hit rate", "Average return", "Return / risk"
    par_actif: int = 3
    rendement_min: float = 0.0


def _chevauche(a: tuple[int, int], b: tuple[int, int]) -> bool:
    """Deux fenêtres (début, durée) se chevauchent-elles sur le calendrier circulaire ?"""
    jours_a = {(a[0] + k) % JOURS_AN for k in range(a[1])}
    return any(((b[0] + k) % JOURS_AN) in jours_a for k in range(b[1]))


def chercher_fenetres(grille: pd.DataFrame, c: CriteresScreener) -> pd.DataFrame:
    """Toutes les fenêtres (départ x durée) d'un actif qui respectent les critères ;
    on garde les meilleures qui ne se chevauchent pas (au plus c.par_actif)."""
    toutes = sorted(set(annees_completes(grille)))
    annees = toutes[-c.annees:]
    if len(annees) < max(5, int(0.8 * c.annees)):
        return pd.DataFrame()
    ext = _etendue(grille, annees)
    candidats = []
    for duree in range(c.jours_min, c.jours_max + 1):
        r = ext[:, duree:duree + JOURS_AN] / ext[:, :JOURS_AN] - 1       # (années, 365)
        valides = ~np.isnan(r)
        n = valides.sum(axis=0)
        for sens in (["Long", "Short"] if c.sens == "Both" else [c.sens]):
            rr = -r if sens == "Short" else r
            moyenne = np.nanmean(rr, axis=0)
            taux = np.where(n > 0, (rr > 0).sum(axis=0) / np.maximum(n, 1), np.nan)
            ecart = np.nanstd(rr, axis=0, ddof=1)
            ok = (n >= 0.8 * len(annees)) & (taux >= c.taux_min) & (moyenne > c.rendement_min)
            for debut in np.flatnonzero(ok):
                candidats.append((int(debut), duree, sens, float(moyenne[debut]), float(taux[debut]),
                                  float(ecart[debut]), int(n[debut]), float(np.nanmin(rr[:, debut]))))
    if not candidats:
        return pd.DataFrame()
    df = pd.DataFrame(candidats, columns=["start_day", "days", "Direction", "Average return", "Hit rate",
                                          "Std dev", "Years", "Worst year"])
    df["Annualized return"] = (1 + df["Average return"]) ** (JOURS_AN / df["days"]) - 1
    df["Return / risk"] = df["Average return"] / df["Std dev"].replace(0, np.nan)
    if c.debut_dans is not None and c.aujourd_hui is not None:
        j0 = jour_de_l_annee(c.aujourd_hui)
        df = df[((df["start_day"] - j0) % JOURS_AN) <= c.debut_dans]
    df = df.sort_values([c.tri, "Hit rate"], ascending=False)
    gardes: list[tuple[int, int]] = []
    index_gardes = []
    for i, debut, duree in zip(df.index, df["start_day"], df["days"]):
        if all(not _chevauche((debut, duree), g) for g in gardes):
            gardes.append((debut, duree))
            index_gardes.append(i)
        if len(gardes) >= c.par_actif:
            break
    res = df.loc[index_gardes].reset_index(drop=True)
    if res.empty:
        return res
    res["end_day"] = (res["start_day"] + res["days"] - 1) % JOURS_AN
    res["Start"] = [ETIQUETTES[d] for d in res["start_day"]]
    res["End"] = [ETIQUETTES[d] for d in res["end_day"]]
    return res


def prochaine_date(jour: int, aujourd_hui: date) -> date:
    """Prochaine occurrence (aujourd'hui inclus) d'un jour du calendrier de référence."""
    for annee in (aujourd_hui.year, aujourd_hui.year + 1):
        d = date_du_jour(annee, jour)
        if d >= aujourd_hui:
            return d
    return date_du_jour(aujourd_hui.year + 1, jour)


# =========================================================================== événements
def _jour_semaine_n(annee: int, mois: int, jour_semaine: int, rang: int) -> date:
    """rang-ième jour_semaine (lundi = 0) du mois ; rang = -1 pour le dernier."""
    if rang > 0:
        d = date(annee, mois, 1)
        d += timedelta(days=(jour_semaine - d.weekday()) % 7)
        return d + timedelta(weeks=rang - 1)
    d = (date(annee + (mois == 12), mois % 12 + 1, 1) - timedelta(days=1))
    return d - timedelta(days=(d.weekday() - jour_semaine) % 7)


def jour_election_us(annee: int) -> date:
    """Mardi suivant le premier lundi de novembre."""
    return _jour_semaine_n(annee, 11, 0, 1) + timedelta(days=1)


EVENEMENTS = [
    "US presidential election day", "US midterm election day", "Thanksgiving (US)", "Christmas",
    "First trading day of the year", "Monthly options expiration (3rd Friday)",
    "First trading day of the month", "Last trading day of the month", "Quarter end (last trading day)",
    "Custom dates",
]


def dates_evenement(nom: str, jours_bourse: pd.DatetimeIndex, annees: list[int],
                    personnalisees: list[date] | None = None) -> list[pd.Timestamp]:
    """Dates d'un événement sur les années demandées. Pour les événements « jour de bourse »,
    la date est choisie dans le calendrier réel de cotation de l'actif."""
    jb = pd.DatetimeIndex(jours_bourse).normalize()
    a_set = set(annees)
    if nom == "US presidential election day":
        return [pd.Timestamp(jour_election_us(a)) for a in annees if a % 4 == 0]
    if nom == "US midterm election day":
        return [pd.Timestamp(jour_election_us(a)) for a in annees if a % 4 == 2]
    if nom == "Thanksgiving (US)":
        return [pd.Timestamp(_jour_semaine_n(a, 11, 3, 4)) for a in annees]
    if nom == "Christmas":
        return [pd.Timestamp(date(a, 12, 25)) for a in annees]
    if nom == "Monthly options expiration (3rd Friday)":
        return [pd.Timestamp(_jour_semaine_n(a, m, 4, 3)) for a in annees for m in range(1, 13)]
    if nom == "Custom dates":
        return [pd.Timestamp(d) for d in (personnalisees or []) if pd.Timestamp(d).year in a_set]
    s = pd.Series(jb, index=jb)
    s = s[s.index.year.isin(a_set)]
    if nom == "First trading day of the year":
        return list(s.groupby(s.index.year).min())
    cle = [s.index.year, s.index.month]
    if nom == "First trading day of the month":
        return list(s.groupby(cle).min())
    if nom == "Last trading day of the month":
        return list(s.groupby(cle).max())
    if nom == "Quarter end (last trading day)":
        fin = s.groupby(cle).max()
        return [d for d in fin if d.month in (3, 6, 9, 12)]
    raise ValueError(f"Unknown event: {nom}")


def etude_evenement(prix: pd.Series, dates: list[pd.Timestamp], avant: int, apres: int) -> pd.DataFrame:
    """Chemins autour de chaque événement, en jours de bourse.
    Jour 0 = dernière clôture le jour même ou juste avant l'événement (si la Bourse est fermée
    ce jour-là, comme à Noël). Valeur = variation depuis la clôture du jour 0.
    Lignes = événements, colonnes = décalage (−avant … +apres)."""
    s = pd.Series(prix, dtype="float64").dropna()
    s.index = pd.to_datetime(s.index).normalize()
    idx = s.index
    valeurs = s.to_numpy()
    lignes, etiquettes = [], []
    for d in sorted(set(dates)):
        i = idx.searchsorted(pd.Timestamp(d), side="right") - 1
        if i - avant < 0 or i + apres >= len(valeurs) or i < 0:
            continue
        lignes.append(valeurs[i - avant:i + apres + 1] / valeurs[i] - 1)
        etiquettes.append(pd.Timestamp(d).date())
    return pd.DataFrame(lignes, index=etiquettes, columns=range(-avant, apres + 1))


def fenetre_evenement(chemins: pd.DataFrame, a: int, b: int, short: bool = False) -> pd.DataFrame:
    """Rendement de la clôture du jour a à la clôture du jour b, pour chaque événement."""
    if chemins.empty:
        return pd.DataFrame(columns=["Return"])
    r = (1 + chemins[b]) / (1 + chemins[a]) - 1
    if short:
        r = -r
    return pd.DataFrame({"Return": r})


# =========================================================================== mensuel / semaine
MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
JOURS_SEMAINE = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def rendements_mensuels_table(prix: pd.Series) -> pd.DataFrame:
    """Tableau Année x Mois des rendements (clôture de fin de mois à clôture de fin de mois)."""
    s = pd.Series(prix, dtype="float64").dropna()
    s.index = pd.to_datetime(s.index)
    fin_mois = s.resample("ME").last()
    r = fin_mois.pct_change().dropna()
    t = pd.DataFrame({"annee": r.index.year, "mois": r.index.month, "r": r.values})
    tab = t.pivot(index="annee", columns="mois", values="r").reindex(columns=range(1, 13))
    tab.columns = MOIS
    return tab


def statistiques_mensuelles(tab: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Average": tab.mean(), "Median": tab.median(), "Hit rate": (tab > 0).sum() / tab.notna().sum(),
        "Best": tab.max(), "Worst": tab.min(), "Years": tab.notna().sum(),
    })


def statistiques_jours_semaine(prix: pd.Series, annees: list[int] | None = None) -> pd.DataFrame:
    s = pd.Series(prix, dtype="float64").dropna()
    s.index = pd.to_datetime(s.index)
    r = s.pct_change().dropna()
    if annees:
        r = r[r.index.year.isin(annees)]
    g = r.groupby(r.index.dayofweek)
    res = pd.DataFrame({"Average": g.mean(), "Hit rate": g.apply(lambda x: (x > 0).mean()),
                        "Volatility (annualized)": g.std() * np.sqrt(JOURS_BOURSE_AN), "Days": g.size()})
    res = res[res.index < 5]
    res.index = [JOURS_SEMAINE[i] for i in res.index]
    return res


# =========================================================================== calendrier (.ics)
def calendrier_ics(fenetres: list[dict], aujourd_hui: date) -> str:
    """Fichier .ics (Google Agenda, Outlook, Apple) avec un rappel au début et à la fin de chaque
    fenêtre enregistrée : remplace les alertes par courriel d'un service payant."""
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")

    lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Quant Terminal//Seasonality//EN", "CALSCALE:GREGORIAN"]
    for k, f in enumerate(fenetres):
        debut = prochaine_date(f["start_day"], aujourd_hui)
        duree = duree_calendaire(f["start_day"], f["end_day"])
        fin = debut + timedelta(days=duree - 1)
        for quand, quoi in ((debut, "starts"), (fin, "ends")):
            lignes += ["BEGIN:VEVENT", f"UID:tq-seas-{k}-{quoi}-{quand.isoformat()}@quant-terminal",
                       f"DTSTAMP:{aujourd_hui.strftime('%Y%m%d')}T000000Z",
                       f"DTSTART;VALUE=DATE:{quand.strftime('%Y%m%d')}",
                       f"DTEND;VALUE=DATE:{(quand + timedelta(days=1)).strftime('%Y%m%d')}",
                       "SUMMARY:" + esc(f"{f['ticker']} seasonal window {quoi} ({f['direction']} "
                                        f"{ETIQUETTES[f['start_day']]} → {ETIQUETTES[f['end_day']]})"),
                       "DESCRIPTION:" + esc(f"Average return {f.get('avg', float('nan')):.2%}, hit rate "
                                            f"{f.get('hit', float('nan')):.0%} over {f.get('years', '?')} years. "
                                            "Statistics, not a forecast."),
                       "END:VEVENT"]
    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes) + "\r\n"
