"""
TKR — Répertoire des tickers classés par famille.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from interface.aide import titre
from interface.navigation import valeur_initiale
from repertoire import NOTE_OPTIONS, REPERTOIRE


def _tableau() -> pd.DataFrame:
    """Aplatit le répertoire en un seul tableau (une ligne par ticker)."""
    lignes = [
        {"Family": famille, "Name": nom, "Yahoo ticker (terminal)": yahoo,
         "TradingView symbol": tv, "Description": note}
        for famille, entrees in REPERTOIRE.items()
        for nom, yahoo, tv, note in entrees
    ]
    return pd.DataFrame(lignes)


def afficher(params: dict) -> None:
    titre("Ticker directory", "repertoire", "TKR",
          f"{sum(len(v) for v in REPERTOIRE.values())} of the most widely used symbols, in {len(REPERTOIRE)} families. "
          "Any other Yahoo ticker also works in the terminal.")

    tout = _tableau()
    valeur_initiale("rep_recherche", "", "cmd_rep_recherche")
    c1, c2 = st.columns([2, 3])
    recherche = c1.text_input("Search (name, ticker, description)", key="rep_recherche",
                              placeholder="e.g. gold, bank, semi, BTC")
    familles = ["All"] + list(REPERTOIRE)
    famille = c2.selectbox("Family", familles)

    vue = tout if famille == "All" else tout[tout["Family"] == famille]
    if recherche.strip():
        motif = recherche.strip().lower()
        masque = vue.apply(lambda ligne: motif in " ".join(map(str, ligne.values)).lower(), axis=1)
        vue = vue[masque]

    if famille.startswith("Options"):
        st.info(NOTE_OPTIONS)
    st.caption(f"{len(vue)} result(s). Click a cell, then Ctrl+C to copy a ticker.")
    st.dataframe(vue, hide_index=True, width="stretch", height=min(38 * (len(vue) + 1), 640),
                 column_config={"Yahoo ticker (terminal)": st.column_config.TextColumn(width="small"),
                                "TradingView symbol": st.column_config.TextColumn(width="small")})

    with st.expander("How to write a Yahoo ticker", icon=":material/help:"):
        st.markdown(
            "| Market | Format | Examples |\n|---|---|---|\n"
            "| US stock | Symbol only | `AAPL`, `MU` |\n"
            "| Canadian stock | Symbol + `.TO` (or `.V` for the Venture Exchange) | `RY.TO`, `SHOP.TO` |\n"
            "| European stock | Symbol + exchange suffix | `MC.PA` (Paris), `SAP.DE` (Frankfurt) |\n"
            "| Index | `^` prefix | `^GSPC`, `^GSPTSE` |\n"
            "| Futures | `=F` suffix | `GC=F`, `CL=F` |\n"
            "| Forex | Pair + `=X` | `USDCAD=X` |\n"
            "| Crypto | Symbol-currency | `BTC-USD`, `ETH-CAD` |\n\n"
            "**TradingView** symbols use the `EXCHANGE:SYMBOL` format (e.g. `TSX:RY`, `COMEX:GC1!`). "
            "They are only used for the TradingView charts of the CMP function; they are indicative. "
            "**The free widget does not display futures** (symbols ending in `1!`) or some indices: "
            "use the spot equivalent (`OANDA:XAUUSD`, `TVC:USOIL`) or an ETF (`AMEX:SPY`, `TSX:XIU`)."
        )
    st.download_button("Download the directory (CSV)", tout.to_csv(index=False).encode("utf-8-sig"),
                       file_name="ticker_directory.csv", mime="text/csv", icon=":material/download:")
