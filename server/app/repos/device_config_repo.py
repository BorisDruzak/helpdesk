"""
Device configuration repository.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import DeviceConfig


class DeviceConfigRepo:
    """Repository for device configuration operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_create_default(self, device_id: str) -> DeviceConfig:
        """
        Get device config or create with default values.
        
        Args:
            device_id: Device identifier
            
        Returns:
            DeviceConfig: Existing or newly created config
        """
        # Try to get existing config
        stmt = select(DeviceConfig).where(DeviceConfig.device_id == device_id)
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()
        
        if config:
            logger.debug(f"[DeviceConfigRepo] Found config: device_id={device_id}")
            return config
        
        # Create default config
        now = datetime.now(timezone.utc)
        config = DeviceConfig(
            device_id=device_id,
            desired_revision=0,
            desired_config={},
            updated_at=now
        )
        self.session.add(config)
        await self.session.flush()
        
        logger.info(
            f"[DeviceConfigRepo] Created default config: device_id={device_id}"
        )
        return config
    
    async def get_desired(self, device_id: str) -> Optional[DeviceConfig]:
        """
        Get device config.
        
        Args:
            device_id: Device identifier
            
        Returns:
            Optional[DeviceConfig]: Config or None if not found
        """
        stmt = select(DeviceConfig).where(DeviceConfig.device_id == device_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def mark_applied(
        self,
        device_id: str,
        revision: int,
        status: str,
        error: Optional[dict] = None
    ) -> bool:
        """
        Mark configuration as applied.
        
        Args:
            device_id: Device identifier
            revision: Applied revision number
            status: Apply status (e.g., "success", "error")
            error: Optional error details
            
        Returns:
            bool: True if updated, False if not found
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceConfig)
            .where(DeviceConfig.device_id == device_id)
            .values(
                applied_revision=revision,
                applied_at=now,
                last_apply_status=status,
                last_apply_error=error,
                updated_at=now
            )
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount > 0:
            logger.info(
                f"[DeviceConfigRepo] Marked config applied: "
                f"device_id={device_id} revision={revision} status={status}"
            )
            return True
        
        logger.warning(
            f"[DeviceConfigRepo] Config not found for mark_applied: "
            f"device_id={device_id}"
        )
        return False
    
    async def update_desired(
        self,
        device_id: str,
        revision: int,
        config: dict
    ) -> bool:
        """
        Update desired configuration.
        
        Args:
            device_id: Device identifier
            revision: New revision number
            config: New desired configuration
            
        Returns:
            bool: True if updated, False if not found
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceConfig)
            .where(DeviceConfig.device_id == device_id)
            .values(
                desired_revision=revision,
                desired_config=config,
                updated_at=now
            )
        )
        
        result = await self.session.execute(stmt)
        
        if result.rowcount > 0:
            logger.info(
                f"[DeviceConfigRepo] Updated desired config: "
                f"device_id={device_id} revision={revision}"
            )
            return True
        
        logger.warning(
            f"[DeviceConfigRepo] Config not found for update_desired: "
            f"device_id={device_id}"
        )
        return False
