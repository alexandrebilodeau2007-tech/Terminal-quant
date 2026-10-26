"""
Section 4 — Options : chaîne, volatilité implicite (smile) et grecques,
plus une calculatrice Black-Scholes utilisable pour N'IMPORTE quel sous-jacent
(commodité, devise, indice) en saisissant les paramètres soi-même.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculs import options_math as om
from export.excel import exporter_excel
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from interface.navigation import valeur_initiale
from sources import options as src


def _temps_a_echeance(echeance: str) -> float:
    """Années restantes jusqu'à l'échéance, en jours CALENDAIRES / 365.
    Les options US expirent à la clôture (16 h, heure de New York ≈ 20 h ou 21 h UTC) ;
    on prend 20 h UTC, l'écart d'une heure est négligeable sauf le dernier jour."""
    expiration = datetime.fromisoformat(echeance).replace(hour=20, tzinfo=timezone.utc)
    secondes = (expiration - datetime.now(timezone.utc)).total_seconds()
    return max(secondes, 0) / (365 * 24 * 3600)


def _enrichir(df: pd.DataFrame, S: float, T: float, r: float, q: float, type_option: str) -> pd.DataFrame:
    """Ajoute à chaque ligne de la chaîne : notre volatilité implicite et les grecques."""
    df = df.copy()
    df["Computed IV"] = [om.volatilite_implicite(p, S, K, T, r, q, type_option)
                         for p, K in zip(df["prix_milieu"], df["strike"])]
    grecs = [om.grecques(S, K, T, r, q, v, type_option) if np.isfinite(v) else {}
             for K, v in zip(df["strike"], df["Computed IV"])]
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(grecs)], axis=1)


def _section_chaine() -> None:
    """Chaîne d'options réelle. Dans une fonction séparée pour pouvoir
    sortir tôt (return) sans bloquer l'onglet Calculatrice."""
    sous_titre("Option chain", "opt_chaine")
    valeur_initiale("opt_ticker", "SPY", "cmd_opt_ticker")
    c1, c2, c3 = st.columns(3)
    ticker = c1.text_input("Underlying (US stocks/ETFs)", key="opt_ticker").strip().upper()
    r = c2.number_input("Risk-free rate (%)", 0.0, 20.0, 4.0, 0.1, key="opt_r") / 100
    q = c3.number_input("Dividend yield (%)", 0.0, 20.0, 1.2, 0.1, key="opt_q") / 100
    try:
        dates = src.echeances(ticker)
    except Exception as e:
        st.error(f"Expirations unavailable for {ticker} : {e}")
        dates = []
    if not dates:
        st.info("No options listed for this underlying on Yahoo (common outside the US). "
                "Use the calculator.")
    else:
        echeance = st.selectbox("Expiration", dates)
        c4, c5 = st.columns(2)
        oi_min = c4.number_input("Minimum open interest", 0, 100_000, 100, 50,
                                 help="Filters out illiquid options whose price is unreliable.")
        ecart_max = c5.slider("Max bid-ask spread (% of price)", 1, 100, 25)

        try:
            calls, puts, S = src.chaine(ticker, echeance)
        except Exception as e:  # réseau ou format Yahoo inattendu
            st.error(f"Chain unavailable: {e}")
            return
        T = _temps_a_echeance(echeance)
        if T <= 0:
            st.warning("Expiration reached or passed.")
            return
        st.caption(f"Underlying: {S:,.2f} · T = {T * 365:.1f} days")

        def filtrer(df):
            return df[(df["openInterest"].fillna(0) >= oi_min) & (df["ecart_fourchette_%"] <= ecart_max)]

        calls_e = _enrichir(filtrer(calls), S, T, r, q, "call")
        puts_e = _enrichir(filtrer(puts), S, T, r, q, "put")

        # --- Smile de volatilité ---
        fig = go.Figure()
        for nom, df in (("Calls", calls_e), ("Puts", puts_e)):
            fig.add_trace(go.Scatter(x=df["strike"], y=df["Computed IV"], mode="markers+lines", name=f"{nom} (computed)"))
            fig.add_trace(go.Scatter(x=df["strike"], y=df["impliedVolatility"], mode="markers", name=f"{nom} (Yahoo)",
                                     marker={"symbol": "x", "size": 6}, opacity=0.5))
        fig.add_vline(x=S, line_dash="dot", annotation_text="Spot")
        fig.update_layout(title="Implied volatility smile", xaxis_title="Strike price",
                          yaxis_title="Implied volatility", yaxis_tickformat=".0%", height=420)
        st.plotly_chart(fig, width="stretch")

        colonnes = ["contractSymbol", "strike", "bid", "ask", "prix_milieu", "ecart_fourchette_%", "volume",
                    "openInterest", "Computed IV", "Delta", "Gamma", "Vega", "Theta (per day)", "Rho"]
        for titre, df in (("Calls", calls_e), ("Puts", puts_e)):
            st.markdown(f"**{titre}** — {len(df)} contracts after filters")
            st.dataframe(df.reindex(columns=colonnes).style.format(
                {"Computed IV": "{:.1%}", "ecart_fourchette_%": "{:.1f}", "Delta": "{:.3f}", "Gamma": "{:.4f}",
                 "Vega": "{:.3f}", "Theta (per day)": "{:.3f}", "Rho": "{:.3f}", "prix_milieu": "{:.2f}"},
                na_rep="N/A"), width="stretch", hide_index=True)

        fichier = exporter_excel({"Calls": calls_e.set_index("contractSymbol"), "Puts": puts_e.set_index("contractSymbol")},
                                 {"Underlying": ticker, "Spot": S, "Expiration": echeance, "T (years)": T,
                                  "Risk-free rate": r, "Dividend": q, "Open interest filter": oi_min,
                                  "Max spread filter %": ecart_max, "Model": "Black-Scholes-Merton (European)",
                                  "Source": "Yahoo Finance (delayed)"})
        st.download_button("Export the chain (Excel)", fichier, file_name=f"options_{ticker}_{echeance}.xlsx")


def afficher(params: dict) -> None:
    titre("Options", "opt", "OPT",
          "Yahoo option chains (delayed) · implied volatility and Greeks recomputed (Black-Scholes-Merton).")

    onglet_chaine, onglet_calc = st.tabs([":material/view_list: Option chain", ":material/calculate: Black-Scholes calculator"])

    with onglet_chaine:
        _section_chaine()

    # ======================================================= Calculatrice
    with onglet_calc:
        sous_titre("Black-Scholes calculator", "opt_calc")
        st.markdown("For any underlying (gold, oil, currency…): **you provide** spot, volatility and rate. "
                    "For an option on a futures contract (Black 76 model), set q = r.")
        c1, c2, c3 = st.columns(3)
        S = c1.number_input("Spot", 0.01, value=100.0)
        K = c2.number_input("Strike price", 0.01, value=100.0)
        jours = c3.number_input("Days to expiration", 1, 3650, 30)
        c4, c5, c6, c7 = st.columns(4)
        sigma = c4.number_input("Volatility (%)", 1.0, 300.0, 20.0, 0.5) / 100
        r_c = c5.number_input("Risk-free rate (%)", 0.0, 20.0, 4.0, 0.1, key="calc_r") / 100
        q_c = c6.number_input("Dividend / carry yield (%)", 0.0, 20.0, 0.0, 0.1, key="calc_q") / 100
        type_c = c7.radio("Type", ["call", "put"], horizontal=True)
        T_c = jours / 365
        metriques({"Theoretical price": om.prix_bsm(S, K, T_c, r_c, q_c, sigma, type_c),
                   **om.grecques(S, K, T_c, r_c, q_c, sigma, type_c)}, "{:.4f}", par_ligne=6)

        # Profil du prix de l'option selon le spot (aujourd'hui vs à l'échéance).
        grille = np.linspace(S * 0.6, S * 1.4, 120)
        valeur = [om.prix_bsm(s, K, T_c, r_c, q_c, sigma, type_c) for s in grille]
        intrinseque = np.maximum(grille - K, 0) if type_c == "call" else np.maximum(K - grille, 0)
        fig = go.Figure([go.Scatter(x=grille, y=valeur, name="Value today"),
                         go.Scatter(x=grille, y=intrinseque, name="Value at expiration", line={"dash": "dash"})])
        fig.update_layout(xaxis_title="Underlying price", yaxis_title="Option value", height=380)
        st.plotly_chart(fig, width="stretch")

    note_methodo(
        "- **Mid price** (bid+ask)/2; contracts without a bid or ask are excluded.\n"
        "- **Black-Scholes-Merton** assumes a European option and constant volatility. "
        "US equity options are American: an acceptable approximation for calls, less so for puts "
        "deep in the money.\n"
        "- Price below intrinsic value → IV = N/A (stale quote).\n"
        "- **Vega** and **Rho** per +1 point; **Theta** per calendar day.\n"
        "- Delayed Yahoo data: never use it to execute an order."
    )
