from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from control_plane import create_control_app


ADMIN_TOKEN = "test-ui-admin-token"
SUPPORT_TOKEN = "test-ui-support-token"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def control_client(patched_get_session, monkeypatch):
    def fake_extract_token_from_header(request):
        auth_header = request.headers.get("Authorization", "")
        if " " in auth_header:
            return auth_header.split(" ", 1)[1].strip()
        return auth_header.strip() or None

    async def fake_verify_agent_token(self, token):
        return None

    async def fake_verify_ui_token(self, token):
        if token == ADMIN_TOKEN:
            return {"user_login": "admin-test", "actor_role": "admin", "type": "ui"}
        if token == SUPPORT_TOKEN:
            return {"user_login": "support-test", "actor_role": "support", "type": "ui"}
        return None

    monkeypatch.setattr("control_plane.extract_token_from_header", fake_extract_token_from_header)
    monkeypatch.setattr("control_plane.AuthService.verify_agent_token", fake_verify_agent_token)
    monkeypatch.setattr("control_plane.AuthService.verify_ui_token", fake_verify_ui_token)
    app = create_control_app()
    async with TestClient(TestServer(app)) as client:
        yield client


@pytest.mark.asyncio
async def test_control_status_returns_runtime_snapshot(control_client, monkeypatch):
    monkeypatch.setattr(
        "control_plane.get_unit_status",
        lambda target, pending_action=None: {
            "target": target,
            "unit": "pc-client-server",
            "display_state": "running",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": 1234,
            "uptime_sec": 45,
            "started_at": "2026-04-13T10:00:00+00:00",
            "status_excerpt": "active (running)",
        },
    )
    monkeypatch.setattr(
        "control_plane.load_control_state",
        lambda: {"last_server_action": {"action": "restart", "reason": "apply release", "status": "ok"}},
    )

    async def fake_main_health(_request):
        return {"reachable": True, "overview": {"postgres_health": {"pool_status": "Pool size: 5"}}}

    monkeypatch.setattr("control_plane._fetch_main_server_health", fake_main_health)

    response = await control_client.get("/api/control/server/status", headers=_auth(ADMIN_TOKEN))
    body = await response.json()

    assert response.status == 200
    assert body["status"] == "ok"
    assert body["server"]["display_state"] == "running"
    assert body["server"]["last_restart_reason"] == "apply release"
    assert body["server"]["main_server_health"]["reachable"] is True


@pytest.mark.asyncio
async def test_control_logs_filters_entries(control_client, monkeypatch):
    monkeypatch.setattr(
        "control_plane.list_journal_entries",
        lambda target, lines=200: [
            {"timestamp": "2026-04-13T10:00:00+00:00", "level": "warning", "message": "slow query", "identifier": "server", "pid": 100},
            {"timestamp": "2026-04-13T10:01:00+00:00", "level": "error", "message": "timeout while starting", "identifier": "server", "pid": 100},
        ],
    )

    response = await control_client.get(
        "/api/control/server/logs?levels=error&contains=timeout",
        headers=_auth(ADMIN_TOKEN),
    )
    body = await response.json()

    assert response.status == 200
    assert body["count"] == 1
    assert body["logs"][0]["message"] == "timeout while starting"


@pytest.mark.asyncio
async def test_control_action_requires_admin(control_client):
    response = await control_client.post(
        "/api/control/server/actions",
        headers=_auth(SUPPORT_TOKEN),
        json={"action": "restart", "reason": "manual"},
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_control_action_restart_updates_state_and_audit(control_client, monkeypatch):
    recorded_state = []
    recorded_audit = []

    monkeypatch.setattr(
        "control_plane.run_action_and_wait",
        lambda target, action: {
            "target": target,
            "display_state": "running",
            "active_state": "active",
            "sub_state": "running",
            "main_pid": 4321,
        },
    )
    monkeypatch.setattr("control_plane.update_last_server_action", lambda **kwargs: recorded_state.append(kwargs) or kwargs)

    async def fake_record_runtime_audit(**kwargs):
        recorded_audit.append(kwargs)

    monkeypatch.setattr("control_plane._record_runtime_audit", fake_record_runtime_audit)

    response = await control_client.post(
        "/api/control/server/actions",
        headers=_auth(ADMIN_TOKEN),
        json={"action": "restart", "reason": "deploy verified build"},
    )
    body = await response.json()

    assert response.status == 200
    assert body["status"] == "ok"
    assert body["action"] == "restart"
    assert any(item["status"] == "running" for item in recorded_state)
    assert any(item["status"] == "ok" for item in recorded_state)
    assert recorded_audit and recorded_audit[0]["action"] == "server_runtime_restart"
