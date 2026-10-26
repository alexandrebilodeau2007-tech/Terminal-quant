"""
export/excel.py — Export de n'importe quelle analyse vers un fichier Excel.

Règle de rigueur : chaque export contient un onglet "Métadonnées" (date,
sources, paramètres). Un chiffre sans sa provenance n'est pas vérifiable.
"""

from __future__ import annotations

import io
import re
from datetime import datetime

import pandas as pd

from config import AVERTISSEMENT


def _nom_onglet(nom: str, existants: list[str]) -> str:
    """Nom d'onglet valide pour Excel : 31 caractères au plus, sans [ ] : * ? / \\,
    et unique dans le classeur (sinon un numéro est ajouté)."""
    propre = re.sub(r"[\[\]:*?/\\]", "-", nom).strip() or "Sheet"
    propre = propre[:31]
    candidat, i = propre, 2
    while candidat in existants:
        suffixe = f" ({i})"
        candidat, i = propre[: 31 - len(suffixe)] + suffixe, i + 1
    return candidat


def exporter_excel(onglets: dict[str, pd.DataFrame], metadonnees: dict[str, object]) -> bytes:
    """Crée un classeur Excel en mémoire et renvoie ses octets
    (directement utilisables par st.download_button).

    onglets     : {"Nom de l'onglet": DataFrame}
    metadonnees : {"Paramètre": valeur} -> premier onglet
    """
    tampon = io.BytesIO()  # fichier "virtuel" en mémoire : rien n'est écrit sur le disque
    meta = {"Export date": datetime.now().strftime("%Y-%m-%d %H:%M"), **metadonnees,
            "Disclaimer": AVERTISSEMENT}
    with pd.ExcelWriter(tampon, engine="openpyxl") as classeur:
        pd.DataFrame(list(meta.items()), columns=["Item", "Value"]).to_excel(
            classeur, sheet_name="Metadata", index=False)
        for nom, df in onglets.items():
            if df is None or df.empty:
                continue
            copie = df.copy()
            # Excel n'accepte pas les dates avec fuseau horaire ; on les retire.
            if isinstance(copie.index, pd.DatetimeIndex):
                copie.index = copie.index.tz_localize(None).date
            copie.to_excel(classeur, sheet_name=_nom_onglet(nom, classeur.book.sheetnames))

        # Mise en forme minimale : largeur de colonne adaptée au contenu.
        for feuille in classeur.book.worksheets:
            for colonne in feuille.columns:
                largeur = max((len(str(c.value)) for c in colonne if c.value is not None), default=8)
                feuille.column_dimensions[colonne[0].column_letter].width = min(largeur + 2, 60)
    return tampon.getvalue()
