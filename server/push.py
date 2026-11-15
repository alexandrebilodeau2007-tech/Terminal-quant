"""Web Push (VAPID) — fonctionne sur iPhone (iOS 16.4+, site ajouté à l'écran d'accueil),
Android, Chrome, Edge, Firefox et Safari macOS."""
import base64
import hashlib
import json
import logging
import threading

from . import storage
from .config import VAPID_SUB

log = logging.getLogger("push")
_lock = threading.RLock()
KEY_FILE = "vapid_private.pem"

DEFAULT_PREFS = {"currencies": ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF", "CNY"],
                 "impacts": ["high", "medium"], "reminder": True, "release": True, "weekly": True}


def _ensure_keys():
    from py_vapid import Vapid
    p = storage.path(KEY_FILE)
    if not p.exists():
        v = Vapid()
        v.generate_keys()
        v.save_key(str(p))
        log.info("Clés VAPID générées")
    return Vapid.from_file(str(p))


def public_key() -> str:
    from cryptography.hazmat.primitives import serialization
    v = _ensure_keys()
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _sub_id(sub: dict) -> str:
    return hashlib.sha1(sub["endpoint"].encode()).hexdigest()[:16]


def subscriptions() -> dict:
    return storage.load("subscriptions.json", {})


def add_subscription(sub: dict, prefs: dict | None = None) -> str:
    with _lock:
        subs = subscriptions()
        sid = _sub_id(sub)
        old = subs.get(sid, {})
        subs[sid] = {"sub": sub, "prefs": {**DEFAULT_PREFS, **old.get("prefs", {}), **(prefs or {})}}
        storage.save("subscriptions.json", subs)
        return sid


def update_prefs(endpoint: str, prefs: dict) -> bool:
    with _lock:
        subs = subscriptions()
        sid = hashlib.sha1(endpoint.encode()).hexdigest()[:16]
        if sid not in subs:
            return False
        subs[sid]["prefs"] = {**subs[sid]["prefs"], **prefs}
        storage.save("subscriptions.json", subs)
        return True


def get_prefs(endpoint: str) -> dict | None:
    sid = hashlib.sha1(endpoint.encode()).hexdigest()[:16]
    s = subscriptions().get(sid)
    return s["prefs"] if s else None


def send(title: str, body: str, *, tag: str | None = None, url: str = "/", kind: str = "release",
         currency: str | None = None, impact: str | None = None) -> int:
    """Envoie à tous les abonnés dont les préférences correspondent. Retourne le nb envoyé."""
    from pywebpush import webpush, WebPushException
    key_path = str(storage.path(KEY_FILE))
    _ensure_keys()
    payload = json.dumps({"title": title, "body": body, "tag": tag, "url": url})
    sent, dead = 0, []
    for sid, s in subscriptions().items():
        p = s["prefs"]
        if kind in ("reminder", "release", "weekly") and not p.get(kind, True):
            continue
        if currency and currency not in p.get("currencies", []):
            continue
        if impact and impact not in p.get("impacts", []):
            continue
        try:
            webpush(s["sub"], data=payload, vapid_private_key=key_path,
                    vapid_claims={"sub": VAPID_SUB}, ttl=3600,
                    headers={"Urgency": "high"})
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", None)
            log.warning("Push échoué (%s): %s", code, e)
            if code in (404, 410):
                dead.append(sid)
        except Exception as e:
            log.warning("Push erreur: %s", e)
    if dead:
        with _lock:
            subs = subscriptions()
            for sid in dead:
                subs.pop(sid, None)
            storage.save("subscriptions.json", subs)
    return sent
