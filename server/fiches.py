"""Fiches de triche macro d'Alex (C:\\MTA), stockées chiffrées dans le dépôt public.

Le paquet est déchiffré au démarrage avec APP_TOKEN : sans le mot de passe, personne
ne peut lire les fiches sur GitHub.
"""
import base64
import io
import json
import logging
import re
import zipfile
from pathlib import Path

from .config import APP_TOKEN

log = logging.getLogger("fiches")
_PATH = Path(__file__).with_name("fiches.enc")
_SALT = b"atlas-macro-fiches-v1"
_cache: dict = {}
EXTRA = {"jobless-claims": r"|unemployment claims", "industrial-production": r"|manufacturing production"}


def _load():
    if "items" in _cache:
        return _cache
    _cache.update(items=[], files={})
    if not APP_TOKEN or not _PATH.exists():
        return _cache
    try:
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        key = base64.urlsafe_b64encode(PBKDF2HMAC(hashes.SHA256(), 32, _SALT, 300000).derive(APP_TOKEN.encode()))
        z = zipfile.ZipFile(io.BytesIO(Fernet(key).decrypt(_PATH.read_bytes())))
        _cache["items"] = json.loads(z.read("fiches.json"))
        _cache["files"] = {n: z.read(n) for n in z.namelist() if n.endswith(".png")}
        for f in _cache["items"]:
            f["_re"] = re.compile(f["match"] + EXTRA.get(f["id"], ""), re.I)
    except Exception as e:  # mauvais mot de passe ou fichier corrompu
        log.warning("Fiches illisibles: %s", e)
    return _cache


def set_items(items, files=None):
    """Utilisé par les tests."""
    _cache.clear()
    _cache.update(items=items, files=files or {})
    for f in items:
        f["_re"] = re.compile(f["match"], re.I)


def all_items():
    return [{k: v for k, v in f.items() if not k.startswith("_")} for f in _load()["items"]]


def image(name):
    return _load()["files"].get(name)


def match(title: str):
    """Fiche correspondant à un titre d'événement (Core CPI avant CPI)."""
    items = sorted(_load()["items"], key=lambda f: f["id"] != "core-cpi")
    for f in items:
        if f["_re"].search(title or ""):
            return f["id"]
    return None
