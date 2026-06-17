from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import CustomerHistoryEvent

SENSITIVE_KEY_PARTS = (
    "password",
    "token",
    "cookie",
    "authorization",
    "headers",
    "metadata_json",
    "access_code",
    "pairing_code",
    "pairing_code_hash",
    "poll_secret",
    "session",
    "secret",
    "trace_id",
    "span_attrs",
    "raw_request",
    "raw_response",
)

RAW_ID_KEYS = {
    "person_id",
    "creator_person_id",
    "affected_person_id",
    "device_id",
    "binding_id",
    "target_device_id",
    "target_binding_id",
    "operation_id",
    "trace_id",
}
RAW_CONTEXT_KEYS = {
    "ticket_context",
    "policy_refs",
    "redaction",
    "diagnostic_target_source",
}

REQUESTER_KB_SCOPES = {"public", "requester", "requester_visible", "creator_visible", "creator"}
REQUESTER_KB_AUDIENCE_SCOPES = {"public", "requester", "requester_visible", "creator_visible", "creator"}


@dataclass(slots=True)
class RedactionResult:
    value: Any
    removed_count: int = 0


def _role_key(role: str) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in {"user", "requester"}:
        return "requester"
    if normalized == "llm_preview":
        return "llm"
    if normalized in {"admin", "support", "llm"}:
        return normalized
    return "support"


def _visible(event: CustomerHistoryEvent, role: str) -> bool:
    key = _role_key(role)
    visibility = dict(event.visibility or {})
    if key in visibility:
        return bool(visibility[key])
    if key == "admin":
        return bool(visibility.get("support", True))
    if key == "llm":
        return bool(visibility.get("support", True))
    return True


def _sensitive_key(key: str, *, role: str) -> bool:
    normalized = str(key or "").strip().lower()
    if not normalized:
        return False
    if any(part in normalized for part in SENSITIVE_KEY_PARTS):
        return True
    if _role_key(role) in {"requester", "llm"} and normalized in RAW_CONTEXT_KEYS:
        return True
    if _role_key(role) in {"requester", "llm"} and normalized in RAW_ID_KEYS:
        return True
    if _role_key(role) == "llm" and normalized.endswith("_id"):
        return True
    return False


def _knowledge_attempt_allowed(item: Mapping[str, Any], *, role: str) -> bool:
    key = _role_key(role)
    if key in {"support", "admin"}:
        return True
    visibility_scope = str(item.get("visibility_scope") or "").strip().lower()
    audience_scope = str(item.get("audience_scope") or "").strip().lower()
    if visibility_scope and visibility_scope not in REQUESTER_KB_SCOPES:
        return False
    if audience_scope and audience_scope not in REQUESTER_KB_AUDIENCE_SCOPES:
        return False
    return bool(visibility_scope or audience_scope)


def _sanitize(value: Any, *, role: str, key_path: Iterable[str] = ()) -> RedactionResult:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        removed = 0
        for key, child in value.items():
            key_text = str(key)
            if _sensitive_key(key_text, role=role):
                removed += 1
                continue
            result = _sanitize(child, role=role, key_path=(*key_path, key_text))
            removed += result.removed_count
            if result.value is not None:
                output[key_text] = result.value
        return RedactionResult(output, removed)
    if isinstance(value, list):
        parent_key = str(tuple(key_path)[-1] if tuple(key_path) else "")
        output: list[Any] = []
        removed = 0
        for item in value:
            if parent_key == "knowledge_attempts" and isinstance(item, Mapping):
                if not _knowledge_attempt_allowed(item, role=role):
                    removed += 1
                    continue
            result = _sanitize(item, role=role, key_path=key_path)
            removed += result.removed_count
            if result.value is not None:
                output.append(result.value)
        return RedactionResult(output, removed)
    if isinstance(value, str) and len(value) > 500 and tuple(key_path)[-1:] in {("content",), ("body",), ("raw",)}:
        return RedactionResult(None, 1)
    return RedactionResult(value, 0)


def redact_event_for_role(
    event: CustomerHistoryEvent,
    *,
    role: str,
    mode: str | None = None,
) -> tuple[dict[str, Any] | None, int]:
    key = _role_key(role)
    if not _visible(event, key):
        return None, 1
    sanitized = _sanitize(dict(event.payload or {}), role=key)
    include_raw_ids = key in {"support", "admin"}
    include_refs = bool(event.safe_refs)
    data = event.to_dict(payload=sanitized.value, include_refs=include_refs, include_raw_ids=include_raw_ids)
    if key in {"requester", "llm"}:
        data.pop("event_id", None)
    if mode:
        data["mode"] = mode
    return data, sanitized.removed_count


def redact_for_requester(event: CustomerHistoryEvent) -> dict[str, Any] | None:
    return redact_event_for_role(event, role="requester")[0]


def redact_for_support(event: CustomerHistoryEvent) -> dict[str, Any] | None:
    return redact_event_for_role(event, role="support")[0]


def redact_for_admin(event: CustomerHistoryEvent) -> dict[str, Any] | None:
    return redact_event_for_role(event, role="admin")[0]


def redact_for_llm(event: CustomerHistoryEvent, *, mode: str = "preview") -> dict[str, Any] | None:
    return redact_event_for_role(event, role="llm", mode=mode)[0]
