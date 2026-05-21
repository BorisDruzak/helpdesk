import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DiagnosticSession, Operation, Ticket, TicketApproval, UiUser
from tests.conftest import TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX
from tests.test_ticket_queue_routing_contracts import _seed_queue


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_ADMIN_TOKEN}"}


def _requester_headers(actor_id: str = "requester-command-center") -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{actor_id}"}


@pytest.mark.asyncio
async def test_operator_command_center_rejects_requester_role(test_client):
    response = await test_client.get("/api/web/support/command-center", headers=_requester_headers())

    assert response.status == 403


@pytest.mark.asyncio
async def test_operator_command_center_returns_typed_sections(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code=f"cmd_{uuid.uuid4().hex[:8]}", name="Command center", members=["support-test"])
        unassigned = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="cmd-device-unassigned",
            title="Live command center unassigned",
            description="Visible unassigned ticket",
            status="queued",
            requester_id="requester-unassigned",
            queue_id=queue.id,
            priority="P2",
            first_response_due_at=now + timedelta(minutes=20),
            service_code="workplace",
            offering_code="workplace/laptop",
        )
        action = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="cmd-device-action",
            title="Operator action overdue",
            description="Operator must act",
            status="in_progress",
            requester_id="requester-action",
            queue_id=queue.id,
            assignee_id="support-test",
            next_action_owner="support",
            next_action_due_at=now - timedelta(minutes=5),
        )
        approval = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="cmd-device-approval",
            title="Pending approval ticket",
            description="Approval state is canonical",
            status="waiting_on_approval",
            requester_id="requester-approval",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        unassigned_ticket_id = unassigned.ticket_id
        session.add_all([unassigned, action, approval])
        session.add(
            TicketApproval(
                ticket_id=approval.ticket_id,
                approval_type="service_owner",
                approver_id="owner-1",
                status="requested",
                reason="approval_policy_request",
                requested_by="support-test",
                requested_at=now - timedelta(minutes=10),
            )
        )
        await session.flush()
        await session.commit()

    response = await test_client.get("/api/web/support/command-center?scope=team", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()

    assert payload["status"] == "success"
    data = payload["data"]
    assert data["scope"] == "team"
    assert data["generated_at"]
    assert {section["key"] for section in data["sections"]} == {
        "new_unassigned",
        "operator_action",
        "unread_user_messages",
        "sla_risk",
        "ola_risk",
        "pending_approval",
        "pending_consent",
        "failed_operation",
        "agent_offline_active",
        "diagnostics_recommended",
        "closure_blocked",
        "similar_tickets_spike",
    }
    summary = data["summary"]
    assert summary["new_unassigned_count"] == 1
    assert summary["operator_action_count"] >= 2
    assert summary["pending_approval_count"] == 1
    assert summary["sla_risk_count"] == 1
    new_section = next(section for section in data["sections"] if section["key"] == "new_unassigned")
    assert new_section["title"] == "Новые без владельца"
    assert new_section["items"][0]["href"] == f"/app/tickets/{unassigned_ticket_id}"
    assert new_section["items"][0]["service_code"] == "workplace"
    approval_section = next(section for section in data["sections"] if section["key"] == "pending_approval")
    assert approval_section["items"][0]["reason"] == "Ожидается согласование от owner-1"


@pytest.mark.asyncio
async def test_operator_command_center_aggregates_operations_agent_diagnostics_closure_and_spikes(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code=f"cmd_sig_{uuid.uuid4().hex[:8]}", name="Command signals", members=["support-test"])
        failed_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="cmd-device-failed",
            title="Printer spooler failed",
            description="Operation failed",
            status="in_progress",
            requester_id="requester-failed",
            queue_id=queue.id,
            assignee_id="support-test",
            priority="P1",
            evidence_required=True,
        )
        consent_ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id="cmd-device-consent",
            title="Remote assist consent",
            description="Waiting consent",
            status="queued",
            requester_id="requester-consent",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        similar_tickets = [
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=f"cmd-device-spike-{index}",
                title="VPN client error 720",
                description="Similar incident",
                status="queued",
                requester_id=f"requester-spike-{index}",
                queue_id=queue.id,
                service_code="network",
                updated_at=now - timedelta(minutes=index),
            )
            for index in range(3)
        ]
        session.add_all([failed_ticket, consent_ticket, *similar_tickets])
        await session.flush()
        session.add_all([
            Device(
                device_id="cmd-device-failed",
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                last_seen_at=now - timedelta(hours=1),
                last_handshake_at=now - timedelta(hours=1),
            ),
            Device(
                device_id="cmd-device-consent",
                protocol_version="ws_ticket_v3",
                agent_version="1.0.0",
                last_seen_at=now,
                last_handshake_at=now,
            ),
        ])
        session.add_all([
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=failed_ticket.device_id,
                ticket_id=failed_ticket.ticket_id,
                kind="tool",
                tool_name="printer.diagnostics",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="failed",
                queued_at=now - timedelta(minutes=4),
                finished_at=now - timedelta(minutes=3),
                error_message="Spooler service unavailable",
            ),
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=consent_ticket.device_id,
                ticket_id=consent_ticket.ticket_id,
                kind="tool",
                tool_name="remote.assist",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="waiting_consent",
                queued_at=now - timedelta(minutes=2),
            ),
        ])
        session.add(
            DiagnosticSession(
                id=str(uuid.uuid4()),
                ticket_id=failed_ticket.ticket_id,
                profile_id="printer",
                status="failed",
                trigger_source="policy",
                started_by_user_id="support-test",
                started_at=now - timedelta(minutes=6),
                finished_at=now - timedelta(minutes=5),
                summary="Printer diagnostics failed",
            )
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/support/command-center?scope=all&limit_per_section=5&window_hours=24",
        headers=_admin_headers(),
    )
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    summary = data["summary"]

    assert summary["failed_operation_count"] == 1
    assert summary["pending_consent_count"] == 1
    assert summary["agent_offline_active_count"] == 1
    assert summary["diagnostics_recommended_count"] == 1
    assert summary["closure_blocked_count"] == 1
    assert summary["similar_spikes_count"] == 1
    failed_section = next(section for section in data["sections"] if section["key"] == "failed_operation")
    assert failed_section["items"][0]["operation"]["error_summary"] == "Spooler service unavailable"
    diagnostics_section = next(section for section in data["sections"] if section["key"] == "diagnostics_recommended")
    assert diagnostics_section["items"][0]["diagnostics"]["profile_code"] == "printer"
    spike_section = next(section for section in data["sections"] if section["key"] == "similar_tickets_spike")
    assert spike_section["items"][0]["similar_group"]["count"] == 3
    assert spike_section["items"][0]["href"].startswith("/app/tickets?search=")


@pytest.mark.asyncio
async def test_operator_command_center_excludes_closed_from_unassigned_and_spikes(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True))
        queue = await _seed_queue(session, code=f"cmd_closed_{uuid.uuid4().hex[:8]}", name="Command closed", members=["support-test"])
        session.add(
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id="cmd-device-closed",
                title="Closed VPN client error 720",
                description="Closed ticket must not count",
                status="closed",
                requester_id="requester-closed",
                queue_id=queue.id,
                service_code="network",
                updated_at=now,
            )
        )
        await session.commit()

    response = await test_client.get("/api/web/support/command-center?scope=team", headers=_support_headers())
    assert response.status == 200, await response.text()
    data = (await response.json())["data"]
    assert data["summary"]["new_unassigned_count"] == 0
    assert data["summary"]["similar_spikes_count"] == 0
