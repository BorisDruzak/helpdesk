from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from weakref import WeakValueDictionary

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgentRuntimeAudit,
    DeviceEvent,
    ObserverErrorOccurrence,
    ObserverErrorSignature,
    ObserverSpan,
    ObserverSpanLink,
    ObserverTrace,
    Operation,
    Ticket,
    TicketEvent,
)
from shared.redaction import redact_sensitive_payload


OBSERVER_NAMESPACE = uuid.UUID("7f646dd0-36d4-4789-953b-fc8d1dd0d3e9")
TERMINAL_OPERATION_STATUSES = {"succeeded", "success", "failed", "timed_out", "canceled"}
ERROR_OPERATION_STATUSES = {"failed", "timed_out"}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
ERROR_AUDIT_SEVERITIES = {"error", "critical"}
_TRACE_PROJECTION_LOCK_GUARD = asyncio.Lock()
_TRACE_PROJECTION_LOCKS: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


@dataclass(slots=True)
class TraceOverlayFilters:
    trace_id: Optional[str] = None
    ticket_id: Optional[str] = None
    job_id: Optional[str] = None
    operation_id: Optional[str] = None
    device_id: Optional[str] = None
    root_kind: Optional[str] = None
    tool_name: Optional[str] = None
    module_name: Optional[str] = None
    error_signature: Optional[str] = None
    status: Optional[str] = None
    min_duration_ms: Optional[int] = None
    min_retry_count: Optional[int] = None
    min_timeout_rate: Optional[float] = None
    min_retry_rate: Optional[float] = None
    min_slow_rate: Optional[float] = None
    lookback_hours: Optional[int] = None


@dataclass(slots=True)
class TraceProjectionSources:
    operations: list[Operation]
    ticket_events: list[TicketEvent]
    device_events: list[DeviceEvent]
    runtime_audits: list[AgentRuntimeAudit]
    root_ticket: Optional[Ticket] = None

    @property
    def empty(self) -> bool:
        return not any((self.operations, self.ticket_events, self.device_events, self.runtime_audits, self.root_ticket))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _duration_ms(started_at: Optional[datetime], finished_at: Optional[datetime]) -> Optional[int]:
    if not started_at or not finished_at:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _operation_finished_at(operation: Operation) -> Optional[datetime]:
    return operation.canceled_at or operation.finished_at or operation.started_at or operation.accepted_at or operation.sent_at or operation.queued_at


def _operation_duration_ms(operation: Operation) -> Optional[int]:
    return _duration_ms(operation.queued_at, _operation_finished_at(operation))


def _compact_text(value: Any) -> Optional[str]:
    raw = str(value or "").strip()
    return raw or None


def _normalize_message(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    raw = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27}\b", "<uuid>", raw)
    raw = re.sub(r"\b\d+\b", "<n>", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw[:500]


def _slugify(value: Any) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return raw or "unknown"


def _extract_exception_type(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]+)(?::|\b)", text)
    if match:
        return match.group(1)
    return None


def _split_tool_name(tool_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    raw = _compact_text(tool_name)
    if not raw or "." not in raw:
        return None, raw
    module_name, _rest = raw.split(".", 1)
    return module_name or None, raw


def _trace_scoped_uuid(trace_id: str, label: str) -> str:
    return str(uuid.uuid5(OBSERVER_NAMESPACE, f"{trace_id}:{label}"))


def _parse_action_timestamp(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _span_status_from_operation(status: Optional[str]) -> str:
    key = str(status or "").strip().lower()
    if key in ERROR_OPERATION_STATUSES:
        return "error"
    if key in ACTIVE_OPERATION_STATUSES:
        return "running"
    if key == "canceled":
        return "canceled"
    return "ok"


def _span_status_from_ticket_status(status: Optional[str]) -> str:
    key = str(status or "").strip().lower()
    if key in {"resolved", "closed"}:
        return "ok"
    if key in {"new", "triaged", "in_progress", "waiting_on_user", "waiting_on_vendor"}:
        return "running"
    return "ok"


def _span_status_from_severity(severity: Optional[str]) -> str:
    key = str(severity or "").strip().lower()
    if key in ERROR_AUDIT_SEVERITIES:
        return "error"
    if key == "warning":
        return "warning"
    return "ok"


def _signature_title(*, error_kind: Optional[str], module_name: Optional[str], tool_name: Optional[str], component: Optional[str]) -> str:
    parts = [part for part in [error_kind, module_name, tool_name, component] if part]
    return " / ".join(parts) if parts else "observer_error"


async def _get_trace_projection_lock(trace_id: str) -> asyncio.Lock:
    async with _TRACE_PROJECTION_LOCK_GUARD:
        lock = _TRACE_PROJECTION_LOCKS.get(trace_id)
        if lock is None:
            lock = asyncio.Lock()
            _TRACE_PROJECTION_LOCKS[trace_id] = lock
        return lock


class ObserverOverlayService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_traces(self, filters: TraceOverlayFilters, *, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure_projected(filters, limit=limit, force=False)
        await self.session.flush()
        stmt = select(ObserverTrace)
        prefer_ticket_root = (
            filters.ticket_id is not None
            and not any(
                [
                    filters.trace_id,
                    filters.job_id,
                    filters.operation_id,
                    filters.device_id,
                    filters.root_kind not in (None, "ticket"),
                    filters.tool_name,
                    filters.module_name,
                    filters.error_signature,
                    filters.status,
                    filters.min_duration_ms,
                    filters.min_retry_count,
                ]
            )
        )
        ticket_root_trace_id = await self._load_ticket_root_trace_id(filters.ticket_id) if prefer_ticket_root else None
        if filters.trace_id:
            stmt = stmt.where(ObserverTrace.trace_id == filters.trace_id)
        elif ticket_root_trace_id:
            stmt = stmt.where(ObserverTrace.trace_id == ticket_root_trace_id)
        elif filters.ticket_id:
            stmt = stmt.where(ObserverTrace.ticket_id == filters.ticket_id)
        if filters.job_id:
            stmt = stmt.where(ObserverTrace.job_id == filters.job_id)
        if filters.operation_id:
            stmt = stmt.where(ObserverTrace.operation_id == filters.operation_id)
        if filters.device_id:
            stmt = stmt.where(ObserverTrace.device_id == filters.device_id)
        if filters.root_kind:
            stmt = stmt.where(ObserverTrace.root_kind == filters.root_kind)
        if filters.status:
            stmt = stmt.where(ObserverTrace.status == filters.status)
        if filters.tool_name:
            stmt = stmt.where(
                exists(
                    select(ObserverSpan.span_id).where(
                        ObserverSpan.trace_id == ObserverTrace.trace_id,
                        ObserverSpan.tool_name == filters.tool_name,
                    )
                )
            )
        if filters.module_name:
            stmt = stmt.where(
                exists(
                    select(ObserverSpan.span_id).where(
                        ObserverSpan.trace_id == ObserverTrace.trace_id,
                        ObserverSpan.module_name == filters.module_name,
                    )
                )
            )
        if filters.error_signature:
            stmt = stmt.where(
                exists(
                    select(ObserverErrorOccurrence.occurrence_id).where(
                        ObserverErrorOccurrence.trace_id == ObserverTrace.trace_id,
                        ObserverErrorOccurrence.error_signature == filters.error_signature,
                    )
                )
            )
        stmt = stmt.order_by(ObserverTrace.started_at.desc()).limit(max(limit * 5, limit))
        rows = (await self.session.execute(stmt)).scalars().all()
        rows = await self._filter_traces_by_degradation(rows, filters)
        rows = rows[:limit]
        return [self._serialize_trace(row) for row in rows]

    async def search_degradations(self, filters: TraceOverlayFilters, *, limit: int = 50) -> list[dict[str, Any]]:
        lookback_hours = max(int(filters.lookback_hours or 24), 1)
        retry_threshold = max(int(filters.min_retry_count or 1), 1)
        slow_threshold_ms = max(int(filters.min_duration_ms or 2000), 1)
        window_start = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        stmt = select(Operation).where(
            or_(
                Operation.queued_at >= window_start,
                Operation.finished_at >= window_start,
                Operation.canceled_at >= window_start,
            )
        )
        if filters.ticket_id:
            stmt = stmt.where(Operation.ticket_id == filters.ticket_id)
        if filters.job_id:
            stmt = stmt.where(Operation.job_id == filters.job_id)
        if filters.operation_id:
            stmt = stmt.where(Operation.operation_id == filters.operation_id)
        if filters.device_id:
            stmt = stmt.where(Operation.device_id == filters.device_id)
        if filters.root_kind:
            stmt = stmt.where(Operation.kind == filters.root_kind)
        if filters.tool_name:
            stmt = stmt.where(Operation.tool_name == filters.tool_name)
        if filters.module_name:
            stmt = stmt.where(Operation.tool_name.like(f"{filters.module_name}.%"))
        rows = (await self.session.execute(stmt.order_by(Operation.queued_at.desc()).limit(max(limit * 20, limit)))).scalars().all()

        grouped: dict[tuple[Optional[str], Optional[str], Optional[str]], dict[str, Any]] = {}
        for operation in rows:
            module_name, tool_name = _split_tool_name(operation.tool_name)
            operation_kind = _compact_text(operation.kind)
            key = (operation_kind, module_name, tool_name)
            item = grouped.get(key)
            if item is None:
                item = {
                    "operation_kind": operation_kind,
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "operations_count": 0,
                    "timeout_count": 0,
                    "retried_operations_count": 0,
                    "slow_operations_count": 0,
                    "max_duration_ms": 0,
                    "avg_duration_total_ms": 0,
                    "latest_operation_at": None,
                    "sample_trace_ids": [],
                }
                grouped[key] = item
            duration_ms = _operation_duration_ms(operation) or 0
            latest_operation_at = _operation_finished_at(operation) or operation.queued_at
            item["operations_count"] += 1
            item["avg_duration_total_ms"] += duration_ms
            item["max_duration_ms"] = max(item["max_duration_ms"], duration_ms)
            if str(operation.status or "").strip().lower() == "timed_out":
                item["timeout_count"] += 1
            if int(operation.retry_count or 0) >= retry_threshold:
                item["retried_operations_count"] += 1
            if duration_ms > slow_threshold_ms:
                item["slow_operations_count"] += 1
            if latest_operation_at and (
                item["latest_operation_at"] is None or latest_operation_at > item["latest_operation_at"]
            ):
                item["latest_operation_at"] = latest_operation_at
            trace_id = _compact_text(operation.trace_id)
            if trace_id and trace_id not in item["sample_trace_ids"] and len(item["sample_trace_ids"]) < 5:
                item["sample_trace_ids"].append(trace_id)

        items: list[dict[str, Any]] = []
        for item in grouped.values():
            operations_count = max(int(item["operations_count"]), 1)
            avg_duration_ms = int(item["avg_duration_total_ms"] / operations_count)
            items.append(
                {
                    "operation_kind": item["operation_kind"],
                    "module_name": item["module_name"],
                    "tool_name": item["tool_name"],
                    "operations_count": operations_count,
                    "timeout_count": int(item["timeout_count"]),
                    "timeout_rate": item["timeout_count"] / operations_count,
                    "retried_operations_count": int(item["retried_operations_count"]),
                    "retry_rate": item["retried_operations_count"] / operations_count,
                    "slow_operations_count": int(item["slow_operations_count"]),
                    "slow_rate": item["slow_operations_count"] / operations_count,
                    "avg_duration_ms": avg_duration_ms,
                    "max_duration_ms": int(item["max_duration_ms"]),
                    "latest_operation_at": _iso(item["latest_operation_at"]),
                    "sample_trace_ids": item["sample_trace_ids"],
                }
            )

        min_timeout_rate = max(float(filters.min_timeout_rate or 0), 0.0)
        min_retry_rate = max(float(filters.min_retry_rate or 0), 0.0)
        min_slow_rate = max(float(filters.min_slow_rate or 0), 0.0)
        if min_timeout_rate > 0 or min_retry_rate > 0 or min_slow_rate > 0:
            items = [
                item
                for item in items
                if item["timeout_rate"] >= min_timeout_rate
                and item["retry_rate"] >= min_retry_rate
                and item["slow_rate"] >= min_slow_rate
            ]

        items.sort(
            key=lambda entry: (
                entry["timeout_count"],
                entry["retried_operations_count"],
                entry["slow_operations_count"],
                entry["max_duration_ms"],
                entry["latest_operation_at"] or "",
            ),
            reverse=True,
        )
        return items[:limit]

    async def get_trace_detail(self, trace_id: str) -> Optional[dict[str, Any]]:
        trace = await self.project_trace(trace_id, force=False)
        if trace is None:
            return None
        spans = (
            await self.session.execute(
                select(ObserverSpan).where(ObserverSpan.trace_id == trace_id).order_by(ObserverSpan.started_at.asc(), ObserverSpan.name.asc())
            )
        ).scalars().all()
        occurrences = (
            await self.session.execute(
                select(ObserverErrorOccurrence)
                .where(ObserverErrorOccurrence.trace_id == trace_id)
                .order_by(ObserverErrorOccurrence.created_at.desc())
            )
        ).scalars().all()
        span_ids = [span.span_id for span in spans]
        links: list[ObserverSpanLink] = []
        if span_ids:
            links = (
                await self.session.execute(
                    select(ObserverSpanLink).where(ObserverSpanLink.span_id.in_(span_ids)).order_by(ObserverSpanLink.created_at.asc())
                )
            ).scalars().all()
        return {
            "trace": self._serialize_trace(trace),
            "spans": [self._serialize_span(span) for span in spans],
            "span_links": [self._serialize_span_link(link) for link in links],
            "error_occurrences": [self._serialize_occurrence(item) for item in occurrences],
        }

    async def sync_agent_action_spans(self, trace_id: str, entries: list[dict[str, Any]]) -> int:
        trace = await self.project_trace(trace_id, force=False)
        if trace is None:
            return 0
        span_rows = (
            await self.session.execute(
                select(ObserverSpan).where(ObserverSpan.trace_id == trace_id).order_by(ObserverSpan.started_at.asc())
            )
        ).scalars().all()
        existing_agent_action_span_ids = [span.span_id for span in span_rows if span.source_type == "agent_action"]
        if existing_agent_action_span_ids:
            await self.session.execute(delete(ObserverSpanLink).where(ObserverSpanLink.span_id.in_(existing_agent_action_span_ids)))
            await self.session.execute(
                delete(ObserverSpan).where(
                    ObserverSpan.trace_id == trace_id,
                    ObserverSpan.source_type == "agent_action",
                )
            )
            await self.session.flush()

        if not entries:
            trace.span_count = await self._count_trace_spans(trace_id)
            return 0

        operation_span_ids = {
            span.source_ref: span.span_id
            for span in span_rows
            if span.source_type == "operation" and span.source_ref
        }
        grouped: dict[str, dict[str, Any]] = {}
        ordered_action_ids: list[str] = []

        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            action_id = _compact_text(entry.get("action_id")) or _trace_scoped_uuid(trace_id, f"agent_action:{index}")
            ts = _parse_action_timestamp(entry.get("ts")) or trace.started_at or datetime.now(timezone.utc)
            details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
            redacted_details = redact_sensitive_payload(details or {})
            group = grouped.get(action_id)
            if group is None:
                module_name, tool_name = _split_tool_name(_compact_text(entry.get("tool_name")))
                grouped[action_id] = group = {
                    "action_id": action_id,
                    "parent_action_id": _compact_text(entry.get("parent_action_id")),
                    "source": _compact_text(entry.get("source")) or "agent",
                    "action": _compact_text(entry.get("action")) or "agent.action",
                    "category": _compact_text(entry.get("category")) or "tool",
                    "ticket_id": _compact_text(entry.get("ticket_id")) or trace.ticket_id,
                    "operation_id": _compact_text(entry.get("operation_id")) or trace.operation_id,
                    "tool_name": _compact_text(entry.get("tool_name")) or tool_name,
                    "module_name": _compact_text(redacted_details.get("module_name")) or module_name,
                    "request_id": _compact_text(entry.get("request_id")),
                    "session_key": _compact_text(entry.get("session_key")),
                    "started_at": ts,
                    "finished_at": ts,
                    "last_stage": _compact_text(entry.get("stage")) or "event",
                    "status": str(entry.get("status") or "ok").strip().lower() or "ok",
                    "summary": _compact_text(entry.get("summary")),
                    "details_preview": redacted_details,
                    "stages": [],
                }
                ordered_action_ids.append(action_id)
            else:
                group["started_at"] = min(group["started_at"], ts)
                group["finished_at"] = max(group["finished_at"], ts)
                current_status = str(group.get("status") or "ok").strip().lower()
                new_status = str(entry.get("status") or current_status).strip().lower() or current_status
                if new_status in {"error", "timeout", "canceled"}:
                    group["status"] = new_status
                elif current_status not in {"error", "timeout", "canceled"}:
                    group["status"] = new_status
                group["last_stage"] = _compact_text(entry.get("stage")) or group["last_stage"]
                group["summary"] = _compact_text(entry.get("summary")) or group["summary"]
                if redacted_details:
                    group["details_preview"] = redacted_details
                    group["module_name"] = _compact_text(redacted_details.get("module_name")) or group["module_name"]
                    group["tool_name"] = _compact_text(entry.get("tool_name")) or group["tool_name"]
            group["stages"].append(
                {
                    "ts": _iso(ts),
                    "stage": _compact_text(entry.get("stage")) or "event",
                    "status": str(entry.get("status") or "ok").strip().lower() or "ok",
                    "summary": _compact_text(entry.get("summary")),
                }
            )

        span_id_by_action_id = {
            action_id: _trace_scoped_uuid(trace_id, f"agent_action_span:{action_id}")
            for action_id in ordered_action_ids
        }
        for action_id in ordered_action_ids:
            item = grouped[action_id]
            parent_action_id = str(item.get("parent_action_id") or "")
            linked_parent_span_id = span_id_by_action_id.get(parent_action_id)
            parent_span_id = linked_parent_span_id or operation_span_ids.get(str(item.get("operation_id") or "")) or trace.root_span_id

            self.session.add(
                ObserverSpan(
                    span_id=span_id_by_action_id[action_id],
                    trace_id=trace_id,
                    parent_span_id=parent_span_id,
                    source_type="agent_action",
                    source_ref=action_id,
                    name=str(item["action"]),
                    kind="internal",
                    component="agent_action",
                    event_type=str(item["last_stage"]),
                    module_name=item.get("module_name"),
                    tool_name=item.get("tool_name"),
                    status=str(item["status"]),
                    started_at=item["started_at"],
                    finished_at=item["finished_at"],
                    duration_ms=_duration_ms(item["started_at"], item["finished_at"]),
                    attrs_json={
                        "source": item.get("source"),
                        "category": item.get("category"),
                        "request_id": item.get("request_id"),
                        "session_key": item.get("session_key"),
                        "details_preview": item.get("details_preview") or {},
                        "stages": item.get("stages") or [],
                        "summary": item.get("summary"),
                    },
                )
            )
            if linked_parent_span_id:
                self.session.add(
                    ObserverSpanLink(
                        span_id=span_id_by_action_id[action_id],
                        linked_trace_id=trace_id,
                        linked_span_id=linked_parent_span_id,
                        reason="agent_action_parent",
                        attrs_json={},
                    )
                )
            operation_span_id = operation_span_ids.get(str(item.get("operation_id") or ""))
            if operation_span_id:
                self.session.add(
                    ObserverSpanLink(
                        span_id=span_id_by_action_id[action_id],
                        linked_trace_id=trace_id,
                        linked_span_id=operation_span_id,
                        reason="operation_id_bridge",
                        attrs_json={},
                    )
                )

        await self.session.flush()
        trace.span_count = await self._count_trace_spans(trace_id)
        return len(ordered_action_ids)

    async def search_signatures(self, filters: TraceOverlayFilters, *, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure_projected(filters, limit=limit, force=False)
        stmt = select(ObserverErrorSignature)
        if filters.error_signature:
            stmt = stmt.where(ObserverErrorSignature.error_signature == filters.error_signature)
        if filters.module_name:
            stmt = stmt.where(ObserverErrorSignature.module_name == filters.module_name)
        if filters.tool_name:
            stmt = stmt.where(ObserverErrorSignature.tool_name == filters.tool_name)
        if filters.root_kind:
            stmt = stmt.where(
                exists(
                    select(ObserverErrorOccurrence.occurrence_id)
                    .join(ObserverTrace, ObserverTrace.trace_id == ObserverErrorOccurrence.trace_id)
                    .where(
                        ObserverErrorOccurrence.error_signature == ObserverErrorSignature.error_signature,
                        ObserverTrace.root_kind == filters.root_kind,
                    )
                )
            )
        if filters.status:
            stmt = stmt.where(
                exists(
                    select(ObserverErrorOccurrence.occurrence_id).where(
                        ObserverErrorOccurrence.error_signature == ObserverErrorSignature.error_signature,
                        ObserverErrorOccurrence.failure_stage == filters.status,
                    )
                )
            )
        if filters.trace_id or filters.ticket_id or filters.device_id or filters.operation_id:
            subquery = select(ObserverErrorOccurrence.occurrence_id).where(
                ObserverErrorOccurrence.error_signature == ObserverErrorSignature.error_signature
            )
            if filters.trace_id:
                subquery = subquery.where(ObserverErrorOccurrence.trace_id == filters.trace_id)
            if filters.ticket_id:
                subquery = subquery.where(ObserverErrorOccurrence.ticket_id == filters.ticket_id)
            if filters.device_id:
                subquery = subquery.where(ObserverErrorOccurrence.device_id == filters.device_id)
            if filters.operation_id:
                subquery = subquery.where(ObserverErrorOccurrence.operation_id == filters.operation_id)
            stmt = stmt.where(exists(subquery))
        stmt = stmt.order_by(ObserverErrorSignature.last_seen_at.desc()).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._serialize_signature(item) for item in rows]

    async def get_signature_detail(self, error_signature: str, *, limit: int = 100) -> Optional[dict[str, Any]]:
        signature = await self.session.get(ObserverErrorSignature, error_signature)
        if signature is None:
            return None
        occurrences = (
            await self.session.execute(
                select(ObserverErrorOccurrence)
                .where(ObserverErrorOccurrence.error_signature == error_signature)
                .order_by(ObserverErrorOccurrence.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return {
            "signature": self._serialize_signature(signature),
            "occurrences": [self._serialize_occurrence(item) for item in occurrences],
        }

    async def rebuild_traces(self, filters: TraceOverlayFilters, *, limit: int = 100) -> list[str]:
        candidate_ids = await self._candidate_trace_ids(filters, limit=limit)
        projected: list[str] = []
        for trace_id in candidate_ids:
            if await self.project_trace(trace_id, force=True):
                projected.append(trace_id)
        return projected

    async def project_trace(self, trace_id: str, *, force: bool = False) -> Optional[ObserverTrace]:
        lock = await _get_trace_projection_lock(trace_id)
        async with lock:
            await self._acquire_trace_projection_db_lock(trace_id)
            return await self._project_trace_locked(trace_id, force=force)

    async def _project_trace_locked(self, trace_id: str, *, force: bool) -> Optional[ObserverTrace]:
        sources = await self._collect_sources(trace_id)
        if sources.empty:
            await self._clear_trace_projection(trace_id)
            return None

        existing_trace = await self.session.get(ObserverTrace, trace_id)
        source_last_seen_at = self._source_last_seen_at(sources)
        if existing_trace is not None and not force and not self._projection_needs_refresh(existing_trace, source_last_seen_at):
            return existing_trace

        old_signatures = await self._existing_trace_signatures(trace_id) if existing_trace is not None else set()
        await self._clear_trace_dependents(trace_id)

        span_payloads, link_payloads, trace_meta = self._build_span_payloads(
            trace_id,
            sources,
            source_last_seen_at=source_last_seen_at,
        )
        occurrence_payloads = self._build_occurrence_payloads(trace_id, sources, span_payloads)

        if existing_trace is None:
            trace = ObserverTrace(trace_id=trace_id)
            self.session.add(trace)
        else:
            trace = existing_trace

        trace.root_span_id = trace_meta["root_span_id"]
        trace.root_kind = trace_meta["root_kind"]
        trace.ticket_id = trace_meta["ticket_id"]
        trace.device_id = trace_meta["device_id"]
        trace.operation_id = trace_meta["operation_id"]
        trace.job_id = trace_meta["job_id"]
        trace.status = self._projected_trace_status(trace_meta["status"], occurrence_payloads)
        trace.started_at = trace_meta["started_at"]
        trace.finished_at = trace_meta["finished_at"]
        trace.duration_ms = _duration_ms(trace_meta["started_at"], trace_meta["finished_at"])
        trace.span_count = len(span_payloads)
        trace.error_count = len(occurrence_payloads)
        trace.attrs_json = trace_meta["attrs_json"]
        await self.session.flush()
        for payload in span_payloads:
            self.session.add(ObserverSpan(**payload))
        for payload in link_payloads:
            self.session.add(ObserverSpanLink(**payload))

        touched_signatures = set(old_signatures)
        pending_placeholders: dict[str, dict[str, Any]] = {}
        for payload in occurrence_payloads:
            touched_signatures.add(payload["error_signature"])
            pending_placeholders.setdefault(payload["error_signature"], payload)

        for error_signature, payload in pending_placeholders.items():
            if await self.session.get(ObserverErrorSignature, error_signature) is None:
                self.session.add(
                    ObserverErrorSignature(
                        error_signature=error_signature,
                        title=_signature_title(
                            error_kind=payload.get("error_kind"),
                            module_name=payload.get("module_name"),
                            tool_name=payload.get("tool_name"),
                            component=payload.get("component"),
                        ),
                        component=payload.get("component"),
                        module_name=payload.get("module_name"),
                        tool_name=payload.get("tool_name"),
                        error_kind=payload.get("error_kind"),
                        exception_type=payload.get("exception_type"),
                        failure_stage=payload.get("failure_stage"),
                        message_sample=payload.get("message_norm"),
                        first_seen_at=payload.get("created_at"),
                        last_seen_at=payload.get("created_at"),
                        occurrences_count=0,
                        affected_devices_count=0,
                        attrs_json={},
                    )
                )

        await self.session.flush()

        for payload in occurrence_payloads:
            self.session.add(ObserverErrorOccurrence(**payload))

        await self.session.flush()
        await self._refresh_signatures(touched_signatures)
        return trace

    async def _ensure_projected(self, filters: TraceOverlayFilters, *, limit: int, force: bool) -> None:
        candidate_ids = await self._candidate_trace_ids(filters, limit=limit)
        for trace_id in candidate_ids:
            await self.project_trace(trace_id, force=force)

    async def _candidate_trace_ids(self, filters: TraceOverlayFilters, *, limit: int) -> list[str]:
        if filters.trace_id:
            return [filters.trace_id]

        candidates: list[str] = []
        seen: set[str] = set()

        def _remember(values: Iterable[Optional[str]]) -> None:
            for item in values:
                value = _compact_text(item)
                if value and value not in seen:
                    seen.add(value)
                    candidates.append(value)

        if filters.ticket_id:
            _remember([await self._load_ticket_root_trace_id(filters.ticket_id)])

        if filters.root_kind in (None, "ticket"):
            ticket_root_stmt = select(Ticket.observer_root_trace_id).where(Ticket.observer_root_trace_id.isnot(None))
            if filters.ticket_id:
                ticket_root_stmt = ticket_root_stmt.where(Ticket.ticket_id == filters.ticket_id)
            if filters.device_id:
                ticket_root_stmt = ticket_root_stmt.where(Ticket.device_id == filters.device_id)
            ticket_root_stmt = ticket_root_stmt.order_by(Ticket.created_at.desc()).limit(limit)
            _remember((await self.session.execute(ticket_root_stmt)).scalars().all())

        op_stmt = select(Operation.trace_id).where(Operation.trace_id.isnot(None))
        if filters.ticket_id:
            op_stmt = op_stmt.where(Operation.ticket_id == filters.ticket_id)
        if filters.job_id:
            op_stmt = op_stmt.where(Operation.job_id == filters.job_id)
        if filters.operation_id:
            op_stmt = op_stmt.where(Operation.operation_id == filters.operation_id)
        if filters.device_id:
            op_stmt = op_stmt.where(Operation.device_id == filters.device_id)
        if filters.root_kind and filters.root_kind != "ticket":
            op_stmt = op_stmt.where(Operation.kind == filters.root_kind)
        if filters.tool_name:
            op_stmt = op_stmt.where(Operation.tool_name == filters.tool_name)
        if filters.module_name:
            op_stmt = op_stmt.where(Operation.tool_name.like(f"{filters.module_name}.%"))
        if filters.status:
            op_stmt = op_stmt.where(Operation.status == filters.status)
        op_stmt = op_stmt.order_by(Operation.queued_at.desc()).limit(limit)
        _remember((await self.session.execute(op_stmt)).scalars().all())

        if len(candidates) < limit:
            ticket_stmt = select(TicketEvent.trace_id).where(TicketEvent.trace_id.isnot(None))
            device_stmt = select(DeviceEvent.trace_id).where(DeviceEvent.trace_id.isnot(None))
            if filters.ticket_id:
                ticket_stmt = ticket_stmt.where(TicketEvent.ticket_id == filters.ticket_id)
            if filters.operation_id:
                ticket_stmt = ticket_stmt.where(TicketEvent.operation_id == filters.operation_id)
                device_stmt = device_stmt.where(DeviceEvent.operation_id == filters.operation_id)
            if filters.device_id:
                ticket_stmt = ticket_stmt.where(TicketEvent.device_id == filters.device_id)
                device_stmt = device_stmt.where(DeviceEvent.device_id == filters.device_id)
            ticket_stmt = ticket_stmt.order_by(TicketEvent.created_at.desc()).limit(limit)
            device_stmt = device_stmt.order_by(DeviceEvent.created_at.desc()).limit(limit)
            _remember((await self.session.execute(ticket_stmt)).scalars().all())
            _remember((await self.session.execute(device_stmt)).scalars().all())

        if not candidates:
            recent_stmt = (
                select(Operation.trace_id)
                .where(Operation.trace_id.isnot(None))
                .order_by(Operation.queued_at.desc())
                .limit(limit)
            )
            _remember((await self.session.execute(recent_stmt)).scalars().all())

        return candidates[:limit]

    async def _load_ticket_root_trace_id(self, ticket_id: Optional[str]) -> Optional[str]:
        if not ticket_id:
            return None
        row = await self.session.execute(
            select(Ticket.observer_root_trace_id).where(Ticket.ticket_id == ticket_id).limit(1)
        )
        return _compact_text(row.scalar_one_or_none())

    async def _collect_sources(self, trace_id: str) -> TraceProjectionSources:
        root_ticket = (
            await self.session.execute(select(Ticket).where(Ticket.observer_root_trace_id == trace_id).limit(1))
        ).scalar_one_or_none()
        if root_ticket is not None:
            return await self._collect_ticket_root_sources(trace_id, root_ticket)

        operations = (
            await self.session.execute(select(Operation).where(Operation.trace_id == trace_id).order_by(Operation.queued_at.asc()))
        ).scalars().all()
        ticket_events = (
            await self.session.execute(
                select(TicketEvent).where(TicketEvent.trace_id == trace_id).order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            )
        ).scalars().all()
        device_events = (
            await self.session.execute(
                select(DeviceEvent).where(DeviceEvent.trace_id == trace_id).order_by(DeviceEvent.created_at.asc(), DeviceEvent.id.asc())
            )
        ).scalars().all()

        runtime_audits: list[AgentRuntimeAudit] = []
        operation_ids = [item.operation_id for item in operations if item.operation_id]
        if operation_ids:
            runtime_audits = (
                await self.session.execute(
                    select(AgentRuntimeAudit)
                    .where(AgentRuntimeAudit.operation_id.in_(operation_ids))
                    .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
                )
            ).scalars().all()

        return TraceProjectionSources(
            operations=list(operations),
            ticket_events=list(ticket_events),
            device_events=list(device_events),
            runtime_audits=list(runtime_audits),
        )

    async def _collect_ticket_root_sources(self, trace_id: str, ticket: Ticket) -> TraceProjectionSources:
        operations = (
            await self.session.execute(
                select(Operation)
                .where(Operation.ticket_id == ticket.ticket_id)
                .order_by(Operation.queued_at.asc(), Operation.operation_id.asc())
            )
        ).scalars().all()
        ticket_events = (
            await self.session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket.ticket_id)
                .order_by(TicketEvent.created_at.asc(), TicketEvent.id.asc())
            )
        ).scalars().all()

        operation_ids = [item.operation_id for item in operations if item.operation_id]
        device_events: list[DeviceEvent] = []
        runtime_audits: list[AgentRuntimeAudit] = []
        if operation_ids:
            device_events = (
                await self.session.execute(
                    select(DeviceEvent)
                    .where(or_(DeviceEvent.operation_id.in_(operation_ids), DeviceEvent.trace_id == trace_id))
                    .order_by(DeviceEvent.created_at.asc(), DeviceEvent.id.asc())
                )
            ).scalars().all()
            runtime_audits = (
                await self.session.execute(
                    select(AgentRuntimeAudit)
                    .where(or_(AgentRuntimeAudit.operation_id.in_(operation_ids), AgentRuntimeAudit.ticket_id == ticket.ticket_id))
                    .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
                )
            ).scalars().all()
        else:
            device_events = (
                await self.session.execute(
                    select(DeviceEvent)
                    .where(DeviceEvent.trace_id == trace_id)
                    .order_by(DeviceEvent.created_at.asc(), DeviceEvent.id.asc())
                )
            ).scalars().all()
            runtime_audits = (
                await self.session.execute(
                    select(AgentRuntimeAudit)
                    .where(AgentRuntimeAudit.ticket_id == ticket.ticket_id)
                    .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
                )
            ).scalars().all()

        return TraceProjectionSources(
            operations=list(operations),
            ticket_events=list(ticket_events),
            device_events=list(device_events),
            runtime_audits=list(runtime_audits),
            root_ticket=ticket,
        )

    async def _clear_trace_dependents(self, trace_id: str) -> None:
        span_ids_subquery = select(ObserverSpan.span_id).where(ObserverSpan.trace_id == trace_id)
        await self.session.execute(delete(ObserverErrorOccurrence).where(ObserverErrorOccurrence.trace_id == trace_id))
        await self.session.execute(delete(ObserverSpanLink).where(ObserverSpanLink.span_id.in_(span_ids_subquery)))
        await self.session.execute(delete(ObserverSpan).where(ObserverSpan.trace_id == trace_id))
        await self.session.flush()

    async def _clear_trace_projection(self, trace_id: str) -> None:
        await self._clear_trace_dependents(trace_id)
        await self.session.execute(delete(ObserverTrace).where(ObserverTrace.trace_id == trace_id))
        await self.session.flush()

    async def _acquire_trace_projection_db_lock(self, trace_id: str) -> None:
        bind = self.session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        advisory_key = int.from_bytes(hashlib.blake2b(trace_id.encode("utf-8"), digest_size=8).digest(), "big", signed=True)
        await self.session.execute(select(func.pg_advisory_xact_lock(advisory_key)))

    async def _filter_traces_by_degradation(
        self,
        traces: list[ObserverTrace],
        filters: TraceOverlayFilters,
    ) -> list[ObserverTrace]:
        if not traces:
            return traces
        min_duration_ms = int(filters.min_duration_ms or 0)
        min_retry_count = int(filters.min_retry_count or 0)
        if min_duration_ms <= 0 and min_retry_count <= 0:
            return traces

        trace_ids = [trace.trace_id for trace in traces]
        ticket_ids = [trace.ticket_id for trace in traces if trace.root_kind == "ticket" and trace.ticket_id]
        stmt = select(Operation).where(or_(Operation.trace_id.in_(trace_ids), Operation.ticket_id.in_(ticket_ids)))
        operations = (await self.session.execute(stmt)).scalars().all()

        operations_by_trace_id: dict[str, list[Operation]] = {}
        operations_by_ticket_id: dict[str, list[Operation]] = {}
        for operation in operations:
            operations_by_trace_id.setdefault(operation.trace_id, []).append(operation)
            if operation.ticket_id:
                operations_by_ticket_id.setdefault(operation.ticket_id, []).append(operation)

        filtered: list[ObserverTrace] = []
        for trace in traces:
            scoped_operations = (
                operations_by_ticket_id.get(trace.ticket_id or "", [])
                if trace.root_kind == "ticket" and trace.ticket_id
                else operations_by_trace_id.get(trace.trace_id, [])
            )
            if min_duration_ms > 0:
                operation_durations = [_operation_duration_ms(item) or 0 for item in scoped_operations]
                if not operation_durations and (trace.duration_ms or 0) <= min_duration_ms:
                    continue
                if operation_durations and max(operation_durations) <= min_duration_ms:
                    continue
            if min_retry_count > 0 and not any(int(item.retry_count or 0) >= min_retry_count for item in scoped_operations):
                continue
            filtered.append(trace)
        return filtered

    def _projection_needs_refresh(self, trace: ObserverTrace, source_last_seen_at: Optional[datetime]) -> bool:
        if source_last_seen_at is None:
            return trace.span_count == 0
        projected_at = trace.updated_at or trace.created_at
        if projected_at is None:
            return True
        return source_last_seen_at > projected_at

    def _source_last_seen_at(self, sources: TraceProjectionSources) -> Optional[datetime]:
        candidates = [
            *[
                timestamp
                for timestamp in (
                    getattr(sources.root_ticket, "created_at", None),
                    getattr(sources.root_ticket, "updated_at", None),
                    getattr(sources.root_ticket, "resolved_at", None),
                    getattr(sources.root_ticket, "closed_at", None),
                )
                if timestamp
            ],
            *[
                timestamp
                for operation in sources.operations
                for timestamp in (
                    operation.queued_at,
                    operation.sent_at,
                    operation.accepted_at,
                    operation.started_at,
                    operation.finished_at,
                    operation.canceled_at,
                )
                if timestamp
            ],
            *[item.created_at for item in sources.ticket_events if item.created_at],
            *[item.created_at for item in sources.device_events if item.created_at],
            *[item.created_at for item in sources.runtime_audits if item.created_at],
        ]
        return max(candidates) if candidates else None

    async def _existing_trace_signatures(self, trace_id: str) -> set[str]:
        rows = await self.session.execute(
            select(ObserverErrorOccurrence.error_signature).where(ObserverErrorOccurrence.trace_id == trace_id)
        )
        return {value for value in rows.scalars().all() if value}

    async def _count_trace_spans(self, trace_id: str) -> int:
        row = await self.session.execute(
            select(func.count()).select_from(ObserverSpan).where(ObserverSpan.trace_id == trace_id)
        )
        return int(row.scalar_one() or 0)

    def _build_span_payloads(
        self,
        trace_id: str,
        sources: TraceProjectionSources,
        *,
        source_last_seen_at: Optional[datetime],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        operation_span_ids: dict[str, str] = {}
        root_ticket = sources.root_ticket

        primary_operation = sources.operations[0] if sources.operations else None
        primary_ticket = root_ticket.ticket_id if root_ticket else (
            primary_operation.ticket_id if primary_operation else next((item.ticket_id for item in sources.ticket_events), None)
        )
        primary_device = root_ticket.device_id if root_ticket else (
            primary_operation.device_id if primary_operation else next(
            (item.device_id for item in [*sources.ticket_events, *sources.device_events, *sources.runtime_audits] if getattr(item, "device_id", None)),
            None,
        ))
        primary_job_id = primary_operation.job_id if primary_operation else None
        root_span_id = None

        if root_ticket is not None:
            root_span_id = _trace_scoped_uuid(trace_id, f"ticket_root:{root_ticket.ticket_id}")
            payloads.append(
                {
                    "span_id": root_span_id,
                    "trace_id": trace_id,
                    "parent_span_id": None,
                    "source_type": "ticket_root",
                    "source_ref": root_ticket.ticket_id,
                    "name": "ticket.lifecycle",
                    "kind": "internal",
                    "component": "tickets",
                    "event_type": root_ticket.status,
                    "module_name": None,
                    "tool_name": None,
                    "status": _span_status_from_ticket_status(root_ticket.status),
                    "started_at": root_ticket.created_at,
                    "finished_at": root_ticket.closed_at or root_ticket.resolved_at,
                    "duration_ms": _duration_ms(root_ticket.created_at, root_ticket.closed_at or root_ticket.resolved_at),
                    "attrs_json": {
                        "ticket_id": root_ticket.ticket_id,
                        "ticket_code": root_ticket.ticket_code,
                        "ticket_status": root_ticket.status,
                        "observer_root_trace_id": root_ticket.observer_root_trace_id,
                    },
                }
            )

        for index, operation in enumerate(sources.operations):
            module_name, tool_name = _split_tool_name(operation.tool_name)
            span_id = _trace_scoped_uuid(trace_id, f"operation:{operation.operation_id}")
            parent_span_id = root_span_id
            if index > 0 and primary_operation and root_span_id is None:
                parent_span_id = operation_span_ids.get(primary_operation.operation_id)
            finished_at = _operation_finished_at(operation)
            operation_span_ids[operation.operation_id] = span_id
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "source_type": "operation",
                    "source_ref": operation.operation_id,
                    "name": f"operation.{operation.kind}",
                    "kind": "internal",
                    "component": "operations",
                    "event_type": operation.status,
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "status": _span_status_from_operation(operation.status),
                    "started_at": operation.queued_at,
                    "finished_at": finished_at,
                    "duration_ms": _duration_ms(operation.queued_at, finished_at),
                    "attrs_json": {
                        "operation_id": operation.operation_id,
                        "kind": operation.kind,
                        "status": operation.status,
                        "actor_role": operation.actor_role,
                        "retry_count": operation.retry_count,
                        "max_retries": operation.max_retries,
                        "error_code": operation.error_code,
                        "error_message": operation.error_message,
                        "result_summary": operation.result_summary,
                    },
                }
            )
            payloads.extend(self._build_operation_stage_spans(trace_id, operation, span_id))

        if root_span_id is None:
            root_span_id = operation_span_ids.get(primary_operation.operation_id) if primary_operation else None

        for event in sources.ticket_events:
            span_id = _trace_scoped_uuid(trace_id, f"ticket_event:{event.id}")
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": operation_span_ids.get(event.operation_id) or root_span_id,
                    "source_type": "ticket_event",
                    "source_ref": str(event.id),
                    "name": f"ticket.{event.event_type}",
                    "kind": "event",
                    "component": "ticket_events",
                    "event_type": event.event_type,
                    "module_name": _compact_text((event.payload or {}).get("module_name")),
                    "tool_name": _compact_text((event.payload or {}).get("tool_name")),
                    "status": "ok",
                    "started_at": event.created_at,
                    "finished_at": event.created_at,
                    "duration_ms": 0,
                    "attrs_json": {
                        "ticket_event_id": event.id,
                        "operation_id": event.operation_id,
                        "event_id": event.event_id,
                        "payload": event.payload or {},
                    },
                }
            )
            if root_span_id is None:
                root_span_id = span_id

        for event in sources.device_events:
            span_id = _trace_scoped_uuid(trace_id, f"device_event:{event.id}")
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": operation_span_ids.get(event.operation_id) or root_span_id,
                    "source_type": "device_event",
                    "source_ref": str(event.id),
                    "name": f"device.{event.event_type}",
                    "kind": "event",
                    "component": "device_events",
                    "event_type": event.event_type,
                    "module_name": _compact_text((event.payload or {}).get("module_name")),
                    "tool_name": _compact_text((event.payload or {}).get("tool_name")),
                    "status": "ok",
                    "started_at": event.created_at,
                    "finished_at": event.created_at,
                    "duration_ms": 0,
                    "attrs_json": {
                        "device_event_id": event.id,
                        "operation_id": event.operation_id,
                        "event_id": event.event_id,
                        "payload": event.payload or {},
                    },
                }
            )
            if root_span_id is None:
                root_span_id = span_id

        for audit in sources.runtime_audits:
            linked_operation_span_id = operation_span_ids.get(audit.operation_id or "")
            span_id = _trace_scoped_uuid(trace_id, f"runtime_audit:{audit.id}")
            redacted_details = redact_sensitive_payload(audit.details_json or {})
            module_name = _compact_text(redacted_details.get("module_name"))
            tool_name = _compact_text(redacted_details.get("tool_name"))
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": linked_operation_span_id or root_span_id,
                    "source_type": "agent_runtime_audit",
                    "source_ref": str(audit.id),
                    "name": f"agent.audit.{audit.event_type}",
                    "kind": "event",
                    "component": "agent_runtime_audit",
                    "event_type": audit.event_type,
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "status": _span_status_from_severity(audit.severity),
                    "started_at": audit.created_at,
                    "finished_at": audit.created_at,
                    "duration_ms": 0,
                    "attrs_json": {
                        "audit_id": audit.id,
                        "severity": audit.severity,
                        "source": audit.source,
                        "details_json": redacted_details,
                    },
                }
            )
            if linked_operation_span_id:
                links.append(
                    {
                        "span_id": span_id,
                        "linked_trace_id": trace_id,
                        "linked_span_id": linked_operation_span_id,
                        "reason": "operation_id_bridge",
                        "attrs_json": {"operation_id": audit.operation_id},
                    }
                )
            if root_span_id is None:
                root_span_id = span_id

        all_times = [
            *([root_ticket.created_at] if root_ticket and root_ticket.created_at else []),
            *[item.queued_at for item in sources.operations if item.queued_at],
            *[item.created_at for item in sources.ticket_events],
            *[item.created_at for item in sources.device_events],
            *[item.created_at for item in sources.runtime_audits],
        ]
        started_at = min(all_times)
        trace_status = self._summarize_trace_status(sources)
        finished_at = None
        if trace_status not in {"running"}:
            terminal_times = [
                *[
                    timestamp
                    for timestamp in (
                        getattr(root_ticket, "resolved_at", None),
                        getattr(root_ticket, "closed_at", None),
                    )
                    if timestamp
                ],
                *[item.canceled_at or item.finished_at for item in sources.operations if (item.canceled_at or item.finished_at)],
                *[item.created_at for item in sources.ticket_events],
                *[item.created_at for item in sources.device_events],
                *[item.created_at for item in sources.runtime_audits],
            ]
            finished_at = max(terminal_times) if terminal_times else None

        attrs_json = {
            "root_scope": "ticket" if root_ticket else "execution",
            "source_counts": {
                "operations": len(sources.operations),
                "ticket_events": len(sources.ticket_events),
                "device_events": len(sources.device_events),
                "agent_runtime_audit": len(sources.runtime_audits),
            },
            "operation_count": len(sources.operations),
            "max_retry_count": max((int(item.retry_count or 0) for item in sources.operations), default=0),
            "source_last_seen_at": _iso(source_last_seen_at),
            "tool_names": sorted(
                {
                    value
                    for value in [
                        *[item.tool_name for item in sources.operations],
                        *[(item.payload or {}).get("tool_name") for item in sources.ticket_events],
                        *[(item.payload or {}).get("tool_name") for item in sources.device_events],
                        *[(item.details_json or {}).get("tool_name") for item in sources.runtime_audits],
                    ]
                    if value
                }
            ),
        }
        if root_ticket is not None:
            attrs_json["ticket_status"] = root_ticket.status
            attrs_json["ticket_code"] = root_ticket.ticket_code
            attrs_json["observer_root_trace_id"] = root_ticket.observer_root_trace_id

        return payloads, links, {
            "root_span_id": root_span_id,
            "root_kind": "ticket" if root_ticket is not None else (primary_operation.kind if primary_operation else (sources.ticket_events[0].event_type if sources.ticket_events else "trace")),
            "ticket_id": primary_ticket,
            "device_id": primary_device,
            "operation_id": primary_operation.operation_id if (primary_operation and len(sources.operations) == 1) else None,
            "job_id": primary_job_id,
            "status": trace_status,
            "started_at": started_at,
            "finished_at": finished_at,
            "attrs_json": attrs_json,
        }

    def _build_operation_stage_spans(self, trace_id: str, operation: Operation, parent_span_id: str) -> list[dict[str, Any]]:
        points: list[tuple[str, datetime]] = []
        if operation.queued_at:
            points.append(("queued", operation.queued_at))
        if operation.sent_at:
            points.append(("sent", operation.sent_at))
        if operation.accepted_at:
            points.append(("accepted", operation.accepted_at))
        if operation.started_at:
            points.append(("running", operation.started_at))
        terminal_time = operation.canceled_at or operation.finished_at
        if terminal_time:
            points.append((operation.status or "finished", terminal_time))

        spans: list[dict[str, Any]] = []
        module_name, tool_name = _split_tool_name(operation.tool_name)
        for index, (stage, started_at) in enumerate(points):
            finished_at = points[index + 1][1] if index + 1 < len(points) else terminal_time or started_at
            spans.append(
                {
                    "span_id": _trace_scoped_uuid(trace_id, f"operation_stage:{operation.operation_id}:{stage}"),
                    "trace_id": trace_id,
                    "parent_span_id": parent_span_id,
                    "source_type": "operation_stage",
                    "source_ref": f"{operation.operation_id}:{stage}",
                    "name": f"operation.stage.{stage}",
                    "kind": "internal",
                    "component": "operations",
                    "event_type": stage,
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "status": _span_status_from_operation(stage if stage in TERMINAL_OPERATION_STATUSES else operation.status),
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_ms": _duration_ms(started_at, finished_at),
                    "attrs_json": {
                        "operation_id": operation.operation_id,
                        "stage": stage,
                        "retry_count": operation.retry_count,
                    },
                }
            )
        return spans

    def _build_occurrence_payloads(
        self,
        trace_id: str,
        sources: TraceProjectionSources,
        span_payloads: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        span_ids_by_source: dict[tuple[str, str], str] = {
            (payload["source_type"], payload["source_ref"]): payload["span_id"] for payload in span_payloads
        }
        occurrences: list[dict[str, Any]] = []

        for operation in sources.operations:
            if operation.status not in ERROR_OPERATION_STATUSES:
                continue
            module_name, tool_name = _split_tool_name(operation.tool_name)
            message_norm = _normalize_message(operation.error_message)
            error_kind = _compact_text(operation.error_code) or operation.status
            exception_type = _extract_exception_type(operation.error_message)
            signature = self._make_error_signature(
                error_kind=error_kind,
                component="operations",
                module_name=module_name,
                tool_name=tool_name,
                exception_type=exception_type,
                failure_stage=operation.status,
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("operation", operation.operation_id)),
                    "error_signature": signature,
                    "device_id": operation.device_id,
                    "ticket_id": operation.ticket_id,
                    "operation_id": operation.operation_id,
                    "component": "operations",
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "error_kind": error_kind,
                    "exception_type": exception_type,
                    "failure_stage": operation.status,
                    "severity": "error",
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1((message_norm or "").encode("utf-8")).hexdigest()[:16] if message_norm else None,
                    "attrs_json": {
                        "error_code": operation.error_code,
                        "error_message": operation.error_message,
                    },
                    "created_at": operation.finished_at or operation.queued_at,
                }
            )

        operation_lookup = {item.operation_id: item for item in sources.operations if item.operation_id}
        for audit in sources.runtime_audits:
            if str(audit.severity or "").strip().lower() not in ERROR_AUDIT_SEVERITIES:
                continue
            details = redact_sensitive_payload(audit.details_json or {})
            linked_operation = operation_lookup.get(audit.operation_id or "")
            linked_module_name, linked_tool_name = _split_tool_name(linked_operation.tool_name if linked_operation else None)
            module_name = _compact_text(details.get("module_name")) or linked_module_name
            tool_name = _compact_text(details.get("tool_name")) or linked_tool_name
            error_kind = _compact_text(details.get("error_kind")) or audit.event_type
            exception_type = _compact_text(details.get("exception_type"))
            failure_stage = _compact_text(details.get("failure_stage")) or audit.event_type
            message_norm = _normalize_message(details.get("message") or details.get("reason") or audit.event_type)
            signature = self._make_error_signature(
                error_kind=error_kind,
                component="agent_runtime_audit",
                module_name=module_name,
                tool_name=tool_name,
                exception_type=exception_type,
                failure_stage=failure_stage,
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("agent_runtime_audit", str(audit.id))),
                    "error_signature": signature,
                    "device_id": audit.device_id,
                    "ticket_id": audit.ticket_id,
                    "operation_id": audit.operation_id,
                    "component": "agent_runtime_audit",
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "error_kind": error_kind,
                    "exception_type": exception_type,
                    "failure_stage": failure_stage,
                    "severity": str(audit.severity or "error").lower(),
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1(json.dumps(details, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
                    "attrs_json": {"source": audit.source, "details_json": details},
                    "created_at": audit.created_at,
                }
            )

        result_keys: set[tuple[Optional[str], Optional[str]]] = set()
        for event in sources.ticket_events:
            if event.event_type != "tool_call_result":
                continue
            payload = event.payload if isinstance(event.payload, dict) else {}
            result_keys.add(
                (
                    _compact_text(event.operation_id),
                    _compact_text(payload.get("call_id")),
                )
            )

        for event in sources.ticket_events:
            if event.event_type != "tool_call_started":
                continue
            payload = event.payload if isinstance(event.payload, dict) else {}
            operation_id = _compact_text(event.operation_id)
            call_id = _compact_text(payload.get("call_id"))
            if (operation_id, call_id) in result_keys:
                continue
            if operation_id and operation_id in operation_lookup:
                continue

            module_name, tool_name = _split_tool_name(_compact_text(payload.get("tool_name")))
            error_kind = "TOOL_DISPATCH_ORPHANED"
            failure_stage = "tool_call_started"
            message_norm = _normalize_message(
                f"tool dispatch started without persisted operation or result for {tool_name or 'unknown_tool'}"
            )
            signature = self._make_error_signature(
                error_kind=error_kind,
                component="ticket_events",
                module_name=module_name,
                tool_name=tool_name,
                exception_type=None,
                failure_stage=failure_stage,
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("ticket_event", str(event.id))),
                    "error_signature": signature,
                    "device_id": event.device_id,
                    "ticket_id": event.ticket_id,
                    "operation_id": operation_id,
                    "component": "ticket_events",
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "error_kind": error_kind,
                    "exception_type": None,
                    "failure_stage": failure_stage,
                    "severity": "error",
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1((message_norm or "").encode("utf-8")).hexdigest()[:16] if message_norm else None,
                    "attrs_json": {
                        "event_type": event.event_type,
                        "missing_operation": operation_id not in operation_lookup if operation_id else True,
                        "call_id": call_id,
                        "payload": payload,
                    },
                    "created_at": event.created_at,
                }
            )

        return occurrences

    def _summarize_trace_status(self, sources: TraceProjectionSources) -> str:
        operation_statuses = {str(item.status or "").strip().lower() for item in sources.operations}
        if operation_statuses & ACTIVE_OPERATION_STATUSES:
            return "running"
        if operation_statuses & ERROR_OPERATION_STATUSES:
            return "error"
        if any(str(item.severity or "").strip().lower() in ERROR_AUDIT_SEVERITIES for item in sources.runtime_audits):
            return "error"
        if sources.root_ticket is not None and str(sources.root_ticket.status or "").strip().lower() not in {"resolved", "closed"}:
            return "running"
        if operation_statuses == {"canceled"}:
            return "canceled"
        if operation_statuses and operation_statuses <= TERMINAL_OPERATION_STATUSES:
            return "ok"
        return "ok"

    def _projected_trace_status(self, base_status: str, occurrences: list[dict[str, Any]]) -> str:
        if any(str(item.get("severity") or "").strip().lower() in ERROR_AUDIT_SEVERITIES for item in occurrences):
            return "error"
        return base_status

    def _make_error_signature(
        self,
        *,
        error_kind: Optional[str],
        component: Optional[str],
        module_name: Optional[str],
        tool_name: Optional[str],
        exception_type: Optional[str],
        failure_stage: Optional[str],
        message_norm: Optional[str],
    ) -> str:
        stem_parts = [
            _slugify(error_kind),
            _slugify(component),
            _slugify(module_name or tool_name),
            _slugify(exception_type or failure_stage),
        ]
        digest_source = "|".join([value for value in [message_norm, error_kind, component, module_name, tool_name, exception_type, failure_stage] if value])
        digest = hashlib.sha1(digest_source.encode("utf-8")).hexdigest()[:10] if digest_source else "static"
        return ":".join(stem_parts + [digest])[:160]

    async def _refresh_signatures(self, signatures: Iterable[str]) -> None:
        for error_signature in {item for item in signatures if item}:
            count_stmt = select(
                func.count(ObserverErrorOccurrence.occurrence_id),
                func.min(ObserverErrorOccurrence.created_at),
                func.max(ObserverErrorOccurrence.created_at),
                func.count(func.distinct(ObserverErrorOccurrence.device_id)),
            ).where(ObserverErrorOccurrence.error_signature == error_signature)
            count, first_seen_at, last_seen_at, affected_devices = (await self.session.execute(count_stmt)).one()
            existing = await self.session.get(ObserverErrorSignature, error_signature)
            if not count:
                if existing is not None:
                    await self.session.delete(existing)
                continue

            sample = (
                await self.session.execute(
                    select(ObserverErrorOccurrence)
                    .where(ObserverErrorOccurrence.error_signature == error_signature)
                    .order_by(ObserverErrorOccurrence.created_at.desc())
                    .limit(1)
                )
            ).scalar_one()
            title = _signature_title(
                error_kind=sample.error_kind,
                module_name=sample.module_name,
                tool_name=sample.tool_name,
                component=sample.component,
            )
            if existing is None:
                existing = ObserverErrorSignature(
                    error_signature=error_signature,
                    title=title,
                    component=sample.component,
                    module_name=sample.module_name,
                    tool_name=sample.tool_name,
                    error_kind=sample.error_kind,
                    exception_type=sample.exception_type,
                    failure_stage=sample.failure_stage,
                    message_sample=sample.message_norm,
                    first_seen_at=first_seen_at,
                    last_seen_at=last_seen_at,
                    occurrences_count=int(count or 0),
                    affected_devices_count=int(affected_devices or 0),
                    attrs_json={},
                )
                self.session.add(existing)
            else:
                existing.title = title
                existing.component = sample.component
                existing.module_name = sample.module_name
                existing.tool_name = sample.tool_name
                existing.error_kind = sample.error_kind
                existing.exception_type = sample.exception_type
                existing.failure_stage = sample.failure_stage
                existing.message_sample = sample.message_norm
                existing.first_seen_at = first_seen_at
                existing.last_seen_at = last_seen_at
                existing.occurrences_count = int(count or 0)
                existing.affected_devices_count = int(affected_devices or 0)

    def _serialize_trace(self, trace: ObserverTrace) -> dict[str, Any]:
        return {
            "trace_id": trace.trace_id,
            "root_span_id": trace.root_span_id,
            "root_kind": trace.root_kind,
            "ticket_id": trace.ticket_id,
            "device_id": trace.device_id,
            "operation_id": trace.operation_id,
            "job_id": trace.job_id,
            "status": trace.status,
            "started_at": _iso(trace.started_at),
            "finished_at": _iso(trace.finished_at),
            "duration_ms": trace.duration_ms,
            "span_count": trace.span_count,
            "error_count": trace.error_count,
            "attrs_json": redact_sensitive_payload(trace.attrs_json or {}),
        }

    def _serialize_span(self, span: ObserverSpan) -> dict[str, Any]:
        return {
            "span_id": span.span_id,
            "trace_id": span.trace_id,
            "parent_span_id": span.parent_span_id,
            "source_type": span.source_type,
            "source_ref": span.source_ref,
            "name": span.name,
            "kind": span.kind,
            "component": span.component,
            "event_type": span.event_type,
            "module_name": span.module_name,
            "tool_name": span.tool_name,
            "status": span.status,
            "started_at": _iso(span.started_at),
            "finished_at": _iso(span.finished_at),
            "duration_ms": span.duration_ms,
            "attrs_json": redact_sensitive_payload(span.attrs_json or {}),
        }

    def _serialize_span_link(self, link: ObserverSpanLink) -> dict[str, Any]:
        return {
            "id": link.id,
            "span_id": link.span_id,
            "linked_trace_id": link.linked_trace_id,
            "linked_span_id": link.linked_span_id,
            "reason": link.reason,
            "attrs_json": redact_sensitive_payload(link.attrs_json or {}),
            "created_at": _iso(link.created_at),
        }

    def _serialize_signature(self, signature: ObserverErrorSignature) -> dict[str, Any]:
        return {
            "error_signature": signature.error_signature,
            "title": signature.title,
            "component": signature.component,
            "module_name": signature.module_name,
            "tool_name": signature.tool_name,
            "error_kind": signature.error_kind,
            "exception_type": signature.exception_type,
            "failure_stage": signature.failure_stage,
            "message_sample": signature.message_sample,
            "first_seen_at": _iso(signature.first_seen_at),
            "last_seen_at": _iso(signature.last_seen_at),
            "occurrences_count": signature.occurrences_count,
            "affected_devices_count": signature.affected_devices_count,
            "attrs_json": redact_sensitive_payload(signature.attrs_json or {}),
        }

    def _serialize_occurrence(self, occurrence: ObserverErrorOccurrence) -> dict[str, Any]:
        return {
            "occurrence_id": occurrence.occurrence_id,
            "trace_id": occurrence.trace_id,
            "span_id": occurrence.span_id,
            "error_signature": occurrence.error_signature,
            "device_id": occurrence.device_id,
            "ticket_id": occurrence.ticket_id,
            "operation_id": occurrence.operation_id,
            "component": occurrence.component,
            "module_name": occurrence.module_name,
            "tool_name": occurrence.tool_name,
            "error_kind": occurrence.error_kind,
            "exception_type": occurrence.exception_type,
            "failure_stage": occurrence.failure_stage,
            "severity": occurrence.severity,
            "message_norm": occurrence.message_norm,
            "stack_hash": occurrence.stack_hash,
            "attrs_json": redact_sensitive_payload(occurrence.attrs_json or {}),
            "created_at": _iso(occurrence.created_at),
        }
