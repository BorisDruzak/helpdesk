"""
Command Result Parser and Normalizer

Provides normalization of command_result payload to ensure consistent
structure and type guarantees.
"""

from typing import Any, Dict


def normalize_command_result_payload(raw_payload: Any) -> Dict[str, Any]:
    """
    Нормализует payload command_result в единый формат с гарантированными ключами.
    
    Args:
        raw_payload: Сырой payload от агента (может быть None, не dict, или dict)
    
    Returns:
        dict с ключами:
            - status: normalized lifecycle-compatible status
            - error: dict с code и message (всегда dict, пустой если нет ошибки)
            - data: dict (всегда dict, пустой если нет данных)
            - meta: dict (всегда dict, пустой если нет meta)
            - is_malformed: bool (флаг битого payload)
    
    Invariants:
        - Всегда возвращает dict с указанными ключами
        - status всегда один из поддерживаемых pipeline-статусов
        - Входной status "partial" сохраняется как partial, чтобы lifecycle/UI не показывали полный успех
        - Любой другой неизвестный status → "error" + is_malformed=True
        - None или не-dict payload → "error" + is_malformed=True
    """
    result = {
        "status": "error",  # По умолчанию error
        "error": {},
        "data": {},
        "meta": {},
        "is_malformed": False
    }
    
    # Если payload is None → malformed
    if raw_payload is None:
        result["is_malformed"] = True
        result["error"] = {
            "code": "MALFORMED_RESULT",
            "message": "Command result payload is None"
        }
        return result
    
    # Если payload не dict → malformed
    if not isinstance(raw_payload, dict):
        result["is_malformed"] = True
        result["error"] = {
            "code": "MALFORMED_RESULT",
            "message": f"Command result payload is not a dict: {type(raw_payload).__name__}"
        }
        return result
    
    # Нормализовать status.
    status = raw_payload.get("status", "unknown")
    allowed_statuses = {
        "success",
        "error",
        "consent_required",
        "partial",
        "queued",
        "sent",
        "accepted",
        "running",
        "waiting_consent",
        "succeeded",
        "failed",
        "canceled",
        "cancel_requested",
    }
    if status not in allowed_statuses:
        # КРИТИЧНО: Не только "unknown", но ЛЮБАЯ неизвестная строка
        result["is_malformed"] = True
        result["status"] = "error"
        result["error"] = {
            "code": "MALFORMED_RESULT",
                "message": f"Invalid or missing status field: {status!r}. Expected one of {sorted(allowed_statuses)}"
        }
        # Сохраняем остальные поля если есть
        result["data"] = raw_payload.get("data", {}) if isinstance(raw_payload.get("data"), dict) else {}
        result["meta"] = raw_payload.get("meta", {}) if isinstance(raw_payload.get("meta"), dict) else {}
        return result
    
    result["status"] = status

    # Нормализовать error (всегда dict)
    error_raw = raw_payload.get("error")
    if isinstance(error_raw, dict):
        result["error"] = error_raw
        # Единый контракт consent: status=error + error.code=CONSENT_REQUIRED → consent_required
        if status == "error" and error_raw.get("code") == "CONSENT_REQUIRED":
            result["status"] = "consent_required"
    else:
        result["error"] = {}
    
    # Нормализовать data (всегда dict)
    data_raw = raw_payload.get("data")
    if isinstance(data_raw, dict):
        result["data"] = data_raw
    else:
        result["data"] = {}

    if result["status"] == "partial" and not result["error"]:
        errors = result["data"].get("errors")
        first_error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
        result["error"] = {
            "code": first_error.get("code") or "PARTIAL_RESULT",
            "message": first_error.get("message") or "Command completed with partial result",
        }
        if first_error.get("details") is not None:
            result["error"]["details"] = first_error.get("details")
    
    # Нормализовать meta (всегда dict)
    meta_raw = raw_payload.get("meta")
    if isinstance(meta_raw, dict):
        result["meta"] = meta_raw
    else:
        result["meta"] = {}
    
    return result
