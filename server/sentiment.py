"""Sentiment des traders retail (% long / % short) via l'API officielle Myfxbook « Community Outlook ».

Nécessite un compte Myfxbook gratuit : l'utilisateur entre son courriel et son mot de passe
dans l'onglet Alertes du terminal (stockés seulement sur le serveur, dans data/settings.json).
"""
import logging
import time
from urllib.parse import quote

import httpx

from . import storage

log = logging.getLogger("sentiment")
API = "https://www.myfxbook.com/api"
_state = {"session": None, "ts": 0}


def _settings():
    return storage.load("settings.json", {})


def configured() -> bool:
    s = _settings()
    return bool(s.get("myfxbook_email") and s.get("myfxbook_password"))


def _login(client):
    s = _settings()
    r = client.get(f"{API}/login.json?email={quote(s['myfxbook_email'])}&password={quote(s['myfxbook_password'])}")
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data.get("message", "Connexion Myfxbook refusée"))
    _state["session"] = data["session"]


def refresh():
    if not configured():
        return None
    with httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as c:
        if not _state["session"]:
            _login(c)
        r = c.get(f"{API}/get-community-outlook.json?session={_state['session']}")
        data = r.json()
        if data.get("error"):  # session expirée : on se reconnecte une fois
            _login(c)
            data = c.get(f"{API}/get-community-outlook.json?session={_state['session']}").json()
        if data.get("error"):
            raise RuntimeError(data.get("message", "Erreur Myfxbook"))
    rows = []
    for s in data.get("symbols", []):
        long_p = float(s.get("longPercentage", 0))
        short_p = float(s.get("shortPercentage", 0))
        rows.append({
            "symbol": s.get("name"), "long": round(long_p, 1), "short": round(short_p, 1),
            "long_lots": s.get("longVolume"), "short_lots": s.get("shortVolume"),
            "positions": s.get("totalPositions"),
            "avg_long": s.get("avgLongPrice"), "avg_short": s.get("avgShortPrice"),
            # Lecture contrarienne classique : la foule retail se trompe souvent aux extrêmes
            "signal": "Contrarien HAUSSIER" if short_p >= 65 else ("Contrarien BAISSIER" if long_p >= 65 else "Neutre"),
        })
    rows.sort(key=lambda r: -(r["positions"] or 0))
    out = {"updated": time.time(), "source": "Myfxbook Community Outlook", "rows": rows}
    storage.save("sentiment.json", out)
    return out


def latest():
    return storage.load("sentiment.json")
