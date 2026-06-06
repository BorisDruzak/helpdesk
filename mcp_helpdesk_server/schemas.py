from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shared.redaction import redact_sensitive_payload

from .manifest import TOOL_NAMES

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_PRESENCE_LIMIT = 200
MAX_STRING_LENGTH = 2000
MAX_DEPTH = 8
MAX_LIST_ITEMS = 100


def object_schema(properties: dict[str, Any] | None = None, required: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "helpdesk_db_health": object_schema(),
    "helpdesk_context_search": object_schema(
        {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            "kind": {"type": "string", "enum": ["doc", "topic", "route", "symbol", "test"]},
            "profile": {
                "type": "string",
                "enum": ["default", "debug", "contract", "route", "test", "web"],
                "default": "default",
            },
        },
        ["query"],
    ),
    "helpdesk_context_freshness": object_schema(),
    "helpdesk_locate": object_schema(
        {
            "q": {"type": "string"},
            "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 25},
            "include_traces": {"type": "boolean", "default": True},
            "include_logs": {"type": "boolean", "default": False},
        },
        ["q"],
    ),
    "observer_debug_bundle": object_schema(
        {
            "q": {"type": "string"},
            "trace_id": {"type": "string"},
            "ticket_id": {"type": "string"},
            "operation_id": {"type": "string"},
            "device_id": {"type": "string"},
            "route": {"type": "string"},
            "playbook_run_id": {"type": "integer"},
            "step_run_id": {"type": "integer"},
            "lookback_hours": {"type": "integer", "default": 24, "minimum": 1, "maximum": 168},
            "include_runtime_snapshot": {"type": "boolean", "default": True},
            "include_presence_snapshot": {"type": "boolean", "default": True},
            "include_logs": {"type": "boolean", "default": False},
            "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
        },
    ),
    "observer_trace_detail": object_schema(
        {
            "trace_id": {"type": "string"},
            "include_agent_actions": {"type": "boolean", "default": False},
        },
        ["trace_id"],
    ),
    "observer_ticket_summary": object_schema(
        {
            "ticket_id": {"type": "string"},
            "trace_limit": {"type": "integer", "default": 8, "minimum": 1, "maximum": 25},
            "signature_limit": {"type": "integer", "default": 6, "minimum": 1, "maximum": 25},
            "span_limit": {"type": "integer", "default": 12, "minimum": 1, "maximum": 50},
            "occurrence_limit": {"type": "integer", "default": 6, "minimum": 1, "maximum": 50},
        },
        ["ticket_id"],
    ),
    "observer_runtime_status": object_schema(
        {
            "process_kind": {"type": "string"},
            "include_details": {"type": "boolean", "default": True},
        },
    ),
    "observer_presence_snapshot": object_schema(
        {
            "device_id": {"type": "string"},
            "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 200},
        },
    ),
    "helpdesk_mcp_manifest": object_schema(),
}


def validate_tool_schemas() -> None:
    missing = [name for name in TOOL_NAMES if name not in TOOL_SCHEMAS]
    if missing:
        raise RuntimeError(f"Missing MCP tool schemas: {missing}")


def text_arg(arguments: Mapping[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def int_arg(arguments: Mapping[str, Any], key: str, default: int, *, minimum: int = 1, maximum: int = MAX_LIMIT) -> int:
    value = arguments.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def bool_arg(arguments: Mapping[str, Any], key: str, default: bool = False) -> bool:
    value = arguments.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def controlled_error(error_code: str, message: str, **details: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }
    if details:
        payload["details"] = redact_and_bound(details)
    return payload


def ok(payload: dict[str, Any]) -> dict[str, Any]:
    return redact_and_bound({"status": "ok", **payload})


def redact_and_bound(payload: Any) -> Any:
    return _bound_payload(redact_sensitive_payload(payload))


def _bound_payload(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        return {"truncated": True, "reason": "max_depth"}
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_LIST_ITEMS:
                result["_truncated"] = True
                result["_truncated_count"] = len(value) - MAX_LIST_ITEMS
                break
            result[str(key)] = _bound_payload(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        bounded = [_bound_payload(item, depth=depth + 1) for item in items[:MAX_LIST_ITEMS]]
        if len(items) > MAX_LIST_ITEMS:
            bounded.append({"truncated": True, "truncated_count": len(items) - MAX_LIST_ITEMS})
        return bounded
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        return value[:MAX_STRING_LENGTH] + "...[truncated]"
    return value
