"""
Repository for modules table operations.
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.db.models import Module


class ModulesRepo:
    """Repository for modules table."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_module(
        self,
        module_name: str,
        version: str,
        sha256: str,
        size: int,
        storage_path: str,
        uploaded_by: str,
        manifest_json: Optional[dict] = None,
        validation_json: Optional[dict] = None,
        manifest_summary: Optional[dict] = None
    ) -> Module:
        """
        Создает запись о модуле в БД.
        
        КРИТИЧНО: (module_name, version) - составной PK, уникален.
        При попытке создать дубликат - IntegrityError.
        
        Raises:
            IntegrityError: Если (module_name, version) уже существует
        """
        module = Module(
            module_name=module_name,
            version=version,
            sha256=sha256,
            size=size,
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            manifest_json=manifest_json,
            validation_json=validation_json,
            manifest_summary=manifest_summary
        )
        self.session.add(module)
        try:
            await self.session.flush()
            return module
        except IntegrityError:
            await self.session.rollback()
            raise
    
    async def get_module(
        self,
        module_name: str,
        version: str
    ) -> Optional[Module]:
        """Получает модуль по имени и версии."""
        stmt = select(Module).where(
            Module.module_name == module_name,
            Module.version == version
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_module_by_sha256(
        self,
        sha256: str
    ) -> Optional[Module]:
        """Получает модуль по sha256."""
        stmt = select(Module).where(Module.sha256 == sha256)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def list_modules(
        self,
        module_name: Optional[str] = None,
        limit: int = 100
    ) -> List[Module]:
        """
        Список модулей с опциональной фильтрацией.
        
        Args:
            module_name: Фильтр по имени модуля (optional)
            limit: Максимальное количество результатов
        
        Returns:
            Список модулей, отсортированный по created_at DESC
        """
        stmt = select(Module)
        
        if module_name:
            stmt = stmt.where(Module.module_name == module_name)
        
        stmt = stmt.order_by(Module.created_at.desc()).limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_module(
        self,
        module_name: str,
        version: str
    ) -> bool:
        """
        Удаляет запись о модуле из БД по имени и версии.
        Возвращает True если запись была удалена, False если не найдена.
        Файл на диске вызывающий код должен удалить отдельно.
        """
        module = await self.get_module(module_name, version)
        if not module:
            return False
        await self.session.delete(module)
        await self.session.flush()
        return True

