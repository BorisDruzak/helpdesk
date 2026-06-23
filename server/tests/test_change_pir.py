from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.change_service import ChangeService
from change.pir_service import PIRService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_pir_approval_allows_change_closure(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {"title": "VPN fix", "description": "Implement VPN fix", "change_type": "normal"},
            actor_id="support-1",
        )
        await ChangeService(session).force_status(change["change_id"], "pir_required", actor_id="system")
        pir = await PIRService(session).create_pir(
            change["change_id"],
            {"implementation_successful": True, "met_objectives": True, "lessons_learned": "No regressions"},
            actor_id="support-1",
        )
        await PIRService(session).submit_pir(change["change_id"], pir["pir_id"], actor_id="support-1")
        await PIRService(session).approve_pir(change["change_id"], pir["pir_id"], actor_id="manager-1")
        closed = await ChangeService(session).transition_change(
            change["change_id"],
            "closed",
            {"closure_summary": "PIR approved and objectives met."},
            actor_id="support-1",
        )
        await session.commit()

    assert closed["status"] == "closed"

