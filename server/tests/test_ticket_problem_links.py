from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket
from problem.problem_service import ProblemService


@pytest.mark.asyncio
async def test_support_can_link_and_soft_unlink_ticket_problem(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="device-ticket-problem-link",
                title="VPN",
                description="VPN",
                status="closed",
                requester_id="requester-1",
                resolved_at=datetime.now(timezone.utc),
                closed_at=datetime.now(timezone.utc),
            )
        )
        problem = await ProblemService(session).create_problem(
            {"title": "Repeated VPN issue", "description": "Problem link test"},
            actor_id="support-1",
        )
        link = await ProblemService(session).link_ticket(problem["problem_id"], ticket_id, link_type="suspected", actor_id="support-1")
        listed = await ProblemService(session).list_ticket_problems(ticket_id)
        unlinked = await ProblemService(session).unlink_ticket(problem["problem_id"], ticket_id, actor_id="support-1")
        listed_after = await ProblemService(session).list_ticket_problems(ticket_id)
        await session.commit()

    assert link["link_type"] == "suspected"
    assert len(listed) == 1
    assert unlinked["unlinked"] is True
    assert listed_after == []
