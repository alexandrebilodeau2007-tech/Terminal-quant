"""
interface/aide.py — Textes des boutons d'aide « ? ».

Chaque texte suit le même plan, pour être compris sans connaissances en finance :
    Ce que ça fait  ->  Exemple concret  ->  Pourquoi c'est utile.
Les textes sont centralisés ici pour être faciles à relire et à corriger.
"""

from __future__ import annotations

import streamlit as st

AIDE: dict[str, str] = {
    # ------------------------------------------------------------------ général
    "accueil": """
**Ce que c'est** : le tableau de bord d'accueil. Il montre les grands marchés du jour et donne accès à chaque fonction.

**Exemple** : tu arrives le matin, tu vois que le S&P 500 est à −1,2 % et l'or à +0,8 % : les investisseurs se protègent.

**Pourquoi c'est utile** : en 10 secondes, tu sais dans quelle « humeur » est le marché avant de commencer une analyse.
""",
    "commande": """
**Ce que c'est** : une barre de commande comme sur un terminal Bloomberg. Tu tapes un code, tu arrives directement à la bonne fonction.

**Exemples** : `FA AAPL` ouvre l'analyse fondamentale d'Apple · `OPT SPY` ouvre les options de SPY · `CMP GC=F SI=F` compare l'or et l'argent · `TKR` ouvre le répertoire.

**Pourquoi c'est utile** : c'est beaucoup plus rapide que de cliquer dans les menus quand tu connais ce que tu cherches.
""",
    "repertoire": """
**Ce que c'est** : la liste des principaux tickers, classés par famille (actions, indices, commodités, forex, crypto, obligations, options).

**Exemple** : tu veux analyser le pétrole mais tu ne connais pas son symbole : famille « Commodités », ligne « Pétrole WTI », ticker `CL=F`.

**Pourquoi c'est utile** : un ticker mal écrit ne donne aucune donnée. Ici, tu copies le bon symbole pour Yahoo (le terminal) et pour TradingView (le graphique).
""",
    # ------------------------------------------------------------------ marchés
    "marches": """
**Ce que ça fait** : compare plusieurs marchés en même temps : combien ils ont monté ou baissé, à quel point ils sont agités, et s'ils bougent ensemble.

**Exemple** : tu mets le S&P 500, l'or et le pétrole. Tu vois que l'or a monté pendant que les actions baissaient.

**Pourquoi c'est utile** : c'est le point de départ d'une analyse macro : comprendre ce qui bouge avant de chercher pourquoi.
""",
    "marches_perf": """
**Ce que ça fait** : affiche le rendement de chaque actif sur 1 mois, 3 mois, depuis le 1er janvier et sur 1 an. Le graphique « base 100 » part de 100 pour tous.

**Exemple** : l'or passe de 100 à 115 sur le graphique : il a gagné 15 % sur la période, peu importe son prix en dollars.

**Pourquoi c'est utile** : on peut comparer un actif à 5 000 $ et un autre à 1,35 $ sur la même échelle.
""",
    "marches_risque": """
**Ce que ça fait** : la **volatilité** mesure l'ampleur des mouvements (plus elle est haute, plus ça bouge). La **corrélation** (de −1 à +1) dit si deux actifs bougent ensemble.

**Exemple** : volatilité de 15 % = environ 2 années sur 3, le rendement reste à ±15 % de la moyenne. Corrélation de −0,3 entre actions et or = ils ont tendance à aller en sens inverse.

**Pourquoi c'est utile** : deux actifs peu corrélés se protègent mutuellement dans un portefeuille.
""",
    "marches_detail": """
**Ce que ça fait** : graphique en chandeliers d'un actif, avec ses moyennes mobiles de 50 et 200 jours (le prix moyen des 50 ou 200 derniers jours).

**Exemple** : un prix au-dessus de sa moyenne de 200 jours décrit une tendance haussière de long terme.

**Pourquoi c'est utile** : situer le prix actuel dans sa tendance. C'est du contexte, pas un signal d'achat.
""",
    # ------------------------------------------------------------------ comparateur
    "cmp": """
**Ce que ça fait** : met deux actifs face à face, calcule des formules entre symboles (comme sur TradingView) et affiche le graphique TradingView.

**Exemple** : le ratio or/argent (`GC=F / SI=F`) indique combien d'onces d'argent il faut pour acheter une once d'or.

**Pourquoi c'est utile** : beaucoup d'idées d'analyse viennent d'une **relation** entre deux prix, pas d'un prix seul.
""",
    "cmp_deux": """
**Ce que ça fait** : superpose deux actifs (base 100), calcule leur **ratio**, leur **corrélation glissante** (sur 60 jours) et leur **bêta** (de combien A bouge quand B bouge de 1 %).

**Exemple** : MU contre SOXX : un ratio qui monte veut dire que Micron fait mieux que l'ensemble des semi-conducteurs.

**Pourquoi c'est utile** : savoir si une action surperforme son secteur, ou si deux actifs ont cessé de bouger ensemble.
""",
    "cmp_formule": """
**Ce que ça fait** : calcule n'importe quelle formule entre tickers, jour par jour : `+ - * /`, puissances et parenthèses.

**Exemples** : `GC=F / SI=F` (ratio or/argent) · `CL=F - BZ=F` (écart WTI-Brent) · `(AAPL + MSFT + NVDA) / 3` · `BTC-USD * USDCAD=X` (bitcoin en CAD).

**Attention** : mets des espaces autour du signe moins entre deux tickers (`AAPL - MSFT`), car `BTC-USD` est un seul ticker.

**Pourquoi c'est utile** : tester une idée (un écart qui s'élargit, un ratio extrême) en quelques secondes.
""",
    "cmp_tv": """
**Ce que ça fait** : affiche les graphiques interactifs officiels de TradingView : **1, 2 ou 4 graphiques** à la fois, chacun avec un second symbole superposé si tu veux.

**Réglages** : dans *Réglages de l'affichage*, choisis le style (chandeliers, Heikin Ashi, ligne…), l'intervalle, les indicateurs (RSI, MACD, Bollinger…) et leur **période** (ex. RSI 9 au lieu de 14), les **couleurs des bougies**, du fond et de la grille, les barres d'outils et la taille des graphiques. La couleur des lignes d'indicateurs, elle, ne peut pas être enregistrée (limite de TradingView).

**Exemple** : 4 graphiques pour suivre en même temps l'or, le S&P 500, le TSX et USD/CAD.

**Pourquoi c'est utile** : la meilleure interface de graphique gratuite. Les réglages de base sont les mêmes pour tous les visiteurs ; ce que tu changes ne vaut que pour ta visite. Les symboles TradingView ne s'écrivent pas comme ceux de Yahoo (voir le Répertoire).
""",
    # ------------------------------------------------------------------ portefeuille
    "port": """
**Ce que ça fait** : mesure le risque d'un portefeuille et cherche la meilleure répartition entre ses actifs. Un second onglet donne le **niveau de risque officiel** d'un FNB ou d'un portefeuille.

**Exemple** : 5 actifs, 10 000 $ : le terminal te dit combien tu pourrais perdre un mauvais jour et quels poids réduisent ce risque.

**Pourquoi c'est utile** : c'est le cœur du métier de gestionnaire de portefeuille : ne pas seulement choisir des actifs, mais les combiner.
""",
    "port_mu": """
**Ce que ça fait** : les rendements attendus (μ) sont ce que tu crois que chaque actif rapportera par année. La moyenne passée est pré-remplie.

**Exemple** : Nvidia a fait +60 % par an dans le passé. Le croire pour l'avenir mettrait presque tout ton argent dessus. Une hypothèse de 12 % est plus prudente.

**Pourquoi c'est utile** : c'est TON hypothèse qui guide l'optimisation. C'est là que ton analyse entre dans les calculs.
""",
    "port_opt": """
**Ce que ça fait** : propose des répartitions. **Variance minimale** = le moins risqué possible. **Sharpe maximal** = le meilleur rendement pour chaque unité de risque. **Manuel** = tes propres poids.

**Exemple** : 50 % actions et 50 % obligations peut être moins risqué que 100 % obligations si les deux bougent en sens inverse.

**Pourquoi c'est utile** : voir si ta répartition intuitive est loin de la meilleure possible (la « frontière efficiente »).
""",
    "port_var": """
**Ce que ça fait** : la **VaR** dit combien tu peux perdre dans 95 % (ou 99 %) des cas. La **CVaR** dit combien tu perds en moyenne dans les pires cas restants.

**Exemple** : VaR 95 % de 2 % sur 10 000 $ = 95 jours sur 100, tu ne perds pas plus de 200 $. Les 5 autres jours, la CVaR dit que tu perds en moyenne 280 $.

**Pourquoi c'est utile** : c'est la mesure de risque utilisée par les banques et les gestionnaires. Quatre méthodes sont comparées : un grand écart veut dire que les grosses pertes sont plus fréquentes que prévu.
""",
    "port_kupiec": """
**Ce que ça fait** : vérifie si la VaR a fonctionné dans le passé. On compte les jours où la perte a dépassé la VaR.

**Exemple** : sur 1 000 jours avec une VaR 95 %, on attend environ 50 dépassements. S'il y en a 70, le test « rejette » la VaR : elle sous-estime le risque.

**Pourquoi c'est utile** : une mesure de risque non vérifiée peut donner un faux sentiment de sécurité.
""",
    "port_niveau": """
**Ce que ça fait** : calcule le niveau de risque d'un FNB, d'un titre ou de ton portefeuille avec la **méthode officielle canadienne** (ACVM) : l'écart-type des rendements mensuels sur 10 ans.

**Grille** : moins de 6 % = Faible · 6-11 % = Faible à moyen · 11-16 % = Moyen · 16-20 % = Moyen à élevé · 20 % et plus = Élevé.

**Exemple** : un FNB d'obligations canadiennes comme XBB.TO se classe généralement dans le bas de la grille, un FNB 100 % actions comme XEQT.TO vers le milieu, et une action technologique seule souvent en « Élevé ». Le résultat exact dépend des 10 dernières années.

**Pourquoi c'est utile** : c'est le niveau imprimé dans l'Aperçu du fonds que les conseillers remettent aux clients. Tu peux vérifier un FNB ou classer ton propre portefeuille de la même façon.
""",
    # ------------------------------------------------------------------ fondamental
    "fa": """
**Ce que ça fait** : récupère les états financiers d'une entreprise, calcule ses ratios et t'aide à estimer sa valeur. La conclusion, c'est toi qui l'écris.

**Exemple** : Apple : marge nette, rendement des capitaux propres, P/E, puis un DCF avec tes propres hypothèses de croissance.

**Pourquoi c'est utile** : passer de « j'aime cette entreprise » à « voici les chiffres qui justifient mon opinion ».
""",
    "fa_etats": """
**Ce que ça fait** : montre les chiffres bruts des 6 derniers exercices : revenus, bénéfices, actifs, dettes, flux de trésorerie.

**Exemple** : des revenus qui passent de 100 à 150 milliards en 5 ans = croissance d'environ 8,4 % par an.

**Pourquoi c'est utile** : tous les ratios viennent de ces chiffres. Si un ratio semble bizarre, la réponse est ici.
""",
    "fa_ratios": """
**Ce que ça fait** : transforme les chiffres en ratios comparables : rentabilité (ROE, marges), liquidité (peut-elle payer ses dettes à court terme ?), endettement.

**Exemple** : ROE de 20 % = l'entreprise gagne 20 cents par année pour chaque dollar des actionnaires. DuPont explique si ça vient des marges, des ventes ou de la dette.

**Pourquoi c'est utile** : comparer deux entreprises de tailles très différentes.
""",
    "fa_dcf": """
**Ce que ça fait** : les multiples (P/E…) disent combien le marché paie. Le **DCF** estime ce que l'entreprise vaut selon l'argent qu'elle générera dans le futur, ramené à aujourd'hui.

**Exemple** : prix 150 $, BPA 6 $ → P/E de 25 : tu paies 25 ans de bénéfices actuels. Le DCF te dit si la croissance attendue justifie ce prix.

**Pourquoi c'est utile** : le tableau de sensibilité montre que la valeur change beaucoup selon tes hypothèses. Un DCF donne une **fourchette**, pas un prix exact.
""",
    "fa_carnet": """
**Ce que ça fait** : un espace pour écrire ta thèse, tes catalyseurs, tes risques et ta conclusion. Les champs sont vides exprès.

**Exemple** : « J'achèterais à moins de 140 $ parce que… ; ma thèse est invalidée si les marges baissent deux trimestres de suite. »

**Pourquoi c'est utile** : un analyste est payé pour son raisonnement, pas pour les calculs. Ton texte est inclus dans l'export Excel.
""",
    "fa_export": """
**Ce que ça fait** : crée un fichier Excel avec les états, les ratios, le DCF, ton carnet et un onglet de métadonnées (date, sources).

**Pourquoi c'est utile** : garder une trace de ton analyse et la partager. Les métadonnées permettent à quelqu'un d'autre de vérifier tes chiffres.
""",
    # ------------------------------------------------------------------ options
    "opt": """
**Ce que ça fait** : analyse les options (droit d'acheter ou de vendre un actif à un prix fixé). Le prix des options révèle les mouvements que le marché **anticipe**.

**Exemple** : un call Apple au prix d'exercice de 200 $ prend de la valeur si Apple monte au-dessus de 200 $.

**Pourquoi c'est utile** : la volatilité implicite est la seule mesure du risque **futur** attendu par le marché.
""",
    "opt_chaine": """
**Ce que ça fait** : affiche toutes les options d'un sous-jacent pour une échéance, avec leur volatilité implicite et leurs « grecques » (sensibilités).

**Exemple** : delta 0,6 = l'option gagne environ 0,60 $ quand l'action monte de 1 $. Theta −0,05 = elle perd 5 cents par jour qui passe.

**Pourquoi c'est utile** : le « smile » montre que les puts de protection coûtent plus cher : les investisseurs craignent davantage une baisse qu'une hausse.
""",
    "opt_calc": """
**Ce que ça fait** : calcule le prix théorique d'une option avec le modèle de Black-Scholes, pour n'importe quel actif.

**Exemple** : action à 42 $, prix d'exercice 40 $, 6 mois, taux 10 %, volatilité 20 % → call à 4,76 $ (exemple classique du manuel de Hull).

**Pourquoi c'est utile** : comprendre comment chaque paramètre change la valeur d'une option, en le modifiant toi-même.
""",
    # ------------------------------------------------------------------ taux
    "taux": """
**Ce que ça fait** : montre les taux d'intérêt des gouvernements américain et canadien selon leur durée (la « courbe des taux »), et calcule le risque d'une obligation.

**Exemple** : si le 2 ans paie plus que le 10 ans (courbe inversée), le marché anticipe des baisses de taux, souvent liées à un ralentissement.

**Pourquoi c'est utile** : les taux influencent la valeur de tous les autres actifs, y compris le WACC de ton DCF.
""",
    "taux_courbe": """
**Ce que ça fait** : compare la courbe des taux d'aujourd'hui avec celle d'il y a 1 et 2 ans.

**Exemple** : une courbe qui monte de gauche à droite est « normale » : on exige plus pour prêter longtemps.

**Pourquoi c'est utile** : voir si le marché anticipe une hausse ou une baisse des taux directeurs.
""",
    "taux_calc": """
**Ce que ça fait** : calcule le prix d'une obligation à partir de son rendement (ou l'inverse), puis sa **duration** : de combien son prix baisse si les taux montent de 1 %.

**Exemple** : obligation 10 ans, coupon 4 %, rendement 4,5 % : duration modifiée 8,1 → si les taux montent de 1 %, le prix baisse d'environ 8 %.

**Pourquoi c'est utile** : comprendre pourquoi les obligations longues ont autant chuté en 2022.
""",
    # ------------------------------------------------------------------ spreads
    "spr": """
**Ce que ça fait** : calcule l'écart (« spread ») entre deux taux, en points de base (1 pb = 0,01 %), et le situe dans son historique.

**Exemple** : Canada 10 ans à 3,20 % et US 10 ans à 4,10 % → spread de −90 pb : le Canada emprunte 0,90 % moins cher que les États-Unis.

**Pourquoi c'est utile** : les spreads résument en un chiffre les anticipations du marché : récession (pente), écart de politique monétaire (pays), peur des faillites (crédit).
""",
    "spr_deux": """
**Ce que ça fait** : choisis deux taux, le terminal trace leur écart dans le temps et calcule son **z-score** : à combien d'écarts-types il est de sa moyenne.

**Exemple** : un z-score de +2,1 veut dire que l'écart est inhabituellement large, ce qui arrive environ 2 % du temps si les écarts étaient distribués normalement.

**Pourquoi c'est utile** : repérer quand une relation entre deux taux est extrême, et se demander pourquoi.
""",
    "spr_pred": """
**Ce que ça fait** : les spreads les plus suivis par les professionnels, prêts à l'emploi.

**Exemples** : **pente 10 ans − 2 ans** (négative = courbe inversée, souvent avant une récession) · **Canada − US** (écart de politique monétaire, influence le dollar canadien) · **nominal − réel** (inflation anticipée) · **High Yield − IG** (peur des faillites).

**Pourquoi c'est utile** : un tableau de bord macro en un clic.
""",
    "spr_gspread": """
**Ce que ça fait** : calcule le **G-spread** d'une obligation d'entreprise : son rendement moins celui d'une obligation d'État de même durée (interpolée sur la courbe du jour).

**Exemple** : obligation de 7 ans à 5,30 %, État 7 ans à 4,12 % → G-spread de 118 pb. C'est la prime exigée pour le risque de défaut de l'entreprise.

**Pourquoi c'est utile** : comparer le risque de crédit de deux émetteurs, peu importe leurs échéances.
""",
}


def aide(cle: str, libelle: str = "?") -> None:
    """Bouton « ? » qui ouvre une bulle d'explication.
    Si la clé n'existe pas, rien ne s'affiche (aucune erreur pour l'utilisateur)."""
    texte = AIDE.get(cle)
    if texte:
        with st.popover(libelle, help="Qu'est-ce que c'est ? Clique pour une explication simple avec un exemple."):
            st.markdown(texte)


def titre(texte: str, cle_aide: str, code: str | None = None, sous_titre: str | None = None) -> None:
    """En-tête de section façon terminal : code de fonction, titre, bouton « ? »."""
    gauche, droite = st.columns([14, 1], vertical_alignment="center")
    with gauche:
        prefixe = f"<span class='tq-code'>{code}</span> " if code else ""
        st.markdown(f"<h2 class='tq-titre'>{prefixe}{texte}</h2>", unsafe_allow_html=True)
    with droite:
        aide(cle_aide)
    if sous_titre:
        st.caption(sous_titre)


def sous_titre(texte: str, cle_aide: str) -> None:
    """Sous-titre d'onglet ou de bloc avec son propre bouton « ? »."""
    gauche, droite = st.columns([14, 1], vertical_alignment="center")
    with gauche:
        st.markdown(f"<h4 class='tq-sous-titre'>{texte}</h4>", unsafe_allow_html=True)
    with droite:
        aide(cle_aide)
