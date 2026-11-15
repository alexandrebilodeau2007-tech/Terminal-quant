"""Devises suivies et pays qui les font bouger."""

CURRENCIES = {
    "USD": {"name": "Dollar américain", "flag": "🇺🇸", "countries": ["US"], "bank": "Federal Reserve (Fed)",
            "target": 2.0, "index": "CAPITALCOM:DXY",
            "keywords": ["fed ", "fomc", "federal reserve", "treasury", "us cpi", "nonfarm", "non-farm", "dollar", "usd", "u.s. "]},
    "EUR": {"name": "Euro", "flag": "🇪🇺", "countries": ["EU", "DE", "FR", "IT", "ES"], "bank": "Banque centrale européenne (BCE)",
            "target": 2.0, "index": "FX:EURUSD",
            "keywords": ["ecb", "eurozone", "euro area", "euro zone", "germany", "german", "france", "italy", "eur/", "eurusd", "bund"]},
    "GBP": {"name": "Livre sterling", "flag": "🇬🇧", "countries": ["GB"], "bank": "Bank of England (BoE)",
            "target": 2.0, "index": "FX:GBPUSD",
            "keywords": ["boe", "bank of england", " uk ", "britain", "british", "gbp", "sterling", "cable"]},
    "JPY": {"name": "Yen japonais", "flag": "🇯🇵", "countries": ["JP"], "bank": "Bank of Japan (BoJ)",
            "target": 2.0, "index": "FX:USDJPY",
            "keywords": ["boj", "bank of japan", "japan", "japanese", "jpy", "yen", "usd/jpy", "usdjpy"]},
    "CAD": {"name": "Dollar canadien", "flag": "🇨🇦", "countries": ["CA"], "bank": "Banque du Canada (BdC)",
            "target": 2.0, "index": "FX:USDCAD",
            "keywords": ["boc", "bank of canada", "canada", "canadian", "cad", "loonie", "usd/cad", "usdcad"]},
    "AUD": {"name": "Dollar australien", "flag": "🇦🇺", "countries": ["AU"], "bank": "Reserve Bank of Australia (RBA)",
            "target": 2.5, "index": "FX:AUDUSD",
            "keywords": ["rba", "reserve bank of australia", "australia", "australian", "aud", "aussie"]},
    "NZD": {"name": "Dollar néo-zélandais", "flag": "🇳🇿", "countries": ["NZ"], "bank": "Reserve Bank of New Zealand (RBNZ)",
            "target": 2.0, "index": "FX:NZDUSD",
            "keywords": ["rbnz", "new zealand", "nzd", "kiwi"]},
    "CHF": {"name": "Franc suisse", "flag": "🇨🇭", "countries": ["CH"], "bank": "Banque nationale suisse (BNS/SNB)",
            "target": 1.0, "index": "FX:USDCHF",
            "keywords": ["snb", "swiss national bank", "switzerland", "swiss", "chf", "franc"]},
    "CNY": {"name": "Yuan chinois", "flag": "🇨🇳", "countries": ["CN"], "bank": "People's Bank of China (PBoC)",
            "target": 3.0, "index": "FX:USDCNH",
            "keywords": ["pboc", "people's bank of china", "china", "chinese", "yuan", "cny", "cnh"]},
}

COUNTRY_TO_CCY = {c: ccy for ccy, d in CURRENCIES.items() for c in d["countries"]}
ALL_COUNTRIES = list(COUNTRY_TO_CCY.keys())

# Mots-clés pour reconnaître les décisions de taux dans le calendrier
RATE_KEYWORDS = ["interest rate decision", "rate decision", "deposit facility rate", "main refinancing rate",
                 "cash rate", "bank rate", "policy rate", "loan prime rate", "ocr", "boj interest rate",
                 "fed interest rate", "overnight rate"]

# Indicateurs où une hausse est NÉGATIVE pour la devise (lecture brute)
INVERSE_KEYWORDS = ["unemployment", "jobless", "claims", "claimant", "continuing", "trade deficit"]

# Indicateurs clés affichés en priorité dans la fiche pays
KEY_INDICATOR_HINTS = ["interest rate", "cash rate", "bank rate", "deposit", "inflation rate", "cpi", "core",
                       "pce", "gdp", "unemployment", "non farm", "payroll", "employment change", "pmi",
                       "retail sales", "wage", "earnings", "ppi", "trade balance", "consumer confidence",
                       "sentiment", "ifo", "zew", "tankan"]
