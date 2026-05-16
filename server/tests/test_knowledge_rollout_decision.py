from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

import pytest

from knowledge.operations_service import KnowledgeOperationsService


@pytest.mark.asyncio
async def test_effective_rollout_order_template_beats_offering_service_global(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ops = KnowledgeOperationsService(session)
        await ops.upsert_rollout_policy({"surface": "requester_portal", "enabled": False, "reason": "global"}, actor_id="admin")
        await ops.upsert_rollout_policy(
            {"surface": "requester_portal", "service_code": "network", "enabled": True, "reason": "service"},
            actor_id="admin",
        )
        await ops.upsert_rollout_policy(
            {
                "surface": "requester_portal",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "enabled": False,
                "reason": "offering",
            },
            actor_id="admin",
        )
        await ops.upsert_rollout_policy(
            {
                "surface": "requester_portal",
                "request_template_key": "network",
                "enabled": True,
                "reason": "template",
            },
            actor_id="admin",
        )
        decision = await ops.rollout_decision(
            {
                "surface": "requester_portal",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "request_template_key": "network",
            },
            actor_role="requester",
        )

    assert decision["enabled"] is True
    assert decision["scope_type"] == "template"
    assert decision["reason"] == "template"


@pytest.mark.asyncio
async def test_surface_specific_policy_beats_global_all_surface(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ops = KnowledgeOperationsService(session)
        await ops.upsert_rollout_policy({"surface": "all", "enabled": False, "reason": "all"}, actor_id="admin")
        await ops.upsert_rollout_policy({"surface": "agent_gui", "enabled": True, "reason": "agent"}, actor_id="admin")
        decision = await ops.rollout_decision({"surface": "agent_gui"}, actor_role="agent")

    assert decision["enabled"] is True
    assert decision["surface"] == "agent_gui"
    assert decision["reason"] == "agent"


@pytest.mark.asyncio
async def test_rollout_percent_is_deterministic(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    context = {"surface": "requester_portal", "session_id": "stable-session", "service_code": "network"}
    async with session_maker() as session:
        ops = KnowledgeOperationsService(session)
        await ops.upsert_rollout_policy({"surface": "requester_portal", "rollout_percent": 10}, actor_id="admin")
        first = await ops.rollout_decision(context, actor_role="requester")
        second = await ops.rollout_decision(dict(context), actor_role="requester")

    assert first["rollout_bucket"] == second["rollout_bucket"]
    assert first["enabled"] == second["enabled"]
    if first["rollout_bucket"] > 10:
        assert first["reason"] == "rollout_bucket_disabled"


@pytest.mark.asyncio
async def test_urgency_bypass_marks_submit_as_unblocked(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        ops = KnowledgeOperationsService(session)
        await ops.upsert_rollout_policy(
            {
                "surface": "requester_portal",
                "require_suggestions_before_submit": True,
                "allow_skip": False,
                "urgency_bypass": True,
            },
            actor_id="admin",
        )
        decision = await ops.rollout_decision({"surface": "requester_portal", "urgency": "high"}, actor_role="requester")

    assert decision["bypass_applied"] is True
    assert decision["bypass_reason"] == "urgency"
    assert decision["require_suggestions_before_submit"] is False
    assert decision["allow_skip"] is True


@pytest.mark.asyncio
async def test_no_policy_defaults_allow_submit(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        decision = await KnowledgeOperationsService(session).rollout_decision({"surface": "api"}, actor_role="requester")

    assert decision["enabled"] is True
    assert decision["scope_type"] == "default"
    assert decision["no_suggestions_behavior"] == "allow_submit"
    assert decision["api_unavailable_behavior"] == "allow_submit"
