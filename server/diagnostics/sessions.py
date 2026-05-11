from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticSession, DiagnosticStep
from app.repos.diagnostics_repo import DiagnosticRepo


class DiagnosticSessionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = DiagnosticRepo(session)

    async def create_session(
        self,
        *,
        ticket_id: str,
        profile_id: str | None,
        trigger_source: str | None,
        actor: Any,
        profile_version: str | None = None,
    ) -> DiagnosticSession:
        actor_id = getattr(actor, "actor_id", None) if actor is not None else actor
        return await self.repo.create_session(
            ticket_id=ticket_id,
            profile_id=profile_id,
            profile_version=profile_version,
            trigger_source=trigger_source,
            started_by_user_id=str(actor_id) if actor_id else None,
            status="draft",
        )

    async def add_step(self, *, session_id: str, ticket_id: str, step_type: str, status: str = "pending", **values: Any) -> DiagnosticStep:
        return await self.repo.add_step(session_id=session_id, ticket_id=ticket_id, step_type=step_type, status=status, **values)

    async def complete_session(self, session_id: str, *, summary: str | None = None, confidence: float | None = None) -> DiagnosticSession | None:
        item = await self.repo.get_session(session_id)
        if item is None:
            return None
        item.status = "completed"
        item.finished_at = datetime.now(timezone.utc)
        item.summary = summary
        item.confidence = confidence
        await self.session.flush()
        return item

    async def fail_session(self, session_id: str, error: str) -> DiagnosticSession | None:
        item = await self.repo.get_session(session_id)
        if item is None:
            return None
        item.status = "failed"
        item.finished_at = datetime.now(timezone.utc)
        item.summary = error
        await self.session.flush()
        return item

    async def list_sessions(self, ticket_id: str) -> list[DiagnosticSession]:
        return await self.repo.list_sessions(ticket_id)
