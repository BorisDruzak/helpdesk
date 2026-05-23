from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceAccountLoginRequest, DeviceAccountSession


def new_id() -> str:
    return str(uuid.uuid4())


class AccountSessionRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session(self, session_id: str) -> DeviceAccountSession | None:
        return await self.session.get(DeviceAccountSession, str(session_id))

    async def create_session(self, **fields: Any) -> DeviceAccountSession:
        row = DeviceAccountSession(session_id=fields.pop("session_id", new_id()), **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_sessions_for_device(
        self,
        device_id: str,
        *,
        verification_status: str | None = None,
        limit: int = 50,
    ) -> list[DeviceAccountSession]:
        stmt = select(DeviceAccountSession).where(DeviceAccountSession.device_id == str(device_id))
        if verification_status:
            stmt = stmt.where(DeviceAccountSession.verification_status == verification_status)
        result = await self.session.execute(
            stmt.order_by(desc(DeviceAccountSession.created_at)).limit(max(1, min(int(limit or 50), 200)))
        )
        return list(result.scalars().all())

    async def revoke_session(self, session_id: str, *, revoked_by: str | None = None) -> DeviceAccountSession:
        row = await self.get_session(session_id)
        if row is None:
            raise ValueError("account session not found")
        row.verification_status = "revoked"
        row.revoked_at = datetime.now(timezone.utc)
        row.revoked_by = revoked_by
        await self.session.flush()
        return row

    async def get_login_request(self, request_id: str) -> DeviceAccountLoginRequest | None:
        return await self.session.get(DeviceAccountLoginRequest, str(request_id))

    async def create_login_request(self, **fields: Any) -> DeviceAccountLoginRequest:
        row = DeviceAccountLoginRequest(request_id=fields.pop("request_id", new_id()), **fields)
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_login_requests(
        self,
        *,
        device_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[DeviceAccountLoginRequest]:
        stmt = select(DeviceAccountLoginRequest)
        if device_id:
            stmt = stmt.where(DeviceAccountLoginRequest.device_id == str(device_id))
        if status:
            stmt = stmt.where(DeviceAccountLoginRequest.status == str(status))
        result = await self.session.execute(
            stmt.order_by(desc(DeviceAccountLoginRequest.requested_at)).limit(max(1, min(int(limit or 100), 500)))
        )
        return list(result.scalars().all())

    async def mark_login_request(
        self,
        request_id: str,
        *,
        status: str,
        reviewed_by: str | None = None,
        rejection_reason: str | None = None,
        resulting_session_id: str | None = None,
    ) -> DeviceAccountLoginRequest:
        row = await self.get_login_request(request_id)
        if row is None:
            raise ValueError("account login request not found")
        row.status = status
        row.reviewed_by = reviewed_by
        row.reviewed_at = datetime.now(timezone.utc)
        row.rejection_reason = rejection_reason
        row.resulting_session_id = resulting_session_id
        await self.session.flush()
        return row
