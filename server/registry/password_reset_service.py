from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UiPasswordResetRequest
from app.repos.ui_users_repo import UiUsersRepo
from auth.password_service import hash_password, validate_password_policy


def _trim(value: object, *, max_length: int) -> str | None:
    text = str(value or "").strip()
    return text[:max_length] if text else None


class PasswordResetRequestService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def serialize(row: UiPasswordResetRequest) -> dict[str, Any]:
        return {
            "request_id": row.request_id,
            "login": row.login,
            "status": row.status,
            "requested_at": row.requested_at.isoformat() if row.requested_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "completed_by": row.completed_by,
            "resolution_note": row.resolution_note,
        }

    async def create_request(
        self,
        *,
        login: str,
        client_ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        normalized_login = str(login or "").strip()
        if not normalized_login:
            raise ValueError("login is required")

        existing = (
            await self.session.execute(
                select(UiPasswordResetRequest)
                .where(
                    UiPasswordResetRequest.login == normalized_login,
                    UiPasswordResetRequest.status == "pending",
                )
                .order_by(desc(UiPasswordResetRequest.requested_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return self.serialize(existing)

        row = UiPasswordResetRequest(
            login=normalized_login,
            status="pending",
            requested_ip=_trim(client_ip, max_length=120),
            user_agent=_trim(user_agent, max_length=500),
            metadata_json={},
        )
        self.session.add(row)
        await self.session.flush()
        return self.serialize(row)

    async def list_requests(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        stmt = select(UiPasswordResetRequest)
        normalized_status = str(status or "").strip()
        if normalized_status:
            stmt = stmt.where(UiPasswordResetRequest.status == normalized_status)
        stmt = stmt.order_by(desc(UiPasswordResetRequest.requested_at)).limit(max(1, min(int(limit or 100), 500)))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self.serialize(row) for row in rows]

    async def complete_request(
        self,
        *,
        request_id: str,
        password: str,
        actor_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = await self.session.get(UiPasswordResetRequest, str(request_id or "").strip())
        if row is None:
            raise ValueError("password reset request not found")
        if row.status != "pending":
            raise ValueError("password reset request is not pending")

        validate_password_policy(password, login=row.login)
        repo = UiUsersRepo(self.session)
        user = await repo.get_by_login(row.login)
        if user is None:
            raise ValueError("user not found")

        row.status = "completed"
        row.completed_at = datetime.now(timezone.utc)
        row.completed_by = str(actor_id or "").strip() or None
        row.resolution_note = _trim(reason, max_length=500)
        updated = await repo.set_password(row.login, hash_password(password), actor_id=actor_id)
        if not updated:
            raise ValueError("user not found")
        await self.session.flush()
        return self.serialize(row)
