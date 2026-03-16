"""
Repository for device_desired_modules table operations (desired state).

Источник истины для reconcile engine: что ДОЛЖНО быть установлено на каждом устройстве.
"""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import DeviceDesiredModule


class DeviceDesiredModulesRepo:
    """Repository for device_desired_modules table (desired state)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_desired(
        self,
        device_id: str,
        module_name: str,
        desired_version: Optional[str],
        state: str = "installed",
        reason: str = "manual",
        desired_sha256: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> DeviceDesiredModule:
        """
        Создаёт или обновляет желаемое состояние модуля.

        state="installed", desired_version=X → хотим модуль версии X.
        state="absent"                        → хотим удалить модуль.
        """
        now = datetime.now(timezone.utc)

        stmt = select(DeviceDesiredModule).where(
            DeviceDesiredModule.device_id == device_id,
            DeviceDesiredModule.module_name == module_name,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.desired_version = desired_version
            existing.desired_sha256 = desired_sha256
            existing.state = state
            existing.reason = reason
            existing.updated_at = now
            existing.updated_by = updated_by
            await self.session.flush()
            return existing
        else:
            desired = DeviceDesiredModule(
                device_id=device_id,
                module_name=module_name,
                desired_version=desired_version,
                desired_sha256=desired_sha256,
                state=state,
                reason=reason,
                updated_at=now,
                updated_by=updated_by,
            )
            self.session.add(desired)
            await self.session.flush()
            return desired

    async def get_desired(
        self,
        device_id: str,
        module_name: Optional[str] = None,
    ) -> List[DeviceDesiredModule]:
        """Получает желаемое состояние для устройства (или конкретного модуля)."""
        stmt = select(DeviceDesiredModule).where(
            DeviceDesiredModule.device_id == device_id
        )
        if module_name:
            stmt = stmt.where(DeviceDesiredModule.module_name == module_name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_desired_one(
        self,
        device_id: str,
        module_name: str,
    ) -> Optional[DeviceDesiredModule]:
        """Получает одну запись desired state."""
        stmt = select(DeviceDesiredModule).where(
            DeviceDesiredModule.device_id == device_id,
            DeviceDesiredModule.module_name == module_name,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_installed_desired(self) -> List[DeviceDesiredModule]:
        """Все записи с state='installed' — для глобального reconcile."""
        stmt = select(DeviceDesiredModule).where(
            DeviceDesiredModule.state == "installed"
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_desired(self, device_id: str, module_name: str) -> bool:
        """Удаляет запись desired (если нужно полностью убрать из учёта)."""
        stmt = delete(DeviceDesiredModule).where(
            DeviceDesiredModule.device_id == device_id,
            DeviceDesiredModule.module_name == module_name,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
