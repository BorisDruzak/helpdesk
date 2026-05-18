from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
import pytest

from app.db.models import ContinuousImprovementAction
from change.change_service import ChangeService
from quality.improvement_service import ContinuousImprovementService


@pytest.mark.asyncio
async def test_change_can_be_created_from_improvement_action(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        action = await ContinuousImprovementService(session).create_action(
            {
                "source_kind": "problem",
                "action_type": "create_change_candidate",
                "title": "Implement permanent VPN fix",
                "description": "Move permanent fix through change governance",
                "priority": "high",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
            },
            actor_id="support-1",
        )
        change = await ChangeService(session).create_from_improvement_action(action["action_id"], actor_id="support-1")
        await session.commit()
        linked_action = await session.get(ContinuousImprovementAction, action["action_id"])

    assert change["source_kind"] == "improvement_action"
    assert change["improvement_action_id"] == action["action_id"]
    assert change["service_code"] == "network"
    assert linked_action is not None
    assert linked_action.change_id == change["change_id"]


@pytest.mark.asyncio
async def test_failed_change_creates_improvement_action(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {
                "title": "Risky VPN update",
                "description": "Change failed during validation",
                "risk_level": "high",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
            },
            actor_id="support-1",
        )
        await ChangeService(session).force_status(change["change_id"], "implementation_in_progress", actor_id="support-1")
        await ChangeService(session).transition_change(change["change_id"], "failed", {}, actor_id="support-1")
        await session.commit()
        actions = (await session.execute(select(ContinuousImprovementAction))).scalars().all()

    assert len(actions) == 1
    assert actions[0].source_kind == "change"
    assert actions[0].change_id == change["change_id"]
    assert actions[0].action_type == "process_review"
    assert "requester" not in repr(actions[0].metadata_json)
