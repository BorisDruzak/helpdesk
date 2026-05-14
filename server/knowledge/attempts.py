from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ALLOWED_KNOWLEDGE_ATTEMPT_RESULTS = {
    "suggested",
    "viewed",
    "helpful",
    "not_helpful",
    "deflected",
    "skipped",
    "ticket_created_after_view",
}

MAX_KNOWLEDGE_ATTEMPTS = 20


def sanitize_knowledge_attempts(raw_attempts: Any, *, surface: str) -> list[dict[str, Any]]:
    if not isinstance(raw_attempts, list):
        return []
    sanitized: list[dict[str, Any]] = []
    for raw in raw_attempts[:MAX_KNOWLEDGE_ATTEMPTS]:
        if not isinstance(raw, dict):
            continue
        item_id = str(raw.get("item_id") or "").strip()
        if not item_id:
            continue
        result = str(raw.get("result") or raw.get("event_type") or "viewed").strip()
        if result not in ALLOWED_KNOWLEDGE_ATTEMPT_RESULTS:
            result = "viewed"
        occurred_at = str(raw.get("occurred_at") or raw.get("timestamp") or "").strip()
        sanitized.append(
            {
                "item_id": item_id,
                "version_id": str(raw.get("version_id") or "").strip() or None,
                "result": result,
                "surface": str(raw.get("surface") or surface).strip() or surface,
                "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
            }
        )
    return sanitized


def attach_knowledge_attempts(custom_fields: Any, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(custom_fields or {}) if isinstance(custom_fields, dict) else {}
    if attempts:
        result["knowledge_attempts"] = attempts
    return result
