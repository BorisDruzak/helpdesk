"""Last-mile allowlist for both Sentry errors and sampled transactions.

Unstructured exception messages can contain ticket/chat/upload contents. Only
known structural messages survive; type and source location remain useful.
No recursive blacklist can reliably recognize arbitrary user-provided text.
"""
from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Any

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_.<>]*")
_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
_SAFE_MESSAGES = {
    "division by zero", "integer division or modulo by zero", "float division by zero",
    "list index out of range", "tuple index out of range", "maximum recursion depth exceeded",
    "cannot unpack non-iterable NoneType object", "not enough values to unpack",
    "database unavailable", "connection refused", "operation timed out",
}
_STATUSES = {"ok", "unknown_error", "internal_error", "invalid_argument", "not_found",
             "permission_denied", "unauthenticated", "unavailable", "deadline_exceeded",
             "cancelled", "resource_exhausted", "already_exists", "failed_precondition",
             "out_of_range", "unimplemented", "data_loss", "aborted"}


def _identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and len(value) <= 200 and _IDENTIFIER.fullmatch(value) else None


def _timestamp(value: Any) -> bool:
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return math.isfinite(value)
    return isinstance(value, str) and bool(re.fullmatch(r"\d{4}-\d\d-\d\dT[\d:.]+(?:Z|\+00:00)", value))


def _trace(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    result = {}
    for key, size in (("trace_id", 32), ("span_id", 16), ("parent_span_id", 16)):
        value = source.get(key)
        if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{" + str(size) + "}", value):
            result[key] = value
    # Fixed operation vocabulary prevents arbitrary text in span names.
    if source.get("op") in {"http.server", "http.client", "http", "db", "db.sql.query", "middleware.aiohttp"}:
        result["op"] = source["op"]
    if source.get("status") in _STATUSES:
        result["status"] = source["status"]
    return result


def _frames(stack: Any) -> dict[str, Any]:
    if not isinstance(stack, dict) or not isinstance(stack.get("frames"), list):
        return {}
    frames = []
    for frame in stack["frames"][-50:]:
        if not isinstance(frame, dict):
            continue
        safe = {}
        filename = frame.get("filename")
        if isinstance(filename, str):
            # Absolute paths disclose usernames/home directories. Keep relative
            # source paths; absolute paths retain only the source basename.
            filename = filename.replace("\\", "/")
            if filename.startswith("/") or ":" in filename or ".." in filename.split("/"):
                filename = PurePosixPath(filename).name
            if len(filename) <= 250 and re.fullmatch(r"[A-Za-z0-9_./-]+\.py", filename):
                safe["filename"] = filename
        for key in ("module", "function"):
            value = _identifier(frame.get(key))
            if value:
                safe[key] = value
        if type(frame.get("lineno")) is int and 0 < frame["lineno"] < 10_000_000:
            safe["lineno"] = frame["lineno"]
        if type(frame.get("in_app")) is bool:
            safe["in_app"] = frame["in_app"]
        frames.append(safe)
    return {"frames": frames}


class EventSanitizer:
    """Project events onto policy fields, including late-added SDK scope data."""

    def __init__(self, routes: set[str], release: str | None, environment: str):
        self.routes = frozenset(routes)
        self.release = release
        self.environment = environment

    def __call__(self, event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
        # SDK creates attachment envelope items *after* invoking these hooks.
        try:
            hint.pop("attachments", None)
            return self._project(event)
        except Exception:
            # Malformed extra observability data must neither leak nor affect
            # request handling. Never log event/hint values.
            return None

    def _project(self, event: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"platform": "python", "environment": self.environment}
        if self.release:
            result["release"] = self.release
        event_id = event.get("event_id")
        if isinstance(event_id, str) and re.fullmatch(r"[a-f0-9]{32}", event_id):
            result["event_id"] = event_id
        for key in ("timestamp", "start_timestamp"):
            if _timestamp(event.get(key)):
                result[key] = event[key]
        if event.get("level") in {"fatal", "error", "warning", "info", "debug"}:
            result["level"] = event["level"]
        transaction = event.get("transaction", "")
        method, _, route = transaction.partition(" ") if isinstance(transaction, str) else ("", "", "")
        if method in _METHODS and route in self.routes:
            result["transaction"] = transaction
            result["transaction_info"] = {"source": "route"}
            result["request"] = {"method": method, "url": route}
        else:
            result["transaction"] = "[unresolved route]"
        trace = _trace(event.get("contexts", {}).get("trace"))
        if trace:
            result["contexts"] = {"trace": trace}
        exception = event.get("exception", {})
        values = exception.get("values", []) if isinstance(exception, dict) else []
        safe_values = []
        for value in values[:10]:
            if not isinstance(value, dict):
                continue
            safe = {"type": _identifier(value.get("type")) or "Exception",
                    "value": value.get("value") if value.get("value") in _SAFE_MESSAGES else "[message omitted by privacy policy]"}
            stack = _frames(value.get("stacktrace"))
            if stack:
                safe["stacktrace"] = stack
            mechanism = value.get("mechanism")
            if isinstance(mechanism, dict) and type(mechanism.get("handled")) is bool:
                safe["mechanism"] = {"type": "aiohttp", "handled": mechanism["handled"]}
            safe_values.append(safe)
        if safe_values:
            result["exception"] = {"values": safe_values}
        if event.get("type") == "transaction":
            result["type"] = "transaction"
            result["spans"] = []
            for span in event.get("spans", [])[:200]:
                safe_span = _trace(span)
                if not safe_span:
                    continue
                for key in ("timestamp", "start_timestamp"):
                    if _timestamp(span.get(key)):
                        safe_span[key] = span[key]
                result["spans"].append(safe_span)
        return result
