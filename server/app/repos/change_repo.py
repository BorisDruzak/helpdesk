from __future__ import annotations

from sqlalchemy import select

from app.db.models import Change


class ChangeRepo:
    """Small repository facade for code that needs direct change lookups."""

    def __init__(self, session) -> None:
        self.session = session

    async def get(self, change_id: str) -> Change | None:
        return await self.session.get(Change, change_id)

    async def get_by_key(self, change_key: str) -> Change | None:
        return (await self.session.execute(select(Change).where(Change.change_key == change_key))).scalar_one_or_none()

    async def list_by_problem(self, problem_id: str) -> list[Change]:
        rows = await self.session.execute(select(Change).where(Change.problem_id == problem_id).order_by(Change.created_at.desc()))
        return list(rows.scalars().all())
