from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import Device, Operation, Ticket
from app.repos.ticket_events_repo import TicketEventsRepo


ADMIN_TOKEN = "test-ui-admin-token"
SUPPORT_TOKEN = "test-ui-support-token"
USER_TOKEN = "test-ui-user:plain-user"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_observer_quick_endpoint_returns_hot_traces_signatures_and_flows(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000f201"
    ticket_id = "00000000-0000-0000-0000-00000000f202"
    ticket_trace_id = "00000000-0000-0000-0000-00000000f203"
    update_trace_id = "00000000-0000-0000-0000-00000000f204"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.19",
                hostname="observer-quick-host",
                os="windows",
                capabilities=[],
                tools_version="observer-quick",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(hours=1),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSQ001",
                device_id=device_id,
                title="Observer quick diagnosis",
                description="Quick diagnosis should surface hot traces and dangerous flows",
                status="in_progress",
                created_at=now - timedelta(minutes=50),
                updated_at=now,
                observer_root_trace_id=ticket_trace_id,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id="00000000-0000-0000-0000-00000000f211",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=ticket_trace_id,
                    status="timed_out",
                    queued_at=now - timedelta(minutes=15),
                    started_at=now - timedelta(minutes=15) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=15) + timedelta(seconds=9),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="network ping timeout",
                ),
                Operation(
                    operation_id="00000000-0000-0000-0000-00000000f212",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="agent_update",
                    tool_name="update",
                    actor_role="admin",
                    trace_id=update_trace_id,
                    status="failed",
                    queued_at=now - timedelta(minutes=7),
                    started_at=now - timedelta(minutes=7) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=7) + timedelta(seconds=5),
                    retry_count=1,
                    error_code="VERIFY_FAILED",
                    error_message="launcher signature mismatch",
                ),
                Operation(
                    operation_id="00000000-0000-0000-0000-00000000f213",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id="00000000-0000-0000-0000-00000000f214",
                    status="succeeded",
                    queued_at=now - timedelta(minutes=4),
                    started_at=now - timedelta(minutes=4) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=4) + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="ok",
                ),
            ]
        )
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"message_id": "quick-msg-1", "text": "diagnose this device"},
            trace_id="11111111-1111-1111-1111-111111111111",
            event_id="quick-msg-1",
        )
        await session.commit()

    support_ok = await test_client.get(
        "/api/admin/tech/observer/quick?lookback_hours=24",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert support_ok.status == 200
    payload = await support_ok.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["hot_trace_count"] >= 1
    assert any(item["trace_id"] in {ticket_trace_id, update_trace_id} for item in payload["hot_traces"])
    assert any(item["tool_name"] == "network_ping.ping" for item in payload["top_degradations"])
    assert any(item["error_signature"] for item in payload["top_signatures"])
    assert any(item["root_kind"] in {"tool_call", "agent_update"} for item in payload["dangerous_flows"])

    forbidden = await test_client.get(
        "/api/admin/tech/observer/quick",
        headers=_auth(USER_TOKEN),
    )
    assert forbidden.status == 403


@pytest.mark.asyncio
async def test_ticket_observer_summary_returns_root_trace_related_traces_and_signatures(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000f301"
    ticket_id = "00000000-0000-0000-0000-00000000f302"
    root_trace_id = "00000000-0000-0000-0000-00000000f303"
    legacy_trace_id = "00000000-0000-0000-0000-00000000f304"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.19",
                hostname="observer-ticket-host",
                os="windows",
                capabilities=[],
                tools_version="observer-ticket",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(hours=2),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSTKT1",
                device_id=device_id,
                title="Ticket observer summary",
                description="Support should see the current trace summary for a ticket",
                status="in_progress",
                created_at=now - timedelta(minutes=45),
                updated_at=now,
                observer_root_trace_id=root_trace_id,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id="00000000-0000-0000-0000-00000000f311",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=root_trace_id,
                    status="succeeded",
                    queued_at=now - timedelta(minutes=20),
                    started_at=now - timedelta(minutes=20) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=20) + timedelta(seconds=3),
                    retry_count=0,
                    result_summary="ok",
                ),
                Operation(
                    operation_id="00000000-0000-0000-0000-00000000f312",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=legacy_trace_id,
                    status="failed",
                    queued_at=now - timedelta(minutes=6),
                    started_at=now - timedelta(minutes=6) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=6) + timedelta(seconds=5),
                    retry_count=1,
                    error_code="TOOL_EXEC_FAILED",
                    error_message="left, top, width and height must be provided together",
                ),
            ]
        )
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"message_id": "ticket-observer-msg", "text": "user reported issue"},
            trace_id="99999999-9999-9999-9999-999999999999",
            event_id="ticket-observer-msg",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="status_changed",
            payload={"from_status": "new", "to_status": "in_progress"},
            trace_id="88888888-8888-8888-8888-888888888888",
            event_id="ticket-observer-status",
        )
        await session.commit()

    response = await test_client.get(
        f"/api/tickets/{ticket_id}/observer",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["summary"]["ticket_id"] == ticket_id
    assert payload["summary"]["root_trace_id"] == root_trace_id
    assert payload["root_trace"]["trace_id"] == root_trace_id
    assert any(item["trace_id"] == legacy_trace_id for item in payload["related_traces"])
    assert any(span["name"] == "ticket.chat_message" for span in payload["root_trace_excerpt"]["spans"])
    assert payload["summary"]["trace_count"] >= 2
    assert any(item["error_signature"] for item in payload["signatures"])


@pytest.mark.asyncio
async def test_ticket_observer_summary_counts_all_ticket_traces_and_local_signature_occurrences(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000f401"
    ticket_id = "00000000-0000-0000-0000-00000000f402"
    other_ticket_id = "00000000-0000-0000-0000-00000000f403"
    root_trace_id = "00000000-0000-0000-0000-00000000f404"
    other_trace_id = "00000000-0000-0000-0000-00000000f405"
    shared_error_message = "left, top, width and height must be provided together"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.19",
                hostname="observer-ticket-counts",
                os="windows",
                capabilities=[],
                tools_version="observer-ticket",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(hours=2),
            )
        )
        session.add_all(
            [
                Ticket(
                    ticket_id=ticket_id,
                    ticket_code="T-OBSTKT2",
                    device_id=device_id,
                    title="Ticket observer counts",
                    description="Counts should include the full ticket trace set",
                    status="new",
                    created_at=now - timedelta(hours=1),
                    updated_at=now,
                    observer_root_trace_id=root_trace_id,
                ),
                Ticket(
                    ticket_id=other_ticket_id,
                    ticket_code="T-OBSTKT3",
                    device_id=device_id,
                    title="Other ticket observer counts",
                    description="Shared signature should keep global and ticket-local counts separate",
                    status="new",
                    created_at=now - timedelta(hours=1),
                    updated_at=now,
                    observer_root_trace_id=other_trace_id,
                ),
            ]
        )
        session.add(
            Operation(
                operation_id="00000000-0000-0000-0000-00000000f411",
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="screen.collect",
                actor_role="support",
                trace_id=root_trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=40),
                started_at=now - timedelta(minutes=40) + timedelta(seconds=1),
                finished_at=now - timedelta(minutes=40) + timedelta(seconds=4),
                retry_count=0,
                error_code="TOOL_EXEC_FAILED",
                error_message=shared_error_message,
            )
        )
        for index in range(9):
            trace_id = f"00000000-0000-0000-0000-00000000f42{index}"
            queued_at = now - timedelta(minutes=18 - index)
            session.add(
                Operation(
                    operation_id=f"00000000-0000-0000-0000-00000000f43{index}",
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="system.collect",
                    actor_role="support",
                    trace_id=trace_id,
                    status="succeeded",
                    queued_at=queued_at,
                    started_at=queued_at + timedelta(seconds=1),
                    finished_at=queued_at + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="ok",
                )
            )
        session.add(
            Operation(
                operation_id="00000000-0000-0000-0000-00000000f499",
                device_id=device_id,
                ticket_id=other_ticket_id,
                kind="tool_call",
                tool_name="screen.collect",
                actor_role="support",
                trace_id=other_trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=10),
                started_at=now - timedelta(minutes=10) + timedelta(seconds=1),
                finished_at=now - timedelta(minutes=10) + timedelta(seconds=4),
                retry_count=0,
                error_code="TOOL_EXEC_FAILED",
                error_message=shared_error_message,
            )
        )
        await session.commit()

    response = await test_client.get(
        f"/api/tickets/{ticket_id}/observer",
        headers=_auth(SUPPORT_TOKEN),
    )
    assert response.status == 200
    payload = await response.json()

    assert payload["summary"]["trace_count"] >= 10
    assert payload["summary"]["error_trace_count"] == 1
    assert len(payload["error_traces"]) == 1
    assert payload["error_traces"][0]["trace_id"] == root_trace_id
    assert payload["signatures"]
    assert payload["signatures"][0]["ticket_occurrences_count"] == 1
    assert payload["signatures"][0]["occurrences_count"] >= payload["signatures"][0]["ticket_occurrences_count"]
