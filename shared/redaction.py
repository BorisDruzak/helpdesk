from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Iterable


REDACTED = "***REDACTED***"
DEFAULT_SENSITIVE_FIELD_MARKERS = {
    "access_token",
    "api_key",
    "auth",
    "authorization",
    "bearer",
    "consent_token",
    "cookie",
    "password",
    "proxy_authorization",
    "refresh_token",
    "secret",
    "session_token",
    "set_cookie",
    "token",
}
SAFE_KEY_MARKERS = {
    "trace_id",
    "ticket_id",
    "device_id",
    "operation_id",
    "message_id",
    "action_id",
    "parent_action_id",
    "request_id",
    "job_id",
}
SAFE_SENSITIVE_SUFFIXES = ("_hash", "_hash_prefix", "_prefix", "_count", "_ms", "_sec")
_BEARER_RE = re.compile(r"^\s*(bearer|token)\s+[a-z0-9._\-]+=*\s*$", re.IGNORECASE)


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return value


def is_sensitive_key(key: Any, *, extra_markers: Iterable[str] | None = None) -> bool:
    key_normalized = str(key or "").strip().lower()
    if not key_normalized:
        return False
    if key_normalized in SAFE_KEY_MARKERS:
        return False
    if any(key_normalized.endswith(suffix) for suffix in SAFE_SENSITIVE_SUFFIXES):
        return False
    markers = set(DEFAULT_SENSITIVE_FIELD_MARKERS)
    if extra_markers:
        markers.update(str(item).strip().lower() for item in extra_markers if str(item or "").strip())
    if key_normalized in markers:
        return True
    if any(marker in key_normalized for marker in markers):
        if "hash" in key_normalized and "token" in key_normalized:
            return False
        if "prefix" in key_normalized and "token" in key_normalized:
            return False
        return True
    return False


def redact_sensitive_payload(
    payload: Any,
    *,
    extra_markers: Iterable[str] | None = None,
    field_name: str | None = None,
) -> Any:
    if payload is None:
        return None
    payload = _normalize_scalar(payload)
    if field_name and is_sensitive_key(field_name, extra_markers=extra_markers):
        return REDACTED
    if isinstance(payload, Mapping):
        return {
            str(key): redact_sensitive_payload(
                value,
                extra_markers=extra_markers,
                field_name=str(key),
            )
            for key, value in payload.items()
        }
    if isinstance(payload, (list, tuple, set)):
        return [
            redact_sensitive_payload(
                item,
                extra_markers=extra_markers,
                field_name=field_name,
            )
            for item in payload
        ]
    if isinstance(payload, str):
        if field_name and is_sensitive_key(field_name, extra_markers=extra_markers):
            return REDACTED
        if _BEARER_RE.match(payload):
            return REDACTED
        return payload
    return payload


def redact_context_scalar(value: Any, *, field_name: str) -> Any:
    normalized = _normalize_scalar(value)
    if is_sensitive_key(field_name):
        return REDACTED if normalized else None
    if isinstance(normalized, str) and _BEARER_RE.match(normalized):
        return REDACTED
    return normalized
