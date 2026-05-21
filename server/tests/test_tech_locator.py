from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceOutbox, ObserverTrace, Operation, Ticket, TicketApproval
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _requester_headers(actor_id: str = "requester-tech-locator") -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{actor_id}"}


async def _seed_locator_context(test_engine):
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
                agent_version="3.1.40",
                hostname="pilot-host-01",
                os="ALT Linux",
                first_seen_at=now - timedelta(days=2),
                last_seen_at=now - timedelta(hours=2),
                last_handshake_at=now - timedelta(hours=2),
            )
        )
        session.add(
            Ticket(
                ticket_id=ticket_id,
                ticket_code="T-910571",
                device_id=device_id,
                title="Pilot workstation cannot print",
                description="Printer is unavailable",
                status="in_progress",
                priority="P1",
                requester_id="requester-1",
                assignee_id="support-test",
                first_response_due_at=now - timedelta(minutes=10),
                resolution_due_at=now + timedelta(hours=2),
                created_at=now - timedelta(hours=3),
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
                command_name=None,
                actor_role="support",
                trace_id=trace_id,
                status="failed",
                phase="finished",
                queued_at=now - timedelta(minutes=20),
                sent_at=now - timedelta(minutes=19),
                accepted_at=now - timedelta(minutes=18),
                started_at=now - timedelta(minutes=17),
                finished_at=now - timedelta(minutes=16),
                error_code="COLLECT_FAILED",
                error_message="failed with password=secret-token",
            )
        )
        session.add(
            DeviceOutbox(
                device_id=device_id,
                command_id=str(uuid.uuid4()),
                command="run_tool",
                params={"operation_id": operation_id},
                status="pending",
                operation_id=operation_id,
                trace_id=trace_id,
                actor_role="support",
                created_at=now - timedelta(minutes=15),
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
                finished_at=now - timedelta(minutes=16),
                error_count=1,
                attrs_json={"title": "inventory.collect failed", "latest_error": "collector failed"},
            )
        )
        session.add(
            TicketApproval(
                ticket_id=ticket_id,
                approval_type="explicit_user",
                approver_id="manager-1",
                status="requested",
                requested_by="support-test",
                requested_at=now - timedelta(minutes=30),
            )
        )
        await session.commit()

    return {
        "ticket_id": ticket_id,
        "ticket_code": "T-910571",
        "device_id": device_id,
        "hostname": "pilot-host-01",
        "operation_id": operation_id,
        "trace_id": trace_id,
    }


@pytest.mark.asyncio
async def test_ticket_code_locates_ticket_and_links(test_client, test_engine):
    seeded = await _seed_locator_context(test_engine)

    response = await test_client.get(
        f"/api/web/admin/tech/locate?q={seeded['ticket_code']}",
        headers=_admin_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    ticket_match = next(item for item in payload["matches"] if item["kind"] == "ticket")
    assert ticket_match["context"]["ticket_id"] == seeded["ticket_id"]
    assert ticket_match["context"]["ticket_code"] == seeded["ticket_code"]
    assert ticket_match["signals"]["ticket_sla_risk"] is True
    assert ticket_match["signals"]["pending_approval"] is True
    assert {"label": "Открыть тикет", "href": f"/app/tickets/{seeded['ticket_id']}", "kind": "ticket"} in ticket_match["links"]


@pytest.mark.asyncio
async def test_device_id_and_hostname_locate_device(test_client, test_engine):
    seeded = await _seed_locator_context(test_engine)

    by_id = await test_client.get(f"/api/web/admin/tech/locate?q={seeded['device_id']}", headers=_support_headers())
    by_hostname = await test_client.get("/api/web/admin/tech/locate?q=pilot-host-01", headers=_support_headers())

    assert by_id.status == 200, await by_id.text()
    assert by_hostname.status == 200, await by_hostname.text()
    id_payload = await by_id.json()
    host_payload = await by_hostname.json()
    for payload in (id_payload, host_payload):
        device_match = next(item for item in payload["matches"] if item["kind"] in {"device", "hostname"})
        assert device_match["context"]["device_id"] == seeded["device_id"]
        assert device_match["signals"]["stale_agent"] is True
        assert device_match["signals"]["failed_operation"] is True
        assert any(link["href"] == f"/app/admin/device-operations/{seeded['device_id']}" for link in device_match["links"])


@pytest.mark.asyncio
async def test_operation_id_locates_operation_and_redacts_error(test_client, test_engine):
    seeded = await _seed_locator_context(test_engine)

    response = await test_client.get(
        f"/api/web/admin/tech/locate?q={seeded['operation_id']}",
        headers=_admin_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    operation_match = next(item for item in payload["matches"] if item["kind"] == "operation")
    assert operation_match["context"]["operation_id"] == seeded["operation_id"]
    assert operation_match["context"]["ticket_id"] == seeded["ticket_id"]
    assert operation_match["signals"]["failed_operation"] is True
    assert "secret-token" not in str(operation_match)
    assert any(link["href"] == f"/app/admin/observer?operation_id={seeded['operation_id']}" for link in operation_match["links"])


@pytest.mark.asyncio
async def test_trace_id_locates_observer_trace(test_client, test_engine):
    seeded = await _seed_locator_context(test_engine)

    response = await test_client.get(f"/api/web/admin/tech/locate?q={seeded['trace_id']}", headers=_admin_headers())

    assert response.status == 200, await response.text()
    payload = await response.json()
    trace_match = next(item for item in payload["matches"] if item["kind"] == "trace")
    assert trace_match["context"]["trace_id"] == seeded["trace_id"]
    assert trace_match["signals"]["observer_errors"] is True
    assert any(link["href"] == f"/app/admin/observer?trace_id={seeded['trace_id']}" for link in trace_match["links"])


@pytest.mark.asyncio
async def test_no_match_and_short_query_are_controlled(test_client, test_engine):
    await _seed_locator_context(test_engine)

    no_match = await test_client.get("/api/web/admin/tech/locate?q=missing-object", headers=_admin_headers())
    short = await test_client.get("/api/web/admin/tech/locate?q=Pi", headers=_admin_headers())

    assert no_match.status == 200, await no_match.text()
    assert short.status == 200, await short.text()
    no_match_payload = await no_match.json()
    short_payload = await short.json()
    assert no_match_payload["matches"] == []
    assert "ничего не найдено" in no_match_payload["summary"]["primary_diagnosis"]
    assert short_payload["matches"] == []


@pytest.mark.asyncio
async def test_requester_forbidden_for_locator(test_client):
    response = await test_client.get("/api/web/admin/tech/locate?q=T-910571", headers=_requester_headers())

    assert response.status == 403
