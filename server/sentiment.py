"""Sentiment des traders retail (% long / % short) via l'API officielle Myfxbook « Community Outlook ».

Nécessite un compte Myfxbook gratuit : l'utilisateur entre son courriel et son mot de passe
dans l'onglet Alertes du terminal (stockés seulement sur le serveur, dans data/settings.json).
"""
import logging
import re
import time
from urllib.parse import quote

import httpx

from . import storage

log = logging.getLogger("sentiment")
API = "https://www.myfxbook.com/api"
_state = {"session": None, "ts": 0, "blocked_until": 0}
DAILY_LIMIT_MSG = "API limit"


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
        msg = data.get("message", "Connexion Myfxbook refusée")
        if DAILY_LIMIT_MSG.lower() in msg.lower():
            _state["blocked_until"] = _next_utc_midnight()
        raise RuntimeError(msg)
    _state["session"] = data["session"]


OUTLOOK_URL = "https://www.myfxbook.com/community/outlook"
_ROW = re.compile(
    r"([A-Z]{6}|XAUUSD|XAGUSD)\s+([\d.]+)\s+[+-]?\d+\s*pips\s+([\d.]+)\s+[+-]?\d+\s*pips\s+([\d.]+)\s+"
    r"Symbol\s+Action\s+Percentage\s+Volume\s+Positions\s+\1\s+Short\s+(\d+)%\s+([\d.]+)\s*lots\s+(\d+)\s+"
    r"Long\s+(\d+)%\s+([\d.]+)\s*lots\s+(\d+)", re.I)


def parse_outlook(html: str) -> list[dict]:
    """Lit la page publique Community Outlook (aucun compte requis)."""
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"&nbsp;|&#160;", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    rows = []
    for m in _ROW.finditer(txt):
        sym, avg_s, avg_l, price, sp, sv, spos, lp, lv, lpos = m.groups()
        rows.append({"name": sym.upper(), "avgShortPrice": float(avg_s), "avgLongPrice": float(avg_l),
                     "shortPercentage": int(sp), "longPercentage": int(lp),
                     "shortVolume": float(sv), "longVolume": float(lv),
                     "totalPositions": int(spos) + int(lpos), "price": float(price)})
    return rows


def _scrape():
    with httpx.Client(timeout=20, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"}) as c:
        r = c.get(OUTLOOK_URL)
        r.raise_for_status()
    return parse_outlook(r.text)


def _next_utc_midnight():
    t = time.gmtime()
    return time.time() - (t.tm_hour * 3600 + t.tm_min * 60 + t.tm_sec) + 86400 + 60


def _api():
    """Myfxbook limite l'API à 100 requêtes par jour : si la limite est atteinte, on attend minuit UTC."""
    if time.time() < _state["blocked_until"]:
        raise RuntimeError("Limite quotidienne Myfxbook atteinte, nouvel essai après minuit UTC")
    with httpx.Client(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as c:
        if not _state["session"]:
            _login(c)
        r = c.get(f"{API}/get-community-outlook.json?session={_state['session']}")
        data = r.json()
        if data.get("error"):  # session expirée : on se reconnecte une fois
            _login(c)
            data = c.get(f"{API}/get-community-outlook.json?session={_state['session']}").json()
        if data.get("error"):
            msg = data.get("message", "Erreur Myfxbook")
            if DAILY_LIMIT_MSG.lower() in msg.lower():
                _state["blocked_until"] = _next_utc_midnight()
            raise RuntimeError(msg)
    return data.get("symbols", [])


def refresh():
    symbols, source, err = [], "", None
    try:
        symbols, source = _scrape(), "Myfxbook Community Outlook (page publique)"
    except Exception as e:
        err = e
    if not symbols and configured():
        symbols, source = _api(), "Myfxbook Community Outlook (API)"
    if not symbols:
        raise RuntimeError(f"Sentiment indisponible: {err}")
    rows = []
    for s in symbols:
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
    rows = [r for r in rows if (r["positions"] or 0) >= 200] or rows  # retire les cryptos quasi vides
    out = {"updated": time.time(), "source": source, "rows": rows, "threshold": 65}
    storage.save("sentiment.json", out)
    return out


def latest():
    return storage.load("sentiment.json")
