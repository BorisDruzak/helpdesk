from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DevicePresenceSnapshot, ObserverTrace, Operation, Ticket
from observer.debug_facade import (
    ObserverDebugFilters,
    _redact_debug_payload,
    agent_presence_snapshot,
    locate_debug_context,
    observer_debug_bundle_v2,
    runtime_snapshot,
)


async def _seed_debug_context(test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.61",
                hostname="mcp-debug-host",
                os="ALT Linux",
                first_seen_at=now - timedelta(days=1),
                last_seen_at=now - timedelta(hours=1),
                last_handshake_at=now - timedelta(hours=1),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-920777",
                device_id=device_id,
                title="MCP debug seeded ticket",
                description="Seeded for MCP facade",
                status="in_progress",
                priority="P2",
                requester_id="requester-mcp",
                created_at=now - timedelta(hours=2),
                updated_at=now - timedelta(minutes=5),
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="inventory.collect",
                actor_role="support",
                trace_id=trace_id,
                status="failed",
                phase="finished",
                queued_at=now - timedelta(minutes=20),
                finished_at=now - timedelta(minutes=10),
                error_code="MCP_TEST_FAILED",
                error_message="failed with password=must-redact",
            )
        )
        session.add(
            ObserverTrace(
                trace_id=trace_id,
                root_span_id=str(uuid.uuid4()),
                root_kind="tool_call",
                ticket_id=ticket_id,
                device_id=device_id,
                operation_id=operation_id,
                status="failed",
                started_at=now - timedelta(minutes=20),
                finished_at=now - timedelta(minutes=10),
                error_count=1,
                attrs_json={
                    "title": "MCP debug trace",
                    "password": "must-redact",
                    "public_access_code": "ABCD1234",
                    "system_message": "Authorization code for ticket access: ABCD1234",
                },
            )
        )
        session.add(
            DevicePresenceSnapshot(
                device_id=device_id,
                snapshot={"session": "active", "token": "must-redact"},
                collected_at=now - timedelta(minutes=3),
                received_at=now - timedelta(minutes=2),
                session_state="active",
                current_user="requester-mcp",
                idle_seconds=5,
                locked=False,
            )
        )
        await session.commit()

    return {
        "ticket_id": ticket_id,
        "ticket_code": "T-920777",
        "device_id": device_id,
        "operation_id": operation_id,
        "trace_id": trace_id,
    }


@pytest.mark.asyncio
async def test_imports_without_aiohttp_request() -> None:
    import observer.debug_facade as facade

    assert hasattr(facade, "locate_debug_context")
    assert hasattr(facade, "observer_debug_bundle_v2")


@pytest.mark.asyncio
async def test_locate_debug_context_works_with_seeded_db_rows(test_engine) -> None:
    seeded = await _seed_debug_context(test_engine)
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        payload = await locate_debug_context(session, q=seeded["ticket_code"])

    assert payload["status"] == "ok"
    assert payload["matches"][0]["kind"] == "ticket"
    assert payload["matches"][0]["context"]["ticket_id"] == seeded["ticket_id"]


@pytest.mark.asyncio
async def test_observer_debug_bundle_v2_returns_partial_or_ok_and_redacts(test_engine) -> None:
    seeded = await _seed_debug_context(test_engine)
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        payload = await observer_debug_bundle_v2(
            session,
            ObserverDebugFilters(trace_id=seeded["trace_id"], limit=10, include_presence_snapshot=True),
        )

    assert payload["status"] in {"ok", "partial"}
    assert payload["primary_trace"]["trace_id"] == seeded["trace_id"]
    assert "must-redact" not in str(payload)
    assert "ABCD1234" not in str(payload)
    assert payload["redaction"]["applied"] is True


@pytest.mark.asyncio
async def test_runtime_and_presence_unavailable_do_not_crash(test_engine) -> None:
    seeded = await _seed_debug_context(test_engine)
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        runtime = await runtime_snapshot(session, process_kind=f"missing-{uuid.uuid4()}")
        presence = await agent_presence_snapshot(session, device_id=seeded["device_id"], limit=5)

    assert runtime["status"] == "partial"
    assert runtime["runtime_snapshot_available"] is False
    assert presence["status"] == "ok"
    assert presence["presence_snapshot_available"] is True
    assert "must-redact" not in str(presence)


@pytest.mark.asyncio
async def test_presence_snapshot_includes_db_device_evidence_without_snapshot(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.61",
                hostname="mcp-no-presence-host",
                os="ALT Linux",
                first_seen_at=now - timedelta(days=1),
                last_seen_at=now - timedelta(minutes=7),
                last_handshake_at=now - timedelta(minutes=8),
            )
        )
        await session.commit()

    async with session_maker() as session:
        presence = await agent_presence_snapshot(session, device_id=device_id, limit=5)

    assert presence["status"] == "partial"
    assert presence["presence_snapshot_available"] is False
    assert presence["device_db_evidence"]["device_id"] == device_id
    assert presence["device_db_evidence"]["hostname"] == "mcp-no-presence-host"
    assert presence["live_ws_state"] == "unavailable_in_debug_readonly_mcp"


def test_observer_debug_redaction_hides_public_access_codes_in_nested_text() -> None:
    payload = _redact_debug_payload(
        {
            "public_access_code": "ZXCV9876",
            "nested": {
                "message": "Authorization code for ticket access: ZXCV9876",
                "ru_message": "\u041a\u043e\u0434 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0438\u0438 "
                "\u0434\u043b\u044f \u0432\u0445\u043e\u0434\u0430 \u0432 \u0442\u0438\u043a\u0435\u0442: ZXCV9876",
            },
        }
    )

    rendered = str(payload)
    assert "ZXCV9876" not in rendered
    assert "***REDACTED***" in rendered
