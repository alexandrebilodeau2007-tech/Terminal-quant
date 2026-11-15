"""Petites fonctions de stockage JSON sur disque (thread-safe)."""
import json
import threading
from pathlib import Path

from .config import DATA_DIR

_lock = threading.RLock()


def path(name: str) -> Path:
    p = DATA_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load(name: str, default=None):
    p = path(name)
    with _lock:
        if not p.exists():
            return default
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default


def save(name: str, obj) -> None:
    p = path(name)
    with _lock:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        tmp.replace(p)
