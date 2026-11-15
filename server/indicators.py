"""Fiche descriptive de chaque événement, façon « Specs » de Forex Factory.

Chaque entrée : expression régulière sur le titre, catégorie, ce que ça mesure,
pourquoi les traders s'y intéressent et, au besoin, une source précise.
"""
import re

from .countries import CURRENCIES, INVERSE_KEYWORDS

CATEGORIES = ["Croissance", "Inflation", "Emploi", "Banque centrale", "Obligations", "Logement",
              "Sondage conso.", "Sondage entreprises", "Discours", "Divers"]

STATS = {"USD": "BLS / BEA / Census (gouv. américain)", "EUR": "Eurostat / instituts nationaux",
         "GBP": "Office for National Statistics (ONS)", "JPY": "Statistics Bureau / Cabinet Office (Japon)",
         "CAD": "Statistique Canada", "AUD": "Australian Bureau of Statistics (ABS)",
         "NZD": "Stats NZ", "CHF": "Office fédéral de la statistique (OFS)",
         "CNY": "National Bureau of Statistics (Chine)"}

# (regex, catégorie, mesure, pourquoi, source facultative)
SPECS = [
    (r"jobless claims|initial claims|continuing claims|unemployment claims", "Emploi",
     "Nombre de personnes qui ont fait une demande d'assurance-chômage pour la première fois (semaine précédente).",
     "Donnée la plus rapide sur l'emploi ; une hausse durable annonce souvent un ralentissement.", "Department of Labor"),
    (r"unemployment change|claimant count", "Emploi", "Variation du nombre de personnes qui touchent des prestations de chômage.",
     "Mesure rapide de la santé du marché du travail.", None),
    (r"non.?farm|\bnfp\b|employment change|payrolls", "Emploi",
     "Variation du nombre de personnes en emploi, hors secteur agricole aux États-Unis.",
     "Création d'emplois = consommation future. C'est la donnée qui fait le plus bouger le marché chaque mois.", None),
    (r"\badp\b", "Emploi", "Variation de l'emploi privé selon la paie d'ADP, deux jours avant le NFP.",
     "Sert d'avant-goût au NFP, mais la corrélation mois par mois est faible.", "ADP"),
    (r"unemployment rate|jobless rate", "Emploi", "Pourcentage de la population active sans emploi qui cherche activement.",
     "Le chômage pèse sur la consommation et guide directement le mandat des banques centrales.", None),
    (r"jolts|job openings", "Emploi", "Nombre de postes vacants (enquête JOLTS).",
     "Mesure la demande de main-d'œuvre ; la Fed suit le ratio postes vacants / chômeurs.", "BLS"),
    (r"average (hourly )?earnings|wage|labou?r cost|average cash earnings", "Emploi",
     "Variation de la rémunération moyenne des salariés.",
     "Les salaires alimentent l'inflation des services : clé pour les banques centrales.", None),
    (r"employment|labou?r force|participation rate|pay growth", "Emploi", "Variation de l'emploi ou de la population active.",
     "La création d'emplois soutient la consommation et la croissance.", None),

    (r"core (cpi|consumer price|inflation)|trimmed|cpi median|cpi trim", "Inflation",
     "Variation des prix à la consommation, hors alimentation et énergie (ou mesure « tronquée »).",
     "Inflation de fond : c'est elle qui guide les décisions de taux.", None),
    (r"\bcpi\b|consumer price|inflation rate|\bhicp\b", "Inflation",
     "Variation des prix d'un panier de biens et services achetés par les consommateurs.",
     "Les consommateurs représentent la majorité de l'activité ; l'inflation dicte la politique monétaire.", None),
    (r"\bpce\b|personal consumption expenditure", "Inflation",
     "Variation des prix des dépenses de consommation (indice PCE).",
     "Mesure d'inflation préférée de la Fed, surtout le PCE de base (core).", "Bureau of Economic Analysis"),
    (r"\bppi\b|producer price|input price|output price", "Inflation",
     "Variation des prix payés ou reçus par les producteurs.",
     "Indicateur avancé de l'inflation à la consommation : les coûts finissent par être refilés aux clients.", None),
    (r"import price|export price", "Inflation", "Variation des prix des biens importés ou exportés.",
     "Influence l'inflation intérieure, surtout pour les économies très ouvertes.", None),
    (r"services inflation|retail price index|\brpix?\b|raw materials|commodity prices|food price", "Inflation",
     "Variation d'une autre mesure de prix (services, RPI, matières premières).",
     "Complète la lecture de l'inflation suivie par la banque centrale.", None),
    (r"inflation expectations|\bdeflator\b", "Inflation", "Inflation attendue ou déflateur des prix.",
     "Des anticipations qui dérapent forcent les banques centrales à réagir.", None),

    (r"\bgdp\b|gross domestic", "Croissance", "Valeur de tous les biens et services produits dans l'économie (variation).",
     "Mesure la plus large de la santé de l'économie, mais publiée avec du retard.", None),
    (r"retail sales|core retail", "Croissance", "Variation de la valeur totale des ventes au détail.",
     "Principal indicateur de la consommation, moteur de la croissance.", None),
    (r"industrial (production|output)|manufacturing production|factory output", "Croissance",
     "Variation du volume produit par les usines, mines et services publics.",
     "Réagit vite aux cycles ; utilisé pour dater les récessions.", None),
    (r"durable goods|factory orders|machinery orders|core machinery", "Croissance",
     "Variation de la valeur des nouvelles commandes de biens durables.",
     "Donne un aperçu des investissements et de la production à venir.", None),
    (r"capacity utili|business inventories|retail inventories|fixed asset|motor vehicle|redbook|productivity|leading index|tertiary industry|\bpsi\b|\bpmi\b.*services nz", "Croissance",
     "Indicateur d'activité (investissement, stocks, utilisation des capacités, indice avancé).",
     "Donne une lecture complémentaire de la vigueur de l'économie.", None),
    (r"trade balance|balance of trade|current account|exports|imports", "Croissance",
     "Différence entre les exportations et les importations de biens et services.",
     "La demande étrangère pour les biens d'un pays crée de la demande pour sa devise.", None),
    (r"\bism\b", "Sondage entreprises",
     "Sondage ISM auprès des directeurs d'achat américains (50 = ligne de partage).",
     "Le premier gros chiffre du mois sur l'activité ; ses sous-indices prix et emploi sont aussi suivis.", "ISM"),
    (r"\bpmi\b|purchasing managers", "Sondage entreprises",
     "Sondage auprès des directeurs d'achat : au-dessus de 50 = expansion, en dessous = contraction.",
     "Publié tôt, il réagit vite aux changements de conjoncture ; très suivi en version « flash ».", "S&P Global / HCOB"),
    (r"\bifo\b", "Sondage entreprises", "Climat des affaires selon ~9 000 entreprises allemandes.",
     "L'Allemagne pèse ~25 % du PIB de la zone euro : bon indicateur avancé.", "Ifo Institute"),
    (r"\bzew\b", "Sondage entreprises", "Sentiment économique d'environ 350 analystes financiers allemands.",
     "Publié avant l'Ifo ; indicateur avancé de la croissance allemande.", "ZEW"),
    (r"tankan", "Sondage entreprises", "Grande enquête trimestrielle de la BoJ sur le climat des affaires.",
     "Influence directement la lecture de la Banque du Japon.", "Banque du Japon"),
    (r"business (confidence|climate|sentiment|survey)|empire state|philly|philadelphia fed|richmond|kc fed|kansas fed|chicago pmi|nab|\bcbi\b|cfib", "Sondage entreprises",
     "Sondage de confiance ou d'activité des entreprises.",
     "Les entreprises réagissent vite à la conjoncture : indicateur avancé.", None),
    (r"consumer (confidence|sentiment|climate)|michigan|gfk|westpac", "Sondage conso.",
     "Niveau de confiance des ménages dans l'économie.",
     "Des ménages confiants dépensent plus ; indicateur avancé de la consommation.", None),
    (r"housing starts|building (permits|approvals|consents)|construction", "Logement",
     "Nombre de nouvelles constructions ou de permis de bâtir.",
     "La construction entraîne beaucoup d'activité ; très sensible aux taux d'intérêt.", None),
    (r"home sales|house price|housing (price|market)|hpi|nationwide|halifax|rightmove|mortgage|\bmba\b|nahb|case.?shiller|pending home", "Logement",
     "Ventes ou prix des logements.",
     "L'immobilier reflète la confiance des ménages et réagit vite aux taux.", None),

    (r"rate decision|interest rate|cash rate|bank rate|refinancing|deposit (facility )?rate|policy rate|\bloan prime\b|\blpr\b", "Banque centrale",
     "Taux directeur fixé par la banque centrale.",
     "Les taux sont le principal moteur de la valeur d'une devise ; le ton du communiqué compte autant que la décision.", "Banque centrale"),
    (r"minutes|monetary policy (statement|report|summary)|press conference|policy statement|summary of opinions|beige book|economic projections|rate statement", "Banque centrale",
     "Communication officielle de la banque centrale (communiqué, minutes, projections).",
     "Indices sur les prochaines décisions de taux : on lit le ton hawkish ou dovish.", "Banque centrale"),
    (r"balance sheet|monetary conditions|financial stability|reserve assets|foreign currency liquidity", "Banque centrale",
     "Bilan, conditions monétaires ou stabilité financière publiés par la banque centrale.",
     "Renseigne sur l'orientation de la politique monétaire et les risques financiers.", "Banque centrale"),
    (r"speaks?|speech|testif|testimony|hearing|remarks|parliament|semi-annual", "Discours",
     "Discours ou témoignage d'un responsable (souvent de la banque centrale).",
     "Un ton plus hawkish que prévu soutient la devise, un ton dovish la pénalise.", "Banque centrale"),
    (r"\btic\b|capital flows|foreign securities|stock investment|foreign direct investment|public sector net", "Obligations",
     "Flux de capitaux étrangers ou besoins d'emprunt du gouvernement.",
     "Montre la demande étrangère pour les actifs du pays et le financement de sa dette.", None),
    (r"auction|bond|bill|gilt|bund|\bjgb\b|treasury|yield", "Obligations",
     "Rendement moyen et demande lors d'une adjudication d'obligations d'État.",
     "Une forte demande et des rendements en hausse peuvent soutenir la devise.", "Trésor / agence de la dette"),
    (r"crude|oil|natural gas|eia|api weekly", "Divers", "Variation des stocks de pétrole ou de gaz.",
     "Influence le prix du pétrole et donc les devises liées aux matières premières (CAD, NOK).", "EIA / API"),
    (r"cftc|speculative", "Divers", "Positions nettes des spéculateurs sur les contrats à terme (COT).",
     "Montre le positionnement des grands spéculateurs.", "CFTC"),
    (r"holiday|bank holiday", "Divers", "Jour férié : marchés locaux fermés.",
     "Liquidité réduite ; mouvements parfois erratiques.", None),
]
_COMPILED = [(re.compile(rx, re.I), cat, mes, why, src) for rx, cat, mes, why, src in SPECS]


def classify(title: str) -> str:
    for rx, cat, *_ in _COMPILED:
        if rx.search(title or ""):
            return cat
    return "Divers"


def _inverse(title):
    t = (title or "").lower()
    return any(k in t for k in INVERSE_KEYWORDS)


def usual_effect(title: str, category: str) -> str:
    if category == "Discours":
        return "Ton plus hawkish que prévu = bon pour la devise"
    if category == "Banque centrale":
        return "Taux ou ton plus élevé que prévu = bon pour la devise"
    if re.search(r"holiday", title or "", re.I):
        return "—"
    if re.search(r"crude|oil|natural gas", title or "", re.I):
        return "Stocks plus élevés que prévu = négatif pour le pétrole (et le CAD)"
    if _inverse(title):
        return "Réel < prévision = bon pour la devise"
    return "Réel > prévision = bon pour la devise"


def describe(title: str, currency: str) -> dict:
    for rx, cat, mes, why, src in _COMPILED:
        if rx.search(title or ""):
            break
    else:
        cat, mes, why, src = "Divers", "Donnée économique.", "Peut faire bouger la devise si l'écart avec la prévision est important.", None
    if src == "Banque centrale":
        src = (CURRENCIES.get(currency) or {}).get("bank", "Banque centrale")
    if re.search(r"holiday", title or "", re.I):
        src = "—"
    return {"category": cat, "source": src or STATS.get(currency, "Agence statistique nationale"),
            "measures": mes, "usual_effect": usual_effect(title, cat), "why": why}
