# Terminal quant — terminal d'analyse financière multi-actifs

Terminal web construit avec **Streamlit** et **Python** pour **accélérer les calculs** d'une analyse financière :
risque de portefeuille, optimisation, ratios fondamentaux, options, taux et obligations.

> **Philosophie : le terminal calcule, l'analyste conclut.**
> Il ne produit aucune recommandation, aucun signal d'achat ou de vente et n'exécute aucun ordre.
> La thèse d'investissement, l'argumentaire et la décision restent ceux de l'utilisateur.

Projet d'**Alexandre Bilodeau**.

---

## Sommaire

1. [Ce que fait le terminal](#1-ce-que-fait-le-terminal)
2. [Ouvrir le terminal](#2-ouvrir-le-terminal)
3. [Configurer les clés API](#3-configurer-les-clés-api)
4. [Guide d'utilisation par section](#4-guide-dutilisation-par-section)
5. [Choix méthodologiques](#5-choix-méthodologiques)
6. [Balises : ce que le terminal refuse de faire](#6-balises--ce-que-le-terminal-refuse-de-faire)
7. [Architecture du code](#7-architecture-du-code)
8. [Tests](#8-tests)
9. [Contribuer ou modifier le code](#9-contribuer-ou-modifier-le-code)
10. [Limites connues et dépannage](#10-limites-connues-et-dépannage)

---

## 1. Ce que fait le terminal

| # | Section | Contenu |
|---|---|---|
| 1 | **Marchés multi-actifs** | Performance (1 mois, 3 mois, depuis le 1er janvier, 1 an), volatilité, matrice de corrélation, chandeliers avec moyennes mobiles. Actions, indices, commodités, forex, FNB obligataires, taux. |
| 2 | **Risque & Portefeuille** | VaR et CVaR selon 4 méthodes (historique, paramétrique, Cornish-Fisher, Monte Carlo), backtest de Kupiec, frontière efficiente de Markowitz (SciPy), contributions au risque, drawdown, export Excel. |
| 3 | **Analyse fondamentale** | États financiers annuels (SEC EDGAR, repli Yahoo), ratios (ROE, DuPont, marges, liquidité, solvabilité, P/E, P/B, VE/EBIT…), DCF avec **vos** hypothèses et tableau de sensibilité, carnet de thèse, export Excel. |
| 4 | **Options** | Chaîne d'options filtrée par liquidité, smile de volatilité implicite, grecques (Black-Scholes-Merton), calculatrice pour tout sous-jacent. |
| 5 | **Taux & Obligations** | Courbes des taux US (FRED) et canadienne (Banque du Canada), pentes et écarts de crédit, calculatrice obligataire (YTM, duration, convexité, DV01, chocs de taux). |

Marchés couverts : **actions** (US, TSX, international), **indices**, **commodités** (or, pétrole, cuivre, gaz, grains…),
**forex**, **obligations** (FNB et courbes de taux), **options** (actions et FNB américains).

---

## 2. Ouvrir le terminal

### Option A — En ligne (aucune installation)

**👉 [terminal-quant-bilodeau.streamlit.app](https://terminal-quant-bilodeau.streamlit.app)**

Fonctionne dans n'importe quel navigateur, sur ordinateur ou téléphone. Si l'app est en veille (après quelques jours sans visite), cliquer sur *« Yes, get this app back up! »* et attendre environ 30 secondes.



## 4. Guide d'utilisation par section

**Paramètres globaux** (barre latérale) : période d'analyse (5 ans par défaut) et **devise de base** (CAD ou USD).

**Saisie des actifs** : liste prédéfinie, ou n'importe quel ticker Yahoo dans le champ libre.
Exemples : `AAPL`, `RY.TO` (TSX), `GC=F` (or), `CL=F` (pétrole WTI), `USDCAD=X`, `^GSPC` (S&P 500), `TLT` (obligations du Trésor 20+ ans).

### Section 1 — Marchés
Choisir des actifs de catégories différentes pour comparer leur performance en base 100 et leurs corrélations.
La case *Convertir* exprime tout dans la devise de base, soit le rendement réellement vécu par un investisseur canadien.

### Section 2 — Risque & Portefeuille
1. Sélectionner de 2 à 20 actifs **investissables** (pas `^TNX` : c'est un taux, pas un prix).
2. Choisir le niveau de confiance, l'horizon, le poids maximum par actif et le taux sans risque.
3. **Rendements attendus (μ)** : la moyenne historique est pré-remplie. **Remplacez-la par vos hypothèses** ;
   c'est le paramètre qui influence le plus l'optimisation.
4. Comparer les portefeuilles de variance minimale, de Sharpe maximal et manuel.
5. Lire la VaR et la CVaR des 4 méthodes. **L'écart entre méthodes est une information** : un grand écart signale des queues épaisses.
6. Vérifier le backtest de Kupiec : une p-value < 0,05 signifie que la VaR est mal calibrée.
7. Exporter vers Excel (poids, hypothèses, covariance, VaR, backtest, métadonnées).

### Section 3 — Analyse fondamentale
1. Entrer un ticker. La source (EDGAR ou Yahoo) et la devise des états sont affichées.
2. Onglets **États financiers** et **Ratios** : 6 derniers exercices. Les définitions sont dans l'encadré.
3. Onglet **Valorisation & DCF** : saisir **vos** croissances, WACC et croissance terminale, puis cocher la case de confirmation.
   Le tableau de sensibilité montre à quel point la valeur dépend de vos hypothèses.
4. Onglet **Carnet d'analyse** : rédiger la thèse, les catalyseurs, les risques et la conclusion. **Ces champs sont vides par conception.**
5. Onglet **Export** : un classeur Excel avec les chiffres, les ratios, le DCF, votre carnet et les métadonnées.

### Section 4 — Options
- **Chaîne d'options** : sous-jacent américain (ex. `SPY`, `AAPL`), échéance et filtres de liquidité.
  La volatilité implicite est recalculée et comparée à celle de Yahoo.
- **Calculatrice** : pour tout sous-jacent (or, devise, indice), en fournissant soi-même spot, volatilité et taux.

### Section 5 — Taux & Obligations
- Courbes US et canadienne aujourd'hui, il y a 1 an et il y a 2 ans : pente et inversion.
- Écarts de crédit Investment Grade et High Yield.
- Calculatrice : prix ↔ rendement, duration, convexité, DV01 et chocs de ±25 à ±200 pb (approximation vs réévaluation exacte).

---

## 5. Choix méthodologiques

| Sujet | Choix | Pourquoi |
|---|---|---|
| Prix | Ajustés (dividendes et fractionnements) | Rendements totaux corrects |
| Devises | Conversion dans une devise de base | Ne pas mélanger des rendements en CAD et en USD |
| Calendriers | Dates communes uniquement, sans interpolation | La covariance exige des observations simultanées ; aucune donnée inventée |
| Annualisation | 252 jours de bourse | Convention de marché |
| Historique minimum | 500 observations (~2 ans) | Une VaR sur peu de données n'est pas crédible |
| Covariance | Ledoit-Wolf par défaut | Réduit l'erreur d'estimation, portefeuilles plus stables |
| Optimisation | SLSQP (SciPy), long-only, poids plafonné, convergence vérifiée | Évite les portefeuilles extrêmes et les résultats silencieusement faux |
| VaR | 4 méthodes + CVaR + backtest | Aucune méthode n'est parfaite ; les comparer *est* l'analyse |
| Monte Carlo | 10 000 scénarios, graine fixe | Résultats reproductibles |
| ROE, ROA | Sur capitaux propres et actif **moyens** | Le bénéfice est gagné sur toute l'année |
| Ratios absurdes | Affichés `N/A` | ROE avec capitaux propres négatifs, P/E avec bénéfice négatif, etc. |
| Devise du P/E | Prix converti dans la devise des états financiers | Ex. : Shopify cote en CAD mais publie en USD |
| DCF | Aucune hypothèse par défaut cachée ; confirmation requise | La valorisation reste le jugement de l'analyste |
| Options | Prix milieu (bid+ask)/2, contrôle d'arbitrage avant le calcul de la VI | Le dernier prix peut être périmé |

Chaque section du terminal contient un encadré **« Méthode et limites »**.

---

## 6. Balises : ce que le terminal refuse de faire

- Aucune recommandation, aucun « signal », aucune prédiction de prix.
- Aucune exécution d'ordre, aucune connexion à un courtier.
- Aucune valeur de DCF tant que l'utilisateur n'a pas confirmé que les hypothèses sont les siennes.
- Portefeuille : 2 à 20 actifs, 500 observations communes minimum, pas de vente à découvert.
- Les taux et le VIX sont refusés comme actifs de portefeuille.
- **Liste fermée de 4 sources.** Aucun *scraping* de site, aucune source payante contournée.
- Aucune clé API dans le code (`st.secrets` uniquement).
- Chaque export Excel inclut un onglet **Métadonnées** : date, sources, paramètres.

Toutes les limites numériques sont centralisées dans **`config.py`**.

---

## 7. Architecture du code

Le code est séparé en **couches qui ne se mélangent pas**. Chaque fichier est commenté en français.

```
terminal-quant/
├── app.py                    Navigation et paramètres globaux (point d'entrée)
├── config.py                 Balises, constantes, univers d'actifs, sources autorisées
├── lancer_windows.bat        Lanceur Windows en double-clic
├── requirements.txt          Bibliothèques Python
├── sources/                  Couche DONNÉES : téléchargement et nettoyage, aucun calcul
│   ├── marche.py               Prix multi-actifs, conversion de devise, alignement des calendriers
│   ├── taux.py                 FRED et Banque du Canada
│   ├── etats_financiers.py     SEC EDGAR (XBRL US GAAP / IFRS) + repli Yahoo, format standardisé
│   └── options.py              Chaînes d'options
├── calculs/                  Couche CALCULS : mathématiques pures, sans Internet ni Streamlit
│   ├── rendements.py           Rendements, statistiques, drawdown
│   ├── risque.py               VaR, CVaR, Monte Carlo, Kupiec
│   ├── optimisation.py         Markowitz, frontière efficiente, contributions au risque
│   ├── fondamentaux.py         Ratios, DuPont, valorisation, DCF, sensibilité
│   ├── obligations.py          Prix, YTM, duration, convexité, chocs
│   └── options_math.py         Black-Scholes-Merton, grecques, volatilité implicite
├── interface/                Couche AFFICHAGE : une page Streamlit par section
│   ├── page_accueil.py  page_marches.py  page_risque.py
│   ├── page_fondamental.py  page_options.py  page_taux.py
│   └── composants.py           Éléments réutilisables
├── export/excel.py           Export Excel avec métadonnées
└── tests/test_calculs.py     Tests des calculs
```

**Pourquoi cette séparation ?** Les calculs n'ont aucune dépendance à Internet ni à l'interface,
donc ils peuvent être testés avec des chiffres connus. Si une source change, seul `sources/` est modifié.

---

## 8. Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

Les 29 tests comparent les calculs à des valeurs connues, par exemple :
- Black-Scholes : exemple du manuel de Hull (S=42, K=40 → call 4,76) et parité call-put ;
- Markowitz : formule fermée de la variance minimale à 2 actifs, contraintes respectées, cas impossible détecté ;
- VaR : convergence vers la loi normale, CVaR ≥ VaR, Cornish-Fisher sur queues épaisses, Kupiec ;
- Obligations : prix au pair, YTM inverse du prix, duration d'un zéro-coupon, dérivées numériques ;
- Ratios : ROE sur moyenne, cohérence DuPont, N/A pour capitaux propres ou BPA négatifs, DCF = perpétuité de Gordon.

---

## 9. Contribuer ou modifier le code

- **Changer une limite** (poids maximum, nombre d'actifs…) : modifier `config.py` uniquement.
- **Ajouter un actif prédéfini** : dictionnaire `UNIVERS` dans `config.py`.
- **Ajouter un ratio** : fonction `calculer_ratios` et dictionnaire `DEFINITIONS` dans `calculs/fondamentaux.py`, puis un test.
- **Ajouter une source de données** : créer un module dans `sources/` et l'ajouter à `SOURCES_AUTORISEES`.
  Seules des sources officielles ou dont les conditions d'utilisation le permettent sont acceptées.
- Règle : **aucun calcul dans `interface/`** et **aucun appel Internet dans `calculs/`**.
- Lancer `python -m pytest tests/` avant chaque *commit*.

Les *issues* et *pull requests* sont bienvenues.

---

## 10. Limites connues et dépannage

**Limites**
- `yfinance` n'est pas une API officielle : elle peut cesser de fonctionner sans préavis. Données différées.
- Les serveurs infonuagiques (Streamlit Cloud) sont parfois limités par Yahoo (« Too Many Requests ») : attendre quelques minutes. Le cache d'une heure réduit le problème.
- Commodités = contrats à terme continus (`=F`) : sauts de prix artificiels possibles lors des changements d'échéance.
- Options : surtout américaines, sans historique ; Black-Scholes est une approximation pour les options américaines.
- Obligations individuelles (CUSIP/ISIN) : pas de source gratuite fiable, utiliser des FNB.
- Sociétés du TSX non inscrites à la SEC : repli Yahoo, vérifier les chiffres clés sur SEDAR+.
- P/E calculé sur le BPA du dernier exercice annuel (pas sur 12 mois glissants).
- Banques et assureurs : certains ratios (liquidité générale, marge brute) ne s'appliquent pas et s'affichent `N/A`.

**Dépannage**

| Problème | Solution |
|---|---|
| `DLL load failed … Application Control policy has blocked this file` (Windows) | Smart App Control de Windows bloque des bibliothèques non signées. Utiliser la version en ligne (option A). |
| « Python introuvable » | Réinstaller Python en cochant « Add python.exe to PATH ». |
| Erreur à l'installation des bibliothèques avec une version très récente de Python | Utiliser Python 3.12. |
| « Ticker sans données » | Vérifier le ticker sur finance.yahoo.com (ex. `RY.TO`, et non `RY` pour le TSX). |
| Section 5 US désactivée | Ajouter `FRED_API_KEY` dans les secrets. |

---

*Outil personnel et éducatif. Ce n'est pas un conseil financier. La VaR n'est pas une perte maximale.
Les performances passées ne garantissent pas les résultats futurs.*
