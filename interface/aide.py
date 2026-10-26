"""
interface/aide.py — Textes des boutons d'aide « ? » (affichés en anglais).

Chaque texte suit le même plan, pour être compris sans connaissances en finance :
    What it does  ->  Concrete example  ->  Why it is useful.
Les textes sont centralisés ici pour être faciles à relire et à corriger.
"""

from __future__ import annotations

import streamlit as st

AIDE: dict[str, str] = {
    # ------------------------------------------------------------------ général
    "accueil": """
**What it is**: the home dashboard. It shows today's major markets and gives access to every function.

**Example**: you arrive in the morning and see the S&P 500 at −1.2% and gold at +0.8%: investors are seeking protection.

**Why it is useful**: in 10 seconds you know the market's "mood" before starting an analysis.
""",
    "commande": """
**What it is**: a command bar, like on a Bloomberg terminal. Type a code and you go straight to the right function.

**Examples**: `FA AAPL` opens Apple's fundamental analysis · `OPT SPY` opens SPY options · `CMP GC=F SI=F` compares gold and silver · `TKR` opens the directory.

**Why it is useful**: much faster than clicking through menus when you know what you are looking for.
""",
    "repertoire": """
**What it is**: the list of the main tickers, sorted by family (stocks, indices, commodities, forex, crypto, bonds, options).

**Example**: you want to analyze oil but do not know its symbol: family "Commodities", row "WTI crude oil", ticker `CL=F`.

**Why it is useful**: a mistyped ticker returns no data. Here you copy the right symbol for Yahoo (the terminal) and for TradingView (the charts).
""",
    # ------------------------------------------------------------------ marchés
    "marches": """
**What it does**: compares several markets at once: how much they rose or fell, how volatile they are, and whether they move together.

**Example**: add the S&P 500, gold and oil. You see that gold rose while stocks fell.

**Why it is useful**: it is the starting point of any macro analysis: understand what is moving before looking for why.
""",
    "marches_perf": """
**What it does**: shows each asset's return over 1 month, 3 months, year to date and 1 year. The "rebased to 100" chart starts every asset at 100.

**Example**: gold goes from 100 to 115 on the chart: it gained 15% over the period, whatever its price in dollars.

**Why it is useful**: you can compare an asset priced at $5,000 and another at $1.35 on the same scale.
""",
    "marches_risque": """
**What it does**: **volatility** measures how large the moves are (the higher, the more it swings). **Correlation** (from −1 to +1) tells whether two assets move together.

**Example**: 15% volatility = about 2 years out of 3, the return stays within ±15% of its average. A −0.3 correlation between stocks and gold = they tend to move in opposite directions.

**Why it is useful**: two weakly correlated assets protect each other in a portfolio.
""",
    "marches_detail": """
**What it does**: candlestick chart of one asset, with its 50-day and 200-day moving averages (the average price of the last 50 or 200 days).

**Example**: a price above its 200-day average describes a long-term uptrend.

**Why it is useful**: it places today's price within its trend. It is context, not a buy signal.
""",
    # ------------------------------------------------------------------ comparateur
    "cmp": """
**What it does**: puts two assets side by side, computes formulas between symbols (like on TradingView) and shows TradingView charts.

**Example**: the gold/silver ratio (`GC=F / SI=F`) tells how many ounces of silver buy one ounce of gold.

**Why it is useful**: many analysis ideas come from a **relationship** between two prices, not from a single price.
""",
    "cmp_deux": """
**What it does**: overlays two assets (rebased to 100), computes their **ratio**, their **rolling correlation** (over 60 days) and their **beta** (how much A moves when B moves 1%).

**Example**: MU vs SOXX: a rising ratio means Micron is beating the semiconductor sector as a whole.

**Why it is useful**: see whether a stock outperforms its sector, or whether two assets stopped moving together.
""",
    "cmp_formule": """
**What it does**: computes any formula between tickers, day by day: `+ - * /`, powers and parentheses.

**Examples**: `GC=F / SI=F` (gold/silver ratio) · `CL=F - BZ=F` (WTI-Brent spread) · `(AAPL + MSFT + NVDA) / 3` · `BTC-USD * USDCAD=X` (bitcoin in CAD).

**Careful**: put spaces around the minus sign between two tickers (`AAPL - MSFT`), because `BTC-USD` is a single ticker.

**Why it is useful**: test an idea (a widening spread, an extreme ratio) in seconds.
""",
    "cmp_tv": """
**What it does**: shows the official interactive TradingView charts: **1, 2 or 4 charts** at once, each with an optional second symbol overlaid.

**Settings**: in *Display settings*, choose the style (candles, Heikin Ashi, line…), the interval, the indicators (RSI, MACD, Bollinger…) and their **period** (e.g. RSI 9 instead of 14), the **candle colors**, background and grid, the toolbars and the chart size. Indicator line colors cannot be saved (a TradingView limitation).

**Charts-only window**: the *Open charts in a new window* button opens a page with only the charts, full width, using your current settings.

**Why it is useful**: the best free charting interface. The base settings are the same for every visitor; what you change only lasts for your visit. TradingView symbols are not written like Yahoo symbols (see the Directory).
""",
    # ------------------------------------------------------------------ portefeuille
    "port": """
**What it does**: measures a portfolio's risk and looks for the best allocation between its assets. A second tab gives the **official risk level** of an ETF or a portfolio.

**Example**: 5 assets, $10,000: the terminal tells you how much you could lose on a bad day and which weights reduce that risk.

**Why it is useful**: it is the core of a portfolio manager's job: not only picking assets, but combining them.
""",
    "port_mu": """
**What it does**: expected returns (μ) are what you believe each asset will return per year. The past average is pre-filled.

**Example**: Nvidia returned +60% a year in the past. Believing that for the future would put almost all your money in it. A 12% assumption is more prudent.

**Why it is useful**: YOUR assumption drives the optimization. This is where your analysis enters the calculations.
""",
    "port_opt": """
**What it does**: proposes allocations. **Minimum variance** = the least risky possible. **Maximum Sharpe** = the best return per unit of risk. **Manual** = your own weights.

**Example**: 50% stocks and 50% bonds can be less risky than 100% bonds if the two move in opposite directions.

**Why it is useful**: see whether your intuitive allocation is far from the best possible one (the "efficient frontier").
""",
    "port_var": """
**What it does**: **VaR** tells how much you can lose in 95% (or 99%) of cases. **CVaR** tells how much you lose on average in the remaining worst cases.

**Example**: a 95% VaR of 2% on $10,000 = 95 days out of 100, you do not lose more than $200. On the other 5 days, CVaR says you lose $280 on average.

**Why it is useful**: it is the risk measure used by banks and asset managers. Four methods are compared: a large gap means big losses are more frequent than expected.
""",
    "port_kupiec": """
**What it does**: checks whether the VaR worked in the past. It counts the days when the loss exceeded the VaR.

**Example**: over 1,000 days with a 95% VaR, about 50 breaches are expected. If there are 70, the test "rejects" the VaR: it underestimates risk.

**Why it is useful**: an unverified risk measure can give a false sense of safety.
""",
    "port_niveau": """
**What it does**: computes the risk level of an ETF, a security or your portfolio with the **official Canadian method** (CSA): the standard deviation of monthly returns over 10 years.

**Grid**: below 6% = Low · 6-11% = Low to medium · 11-16% = Medium · 16-20% = Medium to high · 20% and above = High.

**Example**: a Canadian bond ETF such as XBB.TO usually sits at the bottom of the grid, a 100% equity ETF such as XEQT.TO around the middle, and a single tech stock often at "High". The exact result depends on the last 10 years.

**Why it is useful**: it is the level printed in the Fund Facts that advisors give to clients. You can check an ETF or rate your own portfolio the same way.
""",
    # ------------------------------------------------------------------ fondamental
    "fa": """
**What it does**: retrieves a company's financial statements, computes its ratios and helps you estimate its value. You write the conclusion.

**Example**: Apple: net margin, return on equity, P/E, then a DCF with your own growth assumptions.

**Why it is useful**: move from "I like this company" to "here are the numbers that justify my view".
""",
    "fa_etats": """
**What it does**: shows the raw figures of the last 6 fiscal years: revenue, earnings, assets, debt, cash flows.

**Example**: revenue going from 100 to 150 billion in 5 years = growth of about 8.4% per year.

**Why it is useful**: every ratio comes from these figures. If a ratio looks odd, the answer is here.
""",
    "fa_ratios": """
**What it does**: turns the figures into comparable ratios: profitability (ROE, margins), liquidity (can it pay its short-term debts?), leverage.

**Example**: a 20% ROE = the company earns 20 cents a year for each dollar of shareholders' equity. DuPont explains whether it comes from margins, sales or debt.

**Why it is useful**: compare two companies of very different sizes.
""",
    "fa_dcf": """
**What it does**: multiples (P/E…) tell how much the market pays. The **DCF** estimates what the company is worth based on the cash it will generate in the future, brought back to today.

**Example**: price $150, EPS $6 → P/E of 25: you pay 25 years of current earnings. The DCF tells you whether expected growth justifies that price.

**Why it is useful**: the sensitivity table shows that the value changes a lot with your assumptions. A DCF gives a **range**, not an exact price.
""",
    "fa_carnet": """
**What it does**: a space to write your thesis, catalysts, risks and conclusion. The fields are empty on purpose.

**Example**: "I would buy below $140 because…; my thesis is invalidated if margins fall two quarters in a row."

**Why it is useful**: an analyst is paid for reasoning, not for calculations. Your text is included in the Excel export.
""",
    "fa_export": """
**What it does**: creates an Excel file with the statements, the ratios, the DCF, your notebook and a metadata sheet (date, sources).

**Why it is useful**: keep a record of your analysis and share it. The metadata lets someone else check your numbers.
""",
    # ------------------------------------------------------------------ options
    "opt": """
**What it does**: analyzes options (the right to buy or sell an asset at a set price). Option prices reveal the moves the market **expects**.

**Example**: an Apple call with a $200 strike gains value if Apple rises above $200.

**Why it is useful**: implied volatility is the only measure of the **future** risk expected by the market.
""",
    "opt_chaine": """
**What it does**: shows every option of an underlying for one expiration, with implied volatility and "Greeks" (sensitivities).

**Example**: delta 0.6 = the option gains about $0.60 when the stock rises $1. Theta −0.05 = it loses 5 cents per day.

**Why it is useful**: the "smile" shows that protective puts cost more: investors fear a drop more than a rise.
""",
    "opt_calc": """
**What it does**: computes an option's theoretical price with the Black-Scholes model, for any asset.

**Example**: stock at $42, strike $40, 6 months, 10% rate, 20% volatility → call at $4.76 (classic example from Hull's textbook).

**Why it is useful**: understand how each input changes an option's value by changing it yourself.
""",
    # ------------------------------------------------------------------ taux
    "taux": """
**What it does**: shows US and Canadian government interest rates by maturity (the "yield curve"), and computes a bond's risk.

**Example**: if the 2-year pays more than the 10-year (inverted curve), the market expects rate cuts, often tied to a slowdown.

**Why it is useful**: rates drive the value of every other asset, including the WACC in your DCF.
""",
    "taux_courbe": """
**What it does**: compares today's yield curve with the one from 1 and 2 years ago.

**Example**: a curve rising from left to right is "normal": lenders demand more to lend for longer.

**Why it is useful**: see whether the market expects policy rates to go up or down.
""",
    "taux_calc": """
**What it does**: computes a bond's price from its yield (or the reverse), then its **duration**: how much its price falls if rates rise 1%.

**Example**: 10-year bond, 4% coupon, 4.5% yield: modified duration 8.1 → if rates rise 1%, the price falls about 8%.

**Why it is useful**: understand why long bonds fell so much in 2022.
""",
    # ------------------------------------------------------------------ spreads
    "spr": """
**What it does**: computes the gap ("spread") between two yields, in basis points (1 bp = 0.01%), and places it within its history.

**Example**: Canada 10-year at 3.20% and US 10-year at 4.10% → spread of −90 bp: Canada borrows 0.90% cheaper than the United States.

**Why it is useful**: spreads sum up market expectations in one number: recession (slope), monetary policy gap (countries), default fears (credit).
""",
    "spr_deux": """
**What it does**: pick two yields; the terminal plots their spread over time and computes its **z-score**: how many standard deviations it is from its mean.

**Example**: a z-score of +2.1 means the spread is unusually wide, which would happen about 2% of the time if spreads were normally distributed.

**Why it is useful**: spot when a relationship between two yields is extreme, and ask why.
""",
    "spr_pred": """
**What it does**: the spreads professionals watch most, ready to use.

**Examples**: **10y − 2y slope** (negative = inverted curve, often before a recession) · **Canada − US** (monetary policy gap, drives the Canadian dollar) · **nominal − real** (expected inflation) · **High Yield − IG** (default fears).

**Why it is useful**: a one-click macro dashboard.
""",
    "spr_gspread": """
**What it does**: computes a corporate bond's **G-spread**: its yield minus the yield of a government bond of the same maturity (interpolated on today's curve).

**Example**: 7-year bond at 5.30%, government 7-year at 4.12% → G-spread of 118 bp. It is the premium demanded for the company's default risk.

**Why it is useful**: compare the credit risk of two issuers, whatever their maturities.
""",
}


def aide(cle: str, libelle: str = "?") -> None:
    """Bouton « ? » qui ouvre une bulle d'explication.
    Si la clé n'existe pas, rien ne s'affiche (aucune erreur pour l'utilisateur)."""
    texte = AIDE.get(cle)
    if texte:
        with st.popover(libelle, help="What is this? Click for a simple explanation with an example."):
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
