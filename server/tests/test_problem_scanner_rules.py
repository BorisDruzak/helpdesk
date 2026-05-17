from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketReopenEvent
from problem.candidate_service import ProblemCandidateService


@pytest.mark.asyncio
async def test_reopen_pattern_scan_is_idempotent(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for _ in range(2):
            ticket_id = str(uuid.uuid4())
            session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn_issue", resolved_at=now, closed_at=now))
            session.add(TicketReopenEvent(reopen_id=str(uuid.uuid4()), ticket_id=ticket_id, previous_status="closed", new_status="in_progress", reason_code="problem_returned", service_code="network", offering_code="network.vpn_issue", created_at=now))
        await session.commit()
        first = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        second = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)

    assert first["created"] >= 1
    assert second["created"] == 0
