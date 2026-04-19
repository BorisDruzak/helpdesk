from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app_keys import OBSERVER_REFRESH_RUNTIME_APP_KEY, replace_bound_app_value
from app.db import get_session
from app.db.models import AgentRuntimeAudit, AgentToken, Device, Operation, Ticket, TicketEvent, UiUserAudit
from observer.runtime import ObserverRefreshRuntime
from tech.log_buffer import append_log_record


ADMIN_TOKEN = "test-ui-admin-token"
SUPPORT_TOKEN = "test-ui-support-token"
USER_TOKEN = "test-ui-user:plain-user"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_tech_overview_roles(test_client):
    ok_admin = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    ok_support = await test_client.get("/api/admin/tech/overview", headers=_auth(SUPPORT_TOKEN))
    forbidden_user = await test_client.get("/api/admin/tech/overview", headers=_auth(USER_TOKEN))

    assert ok_admin.status == 200
    assert ok_support.status == 200
    assert forbidden_user.status == 403
    body = await ok_admin.json()
    assert body["status"] == "ok"
    assert "overview" in body
    assert "alerts" in body["overview"]


@pytest.mark.asyncio
async def test_tech_trace_runtime_status_endpoint(test_client):
    runtime = ObserverRefreshRuntime(scan_interval_sec=0.05, debounce_sec=0.01, max_batch=10)
    await runtime.start()
    replace_bound_app_value(
        test_client.app,
        key=OBSERVER_REFRESH_RUNTIME_APP_KEY,
        legacy_name="observer_refresh_runtime",
        value=runtime,
    )
    try:
        response = await test_client.get("/api/admin/tech/traces/runtime", headers=_auth(ADMIN_TOKEN))

        assert response.status == 200
        payload = await response.json()
        assert payload["status"] == "ok"
        runtime_payload = payload["runtime"]
        assert runtime_payload["enabled"] is True
        assert "running" in runtime_payload
        assert "config" in runtime_payload
        assert "stats" in runtime_payload
    finally:
        await runtime.stop()


@pytest.mark.asyncio
async def test_tech_lifecycle_and_agent_audit_feed(test_client):
    now = datetime.now(timezone.utc)
    ticket_id = "00000000-0000-0000-0000-000000000101"
    device_id = "00000000-0000-0000-0000-000000000201"
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="test-host",
                os="windows",
                capabilities=[],
                tools_version="t1",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now,
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-000001",
                device_id=device_id,
                title="Lifecycle test",
                description="desc",
                status="in_progress",
                assignee_id="support-test",
                created_at=now - timedelta(minutes=10),
                updated_at=now,
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="status_changed",
                payload={"old_value": "new", "new_value": "in_progress", "actor_id": "support-test"},
                created_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="assignee_changed",
                payload={"new_value": "support-test", "actor_id": "system"},
                created_at=now - timedelta(minutes=6),
            )
        )
        session.add(
            Operation(
                operation_id="00000000-0000-0000-0000-000000000301",
                device_id=device_id,
                ticket_id=ticket_id,
                kind="agent_update",
                actor_role="admin",
                trace_id="00000000-0000-0000-0000-000000000401",
                status="queued",
                queued_at=now - timedelta(minutes=2),
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="handshake_ok",
                severity="info",
                source="test",
                created_at=now - timedelta(minutes=1),
            )
        )
        await session.commit()

    lifecycle_resp = await test_client.get(
        f"/api/admin/tech/tickets/{ticket_id}/lifecycle",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert lifecycle_resp.status == 200
    lifecycle = await lifecycle_resp.json()
    assert lifecycle["status"] == "ok"
    assert lifecycle["ticket"]["ticket_id"] == ticket_id
    assert lifecycle["ticket"]["device_id"] == device_id
    assert lifecycle["ticket"]["assignee_id"] == "support-test"
    assert lifecycle["milestones"]["assigned"] is not None
    assert lifecycle["milestones"]["in_progress"] is not None
    assert isinstance(lifecycle["timeline"], list)
    assert isinstance(lifecycle.get("milestone_rail"), list)
    assert lifecycle["timeline"] and lifecycle["timeline"][0].get("links")
    assert lifecycle["timeline"][0].get("device_id") == device_id

    audit_resp = await test_client.get(
        "/api/admin/tech/agents/audit?limit=10",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert audit_resp.status == 200
    audit_body = await audit_resp.json()
    assert audit_body["status"] == "ok"
    assert any(item["event_type"] == "handshake_ok" for item in audit_body["events"])

    timeline_resp = await test_client.get(
        f"/api/admin/tech/agents/{device_id}/timeline",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert timeline_resp.status == 200
    timeline_body = await timeline_resp.json()
    assert timeline_body["status"] == "ok"
    assert timeline_body["current_state"]["online"] is False
    assert isinstance(timeline_body["handshake_timeline"], list)
    assert isinstance(timeline_body["recent_operations"], list)
    assert "outbox_summary" in timeline_body


@pytest.mark.asyncio
async def test_tech_overview_ignores_stale_pending_for_devices_with_active_token(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-000000000777"
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                hostname="stale-but-active",
                os="windows",
                capabilities=[],
                tools_version="t1",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now,
            )
        )
        await session.flush()
        session.add(
            AgentToken(
                token_hash="a" * 64,
                token_prefix="aaaaaaaa",
                device_id=device_id,
                created_at=now - timedelta(hours=1),
                expires_at=now + timedelta(days=30),
                revoked_at=None,
            )
        )
        from app.db.models import ConnectionRequest

        session.add(
            ConnectionRequest(
                device_id=device_id,
                status="pending",
                hostname="stale-but-active",
                ip_address="10.0.0.5",
                created_at=now - timedelta(hours=2),
                last_request_at=now - timedelta(hours=1),
            )
        )
        await session.commit()

    overview_resp = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    assert overview_resp.status == 200
    body = await overview_resp.json()
    overview = body["overview"]
    assert overview["agent_health"]["pending_connection_requests"] == 0
    assert not any(
        alert["kind"] == "connection_request_stuck_pending"
        for alert in overview["alerts"]
    )


@pytest.mark.asyncio
async def test_tech_audit_and_logs_are_localized(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-000000000901"
    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="1.2.3",
                hostname="audit-host",
                os="windows",
                capabilities=[],
                tools_version="t1",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now,
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="invalid_token",
                severity="error",
                source="test",
                details_json={"reason": "invalid_token"},
                created_at=now,
            )
        )
        session.add(
            UiUserAudit(
                user_login="support-test",
                action="login_failed",
                actor_id="support-test",
                details_json={"failed_attempts": 2},
                created_at=now,
            )
        )
        await session.commit()

    append_log_record(
        level="warning",
        message="Device warning surfaced in tech panel",
        timestamp=now,
        module="tests.tech",
        function="test_tech_audit_and_logs_are_localized",
        line=123,
    )

    agents_resp = await test_client.get("/api/admin/tech/agents/audit?limit=10", headers=_auth(ADMIN_TOKEN))
    users_resp = await test_client.get("/api/admin/tech/users/audit?limit=10", headers=_auth(ADMIN_TOKEN))
    logs_resp = await test_client.get("/api/admin/tech/logs?limit=10", headers=_auth(ADMIN_TOKEN))

    agents_body = await agents_resp.json()
    users_body = await users_resp.json()
    logs_body = await logs_resp.json()

    assert agents_resp.status == 200
    assert users_resp.status == 200
    assert logs_resp.status == 200
    assert any(
        item["event_label"] == "Неверный токен" and item["severity_label"] == "Ошибка"
        for item in agents_body["events"]
    )
    assert any(item["action_label"] == "Неудачная попытка входа" for item in users_body["events"])
    assert any(
        item["level_label"] == "Предупреждение" and "Device warning surfaced" in item["message"]
        for item in logs_body["logs"]
    )


@pytest.mark.asyncio
async def test_tech_overview_exposes_ui_and_agent_ws_counts(test_client):
    overview_resp = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    overview = await overview_resp.json()

    assert overview_resp.status == 200
    assert "ui_ws_connections" in overview["overview"]["service_health"]
    assert "agent_ws_connections" in overview["overview"]["service_health"]


@pytest.mark.asyncio
async def test_tech_direct_log_dismiss_removes_log_from_panel(test_client):
    now = datetime.now(timezone.utc)
    append_log_record(
        level="warning",
        message="Dismiss me from logs",
        timestamp=now,
        module="tests.tech",
        function="test_tech_direct_log_dismiss_removes_log_from_panel",
        line=77,
    )

    logs_before_resp = await test_client.get("/api/admin/tech/logs?limit=10", headers=_auth(ADMIN_TOKEN))
    logs_before = await logs_before_resp.json()
    target_log = next(item for item in logs_before["logs"] if item["message"] == "Dismiss me from logs")

    dismiss_resp = await test_client.post(
        "/api/admin/tech/dismiss",
        headers=_auth(ADMIN_TOKEN),
        json={"item_type": "log", "item_id": target_log["id"]},
    )
    logs_after_resp = await test_client.get("/api/admin/tech/logs?limit=10", headers=_auth(ADMIN_TOKEN))
    logs_after = await logs_after_resp.json()

    assert dismiss_resp.status == 200
    assert all(item["id"] != target_log["id"] for item in logs_after["logs"])


@pytest.mark.asyncio
async def test_tech_dismiss_alert_also_removes_related_log(test_client):
    now = datetime.now(timezone.utc)
    append_log_record(
        level="error",
        message="Important runtime failure",
        timestamp=now,
        module="tests.tech",
        function="test_tech_dismiss_alert_also_removes_related_log",
        line=91,
    )

    overview_resp = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    logs_resp = await test_client.get("/api/admin/tech/logs?limit=10", headers=_auth(ADMIN_TOKEN))
    overview = await overview_resp.json()
    logs = await logs_resp.json()

    target_log = next(item for item in logs["logs"] if item["message"] == "Important runtime failure")
    target_alert = next(
        item
        for item in overview["overview"]["alerts"]
        if item["kind"] == "runtime_log_problem" and item.get("related_log_id") == target_log["id"]
    )

    dismiss_resp = await test_client.post(
        "/api/admin/tech/dismiss",
        headers=_auth(ADMIN_TOKEN),
        json={
            "item_type": "alert",
            "item_id": target_alert["id"],
            "related_log_id": target_alert["related_log_id"],
        },
    )
    overview_after_resp = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    logs_after_resp = await test_client.get("/api/admin/tech/logs?limit=10", headers=_auth(ADMIN_TOKEN))
    overview_after = await overview_after_resp.json()
    logs_after = await logs_after_resp.json()

    assert dismiss_resp.status == 200
    assert all(item["id"] != target_alert["id"] for item in overview_after["overview"]["alerts"])
    assert all(item["id"] != target_log["id"] for item in logs_after["logs"])


@pytest.mark.asyncio
async def test_tech_noisy_websocket_disconnect_log_is_not_promoted_to_alert(test_client):
    now = datetime.now(timezone.utc)
    append_log_record(
        level="warning",
        message="UI websocket disconnected by peer",
        timestamp=now,
        module="ws_ui.transport",
        function="close",
        line=41,
    )

    overview_resp = await test_client.get("/api/admin/tech/overview", headers=_auth(ADMIN_TOKEN))
    overview = await overview_resp.json()

    assert overview_resp.status == 200
    assert not any(
        item["kind"] == "runtime_log_problem" and "WebSocket" in item["summary"]
        for item in overview["overview"]["alerts"]
    )


@pytest.mark.asyncio
async def test_tech_agent_action_list_tasks_uses_rpc(monkeypatch, test_client):
    captured = {}

    async def fake_send_ws_rpc_request(**kwargs):
        captured.update(kwargs)
        return {
            "payload": {
                "status": "success",
                "data": {
                    "tasks": [{"task_id": "task-1", "kind": "run_tool"}],
                    "count": 1,
                },
            }
        }

    monkeypatch.setattr("tech.handlers.send_ws_rpc_request", fake_send_ws_rpc_request)

    response = await test_client.post(
        "/api/admin/tech/agents/00000000-0000-0000-0000-000000000999/actions",
        headers=_auth(ADMIN_TOKEN),
        json={"action": "list_tasks"},
    )

    body = await response.json()
    assert response.status == 200
    assert body["status"] == "ok"
    assert body["action"] == "list_tasks"
    assert body["result"]["data"]["count"] == 1
    assert captured["method"] == "list_tasks"
