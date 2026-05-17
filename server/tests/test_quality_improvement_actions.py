from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ContinuousImprovementAction
from quality.improvement_service import ContinuousImprovementService


@pytest.mark.asyncio
async def test_improvement_action_lifecycle_requires_owner_and_outcome(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ContinuousImprovementService(session)
        action = await service.create_action(
            {
                "source_kind": "csat",
                "action_type": "update_kb_article",
                "title": "Update VPN article",
                "description": "Low CSAT says VPN article did not help",
                "priority": "high",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
            },
            actor_id="qa-lead",
        )

        with pytest.raises(ValueError, match="owner"):
            await service.update_action(action["action_id"], {"status": "assigned"}, actor_id="qa-lead")

        assigned = await service.update_action(
            action["action_id"],
            {"status": "assigned", "owner_actor_id": "knowledge-owner"},
            actor_id="qa-lead",
        )

        with pytest.raises(ValueError, match="outcome"):
            await service.close_action(action["action_id"], outcome_notes="", actor_id="knowledge-owner")

        closed = await service.close_action(
            action["action_id"],
            outcome_notes="Published a corrected VPN troubleshooting article.",
            actor_id="knowledge-owner",
        )
        await session.commit()

        row = await session.get(ContinuousImprovementAction, action["action_id"])

    assert assigned["status"] == "assigned"
    assert closed["status"] == "done"
    assert row.owner_actor_id == "knowledge-owner"
    assert row.outcome_notes.startswith("Published")
