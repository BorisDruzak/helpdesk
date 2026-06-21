from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import AgentRuntimeAudit, Device, DeviceEvent, ObserverTrace, Operation, Ticket, TicketEvent


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")

ADMIN_TOKEN = "test-ui-admin-token"


def _auth(token: str = ADMIN_TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_trace_overlay_projects_existing_sources_into_search_and_detail(test_client):
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000aa01"
    ticket_id = "00000000-0000-0000-0000-00000000bb01"
    device_id = "00000000-0000-0000-0000-00000000cc01"
    operation_id = "00000000-0000-0000-0000-00000000dd01"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="trace-host",
                os="windows",
                capabilities=[],
                tools_version="t1",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=20),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-TRACE01",
                device_id=device_id,
                title="Trace overlay failure",
                description="Overlay should project an existing failed tool call",
                status="in_progress",
                created_at=now - timedelta(minutes=10),
                updated_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="diag_logs.collect",
                actor_role="support",
                trace_id=trace_id,
                status="failed",
                queued_at=now - timedelta(minutes=4),
                sent_at=now - timedelta(minutes=4) + timedelta(seconds=2),
                accepted_at=now - timedelta(minutes=4) + timedelta(seconds=4),
                started_at=now - timedelta(minutes=4) + timedelta(seconds=6),
                finished_at=now - timedelta(minutes=4) + timedelta(seconds=8),
                error_code="MODULE_CRASH",
                error_message="ImportError: diag_logs module failed to load",
                result_summary="module crash",
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_started",
                payload={"tool_name": "diag_logs.collect", "call_id": "call-1"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(minutes=4),
            )
        )
        session.add(
            DeviceEvent(
                device_id=device_id,
                device_seq=1,
                event_type="command_result",
                payload={"status": "failed", "error_code": "MODULE_CRASH"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(minutes=4) + timedelta(seconds=9),
            )
        )
        session.add(
            AgentRuntimeAudit(
                device_id=device_id,
                event_type="module_crash",
                severity="error",
                source="agent",
                operation_id=operation_id,
                ticket_id=ticket_id,
                details_json={"module_name": "diag_logs", "exception_type": "ImportError"},
                created_at=now - timedelta(minutes=4) + timedelta(seconds=10),
            )
        )
        await session.commit()

    search_resp = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert search_resp.status == 200
    search_payload = await search_resp.json()
    assert search_payload["status"] == "ok"
    assert search_payload["count"] == 1
    trace_summary = search_payload["traces"][0]
    assert trace_summary["trace_id"] == trace_id
    assert trace_summary["ticket_id"] == ticket_id
    assert trace_summary["device_id"] == device_id
    assert trace_summary["operation_id"] == operation_id
    assert trace_summary["root_kind"] == "tool_call"
    assert trace_summary["error_count"] >= 1

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    assert detail_payload["trace"]["trace_id"] == trace_id
    assert detail_payload["trace"]["status"] in {"error", "failed"}
    span_names = {span["name"] for span in detail_payload["spans"]}
    assert "operation.tool_call" in span_names
    assert "ticket.tool_call_started" in span_names
    assert "device.command_result" in span_names
    assert any(span["component"] == "agent_runtime_audit" for span in detail_payload["spans"])
    assert detail_payload["error_occurrences"]
    signature = detail_payload["error_occurrences"][0]["error_signature"]

    signature_resp = await test_client.get(
        f"/api/admin/tech/signatures?error_signature={signature}",
        headers=_auth(),
    )
    assert signature_resp.status == 200
    signature_payload = await signature_resp.json()
    assert signature_payload["status"] == "ok"
    assert any(item["error_signature"] == signature for item in signature_payload["signatures"])

    signature_detail_resp = await test_client.get(
        f"/api/admin/tech/signatures/{signature}",
        headers=_auth(),
    )
    assert signature_detail_resp.status == 200
    signature_detail = await signature_detail_resp.json()
    assert signature_detail["status"] == "ok"
    assert signature_detail["signature"]["error_signature"] == signature
    assert signature_detail["signature"]["occurrences_count"] >= 1
    assert any(item["trace_id"] == trace_id for item in signature_detail["occurrences"])


@pytest.mark.asyncio
async def test_trace_overlay_reuses_fresh_projection_until_new_source_arrives(test_client):
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000aa03"
    ticket_id = "00000000-0000-0000-0000-00000000bb03"
    device_id = "00000000-0000-0000-0000-00000000cc03"
    operation_id = "00000000-0000-0000-0000-00000000dd03"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="fresh-projection-host",
                os="windows",
                capabilities=[],
                tools_version="t3",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-TRACE03",
                device_id=device_id,
                title="Fresh observer projection",
                description="search should reuse a fresh projection until a newer source arrives",
                status="in_progress",
                created_at=now - timedelta(minutes=5),
                updated_at=now,
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool_call",
                tool_name="system.collect",
                actor_role="support",
                trace_id=trace_id,
                status="succeeded",
                queued_at=now - timedelta(minutes=2),
                sent_at=now - timedelta(minutes=2) + timedelta(seconds=1),
                accepted_at=now - timedelta(minutes=2) + timedelta(seconds=2),
                started_at=now - timedelta(minutes=2) + timedelta(seconds=3),
                finished_at=now - timedelta(minutes=2) + timedelta(seconds=4),
                result_summary="ok",
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_started",
                payload={"tool_name": "system.collect", "call_id": "call-fresh-1"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(minutes=2),
            )
        )
        await session.commit()

    first_search = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert first_search.status == 200

    async with get_session() as session:
        projected = await session.get(ObserverTrace, trace_id)
        assert projected is not None
        first_updated_at = projected.updated_at
        assert projected.attrs_json.get("source_last_seen_at") is not None

    second_search = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert second_search.status == 200

    async with get_session() as session:
        projected = await session.get(ObserverTrace, trace_id)
        assert projected is not None
        assert projected.updated_at == first_updated_at

    async with get_session() as session:
        session.add(
            DeviceEvent(
                device_id=device_id,
                device_seq=2,
                event_type="command_result",
                payload={"status": "succeeded", "tool_name": "system.collect"},
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now + timedelta(minutes=1),
            )
        )
        await session.commit()

    refreshed_search = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert refreshed_search.status == 200

    async with get_session() as session:
        refreshed = await session.get(ObserverTrace, trace_id)
        assert refreshed is not None
        assert refreshed.updated_at > first_updated_at

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    span_names = {span["name"] for span in detail_payload["spans"]}
    assert "device.command_result" in span_names


@pytest.mark.asyncio
async def test_get_device_toolset_returns_empty_snapshot_when_device_has_no_snapshot(test_client):
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000ee01"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="empty-toolset-host",
                os="windows",
                capabilities=[],
                tools_version="t-empty",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=5),
            )
        )
        await session.commit()

    response = await test_client.get(
        f"/api/devices/{device_id}/toolset",
        headers=_auth(),
    )
    assert response.status == 200
    payload = await response.json()
    assert payload["status"] == "ok"
    assert payload["device_id"] == device_id
    assert payload["missing_snapshot"] is True
    assert payload["tool_count"] == 0
    assert payload["tools_by_module"] == {}


@pytest.mark.asyncio
async def test_trace_overlay_marks_orphaned_tool_dispatch_as_error_signature(test_client):
    now = datetime.now(timezone.utc)
    trace_id = "00000000-0000-0000-0000-00000000aa02"
    ticket_id = "00000000-0000-0000-0000-00000000bb02"
    device_id = "00000000-0000-0000-0000-00000000cc02"
    operation_id = "00000000-0000-0000-0000-00000000dd02"

    async with get_session() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.15",
                hostname="orphan-trace-host",
                os="windows",
                capabilities=[],
                tools_version="t2",
                device_metadata={},
                last_seen_at=now,
                last_handshake_at=now,
                first_seen_at=now - timedelta(minutes=20),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-TRACE02",
                device_id=device_id,
                title="Orphaned tool dispatch",
                description="tool_call_started exists without persisted operation",
                status="in_progress",
                created_at=now - timedelta(minutes=10),
                updated_at=now,
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="tool_call_started",
                payload={
                    "tool_name": "network_ping.ping",
                    "call_id": "call-orphan-1",
                    "params": {"host": "127.0.0.1"},
                },
                trace_id=trace_id,
                operation_id=operation_id,
                created_at=now - timedelta(minutes=3),
            )
        )
        await session.commit()

    trace_search_resp = await test_client.get(
        f"/api/admin/tech/traces?trace_id={trace_id}",
        headers=_auth(),
    )
    assert trace_search_resp.status == 200
    trace_search_payload = await trace_search_resp.json()
    assert trace_search_payload["status"] == "ok"
    assert trace_search_payload["count"] == 1
    trace_summary = trace_search_payload["traces"][0]
    assert trace_summary["status"] == "error"
    assert trace_summary["error_count"] == 1

    detail_resp = await test_client.get(
        f"/api/admin/tech/traces/{trace_id}",
        headers=_auth(),
    )
    assert detail_resp.status == 200
    detail_payload = await detail_resp.json()
    assert detail_payload["status"] == "ok"
    assert detail_payload["trace"]["status"] == "error"
    assert len(detail_payload["error_occurrences"]) == 1
    occurrence = detail_payload["error_occurrences"][0]
    assert occurrence["error_kind"] == "TOOL_DISPATCH_ORPHANED"
    assert occurrence["failure_stage"] == "tool_call_started"
    assert occurrence["component"] == "ticket_events"
    assert occurrence["error_signature"].startswith("tool_dispatch_orphaned")

    signature_resp = await test_client.get(
        f"/api/admin/tech/signatures?ticket_id={ticket_id}",
        headers=_auth(),
    )
    assert signature_resp.status == 200
    signature_payload = await signature_resp.json()
    assert signature_payload["status"] == "ok"
    assert signature_payload["count"] == 1
    assert signature_payload["signatures"][0]["error_signature"] == occurrence["error_signature"]
