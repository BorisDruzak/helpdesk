from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import HelpdeskService, HelpdeskServiceOffering
from problem.problem_service import ProblemService


@pytest.mark.asyncio
async def test_problem_rejects_invalid_service_offering_when_catalog_exists(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        service_id = str(uuid.uuid4())
        session.add(HelpdeskService(service_id=service_id, code="network", name="Network", public_title="Network", lifecycle_status="published", visibility="public"))
        session.add(HelpdeskServiceOffering(offering_id=str(uuid.uuid4()), service_id=service_id, code="vpn_issue", full_code="network.vpn_issue", name="VPN", public_title="VPN", lifecycle_status="published", visibility="public"))
        await session.flush()
        with pytest.raises(ValueError, match="offering_code"):
            await ProblemService(session).create_problem({"title": "Bad", "description": "Bad", "service_code": "network", "offering_code": "network.bad"}, actor_id="support-1")
        good = await ProblemService(session).create_problem({"title": "Good", "description": "Good", "service_code": "network", "offering_code": "network.vpn_issue"}, actor_id="support-1")

    assert good["service_code"] == "network"
