"""
Toolset snapshots repository.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.db.models import DeviceToolsetSnapshot


class ToolsetSnapshotsRepo:
    """Repository for device toolset snapshot operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def insert_snapshot_if_not_exists(
        self,
        device_id: str,
        toolset_hash: str,
        toolset_json: dict,
        agent_version: str,
        tool_count: int
    ) -> Optional[int]:
        """
        Insert toolset snapshot idempotently.
        
        Uses UNIQUE constraint on (device_id, toolset_hash) to prevent duplicates.
        If snapshot already exists, returns its ID without error.
        
        КРИТИЧНО: Эта функция идемпотентна благодаря UNIQUE constraint.
        Повторные вызовы с теми же device_id и toolset_hash не создают дубликаты.
        
        Args:
            device_id: Device identifier
            toolset_hash: Toolset hash (first 16 chars of SHA256)
            toolset_json: Full toolset JSON ({"tools": [...]})
            agent_version: Agent version that reported this toolset
            tool_count: Number of tools in the list
            
        Returns:
            Optional[int]: snapshot_id if created or found, None on error
        """
        now = datetime.now(timezone.utc)
        
        # Try to insert new snapshot
        snapshot = DeviceToolsetSnapshot(
            device_id=device_id,
            captured_at=now,
            agent_version=agent_version,
            toolset_hash=toolset_hash,
            toolset_json=toolset_json,
            tool_count=tool_count
        )
        
        self.session.add(snapshot)
        
        try:
            await self.session.flush()
            
            logger.info(
                f"[ToolsetSnapshotsRepo] Created snapshot: "
                f"snapshot_id={snapshot.snapshot_id} device_id={device_id} "
                f"toolset_hash={toolset_hash} tool_count={tool_count}"
            )
            return snapshot.snapshot_id
            
        except IntegrityError as e:
            # UNIQUE constraint violation - snapshot already exists
            # This is expected and not an error (idempotency)
            await self.session.rollback()
            
            logger.debug(
                f"[ToolsetSnapshotsRepo] Snapshot already exists: "
                f"device_id={device_id} toolset_hash={toolset_hash}"
            )
            
            # Get existing snapshot ID
            stmt = select(DeviceToolsetSnapshot).where(
                DeviceToolsetSnapshot.device_id == device_id,
                DeviceToolsetSnapshot.toolset_hash == toolset_hash
            )
            result = await self.session.execute(stmt)
            existing_snapshot = result.scalar_one_or_none()
            
            if existing_snapshot:
                logger.debug(
                    f"[ToolsetSnapshotsRepo] Found existing snapshot: "
                    f"snapshot_id={existing_snapshot.snapshot_id}"
                )
                return existing_snapshot.snapshot_id
            
            # Should not happen, but handle gracefully
            logger.error(
                f"[ToolsetSnapshotsRepo] UNIQUE constraint violated but "
                f"snapshot not found: device_id={device_id} toolset_hash={toolset_hash}"
            )
            return None
        
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"[ToolsetSnapshotsRepo] Failed to insert snapshot: {e}",
                exc_info=True
            )
            return None
    
    async def get_latest_hash(self, device_id: str) -> Optional[str]:
        """
        Get latest toolset hash for device.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Optional[str]: Latest toolset hash or None if no snapshots
        """
        stmt = (
            select(DeviceToolsetSnapshot.toolset_hash)
            .where(DeviceToolsetSnapshot.device_id == device_id)
            .order_by(DeviceToolsetSnapshot.captured_at.desc())
            .limit(1)
        )
        
        result = await self.session.execute(stmt)
        hash_value = result.scalar_one_or_none()
        
        if hash_value:
            logger.debug(
                f"[ToolsetSnapshotsRepo] Latest hash: "
                f"device_id={device_id} hash={hash_value}"
            )
        
        return hash_value
    
    async def get_latest_snapshot(self, device_id: str) -> Optional[DeviceToolsetSnapshot]:
        """Get latest snapshot for device."""
        stmt = (
            select(DeviceToolsetSnapshot)
            .where(DeviceToolsetSnapshot.device_id == device_id)
            .order_by(DeviceToolsetSnapshot.captured_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_hash(
        self,
        device_id: str,
        toolset_hash: str
    ) -> Optional[DeviceToolsetSnapshot]:
        """
        Get snapshot by device_id and toolset_hash.
        
        Args:
            device_id: Device identifier
            toolset_hash: Toolset hash to lookup
            
        Returns:
            Optional[DeviceToolsetSnapshot]: Snapshot or None if not found
        """
        stmt = select(DeviceToolsetSnapshot).where(
            DeviceToolsetSnapshot.device_id == device_id,
            DeviceToolsetSnapshot.toolset_hash == toolset_hash
        )
        
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
