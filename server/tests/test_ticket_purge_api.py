import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    AgentObserverEvent,
    AgentRuntimeAudit,
    Artifact,
    DeviceOutbox,
    Operation,
    RemoteAccessEvent,
    RemoteAccessSession,
    Ticket,
    TicketEvent,
    TicketNotification,
    TicketPublicSession,
    TicketWorklog,
)
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN

pytestmark = pytest.mark.db_cleanup("tickets")


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _ticket(ticket_id: str, *, parent_ticket_id: str | None = None) -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        ticket_code=f"T-{ticket_id[-6:].upper()}",
        device_id="device-purge",
        title="purge test ticket",
        description="purge test description",
        status="closed",
        requester_id="user:purge",
        parent_ticket_id=parent_ticket_id,
    )


async def _seed_ticket_graph(session, ticket_id: str, *, operation_status: str = "succeeded", remote_status: str = "ended") -> None:
    now = datetime.now(timezone.utc)
    operation_id = f"op-{ticket_id}"
    trace_id = f"trace-{ticket_id}"
    remote_session_id = f"ra-{ticket_id}"
    session.add(_ticket(ticket_id))
    session.add_all(
        [
            TicketEvent(
                ticket_id=ticket_id,
                device_id="device-purge",
                agent_seq=None,
                event_type="test_event",
                payload={"ok": True},
                trace_id=trace_id,
                operation_id=operation_id,
            ),
            TicketNotification(
                actor_id="support-test",
                ticket_id=ticket_id,
                event_type="test_event",
                payload={},
            ),
            TicketWorklog(
                ticket_id=ticket_id,
                actor_id="support-test",
                spent_minutes=5,
                note="test",
            ),
            TicketPublicSession(
                token_hash=f"hash-{ticket_id}",
                token_prefix="purge",
                ticket_id=ticket_id,
                actor_id="user:purge",
                expires_at=now + timedelta(hours=1),
            ),
            Operation(
                operation_id=operation_id,
                device_id="device-purge",
                ticket_id=ticket_id,
                kind="tool",
                actor_role="support",
                trace_id=trace_id,
                status=operation_status,
                queued_at=now,
            ),
            DeviceOutbox(
                device_id="device-purge",
                command_id=f"cmd-{ticket_id}",
                command="run_tool",
                params={"ticket_id": ticket_id},
                operation_id=operation_id,
                actor_role="support",
                status="delivered",
            ),
            RemoteAccessSession(
                id=remote_session_id,
                ticket_id=ticket_id,
                device_id="device-purge",
                operator_id="support-test",
                mode="view",
                status=remote_status,
                reason="test",
                consent_required=False,
                consent_status="approved",
                expires_at=now + timedelta(minutes=10),
            ),
            RemoteAccessEvent(
                id=f"rae-{ticket_id}",
                session_id=remote_session_id,
                ticket_id=ticket_id,
                actor_type="operator",
                actor_id="support-test",
                event_type="ended",
                payload={},
            ),
            Artifact(
                artifact_id=f"artifact-{ticket_id}",
                storage_path=f"purge/{ticket_id}.txt",
                original_name="purge.txt",
                mime_type="text/plain",
                size_bytes=4,
                sha256="0" * 64,
                device_id="device-purge",
                ticket_id=ticket_id,
                operation_id=operation_id,
            ),
            AgentRuntimeAudit(
                device_id="device-purge",
                event_type="test_runtime_event",
                severity="info",
                source="server",
                operation_id=operation_id,
                ticket_id=ticket_id,
            ),
            AgentObserverEvent(
                event_id=f"aoe-{ticket_id}",
                device_id="device-purge",
                trace_id=trace_id,
                operation_id=operation_id,
                ticket_id=ticket_id,
                root_kind="ticket",
                event_type="test_observer_event",
            ),
        ]
    )
    from app.db.models import ObserverTrace

    session.add(
        ObserverTrace(
            trace_id=trace_id,
            root_kind="ticket",
            ticket_id=ticket_id,
            device_id="device-purge",
            operation_id=operation_id,
            status="ok",
        )
    )
    await session.flush()


async def _count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


@pytest.mark.asyncio
async def test_ticket_purge_preview_is_admin_only_and_reports_related_counts(test_client, test_engine):
    ticket_id = "purge-preview"
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        await _seed_ticket_graph(session, ticket_id)
        await session.commit()

    support_response = await test_client.post(
        "/api/web/admin/tickets/purge/preview",
        headers=_support_headers(),
        json={"ticket_ids": [ticket_id]},
    )
    assert support_response.status == 403

    response = await test_client.post(
        "/api/web/admin/tickets/purge/preview",
        headers=_admin_headers(),
        json={"ticket_ids": [ticket_id]},
    )
    assert response.status == 200
    payload = await response.json()

    data = payload["data"]
    assert data["dry_run"] is True
    assert data["can_purge"] is True
    assert data["requested_count"] == 1
    assert data["found_count"] == 1
    assert data["missing_ticket_ids"] == []
    assert data["affected_counts"]["tickets"] == 1
    assert data["affected_counts"]["ticket_events"] == 1
    assert data["affected_counts"]["operations"] == 1
    assert data["affected_counts"]["device_outbox"] == 1
    assert data["affected_counts"]["remote_access_sessions"] == 1
    assert data["affected_counts"]["artifacts"] == 1
    assert data["affected_counts"]["observer_traces"] == 1


@pytest.mark.asyncio
async def test_ticket_purge_blocks_active_operation_and_remote_assist(test_client, test_engine):
    ticket_id = "purge-blocked"
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        await _seed_ticket_graph(session, ticket_id, operation_status="running", remote_status="active")
        await session.commit()

    response = await test_client.post(
        "/api/web/admin/tickets/purge/preview",
        headers=_admin_headers(),
        json={"ticket_ids": [ticket_id]},
    )
    assert response.status == 200
    data = (await response.json())["data"]
    assert data["can_purge"] is False
    assert {blocker["type"] for blocker in data["blockers"]} == {"active_operation", "active_remote_access"}

    purge_response = await test_client.post(
        "/api/web/admin/tickets/purge",
        headers=_admin_headers(),
        json={"ticket_ids": [ticket_id], "confirm": True},
    )
    assert purge_response.status == 409
    blocked = await purge_response.json()
    assert blocked["error_code"] == "TICKET_PURGE_BLOCKED"


@pytest.mark.asyncio
async def test_ticket_purge_confirmed_removes_fk_and_non_fk_rows(test_client, test_engine):
    ticket_id = "purge-apply"
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        await _seed_ticket_graph(session, ticket_id)
        await session.commit()

    response = await test_client.post(
        "/api/web/admin/tickets/purge",
        headers=_admin_headers(),
        json={"ticket_ids": [ticket_id], "confirm": True, "reason": "test cleanup"},
    )
    assert response.status == 200
    data = (await response.json())["data"]
    assert data["dry_run"] is False
    assert data["can_purge"] is True
    assert data["missing_ticket_ids"] == []
    assert data["purged_ticket_ids"] == [ticket_id]

    async with session_maker() as session:
        assert await _count(session, Ticket) == 0
        assert await _count(session, TicketEvent) == 0
        assert await _count(session, TicketNotification) == 0
        assert await _count(session, TicketWorklog) == 0
        assert await _count(session, TicketPublicSession) == 0
        assert await _count(session, Operation) == 0
        assert await _count(session, DeviceOutbox) == 0
        assert await _count(session, RemoteAccessSession) == 0
        assert await _count(session, RemoteAccessEvent) == 0
        assert await _count(session, Artifact) == 0
        assert await _count(session, AgentRuntimeAudit) == 0
        assert await _count(session, AgentObserverEvent) == 0


@pytest.mark.asyncio
async def test_ticket_purge_blocks_parent_when_child_is_not_selected(test_client, test_engine):
    parent_id = "purge-parent"
    child_id = "purge-child"
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add_all([_ticket(parent_id), _ticket(child_id, parent_ticket_id=parent_id)])
        await session.commit()

    response = await test_client.post(
        "/api/web/admin/tickets/purge/preview",
        headers=_admin_headers(),
        json={"ticket_ids": [parent_id]},
    )
    assert response.status == 200
    data = (await response.json())["data"]
    assert data["can_purge"] is False
    assert data["blockers"] == [
        {
            "type": "child_ticket",
            "ticket_id": parent_id,
            "related_id": child_id,
            "status": "closed",
        }
    ]
