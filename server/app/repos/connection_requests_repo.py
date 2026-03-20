"""Repository for connection_requests and server_config (connection policy)."""
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConnectionRequest, ServerConfig

# Показывать в админке только запросы, обновлённые за последние N секунд
PENDING_ACTIVE_SECONDS = 30

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
        # P0 default: new environment auto-approves provisioning.
        return POLICY_ACCEPT_ALL

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
        now = datetime.now(timezone.utc)
        req = ConnectionRequest(
            device_id=device_id,
            status="pending",
            ip_address=ip_address,
            hostname=hostname,
            request_metadata=metadata or {},
            last_request_at=now,
        )
        self.session.add(req)
        await self.session.flush()
        return req

    async def touch_pending_request(
        self,
        device_id: str,
        metadata_patch: Optional[dict] = None,
    ) -> bool:
        """Обновляет last_request_at у существующего pending-запроса. Возвращает True если обновлён."""
        now = datetime.now(timezone.utc)
        values = {"last_request_at": now}
        if metadata_patch:
            result = await self.session.execute(
                select(ConnectionRequest.request_metadata)
                .where(
                    ConnectionRequest.device_id == device_id,
                    ConnectionRequest.status == "pending",
                )
                .order_by(ConnectionRequest.created_at.desc())
                .limit(1)
            )
            existing_metadata = result.scalar_one_or_none() or {}
            merged_metadata = dict(existing_metadata) if isinstance(existing_metadata, dict) else {}
            merged_metadata.update(metadata_patch)
            values["request_metadata"] = merged_metadata

        result = await self.session.execute(
            update(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "pending",
            )
            .values(**values)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def list_pending(self, only_active: bool = True):
        """Список pending-запросов. При only_active=True — только с last_request_at за последние PENDING_ACTIVE_SECONDS сек."""
        q = select(ConnectionRequest).where(ConnectionRequest.status == "pending")
        if only_active:
            since = datetime.now(timezone.utc) - timedelta(seconds=PENDING_ACTIVE_SECONDS)
            q = q.where(ConnectionRequest.last_request_at >= since)
        q = q.order_by(ConnectionRequest.last_request_at.desc())
        result = await self.session.execute(q)
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

    async def set_approval_token(self, device_id: str, token: str) -> bool:
        """
        Persists one-time approval token in latest approved request.
        Returns True when token was stored.
        """
        result = await self.session.execute(
            update(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "approved",
            )
            .values(
                approved_token=token,
                approved_token_delivered_at=None,
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def consume_approval_token(self, device_id: str) -> Optional[str]:
        """
        Returns token once and atomically marks it as delivered.
        """
        row = await self.session.execute(
            select(ConnectionRequest)
            .where(
                ConnectionRequest.device_id == device_id,
                ConnectionRequest.status == "approved",
                ConnectionRequest.approved_token.isnot(None),
                ConnectionRequest.approved_token_delivered_at.is_(None),
            )
            .order_by(ConnectionRequest.created_at.desc())
            .limit(1)
        )
        req = row.scalar_one_or_none()
        if not req:
            return None
        token = req.approved_token
        await self.session.execute(
            update(ConnectionRequest)
            .where(ConnectionRequest.id == req.id)
            .values(approved_token_delivered_at=datetime.now(timezone.utc))
        )
        await self.session.flush()
        return token

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

    async def get_latest_by_device_id(self, device_id: str) -> Optional[ConnectionRequest]:
        result = await self.session.execute(
            select(ConnectionRequest)
            .where(ConnectionRequest.device_id == device_id)
            .order_by(ConnectionRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
