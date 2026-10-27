"""
SEAS — Saisonnalité (graphique saisonnier, statistiques de fenêtre, screener,
événements, mensuel, liste de suivi).

Données : Yahoo Finance, TOUT l'historique disponible (indépendant de la période
globale : une saisonnalité se mesure sur 10, 15 ou 25 ans). Prix ajustés, en
devise locale de l'actif (pas de conversion : on étudie le comportement de l'actif).

Tous les calculs sont dans calculs/saisonnalite.py (testés) ; cette page ne fait
qu'afficher et gérer les réglages.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calculs import saisonnalite as sz
from config import CACHE_PRIX
from export.excel import exporter_excel
from interface.aide import sous_titre, titre
from interface.composants import metriques, note_methodo
from interface.navigation import valeur_initiale
from interface.theme import AMBRE, GRILLE, ROUGE, TEXTE_DOUX, VERT
from repertoire import FAMILLES_NON_INVESTISSABLES, REPERTOIRE
from sources.marche import ErreurDonnees, telecharger_prix

BLEU = "#4EA8DE"
HORIZONS = {"5 years": 5, "10 years": 10, "15 years": 15, "20 years": 20, "25 years": 25, "30 years": 30, "Max": 200}
NOMS = {yahoo: nom for entrees in REPERTOIRE.values() for nom, yahoo, _tv, _n in entrees}
OPTIONS_ACTIFS = [f"{nom} ({yahoo})" for entrees in REPERTOIRE.values() for nom, yahoo, _tv, _n in entrees]
ACTIF_DEFAUT = "S&P 500 (^GSPC)"


# =========================================================================== données
def _ticker(libelle: str) -> str:
    """« Gold (GC=F) » -> « GC=F » ; un ticker tapé à la main est gardé tel quel."""
    m = re.search(r"\(([^()]+)\)\s*$", libelle or "")
    return (m.group(1) if m else (libelle or "")).strip().upper()


def _libelle(ticker: str) -> str:
    return f"{NOMS[ticker]} ({ticker})" if ticker in NOMS else ticker


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def historique(ticker: str) -> pd.Series:
    """Tout l'historique de clôtures ajustées (depuis 1950 si Yahoo l'a)."""
    fin = (date.today() + timedelta(days=1)).isoformat()
    return telecharger_prix((ticker,), "1950-01-01", fin)[ticker].dropna()


def historiques(tickers: list[str]) -> tuple[dict[str, pd.Series], list[str]]:
    """Plusieurs actifs d'un coup ; ceux qui échouent sont listés au lieu de tout bloquer."""
    fin = (date.today() + timedelta(days=1)).isoformat()
    try:
        tab = telecharger_prix(tuple(tickers), "1950-01-01", fin)
        return {t: tab[t].dropna() for t in tickers if t in tab}, []
    except ErreurDonnees:
        ok, echecs = {}, []
        for t in tickers:
            try:
                ok[t] = historique(t)
            except ErreurDonnees:
                echecs.append(t)
        return ok, echecs


@st.cache_data(ttl=CACHE_PRIX, show_spinner=False)
def grille(ticker: str) -> pd.DataFrame:
    return sz.grille_calendaire(historique(ticker))


def _selecteur_actif(cle: str, libelle: str = "Asset (directory or any Yahoo ticker)") -> str:
    commande = st.session_state.pop("cmd_seas_ticker", None) if cle == "seas_actif" else None
    if commande:                     # barre de commande : « SEAS GC=F »
        st.session_state[cle] = _libelle(commande)
    valeur_initiale(cle, ACTIF_DEFAUT)
    options = OPTIONS_ACTIFS if st.session_state[cle] in OPTIONS_ACTIFS else [st.session_state[cle]] + OPTIONS_ACTIFS
    choix = st.selectbox(libelle, options, key=cle, accept_new_options=True,
                         help="Pick from the directory or type any Yahoo ticker (e.g. KC=F, ^N225, SHOP.TO), then Enter.")
    return _ticker(choix)


# =========================================================================== page
def afficher(params: dict) -> None:
    titre("Seasonality", "seas", "SEAS",
          "Average yearly pattern, pattern statistics, screener for the best windows, events and monthly returns.")
    _appliquer_chargement_en_attente()
    o1, o2, o3, o4, o5 = st.tabs([":material/calendar_month: Seasonal chart", ":material/travel_explore: Screener",
                                  ":material/event: Events", ":material/grid_on: Monthly & weekdays",
                                  ":material/bookmark: Watchlist"])
    with o1:
        _onglet_graphique()
    with o2:
        _onglet_screener()
    with o3:
        _onglet_evenements()
    with o4:
        _onglet_mensuel()
    with o5:
        _onglet_suivi()


def _appliquer_chargement_en_attente() -> None:
    """Une ligne choisie dans le screener ou la liste de suivi est chargée dans le graphique
    AVANT la création des champs (Streamlit interdit de modifier un champ déjà affiché)."""
    a = st.session_state.pop("seas_charger", None)
    if a:
        st.session_state["seas_actif"] = _libelle(a["ticker"])
        st.session_state["seas_debut"] = sz.ETIQUETTES[a["start_day"]]
        st.session_state["seas_fin"] = sz.ETIQUETTES[a["end_day"]]
        st.session_state["seas_sens"] = a["direction"]
        if a.get("years"):
            st.session_state["seas_horizon"] = next((k for k, v in HORIZONS.items() if v == a["years"]), "15 years")
        st.toast(f"Loaded in the Seasonal chart tab: {a['ticker']} {sz.ETIQUETTES[a['start_day']]} → "
                 f"{sz.ETIQUETTES[a['end_day']]}", icon=":material/calendar_month:")


# =========================================================================== 1. graphique saisonnier
def _selection_depuis_graphique() -> None:
    """Glisser sur le graphique (sélection rectangulaire) fixe le début et la fin de la fenêtre."""
    etat = st.session_state.get("seas_graphique")
    try:
        boites = etat["selection"]["box"] if etat else []
    except (KeyError, TypeError):
        boites = []
    if not boites:
        return
    x = sorted(pd.Timestamp(v) for v in boites[0]["x"])
    signature = (str(x[0]), str(x[1]))
    if signature == st.session_state.get("seas_derniere_boite"):
        return
    st.session_state["seas_derniere_boite"] = signature
    debut = sz.jour_de_l_annee(max(x[0], pd.Timestamp("2001-01-01")))
    fin = sz.jour_de_l_annee(min(x[1], pd.Timestamp("2001-12-31")))
    st.session_state["seas_debut"], st.session_state["seas_fin"] = sz.ETIQUETTES[debut], sz.ETIQUETTES[fin]


def _onglet_graphique() -> None:
    sous_titre("Seasonal chart", "seas_chart")
    _selection_depuis_graphique()
    c1, c2, c3, c4 = st.columns([3, 1.3, 1.3, 1.3])
    with c1:
        ticker = _selecteur_actif("seas_actif")
    valeur_initiale("seas_horizon", "15 years")
    horizon = HORIZONS[c2.selectbox("Years", list(HORIZONS), key="seas_horizon")]
    valeur_initiale("seas_sens", "Long")
    sens = c3.segmented_control("Direction", ["Long", "Short"], key="seas_sens", required=True) or "Long"
    valeur_initiale("seas_courbe", "Average")
    type_courbe = c4.segmented_control("Curve", ["Average", "Median"], key="seas_courbe", required=True) or "Average"

    try:
        with st.spinner(f"Loading the full history of {ticker}…"):
            prix = historique(ticker)
            g = grille(ticker)
    except ErreurDonnees as e:
        st.error(str(e))
        return
    completes = sz.annees_completes(g)
    if len(completes) < 3:
        st.warning(f"{ticker}: fewer than 3 complete years of history — a seasonal pattern is not measurable.")
        return

    f1, f2, f3, f4, f5 = st.columns([1.7, 2.0, 1.25, 1.35, 1.7])
    valeur_initiale("seas_cycle", "All years")
    cycle = sz.CYCLES[f1.selectbox("Year filter", list(sz.CYCLES), key="seas_cycle",
                                   help="US presidential cycle, odd or even years.")]
    exclues = f2.multiselect("Exclude years (outliers)", completes[::-1], key="seas_exclure",
                             help="E.g. 2008 or 2020, to see the pattern without a crisis year.")
    detendance = f3.toggle("Detrend", key="seas_detendance",
                           help="Removes the long-term trend so only the seasonal shape remains.")
    annee_courante = f4.toggle("This year", value=True, key="seas_annee_courante",
                               help="Overlay this year's path on the seasonal chart.")
    comparer = _ticker(f5.text_input("Compare with (optional ticker)", key="seas_comparer", placeholder="e.g. SPY"))

    annees_courbe = sz.filtrer_annees(completes, cycle, exclues)[-horizon:]
    if len(annees_courbe) < 3:
        st.warning("Fewer than 3 years remain after the filters.")
        return

    # --- fenêtre (curseurs ; ou glisser sur le graphique)
    valeur_initiale("seas_debut", "Mar 01")
    valeur_initiale("seas_fin", "Apr 30")
    w1, w2 = st.columns(2)
    debut_lbl = w1.select_slider("Pattern start", sz.ETIQUETTES, key="seas_debut")
    fin_lbl = w2.select_slider("Pattern end", sz.ETIQUETTES, key="seas_fin")
    debut, fin = sz.ETIQUETTES.index(debut_lbl), sz.ETIQUETTES.index(fin_lbl)
    jours = sz.duree_calendaire(debut, fin)
    st.caption(f"Tip: **drag across the chart** to select a window. "
               f"{'The window crosses New Year and ends the following year. ' if fin < debut else ''}"
               f"Window: {debut_lbl} → {fin_lbl} ({jours} calendar days).")

    courbe = sz.courbe_saisonniere(g, annees_courbe, detendance, mediane=(type_courbe == "Median"))
    if sens == "Short":
        courbe_aff = -courbe
    else:
        courbe_aff = courbe
    fig = go.Figure()
    x = sz.REFERENCE
    for (a, b) in ([(debut, fin)] if fin >= debut else [(debut, 364), (0, fin)]):
        fig.add_vrect(x0=x[a] - pd.Timedelta(hours=12), x1=x[b] + pd.Timedelta(hours=12),
                      fillcolor=VERT if sens == "Long" else ROUGE, opacity=0.13, line_width=0)
    fig.add_trace(go.Scatter(x=x, y=courbe_aff * 100, name=f"{ticker} · {type_courbe.lower()} of "
                             f"{len(annees_courbe)} years ({annees_courbe[0]}–{annees_courbe[-1]})",
                             line={"color": AMBRE, "width": 2.4}, hovertemplate="%{x|%b %d}: %{y:.2f}%<extra></extra>"))
    if annee_courante:
        an = date.today().year
        pente = float(courbe.iloc[-1]) if detendance else None
        chemin = sz.chemin_annee_en_cours(g, an, pente)
        if not chemin.empty:
            yv = -chemin if sens == "Short" else chemin
            fig.add_trace(go.Scatter(x=x[chemin.index], y=yv * 100, name=f"{an} (so far)",
                                     line={"color": BLEU, "width": 1.6, "dash": "dot"},
                                     hovertemplate="%{x|%b %d}: %{y:.2f}%<extra></extra>"))
    if comparer and comparer != ticker:
        try:
            g2 = grille(comparer)
            a2 = [a for a in annees_courbe if a in sz.annees_completes(g2)]
            if len(a2) >= 3:
                c2v = sz.courbe_saisonniere(g2, a2, detendance, mediane=(type_courbe == "Median"))
                fig.add_trace(go.Scatter(x=x, y=(-c2v if sens == "Short" else c2v) * 100,
                                         name=f"{comparer} · {len(a2)} years", line={"color": "#E5E5E5", "width": 1.4},
                                         hovertemplate="%{x|%b %d}: %{y:.2f}%<extra></extra>"))
            else:
                st.caption(f"{comparer}: not enough common years to compare.")
        except ErreurDonnees as e:
            st.caption(f"Comparison unavailable: {e}")
    fig.add_hline(y=0, line={"color": TEXTE_DOUX, "width": 0.8})
    fig.update_layout(height=470, dragmode="select", hovermode="x unified",
                      title=f"Seasonal chart — {_libelle(ticker)}{' (detrended)' if detendance else ''}"
                            f"{' · short view' if sens == 'Short' else ''}",
                      yaxis={"title": "Cumulative change (%)", "ticksuffix": "%"},
                      xaxis={"tickformat": "%b", "dtick": "M1", "range": [x[0] - pd.Timedelta(days=2), x[-1] + pd.Timedelta(days=2)]},
                      legend={"orientation": "h", "y": -0.12})
    st.plotly_chart(fig, key="seas_graphique", on_select="rerun", selection_mode="box", width="stretch",
                    config={"modeBarButtonsToRemove": ["lasso2d"], "displaylogo": False})

    # --- statistiques de la fenêtre
    annees_fen = sz.filtrer_annees(sz.annees_fenetre(g, debut, fin), cycle, exclues)[-horizon:]
    table = sz.rendements_fenetre(g, debut, fin, annees_fen, short=(sens == "Short"))
    if table.empty:
        st.warning("No year with a complete window.")
        return
    quotidiens = sz.rendements_quotidiens_fenetres(prix, table, debut)
    if sens == "Short":
        quotidiens = -quotidiens
    s = sz.statistiques_fenetre(table, jours, quotidiens, sz.jours_de_bourse_moyens(prix, table))
    sig = sz.significativite(table)
    rang = sz.comparaison_toutes_fenetres(g, annees_fen, debut, fin, short=(sens == "Short"))

    sous_titre(f"Pattern statistics — {sens} {debut_lbl} → {fin_lbl}, {s['Years']} years "
               f"({table.index.min()}–{table.index.max()})", "seas_stats")
    metriques({"Annualized return": f"{s['Annualized return']:+.2%}", "Average return": f"{s['Average return']:+.2%}",
               "Median return": f"{s['Median return']:+.2%}",
               "Hit rate": f"{s['Hit rate']:.0%} ({s['Gains']}/{s['Years']})"}, "{}")
    metriques({"Average profit": s["Average profit"], "Average loss": s["Average loss"],
               "Max profit": s["Max profit"], "Max loss": s["Max loss"]}, "{:+.2%}")
    metriques({"Gains / losses": f"{s['Gains']} / {s['Losses']}",
               "Standard deviation": f"{s['Standard deviation']:.2%}" if pd.notna(s["Standard deviation"]) else "N/A",
               "Volatility (annualized)": f"{s['Volatility']:.2%}" if pd.notna(s["Volatility"]) else "N/A",
               "Sharpe / Sortino": f"{s['Sharpe ratio']:.2f} / {s['Sortino ratio']:.2f}" if pd.notna(s["Sharpe ratio"]) else "N/A"},
              "{}")
    metriques({"Calendar days": f"{s['Calendar days']:.0f}", "Trading days (avg)": f"{s['Trading days']:.1f}",
               "Better than … of all windows": f"{rang['Percentile vs all windows']:.0%}"
               if pd.notna(rang["Percentile vs all windows"]) else "N/A",
               "Excess vs typical window": f"{rang['Excess vs typical window']:+.2%}"
               if pd.notna(rang["Excess vs typical window"]) else "N/A"}, "{}")
    _verdict(s, sig, rang)

    # --- graphiques par année
    g1, g2 = st.columns([3, 2])
    with g1:
        couleurs = [VERT if v > 0 else ROUGE for v in table["Return"]]
        fb = go.Figure(go.Bar(x=table.index.astype(str), y=table["Return"] * 100, marker_color=couleurs,
                              text=[f"{v:+.1%}" for v in table["Return"]], textposition="outside",
                              hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
        fb.add_hline(y=s["Average return"] * 100, line={"color": AMBRE, "dash": "dash"},
                     annotation_text=f"average {s['Average return']:+.2%}", annotation_position="top left")
        fb.update_layout(height=340, title="Pattern return by year", yaxis={"ticksuffix": "%"}, xaxis={"type": "category"})
        st.plotly_chart(fb, width="stretch")
    with g2:
        cum = sz.profit_cumule(table)
        fc = go.Figure(go.Scatter(x=cum.index.astype(str), y=(cum - 1) * 100, mode="lines+markers",
                                  line={"color": AMBRE}, fill="tozeroy", fillcolor="rgba(255,159,28,0.12)",
                                  hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
        fc.update_layout(height=340, title="Cumulative profit (window only, compounded)",
                         yaxis={"ticksuffix": "%"}, xaxis={"type": "category"})
        st.plotly_chart(fc, width="stretch")

    sous_titre("Pattern details by year", "seas_detail")
    vue = table.sort_index(ascending=False).copy()
    st.dataframe(vue.style.format({"Start price": "{:,.2f}", "End price": "{:,.2f}", "Return": "{:+.2%}",
                                   "Max rise": "{:+.2%}", "Max drop": "{:+.2%}"})
                 .map(lambda v: f"color: {VERT}" if v > 0 else f"color: {ROUGE}" if v < 0 else "", subset=["Return"]),
                 width="stretch", height=min(38 * len(vue) + 40, 520))

    # --- cours avec les fenêtres surlignées
    with st.expander("Price chart with the pattern windows highlighted", icon=":material/show_chart:"):
        recents = table.tail(min(len(table), 8))
        depart = pd.Timestamp(recents["Start"].min()) - pd.Timedelta(days=60)
        p = prix[prix.index >= depart]
        fp = go.Figure(go.Scatter(x=p.index, y=p.values, line={"color": "#E5E5E5", "width": 1.2}, name=ticker))
        for an, l in recents.iterrows():
            fp.add_vrect(x0=l["Start"], x1=l["End"], fillcolor=VERT if l["Return"] > 0 else ROUGE, opacity=0.2, line_width=0)
        fp.update_layout(height=360, title=f"{ticker} — last {len(recents)} windows (green = gain, red = loss)",
                         yaxis={"type": "log", "title": "Price (log scale)"}, showlegend=False)
        st.plotly_chart(fp, width="stretch")

    # --- actions : liste de suivi, export
    b1, b2 = st.columns(2)
    if b1.button("Add this pattern to the watchlist", icon=":material/bookmark_add:", width="stretch"):
        st.session_state.setdefault("seas_suivi", []).append({
            "ticker": ticker, "direction": sens, "start_day": debut, "end_day": fin, "years": horizon,
            "avg": s["Average return"], "hit": s["Hit rate"], "ann": s["Annualized return"], "n": s["Years"]})
        st.toast("Added to the watchlist.", icon=":material/bookmark:")
    stats_df = pd.Series({**s, **sig, **rang}, name="Value").to_frame()
    courbe_df = pd.DataFrame({"Day": sz.ETIQUETTES, "Seasonal curve": courbe_aff.values})
    fichier = exporter_excel({"Pattern statistics": stats_df, "Pattern by year": table, "Seasonal curve": courbe_df.set_index("Day")},
                             {"Asset": ticker, "Window": f"{debut_lbl} → {fin_lbl}", "Direction": sens,
                              "Years": f"{table.index.min()}–{table.index.max()} ({len(table)})",
                              "Year filter": next(k for k, v in sz.CYCLES.items() if v == cycle),
                              "Excluded years": ", ".join(map(str, exclues)) or "none", "Detrended": detendance,
                              "Curve": type_courbe, "Source": "Yahoo Finance (yfinance), adjusted closes, local currency"})
    b2.download_button("Export to Excel", fichier, file_name=f"seasonality_{ticker}_{debut_lbl}_{fin_lbl}.xlsx".replace(" ", ""),
                       icon=":material/download:", width="stretch", key="seas_export")
    _note_methode()


def _verdict(s: dict, sig: dict, rang: dict) -> None:
    """Lecture simple : un effet saisonnier est-il plausible, ou peut-il venir du hasard ?"""
    p_moy, p_taux, pct = sig["p-value (mean)"], sig["p-value (hit rate)"], rang["Percentile vs all windows"]
    texte = (f"t-test on the average: p = {p_moy:.3f} · binomial test on the hit rate: p = {p_taux:.3f} · "
             f"this window beats {pct:.0%} of all windows of the same length.") if pd.notna(p_moy) else ""
    if pd.isna(p_moy):
        st.info("Not enough years for a statistical test.")
    elif p_moy < 0.05 and p_taux < 0.10 and pct >= 0.80:
        st.success(f"**Statistically robust pattern** (at the 5% level). {texte} "
                   "Still check that there is an economic reason (harvest, heating season, year-end flows…).")
    elif p_moy < 0.10 or p_taux < 0.10:
        st.warning(f"**Borderline evidence**: could partly be chance. {texte}")
    else:
        st.error(f"**Not significant**: this result could easily be chance. {texte} "
                 "With 10–15 years, even random prices show windows that won 80% of the time.")


# =========================================================================== 2. screener
def _onglet_screener() -> None:
    sous_titre("Seasonal pattern screener", "seas_screener")
    familles_ok = [f for f in REPERTOIRE if f not in FAMILLES_NON_INVESTISSABLES]
    c1, c2 = st.columns([3, 2])
    valeur_initiale("seas_sc_familles", ["Indices", "Commodities (futures)"])
    familles = c1.multiselect("Families from the directory", familles_ok, key="seas_sc_familles")
    autres = c2.text_input("Other tickers (comma-separated)", key="seas_sc_autres", placeholder="e.g. MU, KC=F, ^N225")
    tickers = [y for f in familles for _n, y, _t, _d in REPERTOIRE[f]]
    tickers += [t.strip().upper() for t in autres.split(",") if t.strip()]
    tickers = list(dict.fromkeys(tickers))

    p1, p2, p3, p4 = st.columns(4)
    annees = p1.selectbox("Years", [5, 10, 15, 20, 25], index=2, key="seas_sc_annees")
    jmin, jmax = p2.slider("Pattern length (calendar days)", 5, 120, (10, 45), key="seas_sc_jours")
    taux = p3.slider("Minimum hit rate", 0.5, 1.0, 0.8, 0.05, format="%.2f", key="seas_sc_taux")
    sens = p4.selectbox("Direction", ["Both", "Long", "Short"], key="seas_sc_sens")
    q1, q2, q3 = st.columns(3)
    debut_dans = q1.number_input("Starting within the next … days (0 = any time)", 0, 365, 30, key="seas_sc_dans")
    tri = q2.selectbox("Sort by", ["Annualized return", "Hit rate", "Average return", "Return / risk"], key="seas_sc_tri")
    par_actif = q3.number_input("Patterns per asset (non-overlapping)", 1, 5, 2, key="seas_sc_par")
    st.caption(f"{len(tickers)} asset(s) to scan. Each asset is tested on every start day of the year × every length "
               "in the range, long and short.")

    if st.button("Run the screener", icon=":material/travel_explore:", type="primary", disabled=not tickers):
        crit = sz.CriteresScreener(annees=annees, jours_min=jmin, jours_max=jmax, taux_min=taux, sens=sens,
                                   debut_dans=debut_dans or None, aujourd_hui=date.today(), tri=tri, par_actif=par_actif)
        with st.spinner(f"Downloading {len(tickers)} histories and scanning…"):
            series, echecs = historiques(tickers)
            resultats = []
            for t, p in series.items():
                r = sz.chercher_fenetres(sz.grille_calendaire(p), crit)
                if not r.empty:
                    r.insert(0, "Asset", t)
                    r.insert(1, "Name", NOMS.get(t, t))
                    resultats.append(r)
        res = pd.concat(resultats, ignore_index=True) if resultats else pd.DataFrame()
        if not res.empty:
            aujourd = date.today()
            res["Next start"] = [sz.prochaine_date(d, aujourd) for d in res["start_day"]]
            res["Starts in (days)"] = [(d - aujourd).days for d in res["Next start"]]
            res = res.sort_values([tri, "Hit rate"], ascending=False).reset_index(drop=True)
        st.session_state["seas_sc_resultats"] = (res, echecs, annees)

    if "seas_sc_resultats" not in st.session_state:
        st.info("Set the criteria, then run the screener.")
        return
    res, echecs, annees_sc = st.session_state["seas_sc_resultats"]
    if echecs:
        st.caption(f"Skipped (no data): {', '.join(echecs)}")
    if res.empty:
        st.warning("No pattern meets these criteria. Lower the hit rate or widen the length range.")
        return
    colonnes = ["Asset", "Name", "Direction", "Start", "End", "days", "Annualized return", "Average return", "Hit rate",
                "Worst year", "Return / risk", "Years", "Next start", "Starts in (days)"]
    evenement = st.dataframe(
        res[colonnes].rename(columns={"days": "Days"}), hide_index=True, width="stretch", on_select="rerun", height=460,
        selection_mode="single-row", key="seas_sc_table",
        column_config={"Annualized return": st.column_config.NumberColumn(format="percent"),
                       "Average return": st.column_config.NumberColumn(format="percent"),
                       "Hit rate": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1),
                       "Worst year": st.column_config.NumberColumn(format="percent"),
                       "Return / risk": st.column_config.NumberColumn(format="%.2f")})
    st.caption(f"{len(res)} pattern(s). **Select a row** to open it in the Seasonal chart tab. "
               "Remember: scanning thousands of windows always finds some that look excellent by chance — "
               "check the significance verdict before trusting one.")
    lignes = evenement.selection.rows if evenement and evenement.selection else []
    if lignes:
        l = res.iloc[lignes[0]]
        st.session_state["seas_charger"] = {"ticker": l["Asset"], "start_day": int(l["start_day"]),
                                            "end_day": int(l["end_day"]), "direction": l["Direction"], "years": annees_sc}
        st.rerun()
    fichier = exporter_excel({"Screener": res.drop(columns=["start_day", "end_day"])},
                             {"Assets scanned": len(tickers), "Years": annees_sc, "Lengths": f"{jmin}–{jmax} days",
                              "Minimum hit rate": taux, "Direction": sens, "Sorted by": tri,
                              "Source": "Yahoo Finance (yfinance), adjusted closes"})
    st.download_button("Export the screener (Excel)", fichier, file_name="seasonality_screener.xlsx",
                       icon=":material/download:", key="seas_sc_export")


# =========================================================================== 3. événements
def _onglet_evenements() -> None:
    sous_titre("Event-based seasonality", "seas_events")
    c1, c2, c3 = st.columns([3, 3, 1.4])
    with c1:
        ticker = _selecteur_actif("seas_ev_actif")
    evenement = c2.selectbox("Event", sz.EVENEMENTS, key="seas_ev_type")
    horizon = HORIZONS[c3.selectbox("Years", list(HORIZONS), index=3, key="seas_ev_horizon")]
    personnalisees = []
    if evenement == "Custom dates":
        brut = st.text_area("Dates (YYYY-MM-DD, one per line or comma-separated)", key="seas_ev_dates",
                            placeholder="2024-03-20\n2024-06-12\n2024-09-18", help="E.g. FOMC decisions, earnings dates.")
        for morceau in re.split(r"[\s,;]+", brut.strip()):
            try:
                personnalisees.append(pd.Timestamp(morceau).date())
            except (ValueError, TypeError):
                pass
    d1, d2, d3 = st.columns(3)
    avant = d1.slider("Trading days before", 0, 60, 10, key="seas_ev_avant")
    apres = d2.slider("Trading days after", 1, 60, 20, key="seas_ev_apres")
    valeur_initiale("seas_ev_sens", "Long")
    sens = d3.segmented_control("Direction", ["Long", "Short"], key="seas_ev_sens", required=True) or "Long"
    try:
        prix = historique(ticker)
    except ErreurDonnees as e:
        st.error(str(e))
        return
    derniere = prix.index.max().year
    annees = list(range(max(prix.index.min().year + 1, derniere - horizon + 1), derniere + 1))
    dates = sz.dates_evenement(evenement, prix.index, annees, personnalisees)
    chemins = sz.etude_evenement(prix, dates, avant, apres)
    if len(chemins) < 3:
        st.warning("Fewer than 3 events with enough data around them.")
        return
    decalages = list(range(-avant, apres + 1))
    actuel = st.session_state.get("seas_ev_fenetre")
    if not (isinstance(actuel, (tuple, list)) and len(actuel) == 2 and actuel[0] in decalages and actuel[1] in decalages):
        st.session_state["seas_ev_fenetre"] = (0, min(apres, 10))   # bornes changées : on repart d'une fenêtre valide
    a, b = st.select_slider("Window to measure (trading days relative to the event, day 0 = event close)",
                            decalages, key="seas_ev_fenetre")
    if a >= b:
        st.warning("The window end must be after its start.")
        return
    moy, med = chemins.mean(), chemins.median()
    sgn = -1 if sens == "Short" else 1
    fig = go.Figure()
    fig.add_vrect(x0=a, x1=b, fillcolor=VERT if sens == "Long" else ROUGE, opacity=0.13, line_width=0)
    for _, l in chemins.iterrows():
        fig.add_trace(go.Scatter(x=chemins.columns, y=sgn * l.values * 100, line={"color": GRILLE, "width": 0.8},
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=chemins.columns, y=sgn * moy.values * 100, name="Average", line={"color": AMBRE, "width": 2.6}))
    fig.add_trace(go.Scatter(x=chemins.columns, y=sgn * med.values * 100, name="Median", line={"color": BLEU, "width": 1.6, "dash": "dot"}))
    fig.add_vline(x=0, line={"color": TEXTE_DOUX, "dash": "dash"})
    fig.update_layout(height=430, title=f"{ticker} around « {evenement} » — {len(chemins)} events",
                      xaxis={"title": "Trading days from the event"}, yaxis={"title": "Change from day-0 close (%)", "ticksuffix": "%"},
                      legend={"orientation": "h", "y": -0.18})
    st.plotly_chart(fig, width="stretch")
    table = sz.fenetre_evenement(chemins, a, b, short=(sens == "Short"))
    s = sz.statistiques_fenetre(table, max(1, round((b - a) * 365 / 252)), None, b - a)
    sig = sz.significativite(table)
    metriques({"Average return": f"{s['Average return']:+.2%}", "Median return": f"{s['Median return']:+.2%}",
               "Hit rate": f"{s['Hit rate']:.0%} ({s['Gains']}/{s['Years']})",
               "Annualized return": f"{s['Annualized return']:+.2%}"}, "{}")
    metriques({"Max profit": f"{s['Max profit']:+.2%}", "Max loss": f"{s['Max loss']:+.2%}",
               "Standard deviation": f"{s['Standard deviation']:.2%}" if pd.notna(s["Standard deviation"]) else "N/A",
               "Events": f"{s['Years']}"}, "{}")
    if pd.notna(sig["p-value (mean)"]):
        (st.success if sig["p-value (mean)"] < 0.05 else st.warning if sig["p-value (mean)"] < 0.10 else st.error)(
            f"t-test p = {sig['p-value (mean)']:.3f} · binomial p = {sig['p-value (hit rate)']:.3f} "
            f"({'significant at 5%' if sig['p-value (mean)'] < 0.05 else 'not significant at 5%'}).")
    vue = table.copy()
    vue.index.name = "Event date"
    st.dataframe(vue.sort_index(ascending=False).style.format({"Return": "{:+.2%}"}), width="stretch",
                 height=min(35 * len(vue) + 40, 420))
    fichier = exporter_excel({"Event returns": vue, "Paths": chemins},
                             {"Asset": ticker, "Event": evenement, "Window": f"day {a} → day {b}", "Direction": sens,
                              "Events": len(chemins), "Source": "Yahoo Finance (yfinance), adjusted closes"})
    st.download_button("Export (Excel)", fichier, file_name=f"event_{ticker}.xlsx", icon=":material/download:", key="seas_ev_export")


# =========================================================================== 4. mensuel
def _onglet_mensuel() -> None:
    sous_titre("Monthly returns and weekdays", "seas_monthly")
    c1, c2 = st.columns([3, 1.4])
    with c1:
        ticker = _selecteur_actif("seas_mo_actif")
    horizon = HORIZONS[c2.selectbox("Years", list(HORIZONS), index=3, key="seas_mo_horizon")]
    try:
        prix = historique(ticker)
    except ErreurDonnees as e:
        st.error(str(e))
        return
    tab = sz.rendements_mensuels_table(prix).tail(horizon)
    stats = sz.statistiques_mensuelles(tab)
    hm = go.Figure(go.Heatmap(z=tab.values * 100, x=tab.columns, y=tab.index.astype(str), zmid=0,
                              colorscale=[[0, ROUGE], [0.5, "#11161D"], [1, VERT]],
                              text=[[f"{v:+.1f}" if pd.notna(v) else "" for v in r] for r in tab.values * 100],
                              texttemplate="%{text}", textfont={"size": 10},
                              hovertemplate="%{y} %{x}: %{z:.2f}%<extra></extra>", colorbar={"ticksuffix": "%"}))
    hm.update_layout(height=max(360, 24 * len(tab) + 120), title=f"{ticker} — monthly returns (%)",
                     yaxis={"autorange": "reversed", "type": "category"})
    st.plotly_chart(hm, width="stretch")
    if True:
        fb = go.Figure(go.Bar(x=stats.index, y=stats["Average"] * 100, marker_color=[VERT if v > 0 else ROUGE for v in stats["Average"]],
                              text=[f"{h:.0%} up" for h in stats["Hit rate"]], textposition="outside",
                              hovertemplate="%{x}: %{y:.2f}%<extra></extra>"))
        fb.update_layout(height=330, title="Average return by month (label = share of positive years)", yaxis={"ticksuffix": "%"})
        st.plotly_chart(fb, width="stretch")
    if True:
        idx = pd.IndexSlice
        st.dataframe(stats.T.style.format("{:+.2%}", subset=idx[["Average", "Median", "Best", "Worst"], :])
                     .format("{:.0%}", subset=idx[["Hit rate"], :]).format("{:.0f}", subset=idx[["Years"], :]),
                     width="stretch")
    annees = list(tab.index)
    sem = sz.statistiques_jours_semaine(prix, annees)
    st.markdown("**Weekdays** (same years)")
    st.dataframe(sem.style.format({"Average": "{:+.3%}", "Hit rate": "{:.1%}", "Volatility (annualized)": "{:.1%}", "Days": "{:.0f}"}),
                 width="stretch")
    fichier = exporter_excel({"Monthly returns": tab, "Monthly statistics": stats, "Weekdays": sem},
                             {"Asset": ticker, "Years": f"{annees[0]}–{annees[-1]}", "Source": "Yahoo Finance (yfinance), adjusted closes"})
    st.download_button("Export (Excel)", fichier, file_name=f"monthly_{ticker}.xlsx", icon=":material/download:", key="seas_mo_export")


# =========================================================================== 5. liste de suivi
def _onglet_suivi() -> None:
    sous_titre("Watchlist", "seas_watch")
    suivi = st.session_state.get("seas_suivi", [])
    if not suivi:
        st.info("Empty. In the Seasonal chart tab, click « Add this pattern to the watchlist ».")
        return
    aujourd = date.today()
    lignes = []
    for f in suivi:
        prochain = sz.prochaine_date(f["start_day"], aujourd)
        fin = prochain + timedelta(days=sz.duree_calendaire(f["start_day"], f["end_day"]) - 1)
        en_cours = sz.prochaine_date(f["start_day"], aujourd - timedelta(days=sz.duree_calendaire(f["start_day"], f["end_day"]) - 1))
        actif = en_cours <= aujourd
        lignes.append({"Asset": f["ticker"], "Direction": f["direction"], "Start": sz.ETIQUETTES[f["start_day"]],
                       "End": sz.ETIQUETTES[f["end_day"]], "Average return": f["avg"], "Hit rate": f["hit"],
                       "Annualized return": f["ann"], "Years": f["n"],
                       "Status": "Active now" if actif else f"Starts in {(prochain - aujourd).days} d",
                       "Next start": prochain, "Next end": fin})
    df = pd.DataFrame(lignes)
    ev = st.dataframe(df, hide_index=True, width="stretch", on_select="rerun", selection_mode="multi-row", key="seas_suivi_table",
                      column_config={"Average return": st.column_config.NumberColumn(format="percent"),
                                     "Hit rate": st.column_config.NumberColumn(format="percent"),
                                     "Annualized return": st.column_config.NumberColumn(format="percent")})
    choisies = ev.selection.rows if ev and ev.selection else []
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("Open selected in the chart", disabled=len(choisies) != 1, width="stretch"):
        f = suivi[choisies[0]]
        st.session_state["seas_charger"] = {"ticker": f["ticker"], "start_day": f["start_day"], "end_day": f["end_day"],
                                            "direction": f["direction"], "years": f["years"]}
        st.rerun()
    if b2.button("Remove selected", disabled=not choisies, width="stretch"):
        st.session_state["seas_suivi"] = [f for i, f in enumerate(suivi) if i not in set(choisies)]
        st.rerun()
    b3.download_button("Reminders (.ics calendar)",
                       sz.calendrier_ics([{**f, "end_day": f["end_day"], "years": f["n"]} for f in suivi], aujourd),
                       file_name="seasonal_patterns.ics", mime="text/calendar", icon=":material/event:", width="stretch",
                       help="Import into Google Calendar, Outlook or Apple Calendar: one reminder at the start and one at the end of each window.")
    b4.download_button("Export (Excel)", exporter_excel({"Watchlist": df.set_index("Asset")}, {"Patterns": len(df)}),
                       file_name="seasonal_watchlist.xlsx", icon=":material/download:", width="stretch", key="seas_suivi_export")
    st.caption("The watchlist lasts for your session (it is not stored on a server). Export it to keep it.")


def _note_methode() -> None:
    note_methodo(
        "- **Data**: Yahoo Finance adjusted closes, full history (independent of the global period), in the asset's "
        "own currency.\n"
        "- **Calendar**: 365-day reference year (Feb 29 merged into Feb 28); days without trading keep the last close.\n"
        "- **Seasonal curve**: for each year, cumulative change since the previous Dec 31 close; the curve is the average "
        "(or median) of those yearly paths over complete years. **Detrended**: a straight line from 0 to the final level is "
        "subtracted, so only the seasonal shape remains.\n"
        "- **Window A → B**: bought at the close of the day before A, sold at the close of B (A's move included). If B is "
        "before A, the window ends the following year. Short = −(long return), no borrowing or trading costs.\n"
        "- **Annualized return** = (1 + average return)^(365 / calendar days) − 1. It magnifies short windows: compare "
        "patterns of similar length.\n"
        "- **Volatility, Sharpe, Sortino**: computed on the daily returns inside the windows, annualized with √252, "
        "risk-free rate 0.\n"
        "- **Significance**: t-test (is the average different from 0?) and binomial test (is the hit rate different from 50%?). "
        "**Rank vs all windows**: the same length started on each of the 365 days; a window found by searching is "
        "always among the best by construction — the tests guard against that.\n"
        "- **Limits**: futures (=F) are continuous contracts with roll jumps; 10–15 years is a small sample; past "
        "seasonality is a statistic, not a forecast. Not financial advice."
    )
