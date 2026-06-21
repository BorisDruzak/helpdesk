from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Artifact, ObserverTrace, Operation, Ticket, TicketApproval, TicketEvent, TicketEvidenceItem, TicketWorklog
from tickets.evidence_service import TicketEvidenceService


pytestmark = pytest.mark.db_cleanup("tickets")

@pytest.mark.asyncio
async def test_evidence_service_collects_ticket_scoped_operation_and_artifact_candidates(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Need diagnostics",
                description="Collect proof",
                status="in_progress",
                requester_id="user-evidence",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="network.ping",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="Host reachable",
            )
        )
        session.add(
            Operation(
                operation_id=str(uuid.uuid4()),
                device_id=device_id,
                ticket_id=None,
                kind="tool",
                tool_name="device.old",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="Unrelated device-wide run",
            )
        )
        session.add(
            Artifact(
                artifact_id=artifact_id,
                storage_path="tickets/evidence/screenshot.png",
                original_name="screenshot.png",
                mime_type="image/png",
                size_bytes=1234,
                sha256="a" * 64,
                kind="screenshot",
                device_id=device_id,
                ticket_id=ticket_id,
            )
        )
        await session.flush()

        candidates = await TicketEvidenceService(session).collect_candidates(ticket_id)

    by_source = {(item["source_kind"], item["source_id"]): item for item in candidates}
    assert ("operation", operation_id) in by_source
    assert ("artifact", artifact_id) in by_source
    assert all(item["summary"] != "Unrelated device-wide run" for item in candidates)
    assert by_source[("operation", operation_id)]["source_quality"] == "ticket"
    assert by_source[("artifact", artifact_id)]["evidence_type"] == "screenshot"


@pytest.mark.asyncio
async def test_evidence_service_links_candidate_idempotently(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    operation_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Need diagnostics",
                description="Collect proof",
                status="in_progress",
                requester_id="user-evidence",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            Operation(
                operation_id=operation_id,
                device_id=device_id,
                ticket_id=ticket_id,
                kind="tool",
                tool_name="system.collect",
                actor_role="support",
                trace_id=str(uuid.uuid4()),
                status="succeeded",
                queued_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                result_summary="System facts collected",
            )
        )
        await session.flush()

        service = TicketEvidenceService(session)
        first = await service.link_source(
            ticket_id,
            source_kind="operation",
            source_id=operation_id,
            required_fact="automated_checks",
            actor_id="op1",
        )
        second = await service.link_source(
            ticket_id,
            source_kind="operation",
            source_id=operation_id,
            required_fact="automated_checks",
            actor_id="op1",
        )
        count = await session.scalar(
            select(func.count(TicketEvidenceItem.id)).where(TicketEvidenceItem.ticket_id == ticket_id)
        )

        assert first.id == second.id
        assert count == 1
        assert first.source_kind == "operation"
        assert first.source_id == operation_id
        assert first.required_fact == "automated_checks"
        assert first.verification_status == "accepted"


@pytest.mark.asyncio
async def test_evidence_service_collects_worklog_approval_chat_and_observer_candidates(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=device_id,
                title="Need broader evidence",
                description="Collect proof from all backend sources",
                status="in_progress",
                requester_id="user-evidence",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        session.add(
            TicketWorklog(
                ticket_id=ticket_id,
                actor_id="op1",
                spent_minutes=15,
                note="Checked printer queue and restarted spooler.",
            )
        )
        session.add(
            TicketApproval(
                ticket_id=ticket_id,
                approval_type="manager",
                approver_id="manager1",
                status="approved",
                reason="Approved remote diagnostic.",
                requested_by="op1",
                decided_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            TicketEvent(
                ticket_id=ticket_id,
                device_id=device_id,
                agent_seq=None,
                event_type="chat_message",
                payload={
                    "message_id": "msg-support-1",
                    "text": "Проблема устранена, сервис доступен.",
                    "sender_role": "support",
                    "visibility": "public",
                },
            )
        )
        session.add(
            ObserverTrace(
                trace_id=trace_id,
                root_kind="playbook_run",
                ticket_id=ticket_id,
                device_id=device_id,
                operation_id=None,
                status="failed",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
                duration_ms=1200,
                span_count=3,
                error_count=1,
                attrs_json={"signature": "MODULE_NOT_ON_SERVER", "summary": "Tool missing on server"},
            )
        )
        await session.flush()

        candidates = await TicketEvidenceService(session).collect_candidates(ticket_id)

    by_kind = {item["source_kind"]: item for item in candidates}
    assert by_kind["worklog"]["evidence_type"] == "worklog"
    assert by_kind["worklog"]["required_fact"] == "operator_checks"
    assert "spooler" in by_kind["worklog"]["summary"]
    assert by_kind["approval"]["evidence_type"] == "approval"
    assert by_kind["approval"]["required_fact"] == "approvals"
    assert by_kind["chat_message"]["evidence_type"] == "chat_message"
    assert by_kind["chat_message"]["required_fact"] == "changes_made"
    assert by_kind["observer_trace"]["source_id"] == trace_id
    assert by_kind["observer_trace"]["required_fact"] == "automated_checks"


@pytest.mark.asyncio
async def test_evidence_service_updates_verification_status_and_archive(test_engine):
    session_maker = async_sessionmaker(test_engine)
    ticket_id = str(uuid.uuid4())

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id=str(uuid.uuid4()),
                title="Need verification",
                description="Evidence status update",
                status="in_progress",
                requester_id="user-evidence",
                requester_status="in_work",
                next_action_owner="support",
            )
        )
        item = TicketEvidenceItem(
            ticket_id=ticket_id,
            evidence_type="manual_note",
            source_kind="manual",
            source_id="note-1",
            required_fact="evidence",
            section_key="evidence",
            source_ref="manual:note-1",
            title="Manual note",
            summary="Initial proof",
            visibility="internal",
            verification_status="accepted",
            created_by="op1",
        )
        session.add(item)
        await session.flush()

        updated = await TicketEvidenceService(session).update_evidence(
            ticket_id,
            item.id,
            verification_status="rejected",
            actor_id="op2",
            reason="Not enough detail",
            export_visibility="hidden",
        )

        assert updated.verification_status == "rejected"
        assert updated.verified_by == "op2"
        assert updated.verified_at is not None
        assert updated.export_visibility == "hidden"
        assert updated.metadata_json["verification_reason"] == "Not enough detail"
