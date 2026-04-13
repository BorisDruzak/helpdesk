from __future__ import annotations

from collections import deque
import sys
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Optional

from loguru import logger


DEFAULT_ROTATION = "20 MB"
DEFAULT_RETENTION = "14 days"
DEFAULT_COMPRESSION = "zip"


class RuntimeLogBuffer:
    """Keeps a bounded in-memory tail for local diagnostics endpoints."""

    def __init__(self, limit: int = 300) -> None:
        self._limit = max(10, int(limit))
        self._lines: Deque[str] = deque(maxlen=self._limit)

    def write(self, message: str) -> None:
        text = str(message).rstrip()
        if text:
            self._lines.append(text)

    def snapshot(self, lines: int = 100) -> list[str]:
        limit = max(1, int(lines))
        if limit >= len(self._lines):
            return list(self._lines)
        return list(self._lines)[-limit:]


def _normalize_level(value: Any, default: str = "INFO") -> str:
    raw = str(value or default).strip().upper()
    allowed = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}
    return raw if raw in allowed else default


def _normalize_optional_string(value: Any, default: str) -> str:
    cleaned = str(value or "").strip()
    return cleaned or default


def resolve_log_file(data_root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return (data_root / path).resolve()


def configure_runtime_logging(
    *,
    data_root: Path,
    logging_config: Any,
    role_name: str,
    memory_buffer: Optional[RuntimeLogBuffer] = None,
) -> Dict[str, Any]:
    """Configures loguru sinks for a long-running runtime process."""

    level = _normalize_level(getattr(logging_config, "level", "INFO"))
    file_relative = str(getattr(logging_config, "file", f"logs/{role_name}.log"))
    rotation = _normalize_optional_string(getattr(logging_config, "rotation", DEFAULT_ROTATION), DEFAULT_ROTATION)
    retention = _normalize_optional_string(getattr(logging_config, "retention", DEFAULT_RETENTION), DEFAULT_RETENTION)
    compression = _normalize_optional_string(
        getattr(logging_config, "compression", DEFAULT_COMPRESSION),
        DEFAULT_COMPRESSION,
    )
    console_level = _normalize_level(getattr(logging_config, "console_level", level), level)
    enqueue_logs = bool(getattr(logging_config, "enqueue", True))

    log_file = resolve_log_file(data_root, file_relative)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        enqueue=enqueue_logs,
    )
    logger.add(
        log_file,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        enqueue=enqueue_logs,
        backtrace=False,
        diagnose=False,
    )
    if memory_buffer is not None:
        logger.add(memory_buffer.write, level=level, format="{time:HH:mm:ss} | {level: <8} | {message}")

    return {
        "level": level,
        "console_level": console_level,
        "file": str(log_file),
        "rotation": rotation,
        "retention": retention,
        "compression": compression,
        "enqueue": enqueue_logs,
        "role_name": role_name,
    }


def read_log_tail(path: Path, lines: int = 200) -> list[str]:
    """Reads the tail of a UTF-8 log file without loading the whole file into memory."""

    limit = max(1, int(lines))
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return list(deque(fh, maxlen=limit))


def format_log_tail(lines: Iterable[str]) -> str:
    return "".join(lines).rstrip()
