"""
Devices repository for device registry operations.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import (
    Device,
    DispatchReadyDevice,
    Operation,
    DeviceModule,
    DeviceDesiredModule,
    DeviceConfig,
    DeviceToolsetSnapshot,
    DeviceEvent,
    PlaybookRun,
)


class DevicesRepo:
    """Repository for device registry operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_on_handshake(
        self,
        device_id: str,
        protocol_version: str,
        agent_version: str,
        hostname: Optional[str],
        os: Optional[str],
        capabilities: dict,
        tools_version: Optional[str],
        toolset_hash: Optional[str],
        metadata: dict
    ) -> Device:
        """
        Upsert device on handshake.
        
        Creates new device or updates existing one with latest metadata.
        Updates last_handshake_at and last_seen_at timestamps.
        
        Args:
            device_id: Device identifier
            protocol_version: Protocol version string
            agent_version: Agent version string
            hostname: Optional hostname
            os: Optional OS info
            capabilities: Agent capabilities dict
            tools_version: Optional tools version
            toolset_hash: Optional current toolset hash
            metadata: Additional metadata (modules, etc.)
            
        Returns:
            Device: Updated or created device record
        """
        now = datetime.now(timezone.utc)
        
        # Try to get existing device
        stmt = select(Device).where(Device.device_id == device_id)
        result = await self.session.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            # Update existing device
            device.protocol_version = protocol_version
            device.agent_version = agent_version
            device.hostname = hostname
            device.os = os
            device.capabilities = capabilities
            device.tools_version = tools_version
            device.device_metadata = metadata
            device.last_handshake_at = now
            device.last_seen_at = now
            
            # Update toolset_hash if provided
            if toolset_hash is not None:
                device.current_toolset_hash = toolset_hash

            # Successful handshake revives only active devices. Deleted devices
            # are blocked earlier in auth/token issuance flow and should never
            # reach this branch in normal operation.
            
            logger.debug(
                f"[DevicesRepo] Updated device: device_id={device_id} "
                f"agent_version={agent_version}"
            )
        else:
            # Create new device
            device = Device(
                device_id=device_id,
                first_seen_at=now,
                last_seen_at=now,
                last_handshake_at=now,
                protocol_version=protocol_version,
                agent_version=agent_version,
                hostname=hostname,
                os=os,
                capabilities=capabilities,
                tools_version=tools_version,
                current_toolset_hash=toolset_hash,
                device_metadata=metadata
            )
            self.session.add(device)
            
            logger.info(
                f"[DevicesRepo] Created new device: device_id={device_id} "
                f"agent_version={agent_version}"
            )
        
        await self.session.flush()
        return device
    
    async def ensure_device_exists(self, device_id: str) -> Device:
        """
        Создаёт запись устройства, если её ещё нет (для логина по UUID до первого handshake).
        Используется при POST /api/login: agent_tokens ссылается на devices, поэтому устройство
        должно существовать до создания токена.
        При первом подключении агента upsert_on_handshake обновит запись реальными данными.
        
        Args:
            device_id: Device identifier (UUID)
            
        Returns:
            Device: Существующая или только что созданная запись
        """
        device = await self.get_by_device_id(device_id)
        if device:
            return device
        now = datetime.now(timezone.utc)
        device = Device(
            device_id=device_id,
            first_seen_at=now,
            last_seen_at=now,
            last_handshake_at=now,
            protocol_version="pending",
            agent_version="",
            hostname=None,
            os=None,
            capabilities={},
            tools_version=None,
            current_toolset_hash=None,
            device_metadata={},
            deleted_at=None,
            deleted_by=None,
            delete_reason=None,
        )
        self.session.add(device)
        await self.session.flush()
        logger.info(f"[DevicesRepo] Created stub device for login: device_id={device_id}")
        return device

    async def merge_device_metadata(self, device_id: str, metadata_patch: dict) -> bool:
        device = await self.get_by_device_id(device_id, include_deleted=True)
        if not device:
            return False
        current = device.device_metadata if isinstance(device.device_metadata, dict) else {}
        merged = dict(current)
        merged.update(metadata_patch or {})
        device.device_metadata = merged
        await self.session.flush()
        return True
    
    async def update_toolset_snapshot_ref(
        self,
        device_id: str,
        toolset_hash: str,
        snapshot_id: int
    ) -> bool:
        """
        Update device's current toolset snapshot reference.
        
        Args:
            device_id: Device identifier
            toolset_hash: Toolset hash
            snapshot_id: Snapshot ID to reference
            
        Returns:
            bool: True if updated, False if device not found
        """
        stmt = (
            update(Device)
            .where(Device.device_id == device_id)
            .values(
                current_toolset_hash=toolset_hash,
                current_toolset_snapshot_id=snapshot_id
            )
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount > 0:
            logger.debug(
                f"[DevicesRepo] Updated toolset snapshot ref: "
                f"device_id={device_id} snapshot_id={snapshot_id}"
            )
            return True
        
        logger.warning(
            f"[DevicesRepo] Device not found for toolset update: device_id={device_id}"
        )
        return False
    
    async def update_last_seen(self, device_id: str) -> bool:
        """
        Update device's last_seen_at timestamp.
        
        Called on all incoming messages to track device activity.
        
        Args:
            device_id: Device identifier
            
        Returns:
            bool: True if updated, False if device not found
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(Device)
            .where(Device.device_id == device_id)
            .values(last_seen_at=now)
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount > 0:
            logger.debug(f"[DevicesRepo] Updated last_seen: device_id={device_id}")
            return True
        
        return False
    
    async def update_toolset_info(
        self,
        device_id: str,
        toolset_hash: Optional[str],
        tools_count: Optional[int]
    ) -> bool:
        """
        Update toolset_hash and last_tools_changed_at.
        
        Args:
            device_id: Device identifier
            toolset_hash: Current toolset hash
            tools_count: Number of tools (optional)
            
        Returns:
            bool: True if updated, False if device not found
        """
        now = datetime.now(timezone.utc)
        
        values = {
            "current_toolset_hash": toolset_hash,
            "last_tools_changed_at": now
        }
        
        stmt = (
            update(Device)
            .where(Device.device_id == device_id)
            .values(**values)
        )
        
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def update_toolset_refresh_time(self, device_id: str) -> bool:
        """
        Update device's last_toolset_refresh_at timestamp.
        
        Used for rate-limiting list_tools requests.
        
        Args:
            device_id: Device identifier
            
        Returns:
            bool: True if updated, False if device not found
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(Device)
            .where(Device.device_id == device_id)
            .values(last_toolset_refresh_at=now)
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount > 0:
            logger.debug(
                f"[DevicesRepo] Updated toolset_refresh_time: device_id={device_id}"
            )
            return True
        
        return False
    
    async def get_by_device_id(self, device_id: str, *, include_deleted: bool = True) -> Optional[Device]:
        """
        Get device by device_id.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Optional[Device]: Device record or None if not found
        """
        stmt = select(Device).where(Device.device_id == device_id)
        if not include_deleted:
            stmt = stmt.where(Device.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def should_refresh_toolset(
        self,
        device_id: str,
        rate_limit_minutes: int = 10
    ) -> bool:
        """
        Check if device toolset should be refreshed based on rate-limit.
        
        Returns True if:
        - Device has never had toolset refreshed (last_toolset_refresh_at is None)
        - Last refresh was more than rate_limit_minutes ago
        
        Args:
            device_id: Device identifier
            rate_limit_minutes: Minimum minutes between refreshes (default: 10)
            
        Returns:
            bool: True if refresh is allowed, False if rate-limited
        """
        device = await self.get_by_device_id(device_id)
        
        if not device:
            logger.warning(
                f"[DevicesRepo] Device not found for refresh check: device_id={device_id}"
            )
            return False
        
        # If never refreshed, allow refresh
        if device.last_toolset_refresh_at is None:
            logger.debug(
                f"[DevicesRepo] Toolset never refreshed: device_id={device_id}"
            )
            return True
        
        # Check if enough time has passed
        now = datetime.now(timezone.utc)
        time_since_refresh = now - device.last_toolset_refresh_at
        min_interval = timedelta(minutes=rate_limit_minutes)
        
        if time_since_refresh >= min_interval:
            logger.debug(
                f"[DevicesRepo] Toolset refresh allowed: device_id={device_id} "
                f"time_since_refresh={time_since_refresh.total_seconds():.1f}s"
            )
            return True
        
        logger.debug(
            f"[DevicesRepo] Toolset refresh rate-limited: device_id={device_id} "
            f"time_since_refresh={time_since_refresh.total_seconds():.1f}s "
            f"min_interval={min_interval.total_seconds():.1f}s"
        )
        return False
    
    async def list_all(self, *, include_deleted: bool = False):
        """
        Get all devices from database.
        
        Returns:
            List[Device]: List of all device records
        """
        from typing import List
        stmt = select(Device)
        if not include_deleted:
            stmt = stmt.where(Device.deleted_at.is_(None))
        stmt = stmt.order_by(Device.last_seen_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def archive_device(
        self,
        device_id: str,
        *,
        deleted_by: Optional[str],
        delete_reason: Optional[str] = None,
    ) -> bool:
        """
        Мягко удаляет устройство, отменяет локальную facade-историю операций
        и сохраняет исторические записи для аудита.
        
        Returns:
            True если устройство найдено и архивировано, False если не найдено.
        """
        device = await self.get_by_device_id(device_id, include_deleted=True)
        if not device:
            return False

        now = datetime.now(timezone.utc)
        if device.deleted_at is not None:
            return True

        device.deleted_at = now
        device.deleted_by = deleted_by
        device.delete_reason = delete_reason or None

        active_operations = (
            await self.session.execute(
                select(Operation).where(
                    Operation.device_id == device_id,
                    Operation.status.in_(
                        [
                            "queued",
                            "sent",
                            "accepted",
                            "running",
                            "waiting_consent",
                            "cancel_requested",
                        ]
                    ),
                )
            )
        ).scalars().all()
        for op in active_operations:
            op.status_before_cancel = op.status
            op.status = "canceled"
            op.cancel_reason = "device_archived"
            op.canceled_at = op.canceled_at or now
            op.finished_at = op.finished_at or now
            op.error_code = op.error_code or "DEVICE_ARCHIVED"
            op.error_message = op.error_message or "Операция остановлена: агент архивирован"
            op.result_summary = op.result_summary or "Операция отменена после архивирования агента"

        await self.session.execute(delete(DispatchReadyDevice).where(DispatchReadyDevice.device_id == device_id))
        await self.session.flush()
        logger.info(f"[DevicesRepo] Archived device and preserved history: device_id={device_id}")
        return True

    async def restore_device(
        self,
        device_id: str,
        *,
        restored_by: Optional[str],
        restore_reason: Optional[str] = None,
    ) -> bool:
        """
        Restore a previously archived device record without reviving revoked tokens,
        account sessions, pending requests, outbox rows, or canceled operations.

        Returns:
            True when the device exists, False when it was not found.
        """
        device = await self.get_by_device_id(device_id, include_deleted=True)
        if not device:
            return False

        if device.deleted_at is None:
            return True

        now = datetime.now(timezone.utc)
        old_deleted_at = device.deleted_at.isoformat() if device.deleted_at else None
        old_deleted_by = device.deleted_by
        old_delete_reason = device.delete_reason

        device.deleted_at = None
        device.deleted_by = None
        device.delete_reason = None

        await self.session.flush()
        logger.info(
            f"[DevicesRepo] Restored archived device record without reviving tokens: device_id={device_id}"
        )
        return True
