# Quant Terminal — multi-asset financial analysis terminal

A web terminal built with **Streamlit** and **Python** to **speed up the calculations** of a financial analysis:
portfolio risk, optimization, fundamental ratios, options, rates and bonds.

> **Philosophy: the terminal computes, the analyst concludes.**
> It produces no recommendation, no buy or sell signal, and executes no order.
> The investment thesis, the reasoning and the decision remain the user's.

A project by **Alexandre Bilodeau**.

---

## Contents

1. [What the terminal does](#1-what-the-terminal-does)
2. [Opening the terminal](#2-opening-the-terminal)
3. [User guide by section](#3-user-guide-by-section)
4. [Methodological choices](#4-methodological-choices)
5. [Guardrails: what the terminal refuses to do](#5-guardrails-what-the-terminal-refuses-to-do)
6. [Code architecture](#6-code-architecture)
7. [Tests](#7-tests)
8. [Contributing or modifying the code](#8-contributing-or-modifying-the-code)
9. [Known limitations and troubleshooting](#9-known-limitations-and-troubleshooting)

---

## 1. What the terminal does

The terminal is organized like a professional terminal: each function has a **code** (as on Bloomberg),
reachable from the top menu or from the **command bar** on the left.

| Code | Function | Content |
|---|---|---|
| `HOME` | **Home** | Today's markets, tiles to every function, data source status |
| `TKR` | **Ticker directory** | ~175 symbols by family (US and TSX stocks, indices, commodities, forex, crypto, ETFs, bonds, rates, option underlyings), with Yahoo and TradingView symbols, search and CSV export |
| `MKT` | **Multi-asset markets** | Performance (1 month, 3 months, year to date, 1 year), volatility, correlation matrix, candlesticks with moving averages |
| `CMP` | **Comparator & formulas** | Two symbols side by side (base 100, ratio, rolling correlation and beta) · ticker formulas as on TradingView (`GC=F / SI=F`, `CL=F - BZ=F`…) · embedded TradingView charts, also available in a **charts-only window** |
| `PORT` | **Portfolio & risk** | *Optimization & VaR* tab: VaR and CVaR (4 methods), Kupiec, Markowitz · *Risk level* tab: official CSA risk rating of an ETF, a security or a portfolio, beta, drawdown, fund holdings |
| `FA` | **Fundamental analysis** | Financial statements (SEC EDGAR, Yahoo fallback), ratios, DuPont, P/E, DCF with **your** assumptions and sensitivity, thesis notebook, Excel export |
| `OPT` | **Options** | Option chain filtered by liquidity, implied volatility smile, Greeks, Black-Scholes calculator |
| `YCRV` | **Curves & bonds** | US (FRED) and Canadian (Bank of Canada) yield curves, bond calculator (YTM, duration, convexity, DV01, shocks) |
| `SPRD` | **Yield spreads** | Dashboard of tracked spreads (slopes, Canada − US, breakeven inflation, credit) with historical z-score · spread between any two rates · G-spread of a corporate bond |

Every section and tab has a **?** button that explains the function in plain language, with an example and
why it is useful.

Markets covered: **stocks** (US, TSX, international), **indices**, **commodities** (gold, oil, copper, gas, grains…),
**forex**, **bonds** (ETFs and yield curves), **options** (US stocks and ETFs).

---

## 2. Opening the terminal

**👉 [terminal-quant-bilodeau.streamlit.app](https://terminal-quant-bilodeau.streamlit.app)**

Works in any browser, on a computer or a phone. If the app is asleep (after a few days without visits), click
*"Yes, get this app back up!"* and wait about 30 seconds.

**Charts-only window** (TradingView grid filling the whole window, no menu or sidebar — handy on a second screen):

- From the app: **CMP → TradingView charts → *Open charts in a new window (charts only)***. The window keeps the settings you chose.
- Or bookmark the address directly:
  - [`/?view=charts`](https://terminal-quant-bilodeau.streamlit.app/?view=charts) — base settings from `tradingview.toml`
  - [`/?view=charts&layout=4`](https://terminal-quant-bilodeau.streamlit.app/?view=charts&layout=4) — forces a 2 × 2 grid (`layout=1`, `2` or `4`)

---

## 3. User guide by section

**Command bar** (left): type a code followed by arguments, then Enter.

| Command | Effect |
|---|---|
| `FA AAPL` | Fundamental analysis of Apple |
| `OPT SPY` | SPY options |
| `CMP GC=F SI=F` | Compare gold and silver |
| `MKT AAPL MSFT ^GSPC` | Markets with these tickers |
| `PORT XIU.TO XBB.TO` | Portfolio with these assets |
| `TKR bank` | Directory filtered on "bank" |
| `SPRD`, `YCRV`, `HOME` | Opens the function |

**Global settings** (sidebar, *Global settings* menu): analysis period (5 years by default) and **base currency** (CAD or USD).

**Entering assets**: predefined list, or any Yahoo ticker in the free field.
Examples: `AAPL`, `RY.TO` (TSX), `GC=F` (gold), `CL=F` (WTI crude), `USDCAD=X`, `^GSPC` (S&P 500), `TLT` (20+ year Treasuries).

### TKR — Ticker directory
Pick a family or search a word ("gold", "bank", "BTC"). Copy the Yahoo ticker for the terminal,
or the TradingView symbol for the CMP charts. An option has no ticker of its own: enter the underlying in OPT.

### MKT — Markets
Pick assets from different categories to compare their base-100 performance and correlations.
The *Convert* box expresses everything in the base currency, i.e. the return actually earned by a Canadian investor.

### CMP — Comparator & formulas
- **Two symbols**: base 100, A/B ratio (rising = A beats B), 60-day rolling correlation and beta.
- **Formula**: `GC=F / SI=F`, `CL=F - BZ=F`, `(AAPL + MSFT + NVDA) / 3`, `BTC-USD * USDCAD=X`. Operators `+ - * / **` and parentheses;
  put spaces around a `-` between two tickers (`BTC-USD` is a single ticker).
- **TradingView charts**: 1, 2 or 4 charts (2 × 2 grid), each with an optional overlaid second symbol;
  settings for style, interval, indicators (and their parameters, e.g. RSI length), candle and background colors, toolbars and size.
  The **base settings are shared by all visitors**: they come from [`tradingview.toml`](tradingview.toml). To change them for everyone,
  adjust the display in the app, click *Export these settings as base*, then replace that file on GitHub.
  The *Open charts in a new window* button opens the same grid alone, full window.

### PORT — Portfolio & risk (Optimization & VaR tab)
1. Select 2 to 20 **investable** assets (not `^TNX`: it is a rate, not a price).
2. Choose the confidence level, horizon, maximum weight per asset and risk-free rate.
3. **Expected returns (μ)**: the historical mean is pre-filled. **Replace it with your assumptions**;
   it is the parameter that drives the optimization the most.
4. Compare the minimum-variance, maximum-Sharpe and manual portfolios.
5. Read the VaR and CVaR from the 4 methods. **The gap between methods is information**: a wide gap signals fat tails.
6. Check the Kupiec backtest: a p-value < 0.05 means the VaR is poorly calibrated.
7. Export to Excel (weights, assumptions, covariance, VaR, backtest, metadata).

### PORT — Risk level tab
Enter an ETF or a security (e.g. `XEQT.TO`), or build a portfolio with its weights. The terminal applies the
**official CSA method** (National Instrument 81-102, Appendix F): annualized standard deviation of monthly returns over 10 years,
rated Low (< 6%), Low to medium (6-11%), Medium (11-16%), Medium to high (16-20%) or High (≥ 20%).
Also shown: beta against an index, drawdown, best and worst months, 36-month rolling risk and,
when Yahoo provides it, the fund's holdings.

### FA — Fundamental analysis
1. Enter a ticker. The source (EDGAR or Yahoo) and the currency of the statements are shown.
2. **Financial statements** and **Ratios** tabs: last 6 fiscal years. Definitions are in the info box.
3. **Valuation & DCF** tab: enter **your** growth rates, WACC and terminal growth, then tick the confirmation box.
   The sensitivity table shows how much the value depends on your assumptions.
4. **Analysis notebook** tab: write the thesis, catalysts, risks and conclusion. **These fields are empty by design.**
5. **Export** tab: an Excel workbook with the figures, ratios, DCF, your notebook and metadata.

### OPT — Options
- **Option chain**: US underlying (e.g. `SPY`, `AAPL`), expiry and liquidity filters.
  Implied volatility is recomputed and compared with Yahoo's.
- **Calculator**: for any underlying (gold, currency, index), supplying spot, volatility and rate yourself.

### YCRV — Curves & bonds
- US and Canadian curves today, 1 year ago and 2 years ago: slope and inversion.
- Investment Grade and High Yield credit spreads.
- Calculator: price ↔ yield, duration, convexity, DV01 and ±25 to ±200 bp shocks (approximation vs exact repricing).

### SPRD — Yield spreads
- **Dashboard**: US and Canadian slopes, Canada − US (2 and 10 years), breakeven inflation (nominal − real), High Yield − IG,
  with the current level in basis points, the mean, the **z-score** (amber beyond ±2) and the 1-year change.
- **Between two rates**: any pair among US and Canadian rates and FRED credit spreads.
- **G-spread**: yield of a corporate bond minus the government rate interpolated at the same maturity.

---

## 4. Methodological choices

| Topic | Choice | Why |
|---|---|---|
| Prices | Adjusted (dividends and splits) | Correct total returns |
| Currencies | Conversion to a base currency | Never mix CAD and USD returns |
| Calendars | Common dates only, no interpolation | Covariance requires simultaneous observations; no invented data |
| Annualization | 252 trading days | Market convention |
| Minimum history | 500 observations (~2 years) | A VaR on little data is not credible |
| Covariance | Ledoit-Wolf by default | Reduces estimation error, more stable portfolios |
| Optimization | SLSQP (SciPy), long-only, capped weights, convergence checked | Avoids extreme portfolios and silently wrong results |
| VaR | 4 methods + CVaR + backtest | No method is perfect; comparing them *is* the analysis |
| Monte Carlo | 10,000 scenarios, fixed seed | Reproducible results |
| ROE, ROA | On **average** equity and assets | Earnings are generated over the whole year |
| Absurd ratios | Shown as `N/A` | ROE with negative equity, P/E with negative earnings, etc. |
| P/E currency | Price converted to the statements' currency | E.g. Shopify trades in CAD but reports in USD |
| DCF | No hidden default assumption; confirmation required | Valuation remains the analyst's judgment |
| Options | Mid price (bid+ask)/2, arbitrage check before IV | The last trade may be stale |
| Risk level | CSA grid: monthly standard deviation over 120 months, annualized by √12 | Official method of Canadian Fund Facts |
| Spreads | Common dates only, z-score over the chosen period, interpolation without extrapolation | Never compare two different dates or invent a rate |
| Formulas | Arithmetic parser (`ast` module), never `eval` | No input can execute code |

Every section of the terminal has a **"Method and limitations"** box.

---

## 5. Guardrails: what the terminal refuses to do

- No recommendation, no "signal", no price prediction.
- No order execution, no broker connection.
- No DCF value until the user confirms the assumptions are their own.
- Portfolio: 2 to 20 assets, at least 500 common observations, no short selling.
- Rates and the VIX are refused as portfolio assets.
- **Closed list of 4 data sources** (+ the TradingView display widget). No site scraping, no paid source bypassed.
- CMP formulas are read by a parser that only accepts arithmetic: no code is executed.
- No API key in the code (`st.secrets` only).
- Every Excel export includes a **Metadata** sheet: date, sources, parameters.

All numeric limits are centralized in **`config.py`**.

---

## 6. Code architecture

The code is split into **layers that do not mix**. The interface is in English; code comments are in French.

```
terminal-quant/
├── app.py                    Navigation and global settings (entry point)
├── config.py                 Guardrails, constants, rate series, CSA grid, allowed sources
├── repertoire.py             Ticker directory by family (Yahoo + TradingView)
├── tradingview.toml          Base settings of the TradingView charts (shared by everyone)
├── lancer_windows.bat        Windows double-click launcher
├── requirements.txt          Python libraries
├── sources/                  DATA layer: download and cleaning, no calculation
│   ├── marche.py               Multi-asset prices, currency conversion, calendar alignment
│   ├── taux.py                 FRED and Bank of Canada
│   ├── etats_financiers.py     SEC EDGAR (XBRL US GAAP / IFRS) + Yahoo fallback, standardized format
│   └── options.py              Option chains
├── calculs/                  CALCULATION layer: pure math, no Internet, no Streamlit
│   ├── rendements.py           Returns, statistics, drawdown
│   ├── risque.py               VaR, CVaR, Monte Carlo, Kupiec
│   ├── optimisation.py         Markowitz, efficient frontier, risk contributions
│   ├── fondamentaux.py         Ratios, DuPont, valuation, DCF, sensitivity
│   ├── obligations.py          Price, YTM, duration, convexity, shocks
│   ├── options_math.py         Black-Scholes-Merton, Greeks, implied volatility
│   ├── spreads.py              Spreads in bp, z-score, curve interpolation, G-spread
│   ├── formule.py              Ticker formulas (safe parser, no eval)
│   └── profil_risque.py        CSA risk level, beta, ETF or portfolio profile
├── interface/                DISPLAY layer: one Streamlit page per function
│   ├── page_accueil.py  page_repertoire.py  page_marches.py  page_comparateur.py
│   ├── page_risque.py  page_fondamental.py  page_options.py  page_taux.py  page_spreads.py
│   ├── vue_graphiques.py       Charts-only window (?view=charts)
│   ├── navigation.py           Function codes, menu and command bar
│   ├── aide.py                 Texts of the "?" buttons (plain language, with examples)
│   ├── theme.py  bandeau.py    Dark amber look, quote ticker tape
│   ├── tradingview.py          TradingView widgets: validated settings, 1/2/4 grid, TOML export, settings in the URL
│   └── composants.py           Reusable components
├── export/excel.py           Excel export with metadata
└── tests/test_calculs.py     Calculation tests
```

**Why this split?** The calculations depend on neither the Internet nor the interface,
so they can be tested against known numbers. If a source changes, only `sources/` is modified.

---

## 7. Tests

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

The 60 tests compare the calculations with known values, for example:
- Black-Scholes: Hull's textbook example (S=42, K=40 → call 4.76) and put-call parity;
- Markowitz: closed-form 2-asset minimum variance, constraints respected, infeasible case detected;
- VaR: convergence to the normal distribution, CVaR ≥ VaR, Cornish-Fisher on fat tails, Kupiec;
- Bonds: price at par, YTM as the inverse of price, zero-coupon duration, numerical derivatives;
- Ratios: ROE on average, DuPont consistency, N/A for negative equity or EPS, DCF = Gordon perpetuity;
- Spreads: conversion to bp, common dates, z-score, interpolated G-spread;
- Formulas: operator precedence, hyphenated tickers (`BTC-USD`), refusal of any non-arithmetic code;
- Risk level: CSA grid at exact boundaries, annualized monthly standard deviation, known beta;
- TradingView: settings validation, URL round trip, full-window grid.

---

## 8. Contributing or modifying the code

- **Change a limit** (maximum weight, number of assets…): edit `config.py` only.
- **Add a predefined asset**: `UNIVERS` dictionary in `config.py`.
- **Add a ratio**: `calculer_ratios` function and `DEFINITIONS` dictionary in `calculs/fondamentaux.py`, then a test.
- **Add a data source**: create a module in `sources/` and add it to `SOURCES_AUTORISEES`.
  Only official sources, or sources whose terms of use allow it, are accepted.
- Rule: **no calculation in `interface/`** and **no Internet call in `calculs/`**.
- Run `python -m pytest tests/` before every commit.

Issues and pull requests are welcome.

---

## 9. Known limitations and troubleshooting

**Limitations**
- `yfinance` is not an official API: it may stop working without notice. Data is delayed.
- Cloud servers (Streamlit Cloud) are sometimes rate-limited by Yahoo ("Too Many Requests"): wait a few minutes. The one-hour cache reduces the problem.
- Commodities = continuous futures (`=F`): artificial price jumps are possible at contract rolls.
- Options: mostly US, no history; Black-Scholes is an approximation for American options.
- Individual bonds (CUSIP/ISIN): no reliable free source, use ETFs.
- TSX companies not registered with the SEC: Yahoo fallback, check key figures on SEDAR+.
- P/E computed on the last annual EPS (not trailing 12 months).
- Banks and insurers: some ratios (current ratio, gross margin) do not apply and show `N/A`.
- The free TradingView widget does not display futures (`COMEX:GC1!`…): use the spot equivalent (`OANDA:XAUUSD`) or an ETF.

**Troubleshooting**

| Problem | Solution |
|---|---|
| `DLL load failed … Application Control policy has blocked this file` (Windows) | Windows Smart App Control blocks unsigned libraries. Use the online version. |
| "Python was not found" | Reinstall Python and tick "Add python.exe to PATH". |
| Library installation error with a very recent Python | Use Python 3.12. |
| "Ticker without data" | Check the ticker on finance.yahoo.com (e.g. `RY.TO`, not `RY`, for the TSX). |
| YCRV (US) or SPRD limited to Canada | Add `FRED_API_KEY` to the secrets. |
| The TradingView chart shows nothing | Check the symbol uses the `EXCHANGE:SYMBOL` format (TradingView column of the directory). |

---

*Personal and educational tool. This is not financial advice. VaR is not a maximum loss.
Past performance does not guarantee future results.*
