from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.db.models import Device, Operation, Ticket, TicketEvent
from app.repos.ticket_events_repo import TicketEventsRepo


ADMIN_TOKEN = "test-ui-admin-token"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_ticket_root_trace_canonicalizes_lifecycle_events_and_groups_ticket_detail(test_client):
    now = datetime.now(timezone.utc)
    ticket_id = "00000000-0000-0000-0000-00000000c201"
    device_id = "00000000-0000-0000-0000-00000000c202"
    trace_id = "00000000-0000-0000-0000-00000000c203"
    operation_id_1 = "00000000-0000-0000-0000-00000000c204"
    operation_id_2 = "00000000-0000-0000-0000-00000000c205"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.16",
                hostname="observer-v2-root-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSROOT01",
                device_id=device_id,
                title="Observer root trace",
                description="Ticket lifecycle should stay inside one canonical trace",
                status="in_progress",
                created_at=now - timedelta(minutes=20),
                updated_at=now,
                observer_root_trace_id=trace_id,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=operation_id_1,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="system.collect",
                    actor_role="support",
                    trace_id=trace_id,
                    status="succeeded",
                    queued_at=now - timedelta(minutes=8),
                    sent_at=now - timedelta(minutes=8) + timedelta(seconds=1),
                    accepted_at=now - timedelta(minutes=8) + timedelta(seconds=2),
                    started_at=now - timedelta(minutes=8) + timedelta(seconds=3),
                    finished_at=now - timedelta(minutes=8) + timedelta(seconds=4),
                    retry_count=0,
                    result_summary="ok",
                ),
                Operation(
                    operation_id=operation_id_2,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=trace_id,
                    status="timed_out",
                    queued_at=now - timedelta(minutes=4),
                    sent_at=now - timedelta(minutes=4) + timedelta(seconds=1),
                    accepted_at=now - timedelta(minutes=4) + timedelta(seconds=2),
                    started_at=now - timedelta(minutes=4) + timedelta(seconds=3),
                    finished_at=now - timedelta(minutes=4) + timedelta(seconds=9),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="timeout while collecting screen snapshot",
                ),
            ]
        )
        repo = TicketEventsRepo(session)
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="chat_message",
            payload={"message_id": "msg-root-1", "text": "Первое сообщение"},
            trace_id="11111111-1111-1111-1111-111111111111",
            event_id="msg-root-1",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="status_changed",
            payload={"from_status": "new", "to_status": "in_progress"},
            trace_id="22222222-2222-2222-2222-222222222222",
            event_id="status-root-1",
        )
        await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=None,
            event_type="tool_call_started",
            payload={"tool_name": "screen.collect", "call_id": "call-root-2"},
            trace_id="33333333-3333-3333-3333-333333333333",
            operation_id=operation_id_2,
        )
        await session.commit()

    async with get_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.observer_root_trace_id == trace_id
        rows = (
            await session.execute(
                sa.select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.id.asc())
            )
        ).scalars().all()
        assert rows
        assert {row.trace_id for row in rows} == {trace_id}

    search_resp = await test_client.get(
        f"/api/admin/tech/traces?ticket_id={ticket_id}",
        headers=_auth(),
    )
    assert search_resp.status == 200
    search_payload = await search_resp.json()
    assert search_payload["status"] == "ok"
    assert search_payload["count"] == 1
    assert search_payload["traces"][0]["trace_id"] == trace_id
    assert search_payload["traces"][0]["ticket_id"] == ticket_id

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    span_names = {span["name"] for span in detail_payload["spans"]}
    assert "ticket.chat_message" in span_names
    assert "ticket.status_changed" in span_names
    assert {span["source_ref"] for span in detail_payload["spans"] if span["source_type"] == "operation"} == {
        operation_id_1,
        operation_id_2,
    }


@pytest.mark.asyncio
async def test_observer_degradation_queries_report_slow_timeout_and_retry_rates(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000d201"
    ticket_id = "00000000-0000-0000-0000-00000000d202"
    trace_ids = [
        "00000000-0000-0000-0000-00000000d211",
        "00000000-0000-0000-0000-00000000d212",
        "00000000-0000-0000-0000-00000000d213",
    ]
    operation_ids = [
        "00000000-0000-0000-0000-00000000d221",
        "00000000-0000-0000-0000-00000000d222",
        "00000000-0000-0000-0000-00000000d223",
    ]

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.16",
                hostname="observer-v2-degradation-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSDEG01",
                device_id=device_id,
                title="Observer degradations",
                description="Slow and retry-heavy operations must be queryable",
                status="in_progress",
                created_at=now - timedelta(minutes=30),
                updated_at=now,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=operation_ids[0],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[0],
                    status="timed_out",
                    queued_at=now - timedelta(minutes=12),
                    started_at=now - timedelta(minutes=12) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=12) + timedelta(seconds=7),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="ping timeout",
                ),
                Operation(
                    operation_id=operation_ids[1],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[1],
                    status="failed",
                    queued_at=now - timedelta(minutes=9),
                    started_at=now - timedelta(minutes=9) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=9) + timedelta(seconds=4),
                    retry_count=1,
                    error_code="UNREACHABLE",
                    error_message="host unreachable",
                ),
                Operation(
                    operation_id=operation_ids[2],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="network_ping.ping",
                    actor_role="support",
                    trace_id=trace_ids[2],
                    status="succeeded",
                    queued_at=now - timedelta(minutes=6),
                    started_at=now - timedelta(minutes=6) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=6) + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="ok",
                ),
            ]
        )
        await session.commit()

    slow_search = await test_client.get(
        "/api/admin/tech/traces?tool_name=network_ping.ping&min_duration_ms=5000",
        headers=_auth(),
    )
    assert slow_search.status == 200
    slow_payload = await slow_search.json()
    assert slow_payload["status"] == "ok"
    assert {item["trace_id"] for item in slow_payload["traces"]} == {trace_ids[0]}

    retry_search = await test_client.get(
        "/api/admin/tech/traces?tool_name=network_ping.ping&min_retry_count=2",
        headers=_auth(),
    )
    assert retry_search.status == 200
    retry_payload = await retry_search.json()
    assert retry_payload["status"] == "ok"
    assert {item["trace_id"] for item in retry_payload["traces"]} == {trace_ids[0]}

    degradation_resp = await test_client.get(
        "/api/admin/tech/degradations?tool_name=network_ping.ping&lookback_hours=24&min_duration_ms=2500",
        headers=_auth(),
    )
    assert degradation_resp.status == 200
    degradation_payload = await degradation_resp.json()
    assert degradation_payload["status"] == "ok"
    assert degradation_payload["count"] == 1
    item = degradation_payload["items"][0]
    assert item["tool_name"] == "network_ping.ping"
    assert item["operations_count"] == 3
    assert item["timeout_count"] == 1
    assert item["retried_operations_count"] == 2
    assert item["slow_operations_count"] == 2
    assert item["timeout_rate"] == pytest.approx(1 / 3, rel=1e-4)
    assert item["retry_rate"] == pytest.approx(2 / 3, rel=1e-4)
    assert item["slow_rate"] == pytest.approx(2 / 3, rel=1e-4)


@pytest.mark.asyncio
async def test_observer_can_filter_agent_update_traces_and_rate_threshold_degradations(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000e201"
    ticket_id = "00000000-0000-0000-0000-00000000e202"
    update_trace_ids = [
        "00000000-0000-0000-0000-00000000e211",
        "00000000-0000-0000-0000-00000000e212",
    ]
    update_operation_ids = [
        "00000000-0000-0000-0000-00000000e221",
        "00000000-0000-0000-0000-00000000e222",
    ]
    tool_trace_id = "00000000-0000-0000-0000-00000000e213"
    tool_operation_id = "00000000-0000-0000-0000-00000000e223"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.17",
                hostname="observer-v2-update-host",
                os="windows",
                capabilities=[],
                tools_version="observer-v2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=30),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-OBSUPD01",
                device_id=device_id,
                title="Observer update traces",
                description="agent_update should be queryable as a dangerous flow",
                status="in_progress",
                created_at=now - timedelta(minutes=30),
                updated_at=now,
            )
        )
        session.add_all(
            [
                Operation(
                    operation_id=update_operation_ids[0],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="agent_update",
                    tool_name="update",
                    actor_role="admin",
                    trace_id=update_trace_ids[0],
                    status="timed_out",
                    queued_at=now - timedelta(minutes=12),
                    started_at=now - timedelta(minutes=12) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=12) + timedelta(seconds=8),
                    retry_count=2,
                    error_code="TIMEOUT",
                    error_message="launcher update timeout",
                ),
                Operation(
                    operation_id=update_operation_ids[1],
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="agent_update",
                    tool_name="update",
                    actor_role="admin",
                    trace_id=update_trace_ids[1],
                    status="succeeded",
                    queued_at=now - timedelta(minutes=8),
                    started_at=now - timedelta(minutes=8) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=8) + timedelta(seconds=2),
                    retry_count=0,
                    result_summary="confirmed_by_handshake:3.1.18",
                ),
                Operation(
                    operation_id=tool_operation_id,
                    device_id=device_id,
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="screen.collect",
                    actor_role="support",
                    trace_id=tool_trace_id,
                    status="failed",
                    queued_at=now - timedelta(minutes=6),
                    started_at=now - timedelta(minutes=6) + timedelta(seconds=1),
                    finished_at=now - timedelta(minutes=6) + timedelta(seconds=2),
                    retry_count=0,
                    error_code="TOOL_FAILED",
                    error_message="screen collect failed",
                ),
            ]
        )
        await session.commit()

    trace_search = await test_client.get(
        "/api/admin/tech/traces?root_kind=agent_update",
        headers=_auth(),
    )
    assert trace_search.status == 200
    trace_payload = await trace_search.json()
    assert trace_payload["status"] == "ok"
    assert {item["trace_id"] for item in trace_payload["traces"]} == set(update_trace_ids)

    degradation_resp = await test_client.get(
        (
            "/api/admin/tech/degradations"
            "?root_kind=agent_update"
            "&lookback_hours=24"
            "&min_duration_ms=2000"
            "&min_timeout_rate=0.5"
            "&min_retry_rate=0.5"
            "&min_slow_rate=0.5"
        ),
        headers=_auth(),
    )
    assert degradation_resp.status == 200
    degradation_payload = await degradation_resp.json()
    assert degradation_payload["status"] == "ok"
    assert degradation_payload["count"] == 1
    item = degradation_payload["items"][0]
    assert item["tool_name"] == "update"
    assert item["operation_kind"] == "agent_update"
    assert item["operations_count"] == 2
    assert item["timeout_rate"] == pytest.approx(0.5, rel=1e-4)
    assert item["retry_rate"] == pytest.approx(0.5, rel=1e-4)
    assert item["slow_rate"] == pytest.approx(0.5, rel=1e-4)
