from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosticBundle, DiagnosticEvidence, DiagnosticFinding, DiagnosticSession, DiagnosticStep


def _uuid() -> str:
    return str(uuid.uuid4())


class DiagnosticRepo:
    """Persistence helpers for the ticket diagnostic layer."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        *,
        ticket_id: str,
        profile_id: str | None = None,
        profile_version: str | None = None,
        trigger_source: str | None = None,
        started_by_user_id: str | None = None,
        status: str = "draft",
    ) -> DiagnosticSession:
        item = DiagnosticSession(
            id=_uuid(),
            ticket_id=ticket_id,
            profile_id=profile_id,
            profile_version=profile_version,
            status=status,
            trigger_source=trigger_source,
            started_by_user_id=started_by_user_id,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_session(self, session_id: str) -> DiagnosticSession | None:
        return await self.session.get(DiagnosticSession, session_id)

    async def list_sessions(self, ticket_id: str) -> list[DiagnosticSession]:
        result = await self.session.execute(
            select(DiagnosticSession)
            .where(DiagnosticSession.ticket_id == ticket_id)
            .order_by(DiagnosticSession.started_at.desc())
        )
        return list(result.scalars())

    async def add_step(self, *, session_id: str, ticket_id: str, step_type: str, status: str = "pending", **values: Any) -> DiagnosticStep:
        item = DiagnosticStep(
            id=_uuid(),
            session_id=session_id,
            ticket_id=ticket_id,
            step_type=step_type,
            status=status,
            **values,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_steps(self, ticket_id: str, *, session_id: str | None = None) -> list[DiagnosticStep]:
        stmt = select(DiagnosticStep).where(DiagnosticStep.ticket_id == ticket_id)
        if session_id:
            stmt = stmt.where(DiagnosticStep.session_id == session_id)
        result = await self.session.execute(stmt.order_by(DiagnosticStep.created_at.asc()))
        return list(result.scalars())

    async def upsert_evidence(self, **values: Any) -> DiagnosticEvidence:
        source_type = values.get("source_type")
        source_id = values.get("source_id")
        kind = values.get("kind")
        ticket_id = values.get("ticket_id")
        existing = None
        if ticket_id and source_type and source_id and kind:
            existing = (
                await self.session.execute(
                    select(DiagnosticEvidence).where(
                        DiagnosticEvidence.ticket_id == ticket_id,
                        DiagnosticEvidence.source_type == source_type,
                        DiagnosticEvidence.source_id == str(source_id),
                        DiagnosticEvidence.kind == kind,
                    )
                )
            ).scalar_one_or_none()
        if existing is not None:
            for key, value in values.items():
                if key != "id":
                    setattr(existing, key, value)
            await self.session.flush()
            return existing
        values.setdefault("id", _uuid())
        values.setdefault("observed_at", datetime.now(timezone.utc))
        item = DiagnosticEvidence(**values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_evidence(self, evidence_id: str) -> DiagnosticEvidence | None:
        return await self.session.get(DiagnosticEvidence, evidence_id)

    async def list_evidence(self, ticket_id: str, *, session_id: str | None = None, selected_only: bool = False) -> list[DiagnosticEvidence]:
        stmt = select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id)
        if session_id:
            stmt = stmt.where(DiagnosticEvidence.session_id == session_id)
        if selected_only:
            stmt = stmt.where(DiagnosticEvidence.selected_for_passport.is_(True))
        result = await self.session.execute(stmt.order_by(DiagnosticEvidence.observed_at.desc(), DiagnosticEvidence.created_at.desc()))
        return list(result.scalars())

    async def set_evidence_selected(self, evidence_id: str, selected: bool) -> DiagnosticEvidence | None:
        item = await self.get_evidence(evidence_id)
        if item is None:
            return None
        item.selected_for_passport = selected
        await self.session.flush()
        return item

    async def upsert_finding(self, **values: Any) -> DiagnosticFinding:
        ticket_id = values.get("ticket_id")
        session_id = values.get("session_id")
        root_cause_code = values.get("root_cause_code")
        existing = None
        if ticket_id and root_cause_code:
            stmt = select(DiagnosticFinding).where(
                DiagnosticFinding.ticket_id == ticket_id,
                DiagnosticFinding.root_cause_code == root_cause_code,
                DiagnosticFinding.status == values.get("status", "suspected"),
            )
            if session_id:
                stmt = stmt.where(DiagnosticFinding.session_id == session_id)
            existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            for key, value in values.items():
                if key != "id":
                    setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            await self.session.flush()
            return existing
        values.setdefault("id", _uuid())
        item = DiagnosticFinding(**values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_findings(self, ticket_id: str, *, session_id: str | None = None) -> list[DiagnosticFinding]:
        stmt = select(DiagnosticFinding).where(DiagnosticFinding.ticket_id == ticket_id)
        if session_id:
            stmt = stmt.where(DiagnosticFinding.session_id == session_id)
        result = await self.session.execute(stmt.order_by(DiagnosticFinding.created_at.desc()))
        return list(result.scalars())

    async def create_bundle(self, **values: Any) -> DiagnosticBundle:
        values.setdefault("id", _uuid())
        item = DiagnosticBundle(**values)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_bundle(self, bundle_id: str) -> DiagnosticBundle | None:
        return await self.session.get(DiagnosticBundle, bundle_id)
