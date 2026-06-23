from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ProblemCandidate, Ticket, TicketReopenEvent
from problem.candidate_service import ProblemCandidateService

pytestmark = pytest.mark.db_cleanup("full")


async def _seed_reopen_pattern(session, now: datetime) -> None:
    for _ in range(2):
        ticket_id = str(uuid.uuid4())
        session.add(Ticket(ticket_id=ticket_id, device_id=f"dev-{ticket_id[:8]}", title="VPN", description="VPN", status="closed", requester_id="requester", service_code="network", offering_code="network.vpn", closed_at=now))
        session.add(TicketReopenEvent(reopen_id=str(uuid.uuid4()), ticket_id=ticket_id, previous_status="closed", new_status="in_progress", reason_code="problem_returned", service_code="network", offering_code="network.vpn", created_at=now))


@pytest.mark.asyncio
async def test_dismissed_candidate_cooldown_prevents_recreation(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        await _seed_reopen_pattern(session, now)
        await session.commit()
        first = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        row = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.signal_type == "reopen_pattern"))).scalar_one()
        row.status = "dismissed"
        row.dismissed_until = now + timedelta(days=14)
        await session.commit()

        second = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        rows = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.fingerprint == row.fingerprint))).scalars().all()

    assert first["created"] == 1
    assert second["created"] == 0
    assert second["skipped"] == 1
    assert len(rows) == 1
    assert rows[0].status == "dismissed"


@pytest.mark.asyncio
async def test_converted_candidate_is_not_duplicated_by_scan(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        await _seed_reopen_pattern(session, now)
        await session.commit()
        await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        row = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.signal_type == "reopen_pattern"))).scalar_one()
        row.status = "converted"
        await session.commit()

        result = await ProblemCandidateService(session).scan(actor_id="support-1", now=now)
        rows = (await session.execute(select(ProblemCandidate).where(ProblemCandidate.fingerprint == row.fingerprint))).scalars().all()

    assert result["created"] == 0
    assert result["skipped"] == 1
    assert len(rows) == 1
