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
    df["VI calculée"] = [om.volatilite_implicite(p, S, K, T, r, q, type_option)
                         for p, K in zip(df["prix_milieu"], df["strike"])]
    grecs = [om.grecques(S, K, T, r, q, v, type_option) if np.isfinite(v) else {}
             for K, v in zip(df["strike"], df["VI calculée"])]
    return pd.concat([df.reset_index(drop=True), pd.DataFrame(grecs)], axis=1)


def _section_chaine() -> None:
    """Chaîne d'options réelle. Dans une fonction séparée pour pouvoir
    sortir tôt (return) sans bloquer l'onglet Calculatrice."""
    sous_titre("Chaîne d'options", "opt_chaine")
    valeur_initiale("opt_ticker", "SPY", "cmd_opt_ticker")
    c1, c2, c3 = st.columns(3)
    ticker = c1.text_input("Sous-jacent (actions/FNB US)", key="opt_ticker").strip().upper()
    r = c2.number_input("Taux sans risque (%)", 0.0, 20.0, 4.0, 0.1, key="opt_r") / 100
    q = c3.number_input("Rendement du dividende (%)", 0.0, 20.0, 1.2, 0.1, key="opt_q") / 100
    try:
        dates = src.echeances(ticker)
    except Exception as e:
        st.error(f"Échéances indisponibles pour {ticker} : {e}")
        dates = []
    if not dates:
        st.info("Aucune option listée pour ce sous-jacent sur Yahoo (fréquent hors des États-Unis). "
                "Utilise la calculatrice.")
    else:
        echeance = st.selectbox("Échéance", dates)
        c4, c5 = st.columns(2)
        oi_min = c4.number_input("Intérêt ouvert minimum", 0, 100_000, 100, 50,
                                 help="Filtre les options illiquides dont le prix n'est pas fiable.")
        ecart_max = c5.slider("Écart acheteur-vendeur max (% du prix)", 1, 100, 25)

        try:
            calls, puts, S = src.chaine(ticker, echeance)
        except Exception as e:  # réseau ou format Yahoo inattendu
            st.error(f"Chaîne indisponible : {e}")
            return
        T = _temps_a_echeance(echeance)
        if T <= 0:
            st.warning("Échéance atteinte ou dépassée.")
            return
        st.caption(f"Sous-jacent : {S:,.2f} · T = {T * 365:.1f} jours")

        def filtrer(df):
            return df[(df["openInterest"].fillna(0) >= oi_min) & (df["ecart_fourchette_%"] <= ecart_max)]

        calls_e = _enrichir(filtrer(calls), S, T, r, q, "call")
        puts_e = _enrichir(filtrer(puts), S, T, r, q, "put")

        # --- Smile de volatilité ---
        fig = go.Figure()
        for nom, df in (("Calls", calls_e), ("Puts", puts_e)):
            fig.add_trace(go.Scatter(x=df["strike"], y=df["VI calculée"], mode="markers+lines", name=f"{nom} (calculée)"))
            fig.add_trace(go.Scatter(x=df["strike"], y=df["impliedVolatility"], mode="markers", name=f"{nom} (Yahoo)",
                                     marker={"symbol": "x", "size": 6}, opacity=0.5))
        fig.add_vline(x=S, line_dash="dot", annotation_text="Spot")
        fig.update_layout(title="Smile de volatilité implicite", xaxis_title="Prix d'exercice",
                          yaxis_title="Volatilité implicite", yaxis_tickformat=".0%", height=420)
        st.plotly_chart(fig, width="stretch")

        colonnes = ["contractSymbol", "strike", "bid", "ask", "prix_milieu", "ecart_fourchette_%", "volume",
                    "openInterest", "VI calculée", "Delta", "Gamma", "Vega", "Theta (par jour)", "Rho"]
        for titre, df in (("Calls", calls_e), ("Puts", puts_e)):
            st.markdown(f"**{titre}** — {len(df)} contrats après filtres")
            st.dataframe(df.reindex(columns=colonnes).style.format(
                {"VI calculée": "{:.1%}", "ecart_fourchette_%": "{:.1f}", "Delta": "{:.3f}", "Gamma": "{:.4f}",
                 "Vega": "{:.3f}", "Theta (par jour)": "{:.3f}", "Rho": "{:.3f}", "prix_milieu": "{:.2f}"},
                na_rep="N/A"), width="stretch", hide_index=True)

        fichier = exporter_excel({"Calls": calls_e.set_index("contractSymbol"), "Puts": puts_e.set_index("contractSymbol")},
                                 {"Sous-jacent": ticker, "Spot": S, "Échéance": echeance, "T (années)": T,
                                  "Taux sans risque": r, "Dividende": q, "Filtre intérêt ouvert": oi_min,
                                  "Filtre écart max %": ecart_max, "Modèle": "Black-Scholes-Merton (européen)",
                                  "Source": "Yahoo Finance (différé)"})
        st.download_button("Exporter la chaîne (Excel)", fichier, file_name=f"options_{ticker}_{echeance}.xlsx")


def afficher(params: dict) -> None:
    titre("Options", "opt", "OPT",
          "Chaînes d'options Yahoo (différées) · volatilité implicite et grecques recalculées (Black-Scholes-Merton).")

    onglet_chaine, onglet_calc = st.tabs([":material/view_list: Chaîne d'options", ":material/calculate: Calculatrice Black-Scholes"])

    with onglet_chaine:
        _section_chaine()

    # ======================================================= Calculatrice
    with onglet_calc:
        sous_titre("Calculatrice Black-Scholes", "opt_calc")
        st.markdown("Pour tout sous-jacent (or, pétrole, devise…) : **tu fournis** spot, volatilité et taux. "
                    "Pour une option sur contrat à terme (modèle de Black 76), mets q = r.")
        c1, c2, c3 = st.columns(3)
        S = c1.number_input("Spot", 0.01, value=100.0)
        K = c2.number_input("Prix d'exercice", 0.01, value=100.0)
        jours = c3.number_input("Jours à l'échéance", 1, 3650, 30)
        c4, c5, c6, c7 = st.columns(4)
        sigma = c4.number_input("Volatilité (%)", 1.0, 300.0, 20.0, 0.5) / 100
        r_c = c5.number_input("Taux sans risque (%)", 0.0, 20.0, 4.0, 0.1, key="calc_r") / 100
        q_c = c6.number_input("Dividende / rendement de portage (%)", 0.0, 20.0, 0.0, 0.1, key="calc_q") / 100
        type_c = c7.radio("Type", ["call", "put"], horizontal=True)
        T_c = jours / 365
        metriques({"Prix théorique": om.prix_bsm(S, K, T_c, r_c, q_c, sigma, type_c),
                   **om.grecques(S, K, T_c, r_c, q_c, sigma, type_c)}, "{:.4f}", par_ligne=6)

        # Profil du prix de l'option selon le spot (aujourd'hui vs à l'échéance).
        grille = np.linspace(S * 0.6, S * 1.4, 120)
        valeur = [om.prix_bsm(s, K, T_c, r_c, q_c, sigma, type_c) for s in grille]
        intrinseque = np.maximum(grille - K, 0) if type_c == "call" else np.maximum(K - grille, 0)
        fig = go.Figure([go.Scatter(x=grille, y=valeur, name="Valeur aujourd'hui"),
                         go.Scatter(x=grille, y=intrinseque, name="Valeur à l'échéance", line={"dash": "dash"})])
        fig.update_layout(xaxis_title="Prix du sous-jacent", yaxis_title="Valeur de l'option", height=380)
        st.plotly_chart(fig, width="stretch")

    note_methodo(
        "- **Prix milieu** (bid+ask)/2 ; contrats sans bid ou sans ask exclus.\n"
        "- **Black-Scholes-Merton** suppose une option européenne et une volatilité constante. "
        "Les options sur actions US sont américaines : approximation acceptable pour les calls, moins pour les puts "
        "profondément dans la monnaie.\n"
        "- Prix sous la valeur intrinsèque → VI = N/A (cotation périmée).\n"
        "- **Vega** et **Rho** pour +1 point ; **Theta** par jour calendaire.\n"
        "- Données Yahoo différées : ne jamais utiliser pour exécuter un ordre."
    )
