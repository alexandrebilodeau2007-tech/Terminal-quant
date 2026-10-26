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
from interface.composants import metriques, note_methodo
from sources.etats_financiers import ErreurFondamentaux, donnees_de_marche, obtenir_etats_financiers
from sources.marche import ErreurDonnees, telecharger_prix

# Ratios exprimés en % (les autres sont des multiples, ex. 1,8x).
RATIOS_POURCENT = ["ROE", "ROA", "Marge brute", "Marge d'exploitation", "Marge nette",
                   "Passif / actif", "Croissance des revenus", "Croissance du bénéfice net"]
CHAMPS_CARNET = {
    "these": "Thèse d'investissement (en 3-5 phrases)",
    "catalyseurs": "Catalyseurs (quoi, quand, comment les mesurer)",
    "risques": "Risques principaux et ce qui invaliderait la thèse",
    "hypotheses": "Justification des hypothèses du DCF (croissance, WACC, g)",
    "conclusion": "Conclusion de l'analyste",
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
    st.header("3 · Analyse fondamentale")
    st.caption("Le terminal calcule. **Toi**, tu argumentes et tu conclus.")

    ticker = st.text_input("Ticker (Yahoo)", "AAPL", key="fd_ticker").strip().upper()
    if not ticker:
        return

    try:
        with st.spinner("Extraction des états financiers…"):
            etats = obtenir_etats_financiers(ticker, _user_agent())
    except ErreurFondamentaux as e:
        st.error(str(e))
        return
    except Exception as e:  # erreur réseau ou format inattendu : on l'affiche sans planter
        st.error(f"Impossible d'obtenir les états financiers : {e}")
        return

    t = etats.tableau
    st.markdown(f"**{etats.nom}** — source : `{etats.source}` — devise des états : **{etats.devise}**")
    for note in etats.notes:
        st.info(note)

    # ------------------------------------------------ prix dans la devise des états
    marche = donnees_de_marche(ticker)
    prix, actions = marche["prix"], marche["actions"]
    note_devise = "identique"
    if prix and marche["devise"] and marche["devise"] != etats.devise:
        # Ex. Shopify : cotée en CAD à Toronto, mais publie ses états en USD.
        # Diviser un prix en CAD par un BPA en USD donnerait un P/E faux.
        fx = _taux_de_change(marche["devise"], etats.devise)
        if fx:
            note_devise = f"prix converti {marche['devise']}→{etats.devise} au taux {fx:.4f}"
            prix = prix * fx
        else:
            note_devise = "conversion impossible : ratios de valorisation désactivés"
            prix = None
    ratios = fd.calculer_ratios(t)
    valo = fd.ratios_valorisation(t, prix, actions)

    onglets = st.tabs(["États financiers", "Ratios", "Valorisation & DCF", "Carnet d'analyse", "Export"])

    # ------------------------------------------------ 1. États financiers
    with onglets[0]:
        st.caption(f"Montants en {etats.devise} (unités, non arrondis). BPA en {etats.devise} par action.")
        affichage = t.T.copy()
        affichage.columns = [d.strftime("%Y-%m-%d") for d in t.index]
        st.dataframe(affichage.style.format("{:,.2f}", na_rep="N/A"), width="stretch")

    # ------------------------------------------------ 2. Ratios
    with onglets[1]:
        tableau = ratios.T.copy()
        tableau.columns = [d.strftime("%Y-%m") for d in ratios.index]
        # Format par défaut "1,85" (multiples), puis format % pour les lignes de RATIOS_POURCENT.
        st.dataframe(
            tableau.style.format(lambda v: "N/A" if pd.isna(v) else f"{v:,.2f}")
            .format(lambda v: "N/A" if pd.isna(v) else f"{v:.1%}", subset=pd.IndexSlice[RATIOS_POURCENT, :]),
            width="stretch")
        ecart = fd.verifier_dupont(ratios).dropna()
        if not ecart.empty and ecart.max() > 1e-6:
            st.warning("Contrôle DuPont : marge × rotation × levier ≠ ROE. Vérifie les données sources.")
        fig = px.line(ratios[["Marge brute", "Marge d'exploitation", "Marge nette", "ROE"]], markers=True,
                      labels={"value": "", "index": "", "variable": ""}, title="Marges et ROE")
        st.plotly_chart(fig.update_layout(yaxis_tickformat=".0%"), width="stretch")
        with st.expander("Définitions des ratios"):
            st.table(pd.Series(fd.DEFINITIONS, name="Définition"))

    # ------------------------------------------------ 3. Valorisation & DCF
    with onglets[2]:
        st.caption(f"Prix actuel / dernier exercice ({t.index[-1].date()}). Devise : {note_devise}.")
        metriques({k: valo[k] for k in ("P/E", "P/B", "P/S", "VE / EBIT")}, "{:.2f}x", par_ligne=5)
        metriques({"Rendement FCF": valo["Rendement FCF"]}, "{:.2%}", par_ligne=5)
        metriques({k: valo.get(k) for k in ("Capitalisation", "Valeur d'entreprise (VE)")}, "{:,.0f}", par_ligne=2)

        st.subheader("DCF — tes hypothèses")
        st.markdown("Aucune hypothèse n'est choisie à ta place. Les valeurs de départ sont **neutres** "
                    "(croissance 0 %) et doivent être remplacées puis justifiées dans le Carnet.")
        fcf_hist = ratios["Flux de trésorerie disponible (FCF)"].dropna()
        cagr_rev = (t["Revenus"].iloc[-1] / t["Revenus"].iloc[0]) ** (1 / max(len(t) - 1, 1)) - 1 \
            if t["Revenus"].iloc[0] > 0 else float("nan")
        st.caption(f"Repères historiques (pas des prévisions) : FCF du dernier exercice = "
                   f"{fcf_hist.iloc[-1]:,.0f} {etats.devise} ; croissance annuelle des revenus sur la période = "
                   f"{cagr_rev:.1%}." if not fcf_hist.empty else "FCF historique indisponible.")

        c1, c2, c3 = st.columns(3)
        fcf0 = c1.number_input(f"FCF de départ ({etats.devise})", value=float(fcf_hist.iloc[-1]) if not fcf_hist.empty else 0.0,
                               step=1e6, format="%.0f")
        wacc = c2.number_input("WACC (%)", 1.0, 30.0, 9.0, 0.25) / 100
        g_term = c3.number_input("Croissance terminale g (%)", -5.0, 10.0, 2.0, 0.25) / 100
        croissances = st.data_editor(pd.DataFrame({"Croissance du FCF (%)": [0.0] * 5},
                                                  index=[f"Année {i}" for i in range(1, 6)]),
                                     key=f"dcf_g_{ticker}")["Croissance du FCF (%)"].astype(float).div(100).tolist()
        dette_nette = (t["Dette à long terme"].iloc[-1] if pd.notna(t["Dette à long terme"].iloc[-1]) else 0) \
            - (t["Trésorerie"].iloc[-1] if pd.notna(t["Trésorerie"].iloc[-1]) else 0)
        dette_nette = st.number_input(f"Dette nette ({etats.devise}) — dette LT moins trésorerie, modifiable",
                                      value=float(dette_nette), step=1e6, format="%.0f")
        confirme = st.checkbox("Ces hypothèses sont les miennes et je les justifie dans le Carnet d'analyse.",
                               key=f"dcf_ok_{ticker}")

        resultat_dcf, sensib = None, pd.DataFrame()
        if not actions:
            st.warning("Nombre d'actions indisponible : DCF par action impossible.")
        elif fcf0 <= 0:
            st.warning("FCF de départ négatif ou nul : un DCF sur FCF n'est pas pertinent tel quel "
                       "(envisager une approche par revenus/marges normalisées).")
        elif confirme:
            try:
                resultat_dcf = fd.dcf(fcf0, croissances, wacc, g_term, dette_nette, actions)
            except ValueError as e:
                st.error(str(e))
        if resultat_dcf:
            metriques({"Valeur par action": resultat_dcf["Valeur par action"],
                       "Prix actuel (même devise)": prix if prix else float("nan")}, "{:,.2f}", par_ligne=2)
            if resultat_dcf["Poids de la valeur terminale"] > 0.75:
                st.warning(f"La valeur terminale représente {resultat_dcf['Poids de la valeur terminale']:.0%} "
                           "de la valeur : le résultat dépend surtout de g et du WACC.")
            st.dataframe(resultat_dcf["tableau"].style.format(
                {"Croissance": "{:.1%}", "FCF": "{:,.0f}", "Facteur d'actualisation": "{:.4f}", "FCF actualisé": "{:,.0f}"}),
                width="stretch", hide_index=True)
            st.markdown("**Sensibilité de la valeur par action (WACC × g)**")
            waccs = [wacc + d for d in (-0.02, -0.01, 0, 0.01, 0.02) if wacc + d > 0]
            gs = [g_term + d for d in (-0.01, -0.005, 0, 0.005, 0.01)]
            sensib = fd.sensibilite_dcf(fcf0, croissances, dette_nette, actions, waccs, gs)
            st.dataframe(sensib.style.format("{:,.2f}", na_rep="N/A"), width="stretch")

    # ------------------------------------------------ 4. Carnet d'analyse (rempli par l'analyste)
    with onglets[3]:
        st.markdown("Ces champs sont **vides par conception** : le terminal ne rédige pas ta thèse. "
                    "Ils sont conservés pendant la session et inclus dans l'export Excel.")
        carnet = {}
        for cle, etiquette in CHAMPS_CARNET.items():
            carnet[etiquette] = st.text_area(etiquette, key=f"carnet_{ticker}_{cle}", height=110)

    # ------------------------------------------------ 5. Export
    with onglets[4]:
        valo_df = pd.Series(valo, name="Valeur").to_frame()
        onglets_excel = {
            "États financiers": t, "Ratios": ratios,
            "Définitions": pd.Series(fd.DEFINITIONS, name="Définition").to_frame(),
            "Valorisation": valo_df,
            "Carnet d'analyse": pd.Series(carnet, name="Texte de l'analyste").to_frame(),
        }
        if resultat_dcf:
            hyp = pd.Series({"FCF de départ": fcf0, "WACC": wacc, "Croissance terminale": g_term,
                             "Dette nette": dette_nette, "Nombre d'actions": actions,
                             **{f"Croissance année {i}": g for i, g in enumerate(croissances, 1)},
                             "Valeur par action": resultat_dcf["Valeur par action"],
                             "Poids de la valeur terminale": resultat_dcf["Poids de la valeur terminale"]},
                            name="Valeur").to_frame()
            onglets_excel |= {"DCF hypothèses": hyp, "DCF flux": resultat_dcf["tableau"].set_index("Année"),
                              "DCF sensibilité": sensib}
        fichier = exporter_excel(onglets_excel, {
            "Société": etats.nom, "Ticker": ticker, "Source des états": etats.source,
            "Devise des états": etats.devise, "Prix et devise": note_devise,
            "Notes": " | ".join(etats.notes) or "—",
            "Rappel": "Ratios calculés par le terminal ; thèse et conclusion rédigées par l'analyste.",
        })
        st.download_button("Télécharger l'analyse (Excel)", fichier, file_name=f"analyse_{ticker}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    note_methodo(
        "- **Priorité aux données officielles** : SEC EDGAR (XBRL). Repli Yahoo signalé quand EDGAR n'a pas la société "
        "(fréquent pour le TSX : vérifier alors sur SEDAR+ ou dans le rapport annuel).\n"
        "- **Données annuelles** (10-K / 20-F / 40-F). Valeurs retraitées : la plus récente est retenue.\n"
        "- **ROE, ROA, rotation, levier** sur moyennes de bilan : N/A pour le premier exercice affiché.\n"
        "- **P/E sur BPA du dernier exercice**, pas TTM : peut différer des sites financiers.\n"
        "- **Banques et assureurs** : liquidité générale et marges brutes non pertinentes (bilan non classé) → N/A attendus."
    )
