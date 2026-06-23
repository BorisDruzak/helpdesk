from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Change, Problem, ProblemActivityEvent
from change.change_service import ChangeService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_problem_to_change_records_problem_activity_without_auto_closing_problem(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    problem_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(
            Problem(
                problem_id=problem_id,
                problem_key="PRB-900002",
                title="Mail outage",
                description="Mail repeats",
                status="permanent_fix_planned",
                severity="high",
                priority="high",
                impact="high",
                urgency="high",
                source_kind="manual",
                service_code="mail",
                offering_code="mail.mailbox_issue",
                permanent_fix_summary="Patch mail routing",
            )
        )
        await session.commit()
        change = await ChangeService(session).create_from_problem(problem_id, actor_id="support-1")
        await ChangeService(session).force_status(change["change_id"], "closed", actor_id="system")
        await session.commit()

        problem = await session.get(Problem, problem_id)
        changes = (await session.execute(select(Change).where(Change.problem_id == problem_id))).scalars().all()
        events = (await session.execute(select(ProblemActivityEvent).where(ProblemActivityEvent.problem_id == problem_id))).scalars().all()

    assert problem is not None
    assert problem.status == "permanent_fix_planned"
    assert changes[0].change_id == change["change_id"]
    assert any(event.event_type == "change_created" for event in events)

