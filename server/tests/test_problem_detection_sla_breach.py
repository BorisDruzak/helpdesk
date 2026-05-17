from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemCandidate, Ticket
from problem.candidate_service import ProblemCandidateService


def _ticket(ticket_id: str, now: datetime, *, breach: str) -> Ticket:
    breached_at = now - timedelta(hours=1)
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"device-{ticket_id[:8]}",
        title="Payroll outage",
        description="Payroll request failed",
        status="closed",
        requester_id=f"requester-{ticket_id[:6]}",
        service_code="hr",
        offering_code="hr.payroll",
        request_type="incident",
        created_at=now - timedelta(hours=2),
        closed_at=now,
        first_response_breached_at=breached_at if breach == "first_response" else None,
        resolution_breached_at=breached_at if breach == "resolution" else None,
    )


@pytest.mark.asyncio
async def test_sla_breach_pattern_scan_creates_candidate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for idx, breach in enumerate(["first_response", "resolution", "resolution"]):
            session.add(_ticket(str(uuid.uuid4()), now, breach=breach))
        await session.commit()

        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.commit()
        rows = (await session.execute(select(ProblemCandidate))).scalars().all()

    assert result["created"] >= 1
    candidate = next(row for row in rows if row.signal_type == "sla_breach_pattern")
    assert candidate.service_code == "hr"
    assert candidate.offering_code == "hr.payroll"
    assert candidate.sla_breach_count == 3
    assert candidate.ticket_count == 3
    assert candidate.evidence_json["breach_type_counts"]["resolution"] == 2
    assert "requester-" not in repr(candidate.evidence_json)
