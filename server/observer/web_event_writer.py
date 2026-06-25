from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ObserverErrorOccurrence,
    ObserverErrorSignature,
    ObserverSpan,
    ObserverTrace,
)
from shared.redaction import REDACTED, redact_sensitive_payload


WEB_OBSERVER_ROOT_KIND = "requester_web"
WEB_OBSERVER_COMPONENT = "web_cabinet"
WEB_OBSERVER_NAMESPACE = uuid.UUID("51f47f79-c62f-48c5-8ca1-58dce15cfeb4")

_SUCCESS_RESULTS = {"ok", "success", "succeeded", "created", "previewed"}
_RUNNING_RESULTS = {"started", "running", "queued"}
_ERROR_SEVERITIES = {"warning", "error", "critical"}
_EXTRA_SENSITIVE_MARKERS = {
    "access_code",
    "pairing_code",
    "poll_secret",
    "raw_request_body",
    "raw_response_body",
    "request_body",
    "response_body",
    "email",
    "phone",
}
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _compact(value: Any, *, max_len: int | None = None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:max_len] if max_len else text


def _safe_slug(value: Any, *, fallback: str) -> str:
    raw = re.sub(r"[^a-z0-9_.-]+", "_", str(value or "").strip().lower()).strip("_")
    return raw or fallback


def _status_for_result(result: str, error_code: str | None) -> str:
    normalized = str(result or "").strip().lower()
    if normalized in _SUCCESS_RESULTS and not error_code:
        return "succeeded"
    if normalized in _RUNNING_RESULTS and not error_code:
        return "running"
    return "failed"


def _redact_web_payload(value: Any, *, field_name: str | None = None) -> Any:
    redacted = redact_sensitive_payload(
        value,
        extra_markers=_EXTRA_SENSITIVE_MARKERS,
        field_name=field_name,
    )
    if isinstance(redacted, dict):
        safe: dict[str, Any] = {}
        for key, item in redacted.items():
            key_text = str(key)
            key_norm = key_text.strip().lower().replace("-", "_")
            if key_norm in _EXTRA_SENSITIVE_MARKERS:
                safe[key_text] = REDACTED
            else:
                safe[key_text] = _redact_web_payload(item, field_name=key_text)
        return safe
    if isinstance(redacted, list):
        return [_redact_web_payload(item, field_name=field_name) for item in redacted]
    if isinstance(redacted, str):
        text = _EMAIL_RE.sub(REDACTED, redacted)
        text = _PHONE_RE.sub(REDACTED, text)
        return text
    return redacted


def _actor_ref(actor_context: Any) -> str | None:
    if not isinstance(actor_context, dict):
        return None
    actor_id = _compact(actor_context.get("actor_id"), max_len=300)
    if not actor_id:
        return None
    digest = hashlib.sha256(actor_id.encode("utf-8")).hexdigest()[:16]
    return f"actor:{digest}"


def _execution_ref(actor_context: Any) -> str | None:
    if not isinstance(actor_context, dict):
        return None
    for key in ("idempotency_key", "operation_id", "server_request_id", "request_id", "correlation_id"):
        value = _compact(actor_context.get(key), max_len=120)
        if value:
            return value
    return None


def _trace_id_for_event(
    *,
    source: str,
    event_type: str,
    route: str,
    ticket_id: str | None,
    device_id: str | None,
    person_id: str | None,
    actor_context: Any,
) -> str:
    stable_ref = _execution_ref(actor_context) or ticket_id or person_id or device_id
    if stable_ref:
        raw = "|".join([source, event_type, route, stable_ref])
        return str(uuid.uuid5(WEB_OBSERVER_NAMESPACE, raw))
    return str(uuid.uuid4())


async def write_web_cabinet_observer_event(
    session: AsyncSession,
    *,
    source: str,
    event_type: str,
    severity: str,
    route: str,
    actor_context: Any,
    result: str,
    ticket_id: str | None = None,
    device_id: str | None = None,
    person_id: str | None = None,
    error_code: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Persist a redacted technical Observer event for web requester flows."""

    source = _safe_slug(source, fallback="requester_web")[:120]
    event_type = _safe_slug(event_type, fallback="web_event")[:64]
    severity = _safe_slug(severity, fallback="info")[:16]
    route = _compact(route, max_len=300) or "unknown"
    result = _safe_slug(result, fallback="unknown")[:64]
    ticket_id = _compact(ticket_id, max_len=36)
    device_id = _compact(device_id, max_len=36)
    person_id = _compact(person_id, max_len=36)
    error_code = _compact(error_code, max_len=120)
    method = None
    server_request_id = None
    request_id = None
    correlation_id = None
    idempotency_key = None
    operation_id = None
    actor_role = None
    if isinstance(actor_context, dict):
        method = _compact(actor_context.get("method"), max_len=16)
        server_request_id = _compact(actor_context.get("server_request_id"), max_len=120)
        request_id = _compact(actor_context.get("request_id"), max_len=120)
        correlation_id = _compact(actor_context.get("correlation_id"), max_len=120)
        idempotency_key = _compact(actor_context.get("idempotency_key"), max_len=120)
        operation_id = _compact(actor_context.get("operation_id"), max_len=120)
        actor_role = _compact(actor_context.get("actor_role"), max_len=30)

    now = _now()
    status = _status_for_result(result, error_code)
    is_error = bool(error_code or severity in _ERROR_SEVERITIES or status == "failed")
    trace_id = _trace_id_for_event(
        source=source,
        event_type=event_type,
        route=route,
        ticket_id=ticket_id,
        device_id=device_id,
        person_id=person_id,
        actor_context=actor_context,
    )
    span_status_key = "error" if is_error else "ok"
    source_ref = str(
        uuid.uuid5(WEB_OBSERVER_NAMESPACE, f"{trace_id}:{source}:{event_type}:{span_status_key}:{error_code or result}")
    )
    span_id = str(uuid.uuid5(WEB_OBSERVER_NAMESPACE, f"span:{source_ref}"))
    safe_payload = _redact_web_payload(payload or {})

    attrs = {
        "source": source,
        "event_type": event_type,
        "severity": severity,
        "route": route,
        "method": method,
        "result": result,
        "error_code": error_code,
        "person_id": person_id,
        "actor_role": actor_role,
        "actor_ref": _actor_ref(actor_context),
        "server_request_id": server_request_id,
        "request_id": request_id,
        "correlation_id": correlation_id,
        "idempotency_key": idempotency_key,
        "operation_id": operation_id,
    }
    attrs = {key: value for key, value in attrs.items() if value is not None}
    span_attrs = {**attrs, "payload": safe_payload}

    trace = await session.get(ObserverTrace, trace_id)
    previous_error_count = int(getattr(trace, "error_count", 0) or 0) if trace is not None else 0
    previous_span_count = int(getattr(trace, "span_count", 0) or 0) if trace is not None else 0
    if trace is None:
        trace = ObserverTrace(trace_id=trace_id, created_at=now, updated_at=now)
        session.add(trace)
    trace.root_span_id = span_id
    trace.root_kind = WEB_OBSERVER_ROOT_KIND
    trace.ticket_id = ticket_id
    trace.device_id = device_id
    trace.operation_id = None
    trace.job_id = None
    trace.status = status
    trace.started_at = trace.started_at or now
    trace.finished_at = now
    trace.duration_ms = 0
    trace.error_count = previous_error_count + (1 if is_error else 0)
    trace.attrs_json = attrs
    trace.updated_at = now
    await session.flush()

    existing_span = (
        await session.execute(
            select(ObserverSpan).where(
                ObserverSpan.trace_id == trace_id,
                ObserverSpan.source_type == WEB_OBSERVER_COMPONENT,
                ObserverSpan.source_ref == source_ref,
            )
        )
    ).scalar_one_or_none()
    if existing_span is None:
        existing_span = ObserverSpan(
            span_id=span_id,
            trace_id=trace_id,
            source_type=WEB_OBSERVER_COMPONENT,
            source_ref=source_ref,
            name=f"web.{source}.{event_type}"[:128],
            kind="server",
            started_at=now,
        )
        session.add(existing_span)
        trace.span_count = max(1, previous_span_count + 1)
    else:
        trace.span_count = max(1, previous_span_count)
    existing_span.parent_span_id = None
    existing_span.component = WEB_OBSERVER_COMPONENT
    existing_span.event_type = event_type
    existing_span.module_name = None
    existing_span.tool_name = None
    existing_span.status = "error" if is_error else "ok"
    existing_span.finished_at = now
    existing_span.duration_ms = 0
    existing_span.attrs_json = span_attrs
    await session.flush()

    if is_error:
        signature_id = f"web_cabinet:{source}:{event_type}:{_safe_slug(error_code or result, fallback='error')}"[:160]
        signature = await session.get(ObserverErrorSignature, signature_id)
        if signature is None:
            signature = ObserverErrorSignature(
                error_signature=signature_id,
                title=f"{source} {error_code or result}",
                component=WEB_OBSERVER_COMPONENT,
                module_name=None,
                tool_name=None,
                error_kind=error_code or result,
                exception_type=None,
                failure_stage=event_type,
                message_sample=error_code or result,
                first_seen_at=now,
                last_seen_at=now,
                occurrences_count=0,
                affected_devices_count=0,
                attrs_json={"source": source, "event_type": event_type},
            )
            session.add(signature)
            await session.flush()
        session.add(
            ObserverErrorOccurrence(
                trace_id=trace_id,
                span_id=existing_span.span_id,
                error_signature=signature_id,
                device_id=device_id,
                ticket_id=ticket_id,
                operation_id=None,
                component=WEB_OBSERVER_COMPONENT,
                module_name=None,
                tool_name=None,
                error_kind=error_code or result,
                exception_type=None,
                failure_stage=event_type,
                severity="error" if severity == "critical" else severity,
                message_norm=error_code or result,
                attrs_json=attrs,
                created_at=now,
            )
        )
        await session.flush()
        count, first_seen, last_seen, affected_devices = (
            await session.execute(
                select(
                    func.count(ObserverErrorOccurrence.occurrence_id),
                    func.min(ObserverErrorOccurrence.created_at),
                    func.max(ObserverErrorOccurrence.created_at),
                    func.count(func.distinct(ObserverErrorOccurrence.device_id)),
                ).where(ObserverErrorOccurrence.error_signature == signature_id)
            )
        ).one()
        signature.first_seen_at = first_seen or now
        signature.last_seen_at = last_seen or now
        signature.occurrences_count = int(count or 0)
        signature.affected_devices_count = int(affected_devices or 0)

    await session.flush()
    return trace_id
