from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ContinuousImprovementAction, Problem, ProblemActivityEvent, ProblemTicketLink, Ticket
from problem.problem_service import ProblemService

pytestmark = pytest.mark.db_cleanup("full")


def _ticket(ticket_id: str, *, service_code: str = "network", offering_code: str = "network.vpn_issue") -> Ticket:
    return Ticket(
        ticket_id=ticket_id,
        device_id=f"device-{ticket_id[:8]}",
        title="VPN repeats",
        description="VPN disconnects repeatedly",
        status="closed",
        requester_id="requester-1",
        service_code=service_code,
        offering_code=offering_code,
        request_type="incident",
        reporting_category="network",
        resolved_at=datetime.now(timezone.utc),
        closed_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_problem_lifecycle_ticket_link_and_improvement_action(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_ticket(ticket_id))
        await session.commit()

        service = ProblemService(session)
        problem = await service.create_problem(
            {
                "title": "Repeated VPN outage",
                "description": "Multiple VPN incidents point to one service defect.",
                "severity": "high",
                "priority": "high",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "source_kind": "reopen_pattern",
            },
            actor_id="support-1",
        )
        linked = await service.link_ticket(
            problem["problem_id"],
            ticket_id,
            link_type="confirmed",
            evidence_summary="Same VPN error code",
            actor_id="support-1",
        )
        await service.transition_problem(problem["problem_id"], "investigating", {}, actor_id="support-1")
        await service.transition_problem(
            problem["problem_id"],
            "known_error",
            {"root_cause_summary": "Expired VPN gateway route"},
            actor_id="support-1",
        )
        await service.transition_problem(
            problem["problem_id"],
            "workaround_available",
            {"workaround_summary": "Use backup VPN profile"},
            actor_id="support-1",
        )
        await service.transition_problem(
            problem["problem_id"],
            "resolved",
            {
                "root_cause_summary": "Expired VPN gateway route",
                "permanent_fix_summary": "Gateway route refreshed and monitoring added",
            },
            actor_id="support-1",
        )
        action = await service.create_improvement_action(
            problem["problem_id"],
            action_type="perform_rca",
            title="Document VPN RCA",
            actor_id="support-1",
        )
        await session.commit()

        row = await session.get(Problem, problem["problem_id"])
        link_row = await session.get(ProblemTicketLink, linked["link_id"])
        action_row = await session.get(ContinuousImprovementAction, action["action_id"])
        activity = (await session.execute(select(ProblemActivityEvent))).scalars().all()

    assert row is not None
    assert row.problem_key.startswith("PRB-")
    assert row.status == "resolved"
    assert row.root_cause_summary == "Expired VPN gateway route"
    assert row.permanent_fix_summary == "Gateway route refreshed and monitoring added"
    assert link_row is not None
    assert link_row.link_type == "confirmed"
    assert action_row is not None
    assert action_row.source_kind == "problem"
    assert action_row.problem_id == problem["problem_id"]
    assert any(item.event_type == "status_changed" for item in activity)


@pytest.mark.asyncio
async def test_problem_resolution_requires_root_cause_and_fix(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem = await ProblemService(session).create_problem(
            {"title": "Mail outage pattern", "description": "Repeated mail incidents"},
            actor_id="support-1",
        )
        await ProblemService(session).transition_problem(problem["problem_id"], "investigating", {}, actor_id="support-1")
        with pytest.raises(ValueError, match="root cause"):
            await ProblemService(session).transition_problem(
                problem["problem_id"],
                "resolved",
                {"permanent_fix_summary": "Restarted service"},
                actor_id="support-1",
            )
