from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import KnowledgeGapFinding, ProblemCandidate, Ticket
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_knowledge_gap_plus_repeated_tickets_creates_candidate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        finding_id = str(uuid.uuid4())
        session.add(
            KnowledgeGapFinding(
                finding_id=finding_id,
                service_code="finance",
                offering_code="finance.invoice",
                gap_type="high_volume_no_kb",
                severity="high",
                status="open",
                evidence_json={"requester_id": "must-not-leak", "ticket_count": 3},
                evidence_hash="gap-hash",
                created_at=now,
            )
        )
        for _ in range(3):
            ticket_id = str(uuid.uuid4())
            session.add(
                Ticket(
                    ticket_id=ticket_id,
                    device_id=f"dev-{ticket_id[:8]}",
                    title="Invoice upload fails",
                    description="No useful article exists",
                    status="closed",
                    requester_id="requester-hidden",
                    service_code="finance",
                    offering_code="finance.invoice",
                    request_type="incident",
                    created_at=now,
                    closed_at=now,
                )
            )
        await session.commit()

        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate))).scalars().all()

    assert result["created"] >= 1
    candidate = next(row for row in rows if row.signal_type == "knowledge_gap_pattern")
    assert candidate.ticket_count == 3
    assert candidate.failed_kb_count >= 1
    assert candidate.evidence_json["gap_finding_ids"] == [finding_id]
    assert "must-not-leak" not in repr(candidate.evidence_json)
