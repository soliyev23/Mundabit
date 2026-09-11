"""Mini App uchun aiohttp server: statik sahifa + statistika API."""
import hashlib
import hmac
import json
import logging
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

import db
from config import BOT_TOKEN, WEBAPP_PORT, expectancy_for
from visual import life_stats

log = logging.getLogger("mundabit.web")
WEBAPP_DIR = Path(__file__).parent / "webapp"


def validate_init_data(init_data: str) -> dict | None:
    """Telegram Web App initData imzosini tekshiradi. To'g'ri bo'lsa user dict."""
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None
    try:
        return json.loads(parsed.get("user", ""))
    except json.JSONDecodeError:
        return None


async def api_me(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "bad_request"}, status=400)

    tg_user = validate_init_data(body.get("initData", ""))
    if not tg_user or "id" not in tg_user:
        return web.json_response({"error": "auth"}, status=401)

    user = db.get_user(tg_user["id"])
    if not user:
        return web.json_response({"error": "not_registered"}, status=404)

    s = life_stats(
        date.fromisoformat(user["birth_date"]),
        expectancy_for(user.get("gender")),
    )
    return web.json_response(
        {
            "weeks_lived": s.weeks_lived,
            "weeks_left": s.weeks_left,
            "pct_lived": s.pct_lived,
            "pct_left": s.pct_left,
            "total_weeks": s.total_weeks,
            "birth_date": user["birth_date"],
            "gender": user.get("gender"),
            "lang": user.get("lang") or "uz",
            "ratings": db.get_week_ratings(tg_user["id"]),
        }
    )


async def index(request: web.Request) -> web.FileResponse:
    # Telegram webview sahifani keshlab qolmasligi uchun
    return web.FileResponse(
        WEBAPP_DIR / "index.html",
        headers={"Cache-Control": "no-store, must-revalidate"},
    )


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_post("/api/me", api_me)
    return app


async def start_webserver() -> web.AppRunner:
    runner = web.AppRunner(create_app())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    log.info("Mini App server: http://localhost:%d", WEBAPP_PORT)
    return runner
