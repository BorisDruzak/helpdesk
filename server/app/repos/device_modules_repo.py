"""
Repository for device_modules table operations.
"""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.db.models import DeviceModule


class DeviceModulesRepo:
    """Repository for device_modules table."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_device_module(
        self,
        device_id: str,
        module_name: str,
        version: str,
        installed: bool = False,
        active: bool = False,
        state: str = "installed",
        last_error_code: Optional[str] = None,
        last_error_message: Optional[str] = None,
        source: Optional[str] = None,
        update_last_seen: bool = False,
    ) -> DeviceModule:
        """
        Создает или обновляет запись о модуле на устройстве.

        source: handshake|command_result|event — источник обновления.
        update_last_seen: если True, обновляет last_seen_at = now (только когда installed=True).
        """
        now = datetime.now(timezone.utc)
        
        stmt = select(DeviceModule).where(
            DeviceModule.device_id == device_id,
            DeviceModule.module_name == module_name,
            DeviceModule.version == version
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.installed = installed
            existing.active = active
            existing.state = state
            existing.last_error_code = last_error_code
            existing.last_error_message = last_error_message
            existing.last_updated_at = now
            if source:
                existing.source = source
            if installed and not existing.installed_at:
                existing.installed_at = now
            if active and not existing.activated_at:
                existing.activated_at = now
            if update_last_seen and installed:
                existing.last_seen_at = now
            await self.session.flush()
            return existing
        else:
            device_module = DeviceModule(
                device_id=device_id,
                module_name=module_name,
                version=version,
                installed=installed,
                active=active,
                state=state,
                installed_at=now if installed else None,
                activated_at=now if active else None,
                last_error_code=last_error_code,
                last_error_message=last_error_message,
                last_updated_at=now,
                source=source,
                last_seen_at=now if (installed and update_last_seen) else None,
            )
            self.session.add(device_module)
            await self.session.flush()
            return device_module
    
    async def get_device_modules(
        self,
        device_id: str,
        active_only: bool = False
    ) -> List[DeviceModule]:
        """
        Получает список модулей устройства.
        
        Args:
            device_id: ID устройства
            active_only: Если True, возвращает только активные модули
        
        Returns:
            Список модулей устройства
        """
        stmt = select(DeviceModule).where(DeviceModule.device_id == device_id)
        
        if active_only:
            stmt = stmt.where(DeviceModule.active == True)
        
        stmt = stmt.order_by(DeviceModule.module_name, DeviceModule.version)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_installed(
        self,
        device_id: str,
        module_name: str,
        version: str
    ) -> bool:
        """
        Отмечает модуль как установленный.
        
        Returns:
            True если обновление успешно, False если запись не найдена
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name,
                DeviceModule.version == version
            )
            .values(
                installed=True,
                installed_at=now,
                last_updated_at=now
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def mark_active(
        self,
        device_id: str,
        module_name: str,
        version: str,
        active: bool = True
    ) -> bool:
        """
        Отмечает модуль как активный/неактивный.
        
        Args:
            device_id: ID устройства
            module_name: Имя модуля
            version: Версия модуля
            active: True для активации, False для деактивации
        
        Returns:
            True если обновление успешно, False если запись не найдена
        """
        now = datetime.now(timezone.utc)
        
        values = {
            "active": active,
            "last_updated_at": now
        }
        
        if active:
            values["activated_at"] = now
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name,
                DeviceModule.version == version
            )
            .values(**values)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def mark_error(
        self,
        device_id: str,
        module_name: str,
        version: str,
        error_code: str,
        error_message: str
    ) -> bool:
        """
        Сохраняет ошибку установки/активации.
        
        Args:
            device_id: ID устройства
            module_name: Имя модуля
            version: Версия модуля
            error_code: Код ошибки
            error_message: Сообщение об ошибке
        
        Returns:
            True если обновление успешно, False если запись не найдена
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name,
                DeviceModule.version == version
            )
            .values(
                state="failed",
                last_error_code=error_code,
                last_error_message=error_message,
                last_updated_at=now
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def update_module_state(
        self,
        device_id: str,
        module_name: str,
        version: str,
        installed: bool,
        active: bool,
        state: str
    ) -> bool:
        """
        Обновляет состояние модуля (для синхронизации inventory).
        
        Args:
            device_id: ID устройства
            module_name: Имя модуля
            version: Версия модуля
            installed: Установлен ли модуль
            active: Активен ли модуль
            state: Состояние модуля (installed/active/missing/removed)
        
        Returns:
            True если обновление успешно, False если запись не найдена
        """
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name,
                DeviceModule.version == version
            )
            .values(
                installed=installed,
                active=active,
                state=state,
                last_updated_at=now
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def get_active_modules(self, device_id: str) -> List[DeviceModule]:
        """Get all active modules for device."""
        stmt = (
            select(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.active == True
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_removed(
        self,
        device_id: str,
        module_name: str,
        version: str
    ) -> bool:
        """Mark version as removed (installed=False)."""
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name,
                DeviceModule.version == version
            )
            .values(installed=False, active=False, state="removed", last_updated_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0
    
    async def mark_module_removed(
        self,
        device_id: str,
        module_name: str
    ) -> bool:
        """Mark all versions of module as removed."""
        now = datetime.now(timezone.utc)
        
        stmt = (
            update(DeviceModule)
            .where(
                DeviceModule.device_id == device_id,
                DeviceModule.module_name == module_name
            )
            .values(installed=False, active=False, state="removed", last_updated_at=now)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        
        return result.rowcount > 0

