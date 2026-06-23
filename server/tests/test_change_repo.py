from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Problem
from app.repos.change_repo import ChangeRepo
from change.change_service import ChangeService

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_change_repo_get_by_key_and_problem(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Problem(
                problem_id="problem-1",
                problem_key="PRB-910001",
                title="Repo linked problem",
                description="Repo linked problem",
                status="permanent_fix_planned",
                severity="medium",
                priority="medium",
                impact="medium",
                urgency="medium",
                source_kind="manual",
            )
        )
        await session.flush()
        change = await ChangeService(session).create_change(
            {
                "title": "Repository-visible change",
                "description": "Change repo lookup",
                "problem_id": "problem-1",
            },
            actor_id="support-1",
        )
        await session.commit()

        repo = ChangeRepo(session)
        by_id = await repo.get(change["change_id"])
        by_key = await repo.get_by_key(change["change_key"])
        by_problem = await repo.list_by_problem("problem-1")

    assert by_id is not None
    assert by_key is not None
    assert by_id.change_key == change["change_key"]
    assert [row.change_id for row in by_problem] == [change["change_id"]]
