from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.policy_service import ChangePolicyService


@pytest.mark.asyncio
async def test_change_policy_effective_preview_prefers_risk_over_global(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service = ChangePolicyService(session)
        await service.save_policy(
            {
                "code": "global-default",
                "title": "Global",
                "scope_type": "global",
                "approval_mode": "single",
                "require_pir": True,
            },
            actor_id="admin-1",
        )
        await service.save_policy(
            {
                "code": "critical-cab",
                "title": "Critical CAB",
                "scope_type": "risk_level",
                "risk_level": "critical",
                "approval_mode": "cab",
                "approver_roles": ["change_manager"],
            },
            actor_id="admin-1",
        )
        preview = await service.effective_policy({"risk_level": "critical", "change_type": "normal"})
        await session.commit()

    assert preview["approval_mode"] == "cab"
    assert preview["approver_roles"] == ["change_manager"]

