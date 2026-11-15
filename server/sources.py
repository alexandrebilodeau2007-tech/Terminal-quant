"""Récupération des données brutes : TradingView (calendrier), Forex Factory,
Trading Economics (optionnel), InvestingLive + Investing.com (nouvelles)."""
import logging
import re
from datetime import datetime, timezone

import httpx

from .config import (USER_AGENT, TE_API_KEY, INVESTINGLIVE_FEEDS, INVESTINGLIVE_HOME, EXTRA_NEWS_FEEDS,
                     FINANCIALJUICE_FEED)

log = logging.getLogger("sources")

TV_URL = "https://economic-calendar.tradingview.com/events"
FF_URLS = {
    "thisweek": "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "nextweek": "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
}
TE_URL = "https://api.tradingeconomics.com/calendar/country/All/{d1}/{d2}"

TE_COUNTRY = {"United States": "US", "Euro Area": "EU", "Germany": "DE", "France": "FR", "Italy": "IT",
              "Spain": "ES", "United Kingdom": "GB", "Japan": "JP", "Canada": "CA", "Australia": "AU",
              "New Zealand": "NZ", "Switzerland": "CH", "China": "CN"}


def _client(timeout=15):
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------------------------------------------------------------- TradingView
def fetch_tradingview(start: datetime, end: datetime, countries: list[str]) -> list[dict]:
    """Calendrier économique TradingView (actual / forecast / previous, sans clé API)."""
    params = {"from": iso(start), "to": iso(end), "countries": ",".join(countries)}
    headers = {"Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}
    with _client() as c:
        r = c.get(TV_URL, params=params, headers=headers)
        r.raise_for_status()
        data = r.json()
    return data.get("result", []) if isinstance(data, dict) else []


# --------------------------------------------------------------- Forex Factory
def fetch_forexfactory(which: str = "thisweek") -> list[dict]:
    """Flux JSON public de Forex Factory (impact rouge/orange, forecast, previous)."""
    with _client() as c:
        r = c.get(FF_URLS[which])
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------- Trading Economics
def fetch_tradingeconomics(start: datetime, end: datetime) -> list[dict]:
    """Calendrier Trading Economics (nécessite TE_API_KEY). Retourne [] si pas de clé."""
    if not TE_API_KEY:
        return []
    url = TE_URL.format(d1=start.strftime("%Y-%m-%d"), d2=end.strftime("%Y-%m-%d"))
    with _client(20) as c:
        r = c.get(url, params={"c": TE_API_KEY, "f": "json"})
        r.raise_for_status()
        rows = r.json()
    out = []
    for row in rows if isinstance(rows, list) else []:
        code = TE_COUNTRY.get(row.get("Country", ""))
        if code:
            row["_code"] = code
            out.append(row)
    return out


# ------------------------------------------------------------------- Nouvelles
def _discover_feed(home: str) -> str | None:
    try:
        with _client(10) as c:
            html = c.get(home).text
        m = re.search(r'<link[^>]+type="application/(?:rss|atom)\+xml"[^>]+href="([^"]+)"', html, re.I)
        if m:
            href = m.group(1)
            return href if href.startswith("http") else home.rstrip("/") + "/" + href.lstrip("/")
    except Exception as e:
        log.info("Découverte flux InvestingLive impossible: %s", e)
    return None


def _parse_feed(url: str, source: str) -> list[dict]:
    import feedparser
    with _client(12) as c:
        r = c.get(url)
        r.raise_for_status()
    feed = feedparser.parse(r.content)
    items = []
    for e in feed.entries[:80]:
        ts = None
        for k in ("published_parsed", "updated_parsed"):
            if getattr(e, k, None):
                ts = datetime(*getattr(e, k)[:6], tzinfo=timezone.utc).isoformat()
                break
        summary = re.sub(r"<[^>]+>", " ", getattr(e, "summary", "") or "")
        items.append({"title": getattr(e, "title", "").strip(), "link": getattr(e, "link", ""),
                      "time": ts, "summary": re.sub(r"\s+", " ", summary).strip()[:400], "source": source})
    return items


_il_feed_cache: dict = {"url": None}


def fetch_news() -> list[dict]:
    """InvestingLive en priorité, Investing.com en complément."""
    items: list[dict] = []
    urls = ([_il_feed_cache["url"]] if _il_feed_cache["url"] else []) + INVESTINGLIVE_FEEDS
    got_il = False
    for u in urls:
        try:
            res = _parse_feed(u, "InvestingLive")
            if res:
                items += res
                _il_feed_cache["url"] = u
                got_il = True
                break
        except Exception:
            continue
    if not got_il:
        found = _discover_feed(INVESTINGLIVE_HOME)
        if found:
            try:
                items += _parse_feed(found, "InvestingLive")
                _il_feed_cache["url"] = found
            except Exception as e:
                log.warning("Flux InvestingLive illisible: %s", e)
    for u in EXTRA_NEWS_FEEDS:
        try:
            items += _parse_feed(u, "Investing.com")
        except Exception as e:
            log.info("Flux %s indisponible: %s", u, e)
    return items


def fetch_financialjuice() -> list[dict]:
    """Fil de manchettes FinancialJuice (flux RSS public, non officiel)."""
    items = _parse_feed(FINANCIALJUICE_FEED, "FinancialJuice")
    for it in items:
        it["title"] = re.sub(r"^FinancialJuice:\s*", "", it["title"]).strip()
    return items
