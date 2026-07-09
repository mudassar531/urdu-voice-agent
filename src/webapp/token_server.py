"""
Token + lead-capture HTTP server for the web voice demo.

Runs alongside the LiveKit worker in the same container (see
``scripts/docker_entrypoint.sh``). The landing page calls ``POST /api/session``
with the visitor's email; we record the lead and return a LiveKit access token
whose embedded ``RoomConfiguration`` dispatches the named Urdu agent
(``AGENT_NAME``) into the visitor's room. No microphone audio ever reaches this
server — it only mints tokens and stores leads.

Endpoints:
  POST /api/session  {email, name?} -> {serverUrl, token, roomName}
  GET  /health                      -> {status: "ok"}   (Render health + keep-alive)

Config (env): LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, AGENT_NAME,
ALLOWED_ORIGINS (comma-separated, or "*"), LEAD_STORE_PATH, LEAD_WEBHOOK_URL,
PORT (Render-provided; falls back to TOKEN_SERVER_PORT then 8080).
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from livekit import api

logger = logging.getLogger("token-server")

# Deliberately permissive but sane; real validation is the round-trip email.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _allowed_origins() -> list[str]:
    raw = _env("ALLOWED_ORIGINS", "*")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or ["*"]


def _cors_headers(origin: str | None) -> dict[str, str]:
    allowed = _allowed_origins()
    normalized = (origin or "").rstrip("/")
    if "*" in allowed:
        allow = "*"
    elif normalized and normalized in allowed:
        allow = origin  # echo the exact request origin
    else:
        allow = allowed[0]
    return {
        "Access-Control-Allow-Origin": allow,
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
    }


@web.middleware
async def cors_middleware(request: web.Request, handler):
    origin = request.headers.get("Origin")
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=_cors_headers(origin))
    try:
        resp = await handler(request)
    except web.HTTPException as exc:
        exc.headers.update(_cors_headers(origin))
        raise
    resp.headers.update(_cors_headers(origin))
    return resp


def _err(status: int, code: str) -> web.HTTPException:
    exc_cls = {400: web.HTTPBadRequest, 500: web.HTTPInternalServerError}.get(
        status, web.HTTPBadRequest
    )
    return exc_cls(text=json.dumps({"error": code}), content_type="application/json")


def _record_lead(email: str, name: str, room: str, extra: dict) -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "email": email,
        "name": name,
        "room": room,
        **extra,
    }
    path = _env("LEAD_STORE_PATH", "/tmp/urdu-demo-leads.jsonl")
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:  # non-fatal: a lead write must never block a call
        logger.warning("lead store write failed (%s): %s", path, exc)
    logger.info("[lead] email=%s name=%s room=%s", email, name or "-", room)
    return entry


async def _forward_lead(entry: dict) -> None:
    url = _env("LEAD_WEBHOOK_URL")
    if not url:
        return
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=entry, timeout=aiohttp.ClientTimeout(total=5))
    except Exception as exc:  # non-fatal
        logger.warning("lead webhook POST failed: %s", exc)


async def handle_session(request: web.Request) -> web.Response:
    lk_url = _env("LIVEKIT_URL")
    api_key = _env("LIVEKIT_API_KEY")
    api_secret = _env("LIVEKIT_API_SECRET")
    if not (lk_url and api_key and api_secret):
        logger.error("LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET not configured")
        raise _err(500, "server_not_configured")

    try:
        body = await request.json()
    except Exception:
        raise _err(400, "invalid_json")

    email = str(body.get("email", "")).strip().lower()
    name = str(body.get("name", "")).strip()[:80]
    if not _EMAIL_RE.match(email):
        raise _err(400, "invalid_email")

    agent_name = _env("AGENT_NAME", "voice-agent")
    room = f"urdu-demo-{secrets.token_hex(6)}"
    identity = f"web-{secrets.token_hex(4)}"

    entry = _record_lead(email, name, room, {"source": "web", "identity": identity})
    await _forward_lead(entry)

    # Embed agent dispatch in the token: when the browser joins `room` with this
    # token, LiveKit creates the room and dispatches our named agent into it.
    dispatch_meta = json.dumps({"source": "web", "email": email, "name": name})
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(name or "Guest")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=agent_name, metadata=dispatch_meta)]
            )
        )
        .to_jwt()
    )

    return web.json_response({"serverUrl": lk_url, "token": token, "roomName": room})


async def handle_health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def build_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_post("/api/session", handle_session)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_health)
    return app


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    port = int(_env("PORT") or _env("TOKEN_SERVER_PORT") or "8080")
    logger.info(
        "Token server listening on 0.0.0.0:%d (agent_name=%s)",
        port,
        _env("AGENT_NAME", "voice-agent"),
    )
    web.run_app(build_app(), host="0.0.0.0", port=port, print=None)


if __name__ == "__main__":
    main()
