from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import func, select

from app.db.engine import async_sessionmaker
from app.db.models import Artifact, Operation, Ticket, TicketEvidenceItem
from tickets.evidence_service import TicketEvidenceService


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
