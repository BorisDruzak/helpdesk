"""
Универсальный пайплайн управления артефактами.

Обеспечивает:
- Описание намерений загрузки артефактов через ArtifactIntent
- Загрузку артефактов через ArtifactManager
- Вычисление метаданных (размер, SHA256, MIME)
- Обработку ошибок с сохранением частичных результатов
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from core.tool_response import ArtifactDescriptor, ErrorInfo
from network.uploader import FileUploader


@dataclass
class ArtifactIntent:
    """Намерение загрузки артефакта."""
    
    local_path: Path
    name: str | None = None
    mime: str | None = None
    kind: str | None = None  # например "screenshot", "log", "dump"
    ttl_seconds: int | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ArtifactManager:
    """
    Менеджер артефактов для загрузки файлов на сервер.
    
    Обеспечивает:
    - Валидацию файлов перед загрузкой
    - Вычисление метаданных (размер, SHA256, MIME)
    - Загрузку через FileUploader
    - Обработку ошибок с сохранением частичных результатов
    
    Пример использования:
        ```python
        from network.uploader import FileUploader
        from core.identity import IdentityManager
        from pc_agent.config.config_loader import get_config
        config = get_config()
        
        identity = IdentityManager()
        identity.load_or_create()
        
        uploader = FileUploader(config=config, identity_manager=identity)
        manager = ArtifactManager(uploader=uploader)
        
        intent = ArtifactIntent(
            local_path=Path("screenshot.png"),
            name="screenshot_001",
            kind="screenshot",
            ttl_seconds=3600
        )
        
        descriptor = await manager.upload(intent)
        print(f"Артефакт загружен: {descriptor.url}")
        ```
    """
    
    # Маппинг расширений файлов на MIME-типы
    MIME_MAP = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".zip": "application/zip",
        ".tar": "application/x-tar",
        ".gz": "application/gzip",
        ".log": "text/plain",
        ".txt": "text/plain",
        ".json": "application/json",
        ".xml": "application/xml",
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".csv": "text/csv",
        ".mp4": "video/mp4",
    }
    
    def __init__(self, uploader: FileUploader):
        """
        Инициализация менеджера артефактов.
        
        Args:
            uploader: Загрузчик файлов для отправки на сервер
        """
        self.uploader = uploader
        logger.debug("ArtifactManager инициализирован")
    
    def _compute_sha256(self, file_path: Path) -> str:
        """
        Вычисляет SHA256 хеш файла стримингом по чанкам.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            SHA256 хеш в hex формате
        """
        sha256_hash = hashlib.sha256()
        chunk_size = 8192  # 8KB chunks
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    def _detect_mime(self, intent: ArtifactIntent) -> str:
        """
        Определяет MIME-тип файла.
        
        Приоритет:
        1. intent.mime (если задан)
        2. По расширению файла из MIME_MAP
        3. application/octet-stream (по умолчанию)
        
        Args:
            intent: Намерение загрузки артефакта
            
        Returns:
            MIME-тип файла
        """
        # Если MIME задан явно, используем его
        if intent.mime:
            return intent.mime
        
        # Определяем по расширению
        ext = intent.local_path.suffix.lower()
        mime = self.MIME_MAP.get(ext, "application/octet-stream")
        
        logger.debug(f"MIME для {intent.local_path.name}: {mime} (расширение: {ext})")
        return mime
    
    async def upload(self, intent: ArtifactIntent) -> ArtifactDescriptor:
        """
        Загружает артефакт на сервер.
        
        Args:
            intent: Намерение загрузки артефакта
            
        Returns:
            ArtifactDescriptor с метаданными загруженного артефакта
            
        Raises:
            FileNotFoundError: Если файл не существует
            Exception: Другие ошибки загрузки (пробрасываются из uploader)
        """
        # Проверяем существование файла
        if not intent.local_path.exists():
            error_msg = f"Файл не найден: {intent.local_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Вычисляем размер файла
        size_bytes = intent.local_path.stat().st_size
        logger.debug(f"Размер файла {intent.local_path.name}: {size_bytes:,} bytes")
        
        # Вычисляем SHA256
        logger.debug(f"Вычисляю SHA256 для {intent.local_path.name}...")
        sha256 = self._compute_sha256(intent.local_path)
        logger.debug(f"SHA256: {sha256}")
        
        # Определяем MIME-тип
        mime = self._detect_mime(intent)
        
        # Загружаем файл через uploader (передаём meta для ticket_id, operation_id, kind)
        logger.info(f"📤 Загружаю артефакт: {intent.local_path.name}")
        meta = dict(intent.meta) if intent.meta else {}
        if intent.kind:
            meta["kind"] = intent.kind
        result = await self.uploader.upload_file(intent.local_path, meta=meta if meta else None)
        
        raw = result.get("raw", result) if isinstance(result, dict) else {}
        url = result.get("url") if isinstance(result, dict) else None
        artifact_id = raw.get("artifact_id") if isinstance(raw, dict) else None
        kind_from_server = raw.get("kind") if isinstance(raw, dict) else None
        expires_at_str = raw.get("expires_at") if isinstance(raw, dict) else None
        
        name = intent.name or intent.local_path.name
        
        descriptor = ArtifactDescriptor(
            artifact_id=artifact_id,
            name=name,
            mime=mime,
            size_bytes=size_bytes,
            sha256=sha256,
            url=url,
            local_path=str(intent.local_path),
            ttl_seconds=intent.ttl_seconds,
            kind=kind_from_server or intent.kind,
            expires_at=expires_at_str,
        )
        
        logger.success(
            f"✅ Артефакт загружен: {name}\n"
            f"   URL: {url or 'N/A'}\n"
            f"   Размер: {size_bytes:,} bytes\n"
            f"   MIME: {mime}"
        )
        
        return descriptor
    
    async def upload_many(
        self, 
        intents: list[ArtifactIntent]
    ) -> tuple[list[ArtifactDescriptor], list[ErrorInfo]]:
        """
        Загружает несколько артефактов последовательно.
        
        Ошибки не прерывают процесс: собираются в список ErrorInfo.
        
        Args:
            intents: Список намерений загрузки артефактов
            
        Returns:
            Кортеж (список успешно загруженных дескрипторов, список ошибок)
        """
        logger.info(f"📤 Начинаю пакетную загрузку: {len(intents)} артефактов")
        
        descriptors: list[ArtifactDescriptor] = []
        errors: list[ErrorInfo] = []
        
        for idx, intent in enumerate(intents, start=1):
            logger.debug(f"[{idx}/{len(intents)}] Обрабатываю: {intent.local_path.name}")
            
            try:
                descriptor = await self.upload(intent)
                descriptors.append(descriptor)
                
            except Exception as e:
                # Собираем информацию об ошибке
                error_info = ErrorInfo(
                    code="ARTIFACT_UPLOAD_FAILED",
                    message=f"Ошибка загрузки артефакта: {e}",
                    details={
                        "path": str(intent.local_path),
                        "kind": intent.kind,
                        "exc_type": type(e).__name__,
                        "exc_message": str(e)
                    },
                    retriable=True
                )
                errors.append(error_info)
                
                logger.warning(
                    f"⚠️  Ошибка загрузки {intent.local_path.name}: "
                    f"{type(e).__name__}: {e}"
                )
        
        logger.success(
            f"✅ Пакетная загрузка завершена: "
            f"{len(descriptors)}/{len(intents)} артефактов успешно"
        )
        
        if errors:
            logger.warning(f"⚠️  Неудачных загрузок: {len(errors)}")
        
        return descriptors, errors

