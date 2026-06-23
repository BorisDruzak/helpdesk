from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemCandidate, Ticket, TicketReopenEvent
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_repeated_scan_updates_existing_candidate_metadata(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for _ in range(2):
            ticket_id = str(uuid.uuid4())
            session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn", closed_at=now))
            session.add(TicketReopenEvent(reopen_id=str(uuid.uuid4()), ticket_id=ticket_id, previous_status="closed", new_status="in_progress", reason_code="problem_returned", service_code="network", offering_code="network.vpn", created_at=now))
        await session.commit()

        first = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        row = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.signal_type == "reopen_pattern"))).scalar_one()
        first_seen = row.first_seen_at
        first_fingerprint = row.fingerprint
        second = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        await session.refresh(row)

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["updated"] == 1
    assert row.fingerprint == first_fingerprint
    assert row.fingerprint_version >= 1
    assert row.first_seen_at == first_seen
    assert row.last_seen_at >= first_seen
    assert row.duplicate_count == 1
    assert row.evidence_hash
