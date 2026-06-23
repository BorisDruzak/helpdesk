from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketFeedback
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_low_csat_quality_signal_feeds_problem_candidate(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for _ in range(2):
            ticket_id = str(uuid.uuid4())
            session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn_issue", resolved_at=now, closed_at=now))
            session.add(TicketFeedback(feedback_id=str(uuid.uuid4()), ticket_id=ticket_id, rating=2, sentiment="negative", problem_resolved=False, reason_codes=["not_resolved"], visibility="requester_visible", source_surface="requester_portal", service_code="network", offering_code="network.vpn_issue", submitted_at=now, is_latest=True))
        await session.commit()
        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)

    assert result["created"] >= 1
