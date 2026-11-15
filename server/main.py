"""Serveur web du Macro Terminal (API + site PWA)."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import calendar_data as cal, engine, push, weekly, seasonality, storage, sentiment, macro
from .config import WEB_DIR, APP_TOKEN, PORT, TIMEZONE, ANTHROPIC_API_KEY, TE_API_KEY
from .countries import CURRENCIES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(engine.loop())
    yield
    task.cancel()


app = FastAPI(title="Macro Terminal", lifespan=lifespan)


@app.middleware("http")
async def auth(request: Request, call_next):
    if APP_TOKEN and request.url.path.startswith("/api/") and request.url.path != "/api/health":
        tok = request.headers.get("x-token") or request.query_params.get("token")
        if tok != APP_TOKEN:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-cache"  # toujours la dernière version du site
    return resp


@app.get("/api/health")
def health():
    w = cal.load_week()
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat(), "week_updated": w.get("updated"),
            "errors": w.get("errors"), "engine_error": engine.STATE["last_error"], "timezone": TIMEZONE,
            "auth": bool(APP_TOKEN), "ai": bool(ANTHROPIC_API_KEY), "te": bool(TE_API_KEY)}


@app.get("/api/public-url")
def public_url():
    """Lien https du tunnel Cloudflare (lu dans data/tunnel.log)."""
    import re
    try:
        txt = storage.path("tunnel.log").read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"url": None}
    found = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", txt)
    return {"url": found[-1] if found else None}


@app.get("/api/calendar")
def calendar(impacts: str = "high,medium"):
    w = cal.load_week()
    keep = set(impacts.split(","))
    return {**w, "events": [e for e in w["events"] if e["impact"] in keep]}


@app.post("/api/calendar/refresh")
async def calendar_refresh():
    await asyncio.to_thread(engine.refresh_week)
    return {"ok": True}


@app.get("/api/currencies")
def currencies():
    ovs = engine.overviews()
    light = []
    for c, o in ovs.items():
        nxt = o["upcoming"][0] if o["upcoming"] else None
        light.append({k: o[k] for k in ("code", "name", "flag", "bank", "stance", "policy_rate", "cpi", "core_cpi",
                                         "red_count", "orange_count", "index_symbol")} | {"next": nxt})
    return light


@app.get("/api/currency/{ccy}")
def currency(ccy: str):
    ccy = ccy.upper()
    if ccy not in CURRENCIES:
        raise HTTPException(404)
    return engine.overviews()[ccy]


@app.get("/api/weekly")
def get_weekly():
    return weekly.latest() or {}


@app.post("/api/weekly/generate")
async def gen_weekly(notify: bool = False):
    return await asyncio.to_thread(engine.generate_weekly, notify)


@app.get("/api/news")
def news(ccy: str | None = None, source: str | None = None, limit: int = 120):
    items = engine.news_items()
    if source:
        items = [n for n in items if n.get("source", "").lower() == source.lower()]
    if ccy and ccy.upper() in CURRENCIES:
        kw = CURRENCIES[ccy.upper()]["keywords"]
        items = [n for n in items if any(k in f" {n['title']} ".lower() for k in kw)]
    return items[:limit]


@app.get("/api/macro")
def macro_table():
    hist = cal.load_history()
    week = cal.load_week()["events"]
    by_id = {e["id"]: e for e in hist}
    by_id.update({e["id"]: e for e in week})
    evs = sorted(by_id.values(), key=lambda e: e["time"])
    return macro.table(evs, engine.overviews())


@app.get("/api/sentiment")
def get_sentiment():
    return {"configured": sentiment.configured(), "data": sentiment.latest()}


@app.post("/api/sentiment/refresh")
async def sentiment_refresh():
    try:
        return {"ok": True, "data": await asyncio.to_thread(sentiment.refresh)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/settings")
def get_settings():
    s = storage.load("settings.json", {})
    return {"myfxbook_email": s.get("myfxbook_email", ""), "myfxbook_configured": sentiment.configured()}


@app.post("/api/settings")
async def set_settings(req: Request):
    body = await req.json()
    s = storage.load("settings.json", {})
    for k in ("myfxbook_email", "myfxbook_password"):
        if body.get(k) is not None:
            s[k] = str(body[k]).strip()
    storage.save("settings.json", s)
    sentiment._state["session"] = None
    return {"ok": True, "myfxbook_configured": sentiment.configured()}


@app.get("/api/dashboard")
def dashboard():
    from datetime import timedelta
    w = cal.load_week()
    now = datetime.now(timezone.utc)
    evs = [e for e in w["events"] if e["impact"] in ("high", "medium")]
    upcoming = [e for e in evs if cal.parse_time(e["time"]) >= now - timedelta(minutes=5) and not e.get("released")][:8]
    released = sorted([e for e in evs if e.get("released") and cal.parse_time(e["time"]) >= now - timedelta(hours=36)],
                      key=lambda e: e["time"], reverse=True)[:10]
    ovs = engine.overviews()
    stances = [{"code": c, "flag": o["flag"], "label": o["stance"]["label"], "score": o["stance"]["score"],
                "rate": (o.get("policy_rate") or {}).get("rate"), "red": o["red_count"], "orange": o["orange_count"]}
               for c, o in ovs.items()]
    wk = weekly.latest() or {}
    sent = sentiment.latest() or {}
    majors = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "NZDUSD", "USDCHF", "XAUUSD"]
    srows = [r for r in sent.get("rows", []) if r["symbol"] in majors]
    return {"upcoming": upcoming, "released": released, "stances": stances,
            "news": engine.news_items()[:10], "headline": wk.get("headline"), "counts": wk.get("counts"),
            "sentiment": srows, "sentiment_configured": sentiment.configured()}


@app.get("/api/seasonality/symbols")
def season_symbols():
    return list(seasonality.SYMBOLS.keys())


@app.get("/api/seasonality")
async def season(symbol: str, years: int = 15, start: str | None = None, end: str | None = None):
    try:
        return await asyncio.to_thread(seasonality.run, symbol, max(3, min(years, 40)), start, end)
    except KeyError:
        raise HTTPException(404, "Symbole inconnu")
    except Exception as e:
        raise HTTPException(502, str(e))


# ------------------------------------------------------------------ push
@app.get("/api/push/key")
def push_key():
    return {"key": push.public_key()}


@app.post("/api/push/subscribe")
async def push_subscribe(req: Request):
    body = await req.json()
    sub = body.get("subscription")
    if not sub or "endpoint" not in sub:
        raise HTTPException(400, "subscription manquante")
    sid = push.add_subscription(sub, body.get("prefs"))
    return {"ok": True, "id": sid, "prefs": push.get_prefs(sub["endpoint"])}


@app.post("/api/push/prefs")
async def push_prefs(req: Request):
    body = await req.json()
    ok = push.update_prefs(body.get("endpoint", ""), body.get("prefs", {}))
    return {"ok": ok, "prefs": push.get_prefs(body.get("endpoint", ""))}


@app.post("/api/push/get")
async def push_get(req: Request):
    body = await req.json()
    return {"prefs": push.get_prefs(body.get("endpoint", ""))}


@app.post("/api/push/test")
def push_test():
    n = push.send("✅ Macro Terminal", "Les notifications fonctionnent. Tu recevras les rappels et les chiffres réels.",
                  tag="test", kind="test")
    return {"sent": n}


# ------------------------------------------------------------------ site
@app.get("/sw.js")
def sw():
    return FileResponse(WEB_DIR / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    run()
