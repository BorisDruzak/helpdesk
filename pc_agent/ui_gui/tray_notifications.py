from __future__ import annotations

from typing import Any


AUTH_BLOCK_ERROR_CODES = {
    "TOKEN_LIMIT_EXCEEDED",
    "DEVICE_FINGERPRINT_MISMATCH",
    "DEVICE_ARCHIVED",
}


def tray_notification_from_event(event: dict[str, Any]) -> tuple[str, str] | None:
    if str(event.get("event_type") or "") != "connection_rejected":
        return None
    data = event.get("data")
    if not isinstance(data, dict):
        data = {}
    error_code = str(data.get("error_code") or "").strip().upper()
    message = str(data.get("message") or data.get("detail") or "").strip()
    if error_code not in AUTH_BLOCK_ERROR_CODES:
        return None
    if error_code == "TOKEN_LIMIT_EXCEEDED":
        title = "Maria Agent: токены устройства"
        fallback = "Сервер отклонил выдачу токена. Откройте админку и проверьте токены устройства."
    elif error_code == "DEVICE_FINGERPRINT_MISMATCH":
        title = "Maria Agent: проверка устройства"
        fallback = "Сервер видит другой аппаратный отпечаток для этого machine_id."
    else:
        title = "Maria Agent: подключение отклонено"
        fallback = "Сервер отклонил подключение агента."
    return title, message or fallback
