"""
Сервисный класс для загрузки файлов на сервер.

Обеспечивает:
- Валидацию файлов перед отправкой
- Отправку файлов через HTTP multipart/form-data
- Обработку различных статусов ответа
- Детальное логирование процесса загрузки
- Этап 7: 3 попытки с exponential backoff при ServerConnectionError
"""

import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

import aiohttp
from loguru import logger

# Этап 7.1: настройки ретраев
UPLOAD_MAX_RETRIES = 3
UPLOAD_BACKOFF_BASE_SEC = 1.0

from pc_agent.config.config_loader import get_config
from core.identity import IdentityManager


# Маппинг расширений файлов на MIME-типы
MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
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


class FileUploadError(Exception):
    """Базовое исключение для ошибок загрузки файлов."""
    pass


class AuthorizationError(FileUploadError):
    """Ошибка авторизации (401/403)."""
    pass


class ServerConnectionError(FileUploadError):
    """Ошибка соединения с сервером (5xx)."""
    pass


class FileUploader:
    """
    Сервисный класс для загрузки файлов на сервер.
    
    Использует:
    - config.server.api_url для определения endpoint
    - identity_manager.token для авторизации
    
    Пример использования:
        ```python
        from pc_agent.config.config_loader import config
        from core.identity import IdentityManager
        
        identity = IdentityManager()
        identity.load_or_create()
        
        uploader = FileUploader(config=config, identity_manager=identity)
        result = await uploader.upload_file(Path("screenshot.png"))
        print(f"Файл загружен: {result['url']}")
        ```
    """
    
    def __init__(self, config, identity_manager: IdentityManager):
        """
        Инициализация загрузчика файлов.
        
        Args:
            config: Объект конфигурации приложения (Settings)
            identity_manager: Менеджер идентификации агента
        """
        self.config = config
        self.identity_manager = identity_manager
        
        logger.debug("FileUploader инициализирован")
    
    def _detect_content_type(self, file_path: Path) -> str:
        """
        Определяет MIME-тип файла по расширению.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            MIME-тип файла (по умолчанию application/octet-stream)
        """
        ext = file_path.suffix.lower()
        content_type = MIME_MAP.get(ext, "application/octet-stream")
        logger.debug(f"Content-Type для {file_path.name}: {content_type} (расширение: {ext})")
        return content_type
    
    def _normalize_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует ответ сервера к единому формату.
        
        Преобразует ответ к формату {'url': str | None, 'raw': dict}.
        Если сервер вернул {'url': ...} - оставляет как есть.
        Если сервер вернул другое поле (file_url, download_url, link и т.д.) - 
        извлекает его в 'url' и сохраняет оригинал в 'raw'.
        
        Args:
            response_data: Сырой ответ от сервера
            
        Returns:
            Нормализованный ответ с полем 'url' (str | None)
        """
        if not isinstance(response_data, dict):
            logger.warning(f"Ответ сервера не является dict: {type(response_data)}")
            return {'url': None, 'raw': response_data}
        
        # Если уже есть 'url', возвращаем как есть
        if 'url' in response_data:
            url = response_data.get('url')
            # Гарантируем, что url - это str или None
            normalized_url = url if isinstance(url, str) else None
            return {'url': normalized_url, 'raw': response_data}
        
        # Пробуем найти URL в других возможных полях
        url_fields = ['file_url', 'download_url', 'link', 'fileUrl', 'downloadUrl']
        for field in url_fields:
            if field in response_data:
                url = response_data[field]
                normalized_url = url if isinstance(url, str) else None
                logger.debug(f"Найден URL в поле '{field}': {normalized_url}")
                return {'url': normalized_url, 'raw': response_data}
        
        # URL не найден
        logger.warning(f"URL не найден в ответе сервера. Доступные поля: {list(response_data.keys())}")
        return {'url': None, 'raw': response_data}
    
    async def upload_file(
        self,
        file_path: Path,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Загружает файл на сервер с потоковой передачей (без загрузки всего файла в память).

        В multipart при наличии meta передаются ticket_id, operation_id, kind (для артефактов).

        Args:
            file_path: Путь к файлу для загрузки
            meta: Опциональные метаданные: ticket_id, operation_id, kind (для привязки к тикету/операции)

        Returns:
            Dict[str, Any]: Нормализованный ответ с полем 'url' (str | None), 'raw' (оригинальный ответ),
                при успехе сервер может вернуть artifact_id, sha256, mime_type, kind.

        Raises:
            FileNotFoundError: Если файл не существует
            AuthorizationError: Если токен невалидный (401/403)
            ServerConnectionError: Если сервер недоступен (5xx)
            FileUploadError: Для других ошибок загрузки

        Example:
            >>> result = await uploader.upload_file(Path("data/screenshot.png"))
            >>> result = await uploader.upload_file(Path("cap.png"), meta={"ticket_id": "...", "operation_id": "...", "kind": "screenshot"})
        """
        # Валидация: проверяем существование файла
        if not file_path.exists():
            error_msg = f"Файл не найден: {file_path}"
            logger.error(f"❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # Получаем размер файла для логирования
        file_size = file_path.stat().st_size
        
        logger.info(
            f"📤 Начинаю загрузку файла: {file_path.name} "
            f"(Размер: {file_size:,} bytes)"
        )
        
        # Формируем URL endpoint
        upload_url = f"{self.config.server.api_url}/upload"
        logger.debug(f"🔗 URL загрузки: {upload_url}")
        
        # Проверяем наличие токена
        if not self.identity_manager.has_token:
            error_msg = "Токен авторизации отсутствует. Необходимо выполнить вход."
            logger.error(f"❌ {error_msg}")
            raise AuthorizationError(error_msg)
        
        # Формируем заголовки: сервер ожидает заголовок "Bearer <token>"
        token = self.identity_manager.token
        headers = {
            'Authorization': f"Bearer {token}",
        }
        logger.debug(f"🔑 Токен авторизации: {(token or '')[:20]}...")
        
        last_error = None
        for attempt in range(1, UPLOAD_MAX_RETRIES + 1):
            try:
                return await self._do_upload_once(
                    file_path=file_path,
                    upload_url=upload_url,
                    headers=headers,
                    meta=meta,
                )
            except AuthorizationError:
                # Не ретраим авторизацию
                raise
            except FileNotFoundError:
                raise
            except (ServerConnectionError, aiohttp.ClientError) as e:
                last_error = e
                if attempt < UPLOAD_MAX_RETRIES:
                    delay = UPLOAD_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                    logger.warning(
                        f"⚠️  Попытка {attempt}/{UPLOAD_MAX_RETRIES} не удалась: {e}. "
                        f"Повтор через {delay:.1f} с..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Все {UPLOAD_MAX_RETRIES} попытки загрузки исчерпаны")
                    raise last_error from e
            except Exception:
                raise
    
    async def _do_upload_once(
        self,
        file_path: Path,
        upload_url: str,
        headers: Dict[str, str],
        meta: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Одна попытка загрузки файла (используется в retry-цикле)."""
        content_type = self._detect_content_type(file_path)
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as file:
                    data = aiohttp.FormData()
                    data.add_field(
                        'file',
                        file,
                        filename=file_path.name,
                        content_type=content_type
                    )
                    if meta:
                        if meta.get('ticket_id'):
                            data.add_field('ticket_id', str(meta['ticket_id']))
                        if meta.get('operation_id'):
                            data.add_field('operation_id', str(meta['operation_id']))
                        if meta.get('kind'):
                            data.add_field('kind', str(meta['kind']))

                    logger.debug(
                        f"📦 FormData: file='{file_path.name}', content_type='{content_type}'"
                        + (f", meta={list(meta.keys())}" if meta else "")
                    )
                    
                    async with session.post(
                        upload_url,
                        data=data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        status = response.status
                        logger.debug(f"📨 Получен ответ от сервера: статус {status}")
                        
                        if status == 200:
                            raw_result = await response.json()
                            normalized_result = self._normalize_response(raw_result)
                            file_url = normalized_result.get('url', None)
                            logger.success(
                                f"✅ Файл успешно загружен: {file_path.name}\n"
                                f"   URL: {file_url or 'N/A'}"
                            )
                            return normalized_result
                        
                        elif status in (401, 403):
                            error_text = await response.text()
                            error_msg = (
                                f"Ошибка авторизации (статус {status}). "
                                f"Токен возможно истек или невалидный."
                            )
                            logger.error(f"🔒 {error_msg}")
                            logger.debug(f"   Ответ сервера: {error_text}")
                            raise AuthorizationError(error_msg)
                        
                        elif 500 <= status < 600:
                            error_text = await response.text()
                            error_msg = (
                                f"Ошибка сервера (статус {status}). "
                                f"Сервер временно недоступен."
                            )
                            logger.error(f"🔥 {error_msg}")
                            logger.debug(f"   Ответ сервера: {error_text}")
                            raise ServerConnectionError(error_msg)
                        
                        else:
                            error_text = await response.text()
                            error_msg = f"Неожиданный статус ответа: {status}"
                            logger.error(f"❌ {error_msg}")
                            logger.debug(f"   Ответ сервера: {error_text}")
                            raise FileUploadError(f"{error_msg}. Ответ: {error_text}")
        
        except aiohttp.ClientError as e:
            error_msg = f"Ошибка соединения с сервером: {e}"
            logger.error(f"🌐 {error_msg}")
            raise ServerConnectionError(error_msg) from e
    
    async def upload_multiple(
        self, 
        file_paths: list[Path],
        stop_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Загружает несколько файлов на сервер.
        
        Args:
            file_paths: Список путей к файлам для загрузки
            stop_on_error: Прервать загрузку при первой ошибке (по умолчанию False)
            
        Returns:
            Dict[str, Any]: Результаты загрузки
            {
                'successful': [{'file': 'file1.png', 'result': {...}}, ...],
                'failed': [{'file': 'file2.png', 'error': '...'}, ...],
                'total': 10,
                'success_count': 8,
                'failed_count': 2
            }
            
        Example:
            >>> files = [Path("file1.png"), Path("file2.png"), Path("file3.png")]
            >>> results = await uploader.upload_multiple(files)
            >>> print(f"Загружено: {results['success_count']}/{results['total']}")
        """
        logger.info(f"📤 Начинаю пакетную загрузку: {len(file_paths)} файлов")
        
        successful = []
        failed = []
        
        for idx, file_path in enumerate(file_paths, start=1):
            logger.debug(f"[{idx}/{len(file_paths)}] Обрабатываю: {file_path.name}")
            
            try:
                result = await self.upload_file(file_path)
                successful.append({
                    'file': str(file_path),
                    'result': result
                })
                
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"
                failed.append({
                    'file': str(file_path),
                    'error': error_msg
                })
                
                logger.warning(f"⚠️  Ошибка загрузки {file_path.name}: {error_msg}")
                
                if stop_on_error:
                    logger.error("🛑 Прерываю загрузку из-за ошибки (stop_on_error=True)")
                    break
        
        summary = {
            'successful': successful,
            'failed': failed,
            'total': len(file_paths),
            'success_count': len(successful),
            'failed_count': len(failed)
        }
        
        logger.success(
            f"✅ Пакетная загрузка завершена: "
            f"{summary['success_count']}/{summary['total']} файлов успешно"
        )
        
        if failed:
            logger.warning(f"⚠️  Неудачных загрузок: {summary['failed_count']}")
        
        return summary


# Создание глобального экземпляра (опционально)
_uploader_instance: Optional[FileUploader] = None


def get_uploader(identity_manager: Optional[IdentityManager] = None) -> FileUploader:
    """
    Получает глобальный экземпляр FileUploader (Singleton).
    
    Args:
        identity_manager: Менеджер идентификации (обязателен при первом вызове)
        
    Returns:
        FileUploader: Глобальный экземпляр загрузчика
        
    Raises:
        ValueError: Если identity_manager не передан при первом вызове
        
    Example:
        >>> from core.identity import IdentityManager
        >>> identity = IdentityManager()
        >>> identity.load_or_create()
        >>> 
        >>> # Первый вызов - инициализация
        >>> uploader = get_uploader(identity)
        >>> 
        >>> # Последующие вызовы - возвращает тот же экземпляр
        >>> uploader2 = get_uploader()
        >>> assert uploader is uploader2
    """
    global _uploader_instance
    
    if _uploader_instance is None:
        if identity_manager is None:
            raise ValueError(
                "При первом вызове get_uploader() необходимо передать identity_manager"
            )
        
        _uploader_instance = FileUploader(
            config=get_config(),
            identity_manager=identity_manager
        )
        
        logger.debug("🌍 Создан глобальный экземпляр FileUploader")
    
    return _uploader_instance

