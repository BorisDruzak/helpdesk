"""
Repository for agent_builds table operations.
"""
from __future__ import annotations

from typing import Optional, List

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.models import AgentBuild


class AgentBuildsRepo:
    """Repository for agent_builds table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_build(
        self,
        *,
        target: str,
        channel: str,
        version: str,
        sha256: str,
        size: int,
        storage_path: str,
        uploaded_by: str,
        notes: Optional[str] = None,
        artifact_filename: Optional[str] = None,
        archive_type: Optional[str] = None,
        mime_type: Optional[str] = None,
    ) -> AgentBuild:
        build = AgentBuild(
            target=target,
            channel=channel,
            version=version,
            sha256=sha256,
            size=size,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            notes=notes,
            artifact_filename=artifact_filename,
            archive_type=archive_type,
            mime_type=mime_type,
        )
        self.session.add(build)
        try:
            await self.session.flush()
            return build
        except IntegrityError:
            await self.session.rollback()
            raise

    async def get_build(
        self,
        *,
        target: str,
        channel: str,
        version: str,
    ) -> Optional[AgentBuild]:
        stmt = (
            select(AgentBuild)
            .where(AgentBuild.target == target)
            .where(AgentBuild.channel == channel)
            .where(AgentBuild.version == version)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_builds(
        self,
        *,
        target: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50,
    ) -> List[AgentBuild]:
        stmt = select(AgentBuild)
        if target:
            stmt = stmt.where(AgentBuild.target == target)
        if channel:
            stmt = stmt.where(AgentBuild.channel == channel)
        stmt = stmt.order_by(AgentBuild.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_latest_build(
        self,
        *,
        target: str,
        channel: str,
    ) -> Optional[AgentBuild]:
        stmt = (
            select(AgentBuild)
            .where(AgentBuild.target == target)
            .where(AgentBuild.channel == channel)
            .order_by(AgentBuild.created_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_builds_for_target(
        self,
        *,
        target: str,
    ) -> List[AgentBuild]:
        stmt = (
            select(AgentBuild)
            .where(AgentBuild.target == target)
            .order_by(AgentBuild.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def delete_build(
        self,
        *,
        target: str,
        channel: str,
        version: str,
    ) -> bool:
        stmt = (
            delete(AgentBuild)
            .where(AgentBuild.target == target)
            .where(AgentBuild.channel == channel)
            .where(AgentBuild.version == version)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return bool(result.rowcount)
