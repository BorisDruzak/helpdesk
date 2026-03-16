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
            - status: "success" | "error" | "consent_required" (гарантированно один из трёх)
            - error: dict с code и message (всегда dict, пустой если нет ошибки)
            - data: dict (всегда dict, пустой если нет данных)
            - meta: dict (всегда dict, пустой если нет meta)
            - is_malformed: bool (флаг битого payload)
    
    Invariants:
        - Всегда возвращает dict с указанными ключами
        - status всегда один из: "success", "error", "consent_required"
        - Входной status "partial" (частичный успех, например upload не удался) нормализуется в "success"
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
    
    # Нормализовать status: success | error | consent_required | partial (partial → success для хранения)
    status = raw_payload.get("status", "unknown")
    if status not in ["success", "error", "consent_required", "partial"]:
        # КРИТИЧНО: Не только "unknown", но ЛЮБАЯ неизвестная строка
        result["is_malformed"] = True
        result["status"] = "error"
        result["error"] = {
            "code": "MALFORMED_RESULT",
            "message": f"Invalid or missing status field: {status!r}. Expected: success, error, consent_required, or partial"
        }
        # Сохраняем остальные поля если есть
        result["data"] = raw_payload.get("data", {}) if isinstance(raw_payload.get("data"), dict) else {}
        result["meta"] = raw_payload.get("meta", {}) if isinstance(raw_payload.get("meta"), dict) else {}
        return result
    
    # partial = частичный успех (например, скриншот снят, но upload не удался); обрабатываем как success
    if status == "partial":
        status = "success"
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
    
    # Нормализовать meta (всегда dict)
    meta_raw = raw_payload.get("meta")
    if isinstance(meta_raw, dict):
        result["meta"] = meta_raw
    else:
        result["meta"] = {}
    
    return result
