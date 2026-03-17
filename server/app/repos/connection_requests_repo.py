"""Repository for connection_requests and server_config (connection policy)."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConnectionRequest, ServerConfig

CONNECTION_POLICY_KEY = "connection_policy"
POLICY_REJECT_ALL = "reject_all"
POLICY_ACCEPT_ALL = "accept_all"
POLICY_MANUAL = "manual"


class ConnectionRequestsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_policy(self) -> str:
        row = await self.session.execute(
            select(ServerConfig.value).where(ServerConfig.key == CONNECTION_POLICY_KEY)
        )
        val = row.scalar_one_or_none()
        if val in (POLICY_REJECT_ALL, POLICY_ACCEPT_ALL, POLICY_MANUAL):
            return val
        return POLICY_MANUAL

    async def set_policy(self, policy: str) -> None:
        if policy not in (POLICY_REJECT_ALL, POLICY_ACCEPT_ALL, POLICY_MANUAL):
            raise ValueError(f"Invalid policy: {policy}")
        from sqlalchemy.dialects.postgresql import insert
        await self.session.execute(
            insert(ServerConfig)
            .values(key=CONNECTION_POLICY_KEY, value=policy)
            .on_conflict_do_update(index_elements=["key"], set_={"value": policy})
        )
        await self.session.flush()

    async def get_pending_by_device_id(self, device_id: str) -> Optional[ConnectionRequest]:
        result = await self.session.execute(
            select(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "pending",
            )
            .order_by(ConnectionRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_request(
        self,
        device_id: str,
        ip_address: Optional[str] = None,
        hostname: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ConnectionRequest:
        req = ConnectionRequest(
            device_id=device_id,
            status="pending",
            ip_address=ip_address,
            hostname=hostname,
            request_metadata=metadata or {},
        )
        self.session.add(req)
        await self.session.flush()
        return req

    async def list_pending(self):
        result = await self.session.execute(
            select(ConnectionRequest)
            .where(ConnectionRequest.status == "pending")
            .order_by(ConnectionRequest.created_at.desc())
        )
        return list(result.scalars().all())

    async def set_approved(self, device_id: str) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "pending",
            )
            .values(status="approved", resolved_at=now)
        )
        await self.session.flush()

    async def set_rejected(self, device_id: str) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "pending",
            )
            .values(status="rejected", resolved_at=now)
        )
        await self.session.flush()

    async def get_status(self, device_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ConnectionRequest.status)
            .where(ConnectionRequest.device_id == device_id)
            .order_by(ConnectionRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
