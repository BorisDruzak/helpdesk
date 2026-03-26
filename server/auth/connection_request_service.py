"""
Service layer for DB-backed connection request lifecycle.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.db import get_session
from app.repos.connection_requests_repo import ConnectionRequestsRepo
from app.repos.devices_repo import DevicesRepo


class ConnectionRequestService:
    """Keeps pending/approved/rejected connection state in DB only."""

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

    async def save_approved_token_once(self, *, device_id: str, token: str) -> None:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            await repo.set_approval_token(device_id=device_id, token=token)
            await session.commit()

    async def consume_approved_token_once(self, *, device_id: str) -> Optional[str]:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            token = await repo.consume_approval_token(device_id=device_id)
            await session.commit()
            return token

    async def clear_pending_after_manual_token_issue(self, *, device_id: str) -> None:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            await repo.set_approved(device_id)
            await session.commit()
