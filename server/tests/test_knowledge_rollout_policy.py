from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from knowledge.operations_service import KnowledgeOperationsService


@pytest.mark.asyncio
async def test_old_rollout_payload_gets_production_defaults(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        policy = await KnowledgeOperationsService(session).upsert_rollout_policy(
            {"surface": "requester_portal", "enabled": True, "rollout_percent": 100},
            actor_id="admin-test",
        )
        await session.commit()

    assert policy["scope_type"] == "global"
    assert policy["show_before_form"] is True
    assert policy["require_suggestions_before_submit"] is False
    assert policy["allow_skip"] is True
    assert policy["max_suggestions"] == 5
    assert policy["no_suggestions_behavior"] == "allow_submit"
    assert policy["api_unavailable_behavior"] == "allow_submit"


@pytest.mark.asyncio
async def test_rollout_policy_validates_bounds(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        with pytest.raises(ValueError, match="max_suggestions"):
            await KnowledgeOperationsService(session).upsert_rollout_policy(
                {"surface": "requester_portal", "min_suggestions": 2, "max_suggestions": 1},
                actor_id="admin-test",
            )


@pytest.mark.asyncio
async def test_rollout_policy_supports_structured_fields(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        policy = await KnowledgeOperationsService(session).upsert_rollout_policy(
            {
                "scope_type": "offering",
                "surface": "agent_gui",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "rollout_percent": 50,
                "require_suggestions_before_submit": True,
                "allow_skip": False,
                "max_suggestions": 2,
                "show_known_errors": False,
                "no_suggestions_behavior": "show_message",
                "api_unavailable_behavior": "show_warning",
                "reason": "pilot",
            },
            actor_id="admin-test",
        )
        await session.commit()

    assert policy["scope_type"] == "offering"
    assert policy["surface"] == "agent_gui"
    assert policy["require_suggestions_before_submit"] is True
    assert policy["allow_skip"] is False
    assert policy["max_suggestions"] == 2
    assert policy["show_known_errors"] is False
    assert policy["api_unavailable_behavior"] == "show_warning"
