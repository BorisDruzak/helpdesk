from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DeviceAccountEvent, DeviceAccountLoginRequest, DeviceAccountSession


SESSION_TOKEN_DELIVERY_KEY = "session_token_delivery"
SESSION_TOKEN_DELIVERED_AT_KEY = "session_token_delivered_at"
SESSION_TOKEN_DELIVERY_STATUS_KEY = "session_token_delivery_status"


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

    async def list_sessions(
        self,
        *,
        device_id: str | None = None,
        person_id: str | None = None,
        claim_id: str | None = None,
        binding_id: str | None = None,
        base_binding_id: str | None = None,
        account_mode: str | None = None,
        verification_status: str | None = None,
        limit: int = 200,
    ) -> list[DeviceAccountSession]:
        stmt = select(DeviceAccountSession)
        if device_id:
            stmt = stmt.where(DeviceAccountSession.device_id == str(device_id))
        if person_id:
            stmt = stmt.where(DeviceAccountSession.person_id == str(person_id))
        if claim_id:
            stmt = stmt.where(DeviceAccountSession.claim_id == str(claim_id))
        if binding_id:
            stmt = stmt.where(DeviceAccountSession.binding_id == str(binding_id))
        if base_binding_id:
            stmt = stmt.where(DeviceAccountSession.base_binding_id == str(base_binding_id))
        if account_mode:
            stmt = stmt.where(DeviceAccountSession.account_mode == str(account_mode))
        if verification_status:
            stmt = stmt.where(DeviceAccountSession.verification_status == str(verification_status))
        result = await self.session.execute(
            stmt.order_by(desc(DeviceAccountSession.created_at)).limit(max(1, min(int(limit or 200), 500)))
        )
        return list(result.scalars().all())

    async def revoke_session(
        self,
        session_id: str,
        *,
        revoked_by: str | None = None,
        reason: str | None = None,
    ) -> DeviceAccountSession:
        row = await self.get_session(session_id)
        if row is None:
            raise ValueError("account session not found")
        if row.verification_status == "revoked":
            return row
        row.verification_status = "revoked"
        row.revoked_at = datetime.now(timezone.utc)
        row.revoked_by = revoked_by
        if reason:
            row.metadata_json = {**(row.metadata_json or {}), "revoke_reason": reason}
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
        base_binding_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[DeviceAccountLoginRequest]:
        stmt = select(DeviceAccountLoginRequest)
        if device_id:
            stmt = stmt.where(DeviceAccountLoginRequest.device_id == str(device_id))
        if base_binding_id:
            stmt = stmt.where(DeviceAccountLoginRequest.base_binding_id == str(base_binding_id))
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

    async def lock_login_request_session_token_delivery(
        self,
        *,
        request_id: str,
        device_id: str,
    ) -> DeviceAccountLoginRequest | None:
        result = await self.session.execute(
            select(DeviceAccountLoginRequest)
            .where(
                DeviceAccountLoginRequest.request_id == str(request_id),
                DeviceAccountLoginRequest.device_id == str(device_id),
                DeviceAccountLoginRequest.status == "approved",
            )
            .with_for_update(skip_locked=True)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        metadata = row.metadata_json if isinstance(row.metadata_json, dict) else {}
        if metadata.get(SESSION_TOKEN_DELIVERED_AT_KEY) or not isinstance(metadata.get(SESSION_TOKEN_DELIVERY_KEY), dict):
            return None
        return row

    async def mark_login_request_session_token_delivered(self, row: DeviceAccountLoginRequest) -> DeviceAccountLoginRequest:
        metadata = dict(row.metadata_json or {}) if isinstance(row.metadata_json, dict) else {}
        metadata.pop(SESSION_TOKEN_DELIVERY_KEY, None)
        metadata.pop("session_token_once", None)
        metadata[SESSION_TOKEN_DELIVERED_AT_KEY] = datetime.now(timezone.utc).isoformat()
        metadata[SESSION_TOKEN_DELIVERY_STATUS_KEY] = "delivered"
        row.metadata_json = metadata
        await self.session.flush()
        return row

    async def append_event(
        self,
        *,
        device_id: str,
        event_type: str,
        session_id: str | None = None,
        request_id: str | None = None,
        ticket_id: str | None = None,
        actor_id: str | None = None,
        actor_role: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> DeviceAccountEvent:
        row = DeviceAccountEvent(
            event_id=new_id(),
            device_id=str(device_id),
            session_id=session_id,
            request_id=request_id,
            ticket_id=ticket_id,
            event_type=str(event_type),
            actor_id=actor_id,
            actor_role=actor_role,
            payload=payload or {},
            event_at=datetime.now(timezone.utc),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_events(
        self,
        *,
        device_id: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[DeviceAccountEvent]:
        stmt = select(DeviceAccountEvent)
        if device_id:
            stmt = stmt.where(DeviceAccountEvent.device_id == str(device_id))
        if session_id:
            stmt = stmt.where(DeviceAccountEvent.session_id == str(session_id))
        result = await self.session.execute(
            stmt.order_by(desc(DeviceAccountEvent.event_at)).limit(max(1, min(int(limit or 100), 500)))
        )
        return list(result.scalars().all())
