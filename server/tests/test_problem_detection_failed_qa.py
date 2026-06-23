from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemCandidate, Ticket, TicketQualityReview
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_failed_qa_review_pattern_scan_creates_candidate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for status in ["failed", "action_required"]:
            ticket_id = str(uuid.uuid4())
            session.add(
                Ticket(
                    ticket_id=ticket_id,
                    device_id=f"dev-{ticket_id[:8]}",
                    title="Evidence missing",
                    description="Closure evidence missing",
                    status="closed",
                    requester_id="requester-hidden",
                    service_code="network",
                    offering_code="network.vpn_issue",
                    request_type="incident",
                    closed_at=now,
                )
            )
            session.add(
                TicketQualityReview(
                    review_id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    review_type="missing_evidence",
                    severity="high",
                    status=status,
                    service_code="network",
                    offering_code="network.vpn_issue",
                    created_at=now,
                    review_notes="internal review note must not leak",
                )
            )
        await session.commit()

        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate))).scalars().all()

    assert result["created"] >= 1
    candidate = next(row for row in rows if row.signal_type == "qa_failed_pattern")
    assert candidate.ticket_count == 2
    assert candidate.evidence_json["review_type_counts"]["missing_evidence"] == 2
    assert "internal review note" not in repr(candidate.evidence_json)
