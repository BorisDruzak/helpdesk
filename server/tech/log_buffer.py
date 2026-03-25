"""In-memory log buffer for recent warning/error records shown in the tech panel."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Iterable, Optional

_MAX_RECORDS = 500
_RECORDS: deque[dict[str, Any]] = deque(maxlen=_MAX_RECORDS)
_LOCK = Lock()


def _coerce_level_name(level: str) -> str:
    return str(level or "info").strip().lower()


def append_log_record(
    *,
    level: str,
    message: str,
    timestamp: Optional[datetime] = None,
    module: Optional[str] = None,
    function: Optional[str] = None,
    file_path: Optional[str] = None,
    line: Optional[int] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Append a log record to the ring buffer."""
    ts = timestamp or datetime.now(timezone.utc)
    record = {
        "timestamp": ts.isoformat(),
        "level": _coerce_level_name(level),
        "message": str(message or "").strip(),
        "module": module or "",
        "function": function or "",
        "file_path": file_path or "",
        "line": int(line or 0),
        "extra": extra or {},
    }
    with _LOCK:
        _RECORDS.append(record)


def capture_loguru_message(message: Any) -> None:
    """Loguru sink that stores recent warning/error records in memory."""
    try:
        record = message.record
        append_log_record(
            level=record["level"].name,
            message=record["message"],
            timestamp=record["time"].astimezone(timezone.utc),
            module=record.get("module"),
            function=record.get("function"),
            file_path=getattr(record.get("file"), "path", "") if record.get("file") else "",
            line=record.get("line"),
            extra=record.get("extra") or {},
        )
    except Exception:
        # Tech panel logs are best-effort and must never break application logging.
        return


def list_log_records(
    *,
    levels: Optional[Iterable[str]] = None,
    limit: int = 100,
    contains: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Return recent log records, newest first."""
    normalized_levels = None
    if levels is not None:
        normalized_levels = {_coerce_level_name(level) for level in levels}
    contains_text = str(contains or "").strip().lower()

    with _LOCK:
        source = list(_RECORDS)

    result: list[dict[str, Any]] = []
    for item in reversed(source):
        if normalized_levels is not None and item["level"] not in normalized_levels:
            continue
        if contains_text:
            haystack = " ".join(
                [
                    item.get("message", ""),
                    item.get("module", ""),
                    item.get("function", ""),
                    item.get("file_path", ""),
                ]
            ).lower()
            if contains_text not in haystack:
                continue
        result.append(item)
        if len(result) >= max(1, int(limit)):
            break
    return result
