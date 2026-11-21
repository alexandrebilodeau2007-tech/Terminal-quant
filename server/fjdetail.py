"""Détail d'une nouvelle FinancialJuice.

La page publique de chaque nouvelle contient déjà tout le contenu (texte dans la balise og:description,
image dans og:image) : une fenêtre d'inscription le cache seulement dans le navigateur. Le serveur lit
donc la page publique, sans compte, garde le résultat en cache et l'affiche dans le terminal.
Les pages ne sont lues qu'à la demande (quand on touche une nouvelle), une seule fois chacune.
"""
import html
import re
import time

import httpx

from . import storage

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
LINK = re.compile(r"^https://(www\.)?financialjuice\.com/News/(\d+)/[^?#]*", re.I)
DEFAULT_IMG = "need-to-know.jpg"
_block = {"until": 0.0}


def news_id(link: str) -> str | None:
    m = LINK.match(link or "")
    return m.group(2) if m else None


def clean_url(link: str) -> str:
    m = LINK.match(link or "")
    return m.group(0) if m else ""


def _meta(page: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)="{re.escape(prop)}"[^>]+content="([^"]*)"', page, re.I)
    if not m:
        m = re.search(rf'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="{re.escape(prop)}"', page, re.I)
    return html.unescape(m.group(1)) if m else ""


def to_lines(desc_html: str) -> list[str]:
    """Convertit le HTML de la description en lignes de texte simples (sans balise)."""
    t = re.sub(r"<\s*(li|p|br|div|tr|h\d)[^>]*>", "\n", desc_html, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    return [re.sub(r"\s+", " ", x).strip() for x in t.split("\n") if x.strip() and x.strip() != "..."]


def parse(page: str) -> dict:
    title = _meta(page, "og:title")
    lines = to_lines(_meta(page, "og:description"))
    img = _meta(page, "og:image")
    if DEFAULT_IMG in img or not img.startswith("https://www.financialjuice.com/"):
        img = ""
    return {"title": title, "lines": lines, "image": img}


def get(link: str) -> dict:
    nid = news_id(link)
    if not nid:
        raise ValueError("Lien FinancialJuice invalide")
    cached = storage.load(f"fj_detail/{nid}.json")
    if cached:
        return cached
    if time.time() < _block["until"]:
        raise RuntimeError("FinancialJuice limite les lectures pour quelques minutes, réessaie bientôt")
    r = httpx.get(clean_url(link), headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
    if r.status_code == 429:
        _block["until"] = time.time() + 300
        raise RuntimeError("FinancialJuice limite les lectures pour quelques minutes, réessaie bientôt")
    r.raise_for_status()
    out = {"id": nid, **parse(r.text), "fetched": time.time()}
    storage.save(f"fj_detail/{nid}.json", out)
    return out


def image(nid: str) -> bytes:
    """Image d'une nouvelle (graphique, tableau), gardée en cache sur le serveur."""
    if not nid.isdigit():
        raise ValueError("id invalide")
    p = storage.path(f"fj_detail/{nid}.png")
    if p.exists():
        return p.read_bytes()
    r = httpx.get(f"https://www.financialjuice.com/images/{nid}.png", headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(r.content)
    return r.content
