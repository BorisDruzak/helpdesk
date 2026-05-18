from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Change, ChangeActivityEvent, Problem, ProblemAffectedObject
from change.change_service import ChangeService


@pytest.mark.asyncio
async def test_create_change_and_create_from_problem_copies_context(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        problem_id = str(uuid.uuid4())
        session.add(
            Problem(
                problem_id=problem_id,
                problem_key="PRB-900001",
                title="VPN permanent fix",
                description="VPN keeps failing",
                status="permanent_fix_planned",
                severity="high",
                priority="high",
                impact="high",
                urgency="medium",
                source_kind="manual",
                service_code="network",
                offering_code="network.vpn_issue",
                permanent_fix_summary="Replace VPN gateway route",
                created_by="support-1",
                updated_by="support-1",
            )
        )
        session.add(
            ProblemAffectedObject(
                affected_id=str(uuid.uuid4()),
                problem_id=problem_id,
                object_type="catalog_offering",
                object_ref="network.vpn_issue",
                service_code="network",
                offering_code="network.vpn_issue",
                impact="high",
                created_by="support-1",
            )
        )
        await session.commit()

        manual = await ChangeService(session).create_change(
            {
                "title": "Manual firewall rule update",
                "description": "Adjust firewall policy",
                "change_type": "normal",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
            },
            actor_id="support-1",
        )
        from_problem = await ChangeService(session).create_from_problem(problem_id, actor_id="support-1")
        await session.commit()

        rows = (await session.execute(select(Change))).scalars().all()
        events = (await session.execute(select(ChangeActivityEvent))).scalars().all()

    assert manual["change_key"].startswith("CHG-")
    assert from_problem["problem_id"] == problem_id
    assert from_problem["source_kind"] == "problem"
    assert from_problem["service_code"] == "network"
    assert from_problem["affected_objects"][0]["object_ref"] == "network.vpn_issue"
    assert len(rows) == 2
    assert any(event.event_type == "linked_problem" for event in events)

