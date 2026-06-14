"""
Service layer for DB-backed connection request lifecycle.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db import get_session
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.connection_requests_repo import ConnectionRequestsRepo
from app.repos.devices_repo import DevicesRepo
from auth.service import ArchivedDeviceError


class ConnectionRequestService:
    """Keeps pending/approved/rejected connection state in DB only."""

    @staticmethod
    def generate_poll_secret() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def hash_poll_secret(secret: str) -> str:
        return hashlib.sha256(str(secret).encode("utf-8")).hexdigest()

    async def record_unauthorized_attempt(
        self,
        *,
        device_id: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        reason: str,
    ) -> None:
        metadata = {
            "reason": reason,
            "user_agent": user_agent or "",
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        }
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            devices_repo = DevicesRepo(session)
            device = await devices_repo.get_by_device_id(device_id, include_deleted=True)
            if device and device.deleted_at is not None:
                return
            existing = await repo.get_pending_by_device_id(device_id)
            if existing:
                await repo.touch_pending_request(device_id, metadata_patch=metadata)
            else:
                await repo.create_request(
                    device_id=device_id,
                    ip_address=ip_address,
                    hostname=None,
                    metadata=metadata,
                )
            await session.commit()

    async def consume_approved_token_once(
        self,
        *,
        device_id: str,
        request_id: str,
        poll_secret: str,
    ) -> Optional[str]:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            req = await repo.get_by_request_id(request_id)
            if (
                not req
                or req.device_id != device_id
                or not req.poll_secret_hash
                or req.poll_secret_hash != self.hash_poll_secret(poll_secret)
                or req.status != "approved"
                or req.approved_token_delivered_at is not None
            ):
                return None
            devices_repo = DevicesRepo(session)
            existing_device = await devices_repo.get_by_device_id(device_id, include_deleted=True)
            if existing_device and existing_device.deleted_at is not None:
                raise ArchivedDeviceError("Device is archived and must be restored before reprovision.")
            await devices_repo.ensure_device_exists(device_id)
            claimed = await repo.mark_approval_delivered(request_id=request_id, device_id=device_id)
            if not claimed:
                return None

            raw_token = secrets.token_hex(32)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=4320)
            await AuthTokensRepo(session).create_agent_token(
                token=raw_token,
                device_id=device_id,
                expires_at=expires_at,
                replace_existing=True,
                commit=False,
            )
            await session.commit()
            return raw_token

    async def clear_pending_after_manual_token_issue(self, *, device_id: str) -> None:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            await repo.set_approved(device_id)
            await session.commit()
