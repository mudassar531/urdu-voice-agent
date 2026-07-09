"""Tests for the web-demo token/lead server (src/webapp/token_server.py)."""

from __future__ import annotations

import base64
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from webapp.token_server import build_app


def _decode_jwt_claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


@pytest.fixture
async def client(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVEKIT_URL", "wss://x.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "devkey")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "s" * 40)
    monkeypatch.setenv("AGENT_NAME", "voice-agent")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("LEAD_STORE_PATH", str(tmp_path / "leads.jsonl"))
    monkeypatch.delenv("LEAD_WEBHOOK_URL", raising=False)

    c = TestClient(TestServer(build_app()))
    await c.start_server()
    yield c
    await c.close()


async def test_health_ok(client):
    resp = await client.get("/health")
    assert resp.status == 200
    assert (await resp.json())["status"] == "ok"


async def test_session_rejects_invalid_email(client):
    resp = await client.post("/api/session", json={"email": "not-an-email"})
    assert resp.status == 400
    assert (await resp.json())["error"] == "invalid_email"


async def test_session_mints_token_with_agent_dispatch(client, tmp_path):
    resp = await client.post("/api/session", json={"email": "ali@example.com", "name": "Ali"})
    assert resp.status == 200
    data = await resp.json()

    assert data["serverUrl"] == "wss://x.livekit.cloud"
    assert data["roomName"].startswith("urdu-demo-")

    claims = _decode_jwt_claims(data["token"])
    assert claims["video"]["room"] == data["roomName"]
    assert claims["video"]["roomJoin"] is True
    agents = claims["roomConfig"]["agents"]
    assert agents[0]["agentName"] == "voice-agent"

    # Lead was persisted to the JSONL store.
    leads = (tmp_path / "leads.jsonl").read_text(encoding="utf-8")
    assert "ali@example.com" in leads


async def test_session_500_when_livekit_unconfigured(client, monkeypatch):
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    resp = await client.post("/api/session", json={"email": "ali@example.com"})
    assert resp.status == 500
    assert (await resp.json())["error"] == "server_not_configured"


async def test_cors_preflight(client):
    resp = await client.options("/api/session", headers={"Origin": "https://example.com"})
    assert resp.status == 204
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
