from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeFeedbackEvent, KnowledgeItem, KnowledgeSpace, ProblemCandidate, Ticket
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_failed_kb_ticket_after_knowledge_pattern_creates_candidate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    space_id = str(uuid.uuid4())
    item_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            KnowledgeSpace(
                space_id=space_id,
                code="p41-kb",
                title="P4.1 KB",
                lifecycle_status="active",
                visibility="support_internal",
            )
        )
        await session.commit()
        session.add(
            KnowledgeItem(
                item_id=item_id,
                space_id=space_id,
                slug="printer-failed-article",
                item_type="article",
                title="Printer failed article",
                status="published",
                visibility="support_internal",
            )
        )
        await session.commit()
        for event_type in ["not_helpful", "ticket_created_after_view"]:
            ticket_id = str(uuid.uuid4())
            session.add(
                Ticket(
                    ticket_id=ticket_id,
                    device_id=f"dev-{ticket_id[:8]}",
                    title="Printer article failed",
                    description="Requester still created ticket",
                    status="closed",
                    requester_id="requester-hidden",
                    service_code="workplace",
                    offering_code="workplace.printer",
                    request_type="incident",
                    closed_at=now,
                )
            )
            await session.commit()
            session.add(
                KnowledgeFeedbackEvent(
                    event_id=str(uuid.uuid4()),
                    item_id=item_id,
                    actor_id="requester-hidden",
                    actor_role="requester",
                    ticket_id=ticket_id,
                    service_code="workplace",
                    offering_code="workplace.printer",
                    event_type=event_type,
                    result="failed",
                    created_at=now,
                    metadata_json={"comment": "raw requester KB comment"},
                )
            )
        await session.commit()

        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate))).scalars().all()

    assert result["created"] >= 1
    candidate = next(row for row in rows if row.signal_type == "failed_kb_pattern")
    assert candidate.failed_kb_count == 2
    assert candidate.evidence_json["knowledge_item_ids"] == [item_id]
    assert candidate.evidence_json["event_type_counts"]["ticket_created_after_view"] == 1
    assert "requester-hidden" not in repr(candidate.evidence_json)
    assert "raw requester KB comment" not in repr(candidate.evidence_json)
