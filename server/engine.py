"""Boucle d'arrière-plan : rafraîchit les données, envoie rappels + chiffres réels, et l'analyse du dimanche."""
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import calendar_data as cal, central_banks, push, storage, weekly, sources, sentiment, cot, rates, macro, flows, capflows
from .config import (TIMEZONE, REMINDER_MINUTES, FAST_POLL_SECONDS, RELEASE_TIMEOUT_MINUTES,
                     WEEK_REFRESH_MINUTES, NEWS_REFRESH_MINUTES, WEEKLY_DAY, WEEKLY_HOUR, FJ_REFRESH_SECONDS)
from .countries import CURRENCIES

log = logging.getLogger("engine")
TZ = ZoneInfo(TIMEZONE)

STATE = {"last_week": 0.0, "last_history": 0.0, "last_news": 0.0, "last_fj": 0.0, "last_sent": 0.0, "last_cot": 0.0, "last_rates": 0.0, "last_flows": 0.0, "last_capflows": 0.0, "last_poll": {}, "running": False,
         "last_error": None}


def news_items():
    """FinancialJuice + InvestingLive + Investing.com, du plus récent au plus ancien, sans doublons."""
    items = storage.load("fj.json", {"items": []})["items"] + storage.load("news.json", {"items": []})["items"]
    seen, out = set(), []
    for n in sorted(items, key=lambda n: n.get("time") or "", reverse=True):
        k = n.get("title", "").lower()[:90]
        if k and k not in seen:
            seen.add(k)
            out.append(n)
    return out


def overviews():
    hist = cal.load_history()
    week = cal.load_week()["events"]
    news = news_items()
    return {c: central_banks.currency_overview(c, hist, week, news) for c in CURRENCIES}


def _sent():
    return storage.load("sent.json", {})


def _mark(key):
    s = _sent()
    s[key] = time.time()
    # ménage : on garde 14 jours
    cutoff = time.time() - 14 * 86400
    s = {k: v for k, v in s.items() if v > cutoff}
    storage.save("sent.json", s)


def _flag(ccy):
    return CURRENCIES.get(ccy, {}).get("flag", "")


def _dot(impact):
    return "🔴" if impact == "high" else "🟠"


def reminder_text(e):
    t = cal.parse_time(e["time"]).astimezone(TZ)
    title = f"⏰ {t:%H:%M} {_flag(e['currency'])} {e['currency']} — {e['title']}"
    body = f"{_dot(e['impact'])} Dans {REMINDER_MINUTES} min · Consensus {e['forecast_str']} · Préc. {e['previous_str']}"
    if e.get("te_forecast_str"):
        body += f" · TE {e['te_forecast_str']}"
    return title, body


SPEECH_RE = re.compile(r"\b(speaks?|speech|testif(y|ies)|testimony|press conference|hearing|remarks|"
                       r"parliament|senate|congress|semi-annual|monetary policy report|statement)\b", re.I)


def is_speech(e):
    return bool(SPEECH_RE.search(e.get("title", "")))


def release_text(e):
    """Couleur façon Forex Factory : 🟢 bon pour la devise, 🔴 mauvais, ⚪ en ligne."""
    s = e.get("surprise")
    ccy = e["currency"]
    if s:
        color = {"positif": "🟢", "négatif": "🔴"}.get(s["ccy_bias"], "⚪")
        verdict = {"positif": f"BON pour le {ccy}", "négatif": f"MAUVAIS pour le {ccy}"}.get(s["ccy_bias"], f"neutre pour le {ccy}")
    else:
        color, verdict = "⚪", "pas de consensus"
    title = f"{color} {_flag(ccy)} {ccy} {e['title']} : {e['actual_str']}"
    body = f"{verdict.upper()} · Réel {e['actual_str']} vs consensus {e['forecast_str']} (préc. {e['previous_str']})"
    if s:
        body += f" · écart {s['diff_str']}"
    return title, body


def live_text(e):
    """Notification « en direct » pour les discours de banquiers centraux."""
    ccy = e["currency"]
    who = re.sub(r"\s*(speaks?|speech|testifies)\s*$", "", e["title"], flags=re.I).strip()
    bank = CURRENCIES.get(ccy, {}).get("bank", "")
    title = f"🎙️ EN DIRECT · {_flag(ccy)} {who}"
    body = f"{bank} ({ccy}) parle maintenant. Surveille la volatilité sur le {ccy}."
    return title, body


def live_url(e):
    from urllib.parse import quote
    return "https://www.youtube.com/results?search_query=" + quote(e["title"] + " live") + "&sp=EgJAAQ%253D%253D"


def refresh_week():
    evs = cal.refresh_week()
    STATE["last_week"] = time.time()
    return evs


NEWS_KIND = {"InvestingLive": "news_il", "FinancialJuice": "news_fj", "Investing.com": "news_inv"}
NEWS_ICON = {"InvestingLive": "📰", "FinancialJuice": "⚡", "Investing.com": "🗞️"}


def _news_key(n):
    return (n.get("link") or n.get("title", "")).strip().lower()[:200]


def _merge_news(fname, new, keep_hours=72, cap=600):
    """Ajoute les nouvelles au fichier sans effacer les anciennes (le flux RSS ne garde que ~25 articles)."""
    old = storage.load(fname, {"items": []})["items"]
    by = {_news_key(n): n for n in old}
    for n in new:
        by[_news_key(n)] = {**by.get(_news_key(n), {}), **n}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=keep_hours)).isoformat()
    items = [n for n in by.values() if (n.get("time") or "9") >= cutoff]
    items = sorted(items, key=lambda n: n.get("time") or "", reverse=True)[:cap]
    storage.save(fname, {"updated": datetime.now(timezone.utc).isoformat(), "items": items})
    return items


def notify_news(items):
    """Une notification par nouvelle jamais vue (les plus anciennes d'abord)."""
    sent = storage.load("news_sent.json", {"keys": [], "seeded": False})
    known = set(sent["keys"])
    fresh_cut = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
    todo = [n for n in items if _news_key(n) not in known]
    if not sent.get("seeded"):  # premier passage : on ne bombarde pas avec l'historique
        todo = []
        sent["seeded"] = True
    todo = [n for n in todo if (n.get("time") or "") >= fresh_cut]
    for n in sorted(todo, key=lambda n: n.get("time") or "")[-12:]:
        src = n.get("source", "")
        title = f"{NEWS_ICON.get(src, '📰')} {src}"
        body = n.get("title", "")
        if n.get("summary") and src != "FinancialJuice":
            body += "\n" + re.sub(r"\s+", " ", n["summary"])[:140]
        try:
            push.send(title, body, tag="news-" + str(abs(hash(_news_key(n))))[:10], url=("/#nouvelles" if src == "FinancialJuice" else n.get("link")) or "/#nouvelles",
                      kind=NEWS_KIND.get(src, "news_inv"))
        except Exception as e:
            log.info("Push nouvelle: %s", e)
    sent["keys"] = (sent["keys"] + [_news_key(n) for n in items if _news_key(n) not in known])[-3000:]
    storage.save("news_sent.json", sent)


def refresh_news():
    try:
        items = sources.fetch_news()
        if items:
            notify_news(items)
            _merge_news("news.json", items)
    except Exception as e:
        log.warning("Nouvelles: %s", e)
    STATE["last_news"] = time.time()


def refresh_fj():
    STATE["last_fj"] = time.time()
    try:
        new = sources.fetch_financialjuice()
    except Exception as e:
        log.info("FinancialJuice: %s", e)
        if "429" in str(e):  # limite Cloudflare (erreur 1015) : pause de 15 min
            STATE["last_fj"] = time.time() + 900
        return
    notify_news(new)
    _merge_news("fj.json", new, keep_hours=72, cap=800)


def generate_weekly(notify=True):
    week = cal.load_week()["events"] or refresh_week()
    rep = weekly.build(week, overviews())
    weekly.save(rep)
    if notify:
        c = rep["counts"]
        push.send("📊 Analyse de la semaine prête",
                  f"{c['red']} 🔴 et {c['orange']} 🟠 cette semaine. {rep['headline'][:150]}",
                  tag="weekly", url="/#semaine", kind="weekly")
    return rep


def _weekly_due():
    now = datetime.now(TZ)
    start, _ = cal.week_bounds()
    key = start.astimezone(TZ).strftime("%Y-%m-%d")
    have = storage.load(f"weekly/{key}.json")
    if have:
        return False
    # Dimanche à partir de WEEKLY_HOUR, ou n'importe quand si la semaine en cours n'a pas d'analyse
    if now.weekday() == WEEKLY_DAY:
        return now.hour >= WEEKLY_HOUR
    return True


def check_alerts():
    week = cal.load_week()
    events = week["events"]
    now = datetime.now(timezone.utc)
    sent = _sent()
    changed = False
    slots = {}
    for e in events:
        if e["impact"] not in ("high", "medium"):
            continue
        t = cal.parse_time(e["time"])
        dt = (t - now).total_seconds()
        rk, ak = f"rem:{e['id']}", f"rel:{e['id']}"
        if 0 < dt <= REMINDER_MINUTES * 60 and rk not in sent:
            title, body = reminder_text(e)
            push.send(title, body, tag=rk, url="/#calendrier", kind="reminder", currency=e["currency"], impact=e["impact"])
            _mark(rk)
        if is_speech(e):
            lk = f"live:{e['id']}"
            if -RELEASE_TIMEOUT_MINUTES * 60 < dt <= 30 and lk not in sent:
                title, body = live_text(e)
                push.send(title, body, tag=lk, url=live_url(e), kind="live", currency=e["currency"], impact=e["impact"])
                _mark(lk)
            continue
        if dt <= 0 and ak not in sent:
            if -dt > RELEASE_TIMEOUT_MINUTES * 60:
                _mark(ak)  # trop vieux / jamais publié : on abandonne sans notifier
                continue
            if e.get("actual") is not None:
                title, body = release_text(e)
                push.send(title, body, tag=ak, url="/#calendrier", kind="release", currency=e["currency"], impact=e["impact"])
                _mark(ak)
            else:
                slots.setdefault(e["time"], []).append(e)

    for slot, evs in slots.items():
        last = STATE["last_poll"].get(slot, 0)
        if time.time() - last < FAST_POLL_SECONDS:
            continue
        STATE["last_poll"][slot] = time.time()
        try:
            updated = cal.fast_actual(evs)
        except Exception as ex:
            log.info("Fast poll %s: %s", slot, ex)
            continue
        for e in updated:
            title, body = release_text(e)
            push.send(title, body, tag=f"rel:{e['id']}", url="/#calendrier", kind="release",
                      currency=e["currency"], impact=e["impact"])
            _mark(f"rel:{e['id']}")
            changed = True
    if changed:
        storage.save("week.json", week)  # les objets ont été mis à jour en place


def _fx_closed(now=None) -> bool:
    """Marché des changes fermé : du vendredi 17 h au dimanche 17 h (heure de l'Est)."""
    now = now or datetime.now(ZoneInfo("America/Toronto"))
    wd, h = now.weekday(), now.hour
    return (wd == 4 and h >= 17) or wd == 5 or (wd == 6 and h < 17)


def _sent_interval() -> int:
    """Myfxbook : 100 requêtes par jour au maximum. 20 min = 72 par jour ; marché fermé = 1 par heure."""
    return 3600 if _fx_closed() else 1200


def _cot_interval() -> int:
    """Le COT sort le vendredi vers 15 h 30 (heure de l'Est) : on vérifie toutes les 30 min jusqu'à l'avoir."""
    now = datetime.now(ZoneInfo("America/Toronto"))
    last = (cot.latest() or {}).get("rows") or []
    newest = max((r.get("date", "") for r in last), default="")
    tuesday = (now - timedelta(days=(now.weekday() - 1) % 7)).date().isoformat()
    friday_release = now.weekday() == 4 and (now.hour, now.minute) >= (15, 35)
    after_release = friday_release or now.weekday() in (5, 6)
    if after_release and newest < tuesday:
        return 1800
    return 6 * 3600


async def loop():
    STATE["running"] = True
    log.info("Moteur démarré")
    while True:
        try:
            if time.time() - STATE["last_week"] > WEEK_REFRESH_MINUTES * 60:
                await asyncio.to_thread(refresh_week)
            if time.time() - STATE["last_fj"] > FJ_REFRESH_SECONDS:
                await asyncio.to_thread(refresh_fj)
            if time.time() - STATE["last_sent"] > _sent_interval():
                STATE["last_sent"] = time.time()
                try:
                    await asyncio.to_thread(sentiment.refresh)
                except Exception as ex:
                    log.info("Sentiment: %s", ex)
            if time.time() - STATE["last_rates"] > 1800:
                STATE["last_rates"] = time.time()
                try:
                    await asyncio.to_thread(rates.refresh, current_rates())
                except Exception as ex:
                    log.info("Taux: %s", ex)
            if time.time() - STATE["last_flows"] > 1800:
                STATE["last_flows"] = time.time()
                try:
                    await asyncio.to_thread(flows.refresh)
                except Exception as ex:
                    log.info("Flux OI: %s", ex)
            if time.time() - STATE["last_capflows"] > 6 * 3600:
                STATE["last_capflows"] = time.time()
                try:
                    await asyncio.to_thread(capflows.refresh)
                except Exception as ex:
                    log.info("Flux de capitaux: %s", ex)
            if time.time() - STATE["last_cot"] > _cot_interval():
                STATE["last_cot"] = time.time()
                try:
                    await asyncio.to_thread(cot.refresh)
                except Exception as ex:
                    log.info("COT: %s", ex)
            if time.time() - STATE["last_news"] > 60:
                await asyncio.to_thread(refresh_news)
            if time.time() - STATE["last_history"] > 12 * 3600:
                STATE["last_history"] = time.time()
                await asyncio.to_thread(cal.refresh_history)
            if _weekly_due():
                await asyncio.to_thread(generate_weekly, True)
            await asyncio.to_thread(check_alerts)
            STATE["last_error"] = None
        except Exception as e:
            STATE["last_error"] = str(e)
            log.exception("Erreur moteur: %s", e)
        await asyncio.sleep(2)


def current_rates() -> dict:
    """Taux directeur actuel de chaque devise (même source que l'onglet MACRO)."""
    hist = cal.load_history()
    by_id = {e["id"]: e for e in hist}
    by_id.update({e["id"]: e for e in cal.load_week()["events"]})
    evs = sorted(by_id.values(), key=lambda e: e["time"])
    return {r["code"]: (r.get("rate") or {}).get("value") for r in macro.table(evs, overviews())["rows"]}
