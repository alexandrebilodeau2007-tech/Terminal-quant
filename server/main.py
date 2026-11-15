"""Serveur web du Macro Terminal (API + site PWA)."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import calendar_data as cal, engine, push, weekly, seasonality, storage
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
