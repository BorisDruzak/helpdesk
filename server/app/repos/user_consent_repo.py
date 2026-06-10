from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserConsentRequest


class UserConsentRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, consent_id: str) -> UserConsentRequest | None:
        result = await self.session.execute(
            select(UserConsentRequest).where(UserConsentRequest.consent_id == str(consent_id))
        )
        return result.scalar_one_or_none()

    async def get_pending_by_subject(self, subject_type: str, subject_id: str) -> UserConsentRequest | None:
        result = await self.session.execute(
            select(UserConsentRequest)
            .where(
                UserConsentRequest.subject_type == str(subject_type),
                UserConsentRequest.subject_id == str(subject_id),
                UserConsentRequest.status == "pending",
            )
            .order_by(UserConsentRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_person(self, person_id: str, *, statuses: list[str] | None = None, limit: int = 100) -> list[UserConsentRequest]:
        stmt = select(UserConsentRequest).where(UserConsentRequest.requester_person_id == str(person_id))
        if statuses:
            stmt = stmt.where(UserConsentRequest.status.in_(statuses))
        stmt = stmt.order_by(UserConsentRequest.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_for_device(
        self,
        device_id: str,
        *,
        person_id: str | None = None,
        statuses: list[str] | None = None,
        limit: int = 100,
    ) -> list[UserConsentRequest]:
        stmt = select(UserConsentRequest).where(UserConsentRequest.device_id == str(device_id))
        if person_id:
            stmt = stmt.where(UserConsentRequest.requester_person_id == str(person_id))
        if statuses:
            stmt = stmt.where(UserConsentRequest.status.in_(statuses))
        stmt = stmt.order_by(UserConsentRequest.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **fields: Any) -> UserConsentRequest:
        row = UserConsentRequest(**fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def expire_if_due(self, consent_id: str, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        result = await self.session.execute(
            update(UserConsentRequest)
            .where(
                UserConsentRequest.consent_id == str(consent_id),
                UserConsentRequest.status == "pending",
                UserConsentRequest.expires_at.isnot(None),
                UserConsentRequest.expires_at <= now,
            )
            .values(status="expired", updated_at=now)
        )
        return result.rowcount > 0

    async def decide_pending(
        self,
        consent_id: str,
        *,
        decision: str,
        actor_id: str,
        actor_role: str,
        surface: str,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now(timezone.utc)
        values: dict[str, Any] = {
            "status": decision,
            "decided_by_actor_id": actor_id,
            "decided_by_role": actor_role,
            "decided_from_surface": surface,
            "decided_at": now,
            "updated_at": now,
        }
        if reason:
            values["reason"] = reason
        result = await self.session.execute(
            update(UserConsentRequest)
            .where(
                and_(
                    UserConsentRequest.consent_id == str(consent_id),
                    UserConsentRequest.status == "pending",
                )
            )
            .values(**values)
        )
        return result.rowcount > 0
