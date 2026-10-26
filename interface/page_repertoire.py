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
        {"Famille": famille, "Nom": nom, "Ticker Yahoo (terminal)": yahoo,
         "Symbole TradingView": tv, "Description": note}
        for famille, entrees in REPERTOIRE.items()
        for nom, yahoo, tv, note in entrees
    ]
    return pd.DataFrame(lignes)


def afficher(params: dict) -> None:
    titre("Répertoire des tickers", "repertoire", "TKR",
          f"{sum(len(v) for v in REPERTOIRE.values())} symboles parmi les plus utilisés, en {len(REPERTOIRE)} familles. "
          "N'importe quel autre ticker Yahoo fonctionne aussi dans le terminal.")

    tout = _tableau()
    valeur_initiale("rep_recherche", "", "cmd_rep_recherche")
    c1, c2 = st.columns([2, 3])
    recherche = c1.text_input("Rechercher (nom, ticker, description)", key="rep_recherche",
                              placeholder="ex. or, banque, semi, BTC")
    familles = ["Toutes"] + list(REPERTOIRE)
    famille = c2.selectbox("Famille", familles)

    vue = tout if famille == "Toutes" else tout[tout["Famille"] == famille]
    if recherche.strip():
        motif = recherche.strip().lower()
        masque = vue.apply(lambda ligne: motif in " ".join(map(str, ligne.values)).lower(), axis=1)
        vue = vue[masque]

    if famille.startswith("Options"):
        st.info(NOTE_OPTIONS)
    st.caption(f"{len(vue)} résultat(s). Clique sur une cellule puis Ctrl+C pour copier un ticker.")
    st.dataframe(vue, hide_index=True, width="stretch", height=min(38 * (len(vue) + 1), 640),
                 column_config={"Ticker Yahoo (terminal)": st.column_config.TextColumn(width="small"),
                                "Symbole TradingView": st.column_config.TextColumn(width="small")})

    with st.expander("Comment écrire un ticker Yahoo", icon=":material/help:"):
        st.markdown(
            "| Marché | Format | Exemples |\n|---|---|---|\n"
            "| Action américaine | Symbole seul | `AAPL`, `MU` |\n"
            "| Action canadienne | Symbole + `.TO` (ou `.V` pour la Bourse de croissance) | `RY.TO`, `SHOP.TO` |\n"
            "| Action européenne | Symbole + suffixe de la bourse | `MC.PA` (Paris), `SAP.DE` (Francfort) |\n"
            "| Indice | `^` devant | `^GSPC`, `^GSPTSE` |\n"
            "| Contrat à terme | `=F` à la fin | `GC=F`, `CL=F` |\n"
            "| Forex | Paire + `=X` | `USDCAD=X` |\n"
            "| Crypto | Symbole-devise | `BTC-USD`, `ETH-CAD` |\n\n"
            "Les symboles **TradingView** suivent le format `BOURSE:SYMBOLE` (ex. `TSX:RY`, `COMEX:GC1!`). "
            "Ils servent seulement au graphique TradingView de la fonction CMP ; ils sont indicatifs."
        )
    st.download_button("Télécharger le répertoire (CSV)", tout.to_csv(index=False).encode("utf-8-sig"),
                       file_name="repertoire_tickers.csv", mime="text/csv", icon=":material/download:")
