"""
Storage utilities for module ZIP files.

Provides streaming save/load operations with SHA256 verification.
"""
import hashlib
import shutil
from pathlib import Path
from typing import Tuple, Optional, AsyncIterator
from loguru import logger


async def save_module_zip_from_stream(
    stream: AsyncIterator[bytes],
    module_name: str,
    version: str,
    storage_dir: Path,
    max_size: int,
    chunk_size: int = 8192
) -> Tuple[str, str, int]:
    """
    Сохраняет ZIP модуля на диск атомарно из потока (multipart stream).
    
    КРИТИЧНО: Не держит весь ZIP в памяти. Потоково читает из multipart,
    вычисляет sha256 по кускам и записывает во временный файл.
    
    Args:
        stream: AsyncIterator[bytes] для чтения chunks (из multipart field)
        module_name: Имя модуля
        version: Версия модуля
        storage_dir: Корневая директория для хранения
        max_size: Максимальный размер файла (для проверки)
        chunk_size: Размер chunk для чтения (default 8192)
    
    Returns:
        Tuple[storage_path, sha256, size]
        - storage_path: Относительный путь от storage_dir (например, "custom/1.0.0/module.zip")
        - sha256: SHA256 хеш файла
        - size: Размер файла в байтах
    
    Raises:
        ValueError: Если размер превышает max_size
        OSError: Если не удалось сохранить файл
    """
    # Формируем путь: {module_name}/{version}/module.zip
    module_dir = storage_dir / module_name / version
    module_dir.mkdir(parents=True, exist_ok=True)
    
    # Временный файл для атомарной записи
    temp_path = module_dir / "module.zip.tmp"
    final_path = module_dir / "module.zip"
    
    sha256_hash = hashlib.sha256()
    total_size = 0
    
    try:
        # Потоковое чтение и запись с вычислением sha256
        with open(temp_path, 'wb') as f:
            async for chunk in stream:
                if not chunk:
                    break
                
                # Проверка размера
                total_size += len(chunk)
                if total_size > max_size:
                    raise ValueError(f"File size {total_size} exceeds maximum {max_size}")
                
                # Обновляем sha256
                sha256_hash.update(chunk)
                
                # Записываем chunk во временный файл
                f.write(chunk)
        
        # Финализируем sha256
        sha256_hex = sha256_hash.hexdigest()
        
        # Атомарный rename
        temp_path.rename(final_path)
        
        # Возвращаем относительный путь от storage_dir
        relative_path = f"{module_name}/{version}/module.zip"
        
        logger.info(f"Module saved: {relative_path} (sha256={sha256_hex[:16]}..., size={total_size})")
        return relative_path, sha256_hex, total_size
    
    except Exception as e:
        # Очистка при ошибке
        if temp_path.exists():
            temp_path.unlink()
        raise


async def load_module_zip(
    storage_path: str,
    storage_dir: Path
) -> Optional[bytes]:
    """
    Загружает ZIP модуля с диска.
    
    Args:
        storage_path: Относительный путь от storage_dir
        storage_dir: Корневая директория для хранения
    
    Returns:
        Байты ZIP файла или None если файл не найден
    """
    full_path = storage_dir / storage_path
    
    if not full_path.exists():
        return None
    
    with open(full_path, 'rb') as f:
        return f.read()


async def stream_module_zip(
    storage_path: str,
    storage_dir: Path,
    chunk_size: int = 8192
):
    """
    Генерирует chunks ZIP файла для streaming download.
    
    Args:
        storage_path: Относительный путь от storage_dir
        storage_dir: Корневая директория для хранения
        chunk_size: Размер chunk для чтения
    
    Yields:
        bytes: Chunks файла
    
    Raises:
        FileNotFoundError: Если файл не найден
    """
    full_path = storage_dir / storage_path
    
    if not full_path.exists():
        raise FileNotFoundError(f"Module not found: {storage_path}")
    
    with open(full_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def save_module_zip_bytes(
    zip_bytes: bytes,
    module_name: str,
    version: str,
    storage_dir: Path,
    max_size: int,
) -> Tuple[str, str, int]:
    """
    Сохраняет ZIP модуля на диск из байтов (для create-from-code).

    Returns:
        Tuple[storage_path, sha256, size]
    """
    if len(zip_bytes) > max_size:
        raise ValueError(f"File size {len(zip_bytes)} exceeds maximum {max_size}")
    sha256_hex = hashlib.sha256(zip_bytes).hexdigest()
    module_dir = storage_dir / module_name / version
    module_dir.mkdir(parents=True, exist_ok=True)
    temp_path = module_dir / "module.zip.tmp"
    final_path = module_dir / "module.zip"
    try:
        temp_path.write_bytes(zip_bytes)
        temp_path.rename(final_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise
    relative_path = f"{module_name}/{version}/module.zip"
    logger.info(f"Module saved (bytes): {relative_path} (sha256={sha256_hex[:16]}..., size={len(zip_bytes)})")
    return relative_path, sha256_hex, len(zip_bytes)

