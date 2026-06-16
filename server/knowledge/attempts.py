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

ALLOWED_VISIBILITY_SCOPES = {"creator_visible", "support_only"}
ALLOWED_AUDIENCE_SCOPES = {"creator", "affected_context", "support"}
ALLOWED_ATTEMPT_SURFACES = {"requester_portal", "agent_gui", "support_workspace"}


def _default_visibility_scope(surface: str) -> str:
    return "support_only" if surface == "support_workspace" else "creator_visible"


def _default_audience_scope(surface: str) -> str:
    return "support" if surface == "support_workspace" else "creator"


def _normalize_surface(surface: str) -> str:
    surface_value = str(surface or "").strip()
    return surface_value if surface_value in ALLOWED_ATTEMPT_SURFACES else "requester_portal"


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
        attempt_surface = _normalize_surface(surface)
        if attempt_surface == "support_workspace":
            visibility_scope = str(raw.get("visibility_scope") or "").strip()
            if visibility_scope not in ALLOWED_VISIBILITY_SCOPES:
                visibility_scope = _default_visibility_scope(attempt_surface)
            audience_scope = str(raw.get("audience_scope") or "").strip()
            if audience_scope not in ALLOWED_AUDIENCE_SCOPES:
                audience_scope = _default_audience_scope(attempt_surface)
        else:
            visibility_scope = "creator_visible"
            audience_scope = "creator"
        occurred_at = str(raw.get("occurred_at") or raw.get("timestamp") or "").strip()
        sanitized.append(
            {
                "item_id": item_id,
                "version_id": str(raw.get("version_id") or "").strip() or None,
                "result": result,
                "surface": attempt_surface,
                "visibility_scope": visibility_scope,
                "audience_scope": audience_scope,
                "occurred_at": occurred_at or datetime.now(timezone.utc).isoformat(),
            }
        )
    return sanitized


def attach_knowledge_attempts(custom_fields: Any, attempts: list[dict[str, Any]]) -> dict[str, Any]:
    result = dict(custom_fields or {}) if isinstance(custom_fields, dict) else {}
    if attempts:
        result["knowledge_attempts"] = attempts
    return result
