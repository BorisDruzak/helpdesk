"""In-memory dismiss state for tech panel alerts."""
from __future__ import annotations

from threading import Lock

_DISMISSED_ALERT_IDS: set[str] = set()
_LOCK = Lock()


def dismiss_alert(alert_id: str) -> None:
    value = str(alert_id or "").strip()
    if not value:
        return
    with _LOCK:
        _DISMISSED_ALERT_IDS.add(value)


def is_alert_dismissed(alert_id: str) -> bool:
    value = str(alert_id or "").strip()
    if not value:
        return False
    with _LOCK:
        return value in _DISMISSED_ALERT_IDS


def clear_dismissed_alerts() -> None:
    with _LOCK:
        _DISMISSED_ALERT_IDS.clear()
