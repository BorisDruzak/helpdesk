from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RemoteAccessEvent, RemoteAccessSession


ACTIVE_REMOTE_ACCESS_STATUSES = {"requested", "waiting_consent", "approved", "starting", "active"}
TERMINAL_REMOTE_ACCESS_STATUSES = {"ended", "denied", "expired", "failed", "canceled"}


class RemoteAccessRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        *,
        ticket_id: str,
        device_id: str,
        operator_id: str,
        requester_id: str | None,
        mode: str,
        status: str,
        reason: str | None,
        consent_required: bool,
        consent_status: str,
        expires_at: datetime,
        max_duration_sec: int,
        ice_config: dict[str, Any] | None = None,
    ) -> RemoteAccessSession:
        now = datetime.now(timezone.utc)
        session = RemoteAccessSession(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            device_id=device_id,
            operator_id=operator_id,
            requester_id=requester_id,
            mode=mode,
            status=status,
            reason=reason,
            consent_required=consent_required,
            consent_status=consent_status,
            requested_at=now,
            expires_at=expires_at,
            max_duration_sec=max_duration_sec,
            ice_config=ice_config,
            created_at=now,
            updated_at=now,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get(self, session_id: str) -> RemoteAccessSession | None:
        return await self.session.get(RemoteAccessSession, session_id)

    async def list_for_ticket(self, ticket_id: str, *, limit: int = 20) -> list[RemoteAccessSession]:
        stmt = (
            select(RemoteAccessSession)
            .where(RemoteAccessSession.ticket_id == ticket_id)
            .order_by(RemoteAccessSession.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def active_for_ticket_device(self, ticket_id: str, device_id: str) -> RemoteAccessSession | None:
        stmt = (
            select(RemoteAccessSession)
            .where(
                RemoteAccessSession.ticket_id == ticket_id,
                RemoteAccessSession.device_id == device_id,
                RemoteAccessSession.status.in_(ACTIVE_REMOTE_ACCESS_STATUSES),
            )
            .order_by(RemoteAccessSession.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def expired_active_sessions(self, now: datetime | None = None) -> list[RemoteAccessSession]:
        now = now or datetime.now(timezone.utc)
        stmt = select(RemoteAccessSession).where(
            RemoteAccessSession.status.in_(ACTIVE_REMOTE_ACCESS_STATUSES),
            RemoteAccessSession.expires_at <= now,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_event(
        self,
        *,
        session_id: str,
        ticket_id: str,
        actor_type: str,
        actor_id: str | None,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> RemoteAccessEvent:
        event = RemoteAccessEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            ticket_id=ticket_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            payload=payload or {},
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def set_status(
        self,
        session: RemoteAccessSession,
        *,
        status: str,
        consent_status: str | None = None,
        close_reason: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        expires_at: datetime | None = None,
    ) -> RemoteAccessSession:
        now = datetime.now(timezone.utc)
        session.status = status
        if consent_status is not None:
            session.consent_status = consent_status
        if expires_at is not None:
            session.expires_at = expires_at
        if close_reason is not None:
            session.close_reason = close_reason
        if error_code is not None:
            session.error_code = error_code
        if error_message is not None:
            session.error_message = error_message
        if status == "approved":
            session.approved_at = now
        elif status == "denied":
            session.denied_at = now
        elif status == "active":
            session.started_at = session.started_at or now
        elif status in TERMINAL_REMOTE_ACCESS_STATUSES:
            session.ended_at = session.ended_at or now
        session.updated_at = now
        await self.session.flush()
        return session
