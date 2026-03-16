"""
Repository for artifacts table (uploaded files: screenshots, screen recordings).
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact


class ArtifactsRepo:
    """Repository for artifacts table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        artifact_id: str,
        storage_path: str,
        original_name: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        device_id: str,
        kind: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> Artifact:
        """
        Создаёт запись об артефакте.

        Returns:
            Созданный объект Artifact
        """
        artifact = Artifact(
            artifact_id=artifact_id,
            storage_path=storage_path,
            original_name=original_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            kind=kind,
            device_id=device_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            expires_at=expires_at,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def get_by_id(self, artifact_id: str) -> Optional[Artifact]:
        """Получает артефакт по идентификатору."""
        stmt = select(Artifact).where(Artifact.artifact_id == artifact_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_sha256_and_operation_id(
        self, sha256: str, operation_id: str
    ) -> Optional[Artifact]:
        """
        Этап 7.3: идемпотентность upload — при повторе (тот же sha256 и operation_id)
        возвращаем существующий артефакт.
        """
        stmt = select(Artifact).where(
            Artifact.sha256 == sha256,
            Artifact.operation_id == operation_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_expired(self) -> List[Artifact]:
        """
        Удаляет записи с expires_at < NOW() и возвращает список удалённых артефактов
        (чтобы вызывающий код мог удалить файлы с диска).
        """
        now = datetime.now(timezone.utc)
        stmt = select(Artifact).where(Artifact.expires_at.isnot(None), Artifact.expires_at < now)
        result = await self.session.execute(stmt)
        expired = list(result.scalars().all())
        for a in expired:
            await self.session.delete(a)
        await self.session.flush()
        return expired
