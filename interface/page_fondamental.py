"""
Section 3 — Analyse fondamentale (ACCÉLÉRATEUR DE CALCULS).

Balise centrale de cette section :
    Le terminal extrait les chiffres et calcule les ratios.
    La thèse, l'argumentaire et la conclusion sont écrits par l'analyste dans
    le "Carnet d'analyse". Aucun verdict automatique n'est produit, et le DCF
    n'affiche une valeur qu'une fois que l'analyste confirme que les
    hypothèses sont les siennes.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from calculs import fondamentaux as fd
from export.excel import exporter_excel
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from interface.navigation import valeur_initiale
from sources.etats_financiers import ErreurFondamentaux, donnees_de_marche, obtenir_etats_financiers
from sources.marche import ErreurDonnees, telecharger_prix

# Ratios exprimés en % (les autres sont des multiples, ex. 1,8x).
RATIOS_POURCENT = ["ROE", "ROA", "Gross margin", "Operating margin", "Net margin",
                   "Liabilities / assets", "Revenue growth", "Net income growth"]
CHAMPS_CARNET = {
    "these": "Investment thesis (3-5 sentences)",
    "catalyseurs": "Catalysts (what, when, how to measure them)",
    "risques": "Main risks and what would invalidate the thesis",
    "hypotheses": "Justification of the DCF assumptions (growth, WACC, g)",
    "conclusion": "Analyst's conclusion",
}


def _user_agent() -> str | None:
    try:
        return st.secrets.get("SEC_USER_AGENT") or None
    except Exception:
        return None


def _taux_de_change(de: str, vers: str) -> float | None:
    """Dernier taux de change Yahoo (pour convertir le prix dans la devise des états)."""
    paire = f"{de}{vers}=X"
    fin = pd.Timestamp.today()
    try:
        serie = telecharger_prix((paire,), str((fin - pd.Timedelta(days=10)).date()), str((fin + pd.Timedelta(days=1)).date()))
        return float(serie[paire].dropna().iloc[-1])
    except (ErreurDonnees, IndexError):
        return None


def afficher(params: dict) -> None:
    titre("Fundamental analysis", "fa", "FA", "The terminal computes. You argue and conclude.")
    valeur_initiale("fd_ticker", "AAPL", "cmd_fd_ticker")

    ticker = st.text_input("Ticker (Yahoo)", key="fd_ticker", help="E.g. AAPL, MU, RY.TO, SHOP.TO").strip().upper()
    if not ticker:
        return

    try:
        with st.spinner("Extracting financial statements…"):
            etats = obtenir_etats_financiers(ticker, _user_agent())
    except ErreurFondamentaux as e:
        st.error(str(e))
        return
    except Exception as e:  # erreur réseau ou format inattendu : on l'affiche sans planter
        st.error(f"Could not retrieve financial statements: {e}")
        return

    t = etats.tableau
    st.markdown(f"**{etats.nom}** — source: `{etats.source}` — statement currency: **{etats.devise}**")
    for note in etats.notes:
        st.info(note)

    # ------------------------------------------------ prix dans la devise des états
    marche = donnees_de_marche(ticker)
    prix, actions = marche["prix"], marche["actions"]
    note_devise = "same"
    if prix and marche["devise"] and marche["devise"] != etats.devise:
        # Ex. Shopify : cotée en CAD à Toronto, mais publie ses états en USD.
        # Diviser un prix en CAD par un BPA en USD donnerait un P/E faux.
        fx = _taux_de_change(marche["devise"], etats.devise)
        if fx:
            note_devise = f"price converted {marche['devise']}→{etats.devise} at rate {fx:.4f}"
            prix = prix * fx
        else:
            note_devise = "conversion impossible: valuation ratios disabled"
            prix = None
    ratios = fd.calculer_ratios(t)
    valo = fd.ratios_valorisation(t, prix, actions)

    onglets = st.tabs([":material/table_chart: Financial statements", ":material/percent: Ratios",
                       ":material/price_change: Valuation & DCF", ":material/edit_note: Analysis notebook",
                       ":material/download: Export"])

    # ------------------------------------------------ 1. États financiers
    with onglets[0]:
        sous_titre("Annual financial statements", "fa_etats")
        st.caption(f"Amounts in {etats.devise} (units, not rounded). EPS in {etats.devise} per share.")
        affichage = t.T.copy()
        affichage.columns = [d.strftime("%Y-%m-%d") for d in t.index]
        st.dataframe(affichage.style.format("{:,.2f}", na_rep="N/A"), width="stretch")

    # ------------------------------------------------ 2. Ratios
    with onglets[1]:
        sous_titre("Financial ratios", "fa_ratios")
        tableau = ratios.T.copy()
        tableau.columns = [d.strftime("%Y-%m") for d in ratios.index]
        # Format par défaut "1,85" (multiples), puis format % pour les lignes de RATIOS_POURCENT.
        st.dataframe(
            tableau.style.format(lambda v: "N/A" if pd.isna(v) else f"{v:,.2f}")
            .format(lambda v: "N/A" if pd.isna(v) else f"{v:.1%}", subset=pd.IndexSlice[RATIOS_POURCENT, :]),
            width="stretch")
        ecart = fd.verifier_dupont(ratios).dropna()
        if not ecart.empty and ecart.max() > 1e-6:
            st.warning("DuPont check: margin × turnover × leverage ≠ ROE. Check the source data.")
        fig = px.line(ratios[["Gross margin", "Operating margin", "Net margin", "ROE"]], markers=True,
                      labels={"value": "", "index": "", "variable": ""}, title="Margins and ROE")
        st.plotly_chart(fig.update_layout(yaxis_tickformat=".0%"), width="stretch")
        with st.expander("Ratio definitions"):
            st.table(pd.Series(fd.DEFINITIONS, name="Definition"))

    # ------------------------------------------------ 3. Valorisation & DCF
    with onglets[2]:
        sous_titre("Valuation multiples", "fa_dcf")
        st.caption(f"Current price / latest fiscal year ({t.index[-1].date()}). Currency: {note_devise}.")
        metriques({k: valo[k] for k in ("P/E", "P/B", "P/S", "EV / EBIT")}, "{:.2f}x", par_ligne=5)
        metriques({"FCF yield": valo["FCF yield"]}, "{:.2%}", par_ligne=5)
        metriques({k: valo.get(k) for k in ("Market cap", "Enterprise value (EV)")}, "{:,.0f}", par_ligne=2)

        sous_titre("DCF — your assumptions", "fa_dcf")
        st.markdown("No assumption is chosen for you. Starting values are **neutral** "
                    "(0% growth) and must be replaced, then justified in the Notebook.")
        fcf_hist = ratios["Free cash flow (FCF)"].dropna()
        cagr_rev = (t["Revenue"].iloc[-1] / t["Revenue"].iloc[0]) ** (1 / max(len(t) - 1, 1)) - 1 \
            if t["Revenue"].iloc[0] > 0 else float("nan")
        st.caption(f"Historical reference points (not forecasts): latest fiscal-year FCF = "
                   f"{fcf_hist.iloc[-1]:,.0f} {etats.devise}; annual revenue growth over the period = "
                   f"{cagr_rev:.1%}." if not fcf_hist.empty else "Historical FCF unavailable.")

        c1, c2, c3 = st.columns(3)
        fcf0 = c1.number_input(f"Starting FCF ({etats.devise})", value=float(fcf_hist.iloc[-1]) if not fcf_hist.empty else 0.0,
                               step=1e6, format="%.0f")
        wacc = c2.number_input("WACC (%)", 1.0, 30.0, 9.0, 0.25) / 100
        g_term = c3.number_input("Terminal growth g (%)", -5.0, 10.0, 2.0, 0.25) / 100
        croissances = st.data_editor(pd.DataFrame({"FCF growth (%)": [0.0] * 5},
                                                  index=[f"Year {i}" for i in range(1, 6)]),
                                     key=f"dcf_g_{ticker}")["FCF growth (%)"].astype(float).div(100).tolist()
        dette_nette = (t["Long-term debt"].iloc[-1] if pd.notna(t["Long-term debt"].iloc[-1]) else 0) \
            - (t["Cash"].iloc[-1] if pd.notna(t["Cash"].iloc[-1]) else 0)
        dette_nette = st.number_input(f"Net debt ({etats.devise}) — LT debt minus cash, editable",
                                      value=float(dette_nette), step=1e6, format="%.0f")
        confirme = st.checkbox("These assumptions are mine and I justify them in the Analysis notebook.",
                               key=f"dcf_ok_{ticker}")

        resultat_dcf, sensib = None, pd.DataFrame()
        if not actions:
            st.warning("Share count unavailable: per-share DCF impossible.")
        elif fcf0 <= 0:
            st.warning("Starting FCF negative or zero: an FCF-based DCF is not meaningful as is "
                       "(consider an approach based on normalized revenue/margins).")
        elif confirme:
            try:
                resultat_dcf = fd.dcf(fcf0, croissances, wacc, g_term, dette_nette, actions)
            except ValueError as e:
                st.error(str(e))
        if resultat_dcf:
            metriques({"Value per share": resultat_dcf["Value per share"],
                       "Current price (same currency)": prix if prix else float("nan")}, "{:,.2f}", par_ligne=2)
            if resultat_dcf["Terminal value weight"] > 0.75:
                st.warning(f"The terminal value represents {resultat_dcf['Terminal value weight']:.0%} "
                           "of the value: the result depends mostly on g and the WACC.")
            st.dataframe(resultat_dcf["tableau"].style.format(
                {"Growth": "{:.1%}", "FCF": "{:,.0f}", "Discount factor": "{:.4f}", "Discounted FCF": "{:,.0f}"}),
                width="stretch", hide_index=True)
            st.markdown("**Value per share sensitivity (WACC × g)**")
            waccs = [wacc + d for d in (-0.02, -0.01, 0, 0.01, 0.02) if wacc + d > 0]
            gs = [g_term + d for d in (-0.01, -0.005, 0, 0.005, 0.01)]
            sensib = fd.sensibilite_dcf(fcf0, croissances, dette_nette, actions, waccs, gs)
            st.dataframe(sensib.style.format("{:,.2f}", na_rep="N/A"), width="stretch")

    # ------------------------------------------------ 4. Carnet d'analyse (rempli par l'analyste)
    with onglets[3]:
        sous_titre("Analysis notebook", "fa_carnet")
        st.markdown("These fields are **empty by design**: the terminal does not write your thesis. "
                    "They are kept during the session and included in the Excel export.")
        carnet = {}
        for cle, etiquette in CHAMPS_CARNET.items():
            carnet[etiquette] = st.text_area(etiquette, key=f"carnet_{ticker}_{cle}", height=110)

    # ------------------------------------------------ 5. Export
    with onglets[4]:
        sous_titre("Export the analysis", "fa_export")
        valo_df = pd.Series(valo, name="Value").to_frame()
        onglets_excel = {
            "Financial statements": t, "Ratios": ratios,
            "Definitions": pd.Series(fd.DEFINITIONS, name="Definition").to_frame(),
            "Valuation": valo_df,
            "Analysis notebook": pd.Series(carnet, name="Analyst's text").to_frame(),
        }
        if resultat_dcf:
            hyp = pd.Series({"Starting FCF": fcf0, "WACC": wacc, "Terminal growth": g_term,
                             "Net debt": dette_nette, "Share count": actions,
                             **{f"Growth year {i}": g for i, g in enumerate(croissances, 1)},
                             "Value per share": resultat_dcf["Value per share"],
                             "Terminal value weight": resultat_dcf["Terminal value weight"]},
                            name="Value").to_frame()
            onglets_excel |= {"DCF assumptions": hyp, "DCF cash flows": resultat_dcf["tableau"].set_index("Year"),
                              "DCF sensitivity": sensib}
        fichier = exporter_excel(onglets_excel, {
            "Company": etats.nom, "Ticker": ticker, "Statement source": etats.source,
            "Statement currency": etats.devise, "Price and currency": note_devise,
            "Notes": " | ".join(etats.notes) or "—",
            "Reminder": "Ratios computed by the terminal; thesis and conclusion written by the analyst.",
        })
        st.download_button("Download the analysis (Excel)", fichier, file_name=f"analysis_{ticker}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    note_methodo(
        "- **Official data first**: SEC EDGAR (XBRL). Yahoo fallback flagged when EDGAR does not have the company "
        "(common for the TSX: then check on SEDAR+ or in the annual report).\n"
        "- **Annual data** (10-K / 20-F / 40-F). Restated values: the most recent one is kept.\n"
        "- **ROE, ROA, turnover, leverage** on average balances: N/A for the first fiscal year shown.\n"
        "- **P/E on latest fiscal-year EPS**, not TTM: may differ from financial websites.\n"
        "- **Banks and insurers**: current ratio and gross margin not meaningful (unclassified balance sheet) → N/A expected."
    )
