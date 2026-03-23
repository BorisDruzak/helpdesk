from datetime import datetime, timezone, timedelta

import pytest

from app.db import get_session
from app.db.models import Device, Ticket, TicketEvent, Operation, AgentRuntimeAudit


ADMIN_TOKEN = "test-ui-admin-token"
SUPPORT_TOKEN = "test-ui-support-token"
USER_TOKEN = "test-ui-user:plain-user"


def _auth(token: str) -> dict:
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
