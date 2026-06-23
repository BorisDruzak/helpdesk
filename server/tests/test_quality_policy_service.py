from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from quality.policy_service import QualityPolicyService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_quality_policy_default_and_service_override(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = QualityPolicyService(session)
        default = await service.effective_policy(service_code="network", offering_code="network.vpn_issue", queue_id=None)
        assert default["low_csat_threshold"] == 3
        assert default["reopen_review_enabled"] is True

        saved = await service.save_policy(
            {
                "scope_type": "service",
                "service_code": "network",
                "enabled": True,
                "low_csat_threshold": 4,
                "random_sample_percent": 0,
                "qa_due_hours": 24,
            },
            actor_id="admin",
        )
        effective = await service.effective_policy(service_code="network", offering_code="network.vpn_issue", queue_id=None)
        await session.commit()

    assert saved["policy_id"]
    assert effective["low_csat_threshold"] == 4
    assert effective["qa_due_hours"] == 24


@pytest.mark.asyncio
async def test_quality_policy_offering_override_wins_and_preview_explains_scope(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = QualityPolicyService(session)
        await service.save_policy(
            {
                "scope_type": "service",
                "service_code": "network",
                "enabled": True,
                "low_csat_threshold": 4,
                "qa_due_hours": 48,
            },
            actor_id="admin",
        )
        saved_offering = await service.save_policy(
            {
                "scope_type": "offering",
                "service_code": "network",
                "offering_code": "network.vpn_issue",
                "enabled": True,
                "low_csat_threshold": 2,
                "qa_due_hours": 12,
            },
            actor_id="admin",
        )
        effective = await service.effective_policy(service_code="network", offering_code="network.vpn_issue", queue_id=None)
        await session.commit()

    assert effective["policy_id"] == saved_offering["policy_id"]
    assert effective["scope_type"] == "offering"
    assert effective["service_code"] == "network"
    assert effective["offering_code"] == "network.vpn_issue"
    assert effective["low_csat_threshold"] == 2
    assert effective["qa_due_hours"] == 12
