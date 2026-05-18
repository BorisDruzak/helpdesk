from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from change.change_service import ChangeService
from change.task_service import ChangeTaskService


@pytest.mark.asyncio
async def test_change_tasks_must_complete_before_implemented(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        change = await ChangeService(session).create_change(
            {"title": "App patch", "description": "Patch app", "change_type": "standard"},
            actor_id="support-1",
        )
        task = await ChangeTaskService(session).create_task(
            change["change_id"],
            {"title": "Deploy patch", "task_type": "implementation"},
            actor_id="support-1",
        )
        await ChangeService(session).force_status(change["change_id"], "implementation_in_progress", actor_id="system")
        with pytest.raises(ValueError, match="tasks"):
            await ChangeService(session).transition_change(change["change_id"], "implemented", {}, actor_id="support-1")
        await ChangeTaskService(session).complete_task(change["change_id"], task["task_id"], actor_id="support-1", result_notes="Done")
        implemented = await ChangeService(session).transition_change(change["change_id"], "implemented", {"override": True}, actor_id="support-1")
        await session.commit()

    assert implemented["status"] in {"implemented", "pir_required"}
