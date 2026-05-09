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

import sqlalchemy as sa
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import (
    AgentObserverEvent,
    AgentRuntimeAudit,
    DeviceEvent,
    ObserverErrorOccurrence,
    ObserverErrorSignature,
    ObserverSpan,
    ObserverSpanLink,
    ObserverTrace,
    Operation,
    PlaybookRun,
    PlaybookStep,
    PlaybookStepRun,
    Ticket,
    TicketEvent,
    Device,
)
from shared.redaction import redact_sensitive_payload


OBSERVER_NAMESPACE = uuid.UUID("7f646dd0-36d4-4789-953b-fc8d1dd0d3e9")
TERMINAL_OPERATION_STATUSES = {"succeeded", "success", "failed", "timed_out", "canceled"}
ERROR_OPERATION_STATUSES = {"failed", "timed_out"}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
ERROR_AUDIT_SEVERITIES = {"error", "critical"}
PROBLEM_AUDIT_SEVERITIES = ERROR_AUDIT_SEVERITIES | {"warning"}
RUNTIME_AUDIT_TRACE_PREFIX = "00000000-a075-4a75-8000-"
PLAYBOOK_RUN_TRACE_PREFIX = "00000000-71a7-4b00-8000-"
RUNTIME_AUDIT_PROJECTION_WINDOW = timedelta(minutes=15)
PROVISIONING_AUDIT_EVENTS = {
    "connection_request_created",
    "connection_request_approved",
    "connection_request_rejected",
    "connection_request_policy_rejected",
    "connection_request_token_delivered",
    "connection_request_token_limit",
    "connection_request_approval_waiting_delivery",
}
AUTH_AUDIT_EVENTS = {
    "invalid_token",
    "token_revoked",
    "handshake_failed",
    "device_fingerprint_mismatch",
}
UPDATE_AUDIT_EVENTS = {
    "update_requested",
    "update_failed",
    "update_handshake_confirmed",
}
RUNTIME_AUDIT_EVENTS = {
    "handshake_ok",
    "agent_offline",
    "agent_disconnect",
    "agent_superseded",
}
MODULE_RECONCILE_AUDIT_EVENTS = {"module_reconcile_failed"}
WEB_AUTH_AUDIT_EVENTS = {"web_auth_failed", "web_auth_forbidden"}
OBSERVER_RUNTIME_AUDIT_EVENTS = {"observer_runtime_degraded"}
PROBLEM_AUDIT_EVENTS = (
    PROVISIONING_AUDIT_EVENTS
    | AUTH_AUDIT_EVENTS
    | UPDATE_AUDIT_EVENTS
    | MODULE_RECONCILE_AUDIT_EVENTS
    | WEB_AUTH_AUDIT_EVENTS
    | OBSERVER_RUNTIME_AUDIT_EVENTS
    | {"agent_offline", "agent_disconnect", "agent_superseded"}
)
DANGEROUS_ROOT_KINDS = {
    "agent_update",
    "agent_auth",
    "agent_runtime",
    "device_provisioning",
    "module_install",
    "module_reconcile",
    "module_remove",
    "web_auth",
    "observer_runtime",
    "consent",
}
_TRACE_PROJECTION_LOCK_GUARD = asyncio.Lock()
_TRACE_PROJECTION_LOCKS: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _observer_trace_url(trace_id: str | None) -> str | None:
    value = str(trace_id or "").strip()
    if not value:
        return None
    return f"/app/admin/observer?trace_id={value}"


@dataclass(slots=True)
class TraceOverlayFilters:
    query: Optional[str] = None
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
    playbook_run_id: Optional[int] = None
    step_run_id: Optional[int] = None
    route: Optional[str] = None


@dataclass(slots=True)
class TraceProjectionSources:
    operations: list[Operation]
    ticket_events: list[TicketEvent]
    device_events: list[DeviceEvent]
    runtime_audits: list[AgentRuntimeAudit]
    agent_events: list[AgentObserverEvent]
    playbook_run: Optional[PlaybookRun] = None
    playbook_step_runs: list[tuple[PlaybookStepRun, PlaybookStep]] | None = None
    root_ticket: Optional[Ticket] = None

    @property
    def empty(self) -> bool:
        return not any((
            self.operations,
            self.ticket_events,
            self.device_events,
            self.runtime_audits,
            self.agent_events,
            self.playbook_run,
            self.playbook_step_runs,
            self.root_ticket,
        ))


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


def _runtime_audit_trace_id(audit_id: Optional[int]) -> Optional[str]:
    if audit_id is None:
        return None
    try:
        value = int(audit_id)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    if value <= 0xFFFFFFFFFFFF:
        return f"{RUNTIME_AUDIT_TRACE_PREFIX}{value:012x}"
    return str(uuid.uuid5(OBSERVER_NAMESPACE, f"runtime_audit:{value}"))


def _runtime_audit_id_from_trace_id(trace_id: str) -> Optional[int]:
    value = str(trace_id or "").strip().lower()
    if not value.startswith(RUNTIME_AUDIT_TRACE_PREFIX):
        return None
    suffix = value[len(RUNTIME_AUDIT_TRACE_PREFIX):]
    if len(suffix) != 12:
        return None
    try:
        return int(suffix, 16)
    except ValueError:
        return None


def _playbook_run_trace_id(playbook_run_id: Optional[int]) -> Optional[str]:
    if playbook_run_id is None:
        return None
    try:
        value = int(playbook_run_id)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    if value <= 0xFFFFFFFFFFFF:
        return f"{PLAYBOOK_RUN_TRACE_PREFIX}{value:012x}"
    return str(uuid.uuid5(OBSERVER_NAMESPACE, f"playbook_run:{value}"))


def _playbook_run_id_from_trace_id(trace_id: str) -> Optional[int]:
    value = str(trace_id or "").strip().lower()
    if not value.startswith(PLAYBOOK_RUN_TRACE_PREFIX):
        return None
    suffix = value[len(PLAYBOOK_RUN_TRACE_PREFIX):]
    if len(suffix) != 12:
        return None
    try:
        return int(suffix, 16)
    except ValueError:
        return None


def _runtime_audit_root_kind(audit: AgentRuntimeAudit) -> str:
    event_type = str(audit.event_type or "").strip().lower()
    source = str(audit.source or "").strip().lower()
    if event_type in UPDATE_AUDIT_EVENTS or event_type.startswith("update_"):
        return "agent_update"
    if event_type in PROVISIONING_AUDIT_EVENTS or source.startswith("connection_request"):
        return "device_provisioning"
    if event_type in AUTH_AUDIT_EVENTS or source == "handshake":
        return "agent_auth"
    if event_type in MODULE_RECONCILE_AUDIT_EVENTS or source == "module_reconcile":
        return "module_reconcile"
    if event_type in WEB_AUTH_AUDIT_EVENTS or source == "web_auth":
        return "web_auth"
    if event_type in OBSERVER_RUNTIME_AUDIT_EVENTS or source == "observer_runtime":
        return "observer_runtime"
    if event_type in RUNTIME_AUDIT_EVENTS:
        return "agent_runtime"
    return "agent_runtime"


def _runtime_root_kind_from_audits(audits: Iterable[AgentRuntimeAudit]) -> str:
    kinds = [_runtime_audit_root_kind(audit) for audit in audits]
    for preferred in ("agent_update", "module_reconcile", "web_auth", "observer_runtime", "device_provisioning", "agent_auth", "agent_runtime"):
        if preferred in kinds:
            return preferred
    return "trace"


def _runtime_audit_is_problem(audit: AgentRuntimeAudit) -> bool:
    severity = str(audit.severity or "").strip().lower()
    if severity in ERROR_AUDIT_SEVERITIES:
        return True
    event_type = str(audit.event_type or "").strip().lower()
    return severity in PROBLEM_AUDIT_SEVERITIES and event_type in PROBLEM_AUDIT_EVENTS


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


def _span_status_from_playbook_status(status: Optional[str]) -> str:
    key = str(status or "").strip().lower()
    if key in {"failed", "error", "timed_out"}:
        return "error"
    if key in {"running", "pending"}:
        return "running"
    if key == "skipped":
        return "skipped"
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
        operation_trace_ids: list[str] = []
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
        if filters.operation_id:
            op_row = (
                await self.session.execute(
                    select(Operation.trace_id, Operation.ticket_id)
                    .where(Operation.operation_id == filters.operation_id)
                    .limit(1)
                )
            ).first()
            if op_row is not None:
                op_trace_id = _compact_text(op_row[0])
                op_ticket_id = _compact_text(op_row[1])
                if op_trace_id:
                    operation_trace_ids.append(op_trace_id)
                operation_ticket_root = await self._load_ticket_root_trace_id(op_ticket_id) if op_ticket_id else None
                if operation_ticket_root and operation_ticket_root not in operation_trace_ids:
                    operation_trace_ids.append(operation_ticket_root)
        if filters.trace_id:
            stmt = stmt.where(ObserverTrace.trace_id == filters.trace_id)
        elif ticket_root_trace_id:
            stmt = stmt.where(ObserverTrace.trace_id == ticket_root_trace_id)
        elif filters.ticket_id:
            stmt = stmt.where(ObserverTrace.ticket_id == filters.ticket_id)
        if filters.job_id:
            stmt = stmt.where(ObserverTrace.job_id == filters.job_id)
        if filters.operation_id:
            clauses = [ObserverTrace.operation_id == filters.operation_id]
            if operation_trace_ids:
                clauses.append(ObserverTrace.trace_id.in_(operation_trace_ids))
            stmt = stmt.where(or_(*clauses))
        if filters.device_id:
            stmt = stmt.where(ObserverTrace.device_id == filters.device_id)
        if filters.root_kind:
            stmt = stmt.where(ObserverTrace.root_kind == filters.root_kind)
        if filters.playbook_run_id:
            stmt = stmt.where(ObserverTrace.attrs_json["playbook_run_id"].astext == str(filters.playbook_run_id))
        if filters.step_run_id:
            stmt = stmt.where(
                exists(
                    select(ObserverSpan.span_id).where(
                        ObserverSpan.trace_id == ObserverTrace.trace_id,
                        ObserverSpan.attrs_json["playbook_step_run_id"].astext == str(filters.step_run_id),
                    )
                )
            )
        if filters.route:
            route_pattern = f"%{filters.route}%"
            stmt = stmt.where(
                exists(
                    select(ObserverSpan.span_id).where(
                        ObserverSpan.trace_id == ObserverTrace.trace_id,
                        ObserverSpan.attrs_json.cast(sa.Text).ilike(route_pattern),
                    )
                )
            )
        if filters.status:
            stmt = stmt.where(ObserverTrace.status == filters.status)
        if filters.query:
            query = _compact_text(filters.query)
            if query:
                pattern = f"%{query}%"
                stmt = stmt.where(
                    or_(
                        ObserverTrace.trace_id.ilike(pattern),
                        ObserverTrace.root_kind.ilike(pattern),
                        ObserverTrace.ticket_id.ilike(pattern),
                        ObserverTrace.operation_id.ilike(pattern),
                        ObserverTrace.device_id.ilike(pattern),
                        ObserverTrace.job_id.ilike(pattern),
                        ObserverTrace.attrs_json.cast(sa.Text).ilike(pattern),
                        exists(
                            select(ObserverSpan.span_id).where(
                                ObserverSpan.trace_id == ObserverTrace.trace_id,
                                or_(
                                    ObserverSpan.name.ilike(pattern),
                                    ObserverSpan.component.ilike(pattern),
                                    ObserverSpan.module_name.ilike(pattern),
                                    ObserverSpan.tool_name.ilike(pattern),
                                    ObserverSpan.source_ref.ilike(pattern),
                                ),
                            )
                        ),
                        exists(
                            select(ObserverErrorOccurrence.occurrence_id).where(
                                ObserverErrorOccurrence.trace_id == ObserverTrace.trace_id,
                                or_(
                                    ObserverErrorOccurrence.error_signature.ilike(pattern),
                                    ObserverErrorOccurrence.component.ilike(pattern),
                                    ObserverErrorOccurrence.module_name.ilike(pattern),
                                    ObserverErrorOccurrence.tool_name.ilike(pattern),
                                    ObserverErrorOccurrence.message_norm.ilike(pattern),
                                ),
                            )
                        ),
                    )
                )
        if filters.lookback_hours:
            window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(filters.lookback_hours), 1))
            stmt = stmt.where(
                or_(
                    ObserverTrace.started_at >= window_start,
                    ObserverTrace.finished_at >= window_start,
                )
            )
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

    async def get_quick_diagnosis(
        self,
        filters: TraceOverlayFilters,
        *,
        hot_limit: int = 8,
        signature_limit: int = 6,
        degradation_limit: int = 6,
        flow_limit: int = 6,
    ) -> dict[str, Any]:
        recent_traces = await self.search_traces(filters, limit=max(24, hot_limit * 3))
        hot_traces = self._select_hot_traces(recent_traces, limit=hot_limit)
        top_signatures = await self.search_signatures(filters, limit=signature_limit)
        top_degradations = await self.search_degradations(filters, limit=degradation_limit)
        dangerous_flows = await self._summarize_dangerous_flows(filters, limit=flow_limit)
        return {
            "summary": {
                "recent_trace_count": len(recent_traces),
                "hot_trace_count": len(hot_traces),
                "signature_count": len(top_signatures),
                "degradation_group_count": len(top_degradations),
                "dangerous_flow_count": len(dangerous_flows),
            },
            "hot_traces": hot_traces,
            "recent_traces": recent_traces[:hot_limit],
            "top_signatures": top_signatures,
            "top_degradations": top_degradations,
            "dangerous_flows": dangerous_flows,
        }

    async def get_ticket_observer_summary(
        self,
        ticket_id: str,
        *,
        trace_limit: int = 8,
        signature_limit: int = 6,
        span_limit: int = 12,
        occurrence_limit: int = 6,
    ) -> dict[str, Any]:
        filters = TraceOverlayFilters(ticket_id=ticket_id)
        await self._ensure_projected(filters, limit=max(trace_limit, 12), force=False)

        root_trace_id = await self._load_ticket_root_trace_id(ticket_id)
        related_rows = (
            await self.session.execute(
                select(ObserverTrace)
                .where(ObserverTrace.ticket_id == ticket_id)
                .order_by(ObserverTrace.started_at.desc(), ObserverTrace.trace_id.desc())
                .limit(max(trace_limit, 1))
            )
        ).scalars().all()
        total_traces = await self.session.scalar(
            select(func.count()).select_from(ObserverTrace).where(ObserverTrace.ticket_id == ticket_id)
        )
        active_trace_count = await self.session.scalar(
            select(func.count())
            .select_from(ObserverTrace)
            .where(
                ObserverTrace.ticket_id == ticket_id,
                ObserverTrace.status.in_(tuple(sorted(ACTIVE_OPERATION_STATUSES | {"running"}))),
            )
        )
        error_trace_count = await self.session.scalar(
            select(func.count())
            .select_from(ObserverTrace)
            .where(
                ObserverTrace.ticket_id == ticket_id,
                or_(
                    ObserverTrace.error_count > 0,
                    ObserverTrace.status.in_(("error", "failed", "timed_out", "canceled")),
                ),
            )
        )
        signatures = await self.search_signatures(TraceOverlayFilters(ticket_id=ticket_id), limit=signature_limit)
        recent_occurrences = (
            await self.session.execute(
                select(ObserverErrorOccurrence)
                .where(ObserverErrorOccurrence.ticket_id == ticket_id)
                .order_by(ObserverErrorOccurrence.created_at.desc())
                .limit(max(occurrence_limit, 1))
            )
        ).scalars().all()
        active_related_rows = (
            await self.session.execute(
                select(ObserverTrace)
                .where(
                    ObserverTrace.ticket_id == ticket_id,
                    ObserverTrace.status.in_(tuple(sorted(ACTIVE_OPERATION_STATUSES | {"running"}))),
                )
                .order_by(ObserverTrace.started_at.desc(), ObserverTrace.trace_id.desc())
                .limit(max(trace_limit, 1))
            )
        ).scalars().all()
        error_related_rows = (
            await self.session.execute(
                select(ObserverTrace)
                .where(
                    ObserverTrace.ticket_id == ticket_id,
                    or_(
                        ObserverTrace.error_count > 0,
                        ObserverTrace.status.in_(("error", "failed", "timed_out", "canceled")),
                    ),
                )
                .order_by(ObserverTrace.started_at.desc(), ObserverTrace.trace_id.desc())
                .limit(max(trace_limit, 1))
            )
        ).scalars().all()

        root_detail = await self.get_trace_detail(root_trace_id) if root_trace_id else None
        root_trace = root_detail["trace"] if root_detail else None
        root_excerpt = {
            "spans": (root_detail or {}).get("spans", [])[:span_limit],
            "error_occurrences": (root_detail or {}).get("error_occurrences", [])[:occurrence_limit],
        }
        active_related = [self._serialize_trace(row) for row in active_related_rows]
        error_related = [self._serialize_trace(row) for row in error_related_rows]
        signatures = await self._annotate_ticket_signature_stats(ticket_id, signatures)
        root_trace_id_for_url = str(root_trace_id or "").strip() or None
        top_signature = signatures[0] if signatures else None
        latest_occurrence = recent_occurrences[0] if recent_occurrences else None
        latest_occurrence_payload = self._serialize_occurrence(latest_occurrence) if latest_occurrence else None
        latest_error_label = None
        latest_error_stage = None
        latest_error_at = None
        if latest_occurrence_payload:
            latest_error_label = (
                latest_occurrence_payload.get("message_norm")
                or latest_occurrence_payload.get("error_kind")
                or latest_occurrence_payload.get("exception_type")
                or latest_occurrence_payload.get("error_signature")
            )
            latest_error_stage = latest_occurrence_payload.get("failure_stage") or latest_occurrence_payload.get("component")
            latest_error_at = latest_occurrence_payload.get("created_at")
        health_label = "empty"
        if int(active_trace_count or 0) > 0:
            health_label = "running"
        elif int(error_trace_count or 0) > 0 or signatures:
            health_label = "error"
        elif int(total_traces or 0) > 0:
            health_label = "ok"

        return {
            "summary": {
                "ticket_id": ticket_id,
                "root_trace_id": root_trace_id,
                "root_trace_url": _observer_trace_url(root_trace_id_for_url),
                "root_trace_status": root_trace.get("status") if root_trace else None,
                "root_kind": root_trace.get("root_kind") if root_trace else None,
                "trace_count": int(total_traces or 0),
                "active_trace_count": int(active_trace_count or 0),
                "error_trace_count": int(error_trace_count or 0),
                "signature_count": len(signatures),
                "latest_trace_at": _iso(related_rows[0].started_at) if related_rows else None,
                "latest_error_at": latest_error_at,
                "latest_error_label": latest_error_label,
                "latest_error_stage": latest_error_stage,
                "top_signature": self._compact_signature(top_signature) if top_signature else None,
                "has_active_operation": int(active_trace_count or 0) > 0,
                "health_label": health_label,
            },
            "root_trace": root_trace,
            "root_trace_compact": self._compact_trace(root_trace) if root_trace else None,
            "root_trace_excerpt": root_excerpt,
            "related_traces": [self._serialize_trace(row) for row in related_rows],
            "related_traces_compact": [self._compact_trace(self._serialize_trace(row)) for row in related_rows],
            "signatures": signatures,
            "signatures_compact": [self._compact_signature(item) for item in signatures],
            "recent_occurrences": [self._serialize_occurrence(item) for item in recent_occurrences],
            "recent_occurrences_compact": [self._compact_occurrence(self._serialize_occurrence(item)) for item in recent_occurrences],
            "active_traces": active_related[:trace_limit],
            "active_traces_compact": [self._compact_trace(item) for item in active_related[:trace_limit]],
            "error_traces": error_related[:trace_limit],
            "error_traces_compact": [self._compact_trace(item) for item in error_related[:trace_limit]],
        }

    def _compact_trace(self, trace: dict[str, Any]) -> dict[str, Any]:
        attrs = trace.get("attrs_json") if isinstance(trace.get("attrs_json"), dict) else {}
        trace_id = str(trace.get("trace_id") or "").strip()
        title = (
            attrs.get("title")
            or attrs.get("event_type")
            or attrs.get("tool_name")
            or attrs.get("playbook_id")
            or trace.get("operation_id")
            or trace.get("root_kind")
            or trace_id
        )
        return {
            "trace_id": trace_id,
            "root_kind": trace.get("root_kind"),
            "status": trace.get("status"),
            "title": str(title) if title is not None else None,
            "started_at": trace.get("started_at"),
            "finished_at": trace.get("finished_at"),
            "error_count": int(trace.get("error_count") or 0),
            "operation_id": trace.get("operation_id"),
            "tool_name": attrs.get("tool_name"),
            "playbook_id": attrs.get("playbook_id"),
            "trace_url": _observer_trace_url(trace_id),
        }

    def _compact_signature(self, signature: dict[str, Any]) -> dict[str, Any]:
        return {
            "error_signature": signature.get("error_signature"),
            "title": signature.get("title") or signature.get("message_sample") or signature.get("error_signature"),
            "severity": signature.get("severity") or signature.get("error_kind"),
            "ticket_occurrences_count": int(signature.get("ticket_occurrences_count") or 0),
            "global_occurrences_count": int(signature.get("occurrences_count") or 0),
            "last_seen_at": signature.get("ticket_last_seen_at") or signature.get("last_seen_at"),
        }

    def _compact_occurrence(self, occurrence: dict[str, Any]) -> dict[str, Any]:
        trace_id = str(occurrence.get("trace_id") or "").strip()
        return {
            "error_signature": occurrence.get("error_signature"),
            "message": occurrence.get("message_norm") or occurrence.get("error_kind") or occurrence.get("exception_type"),
            "stage": occurrence.get("failure_stage") or occurrence.get("component"),
            "severity": occurrence.get("severity"),
            "trace_id": trace_id or None,
            "created_at": occurrence.get("created_at"),
            "trace_url": _observer_trace_url(trace_id),
        }

    async def _annotate_ticket_signature_stats(
        self,
        ticket_id: str,
        signatures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        signature_ids = [str(item.get("error_signature") or "").strip() for item in signatures if str(item.get("error_signature") or "").strip()]
        if not signature_ids:
            return signatures

        rows = (
            await self.session.execute(
                select(
                    ObserverErrorOccurrence.error_signature,
                    func.count().label("ticket_occurrences_count"),
                    func.min(ObserverErrorOccurrence.created_at).label("ticket_first_seen_at"),
                    func.max(ObserverErrorOccurrence.created_at).label("ticket_last_seen_at"),
                )
                .where(
                    ObserverErrorOccurrence.ticket_id == ticket_id,
                    ObserverErrorOccurrence.error_signature.in_(signature_ids),
                )
                .group_by(ObserverErrorOccurrence.error_signature)
            )
        ).all()
        stats_by_signature = {
            str(row[0]): {
                "ticket_occurrences_count": int(row[1] or 0),
                "ticket_first_seen_at": _iso(row[2]),
                "ticket_last_seen_at": _iso(row[3]),
            }
            for row in rows
        }

        annotated: list[dict[str, Any]] = []
        for item in signatures:
            signature_id = str(item.get("error_signature") or "").strip()
            stats = stats_by_signature.get(signature_id, {})
            annotated.append(
                {
                    **item,
                    "ticket_occurrences_count": int(stats.get("ticket_occurrences_count") or 0),
                    "ticket_first_seen_at": stats.get("ticket_first_seen_at"),
                    "ticket_last_seen_at": stats.get("ticket_last_seen_at"),
                }
            )
        return annotated

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
        if filters.lookback_hours:
            window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(filters.lookback_hours), 1))
            stmt = stmt.where(ObserverErrorSignature.last_seen_at >= window_start)
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
        await self._release_projection_source_transaction()
        projected: list[str] = []
        for trace_id in candidate_ids:
            async with get_session() as projection_session:
                projected_trace = await ObserverOverlayService(projection_session).project_trace(trace_id, force=True)
                await projection_session.commit()
            if projected_trace:
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
        await self._release_projection_source_transaction()
        for trace_id in candidate_ids:
            async with get_session() as projection_session:
                await ObserverOverlayService(projection_session).project_trace(trace_id, force=force)
                await projection_session.commit()

    async def _release_projection_source_transaction(self) -> None:
        """Close the current read transaction before waiting on per-trace projection locks."""
        if not self.session.in_transaction():
            return
        if self.session.new or self.session.dirty or self.session.deleted:
            return
        await self.session.commit()

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

        if filters.playbook_run_id and filters.root_kind in (None, "playbook_run"):
            _remember([_playbook_run_trace_id(filters.playbook_run_id)])

        if filters.step_run_id and filters.root_kind in (None, "playbook_run"):
            step_run_row = (
                await self.session.execute(
                    select(PlaybookStepRun.playbook_run_id).where(PlaybookStepRun.id == filters.step_run_id).limit(1)
                )
            ).scalar_one_or_none()
            _remember([_playbook_run_trace_id(step_run_row)])

        if filters.query:
            query = _compact_text(filters.query)
            if query:
                pattern = f"%{query}%"
                ticket_query_stmt = (
                    select(Ticket.observer_root_trace_id)
                    .where(
                        Ticket.observer_root_trace_id.isnot(None),
                        or_(
                            Ticket.ticket_id == query,
                            Ticket.device_id == query,
                            Ticket.ticket_code.ilike(pattern),
                            Ticket.title.ilike(pattern),
                            Ticket.description.ilike(pattern),
                        ),
                    )
                    .order_by(Ticket.created_at.desc())
                    .limit(limit)
                )
                _remember((await self.session.execute(ticket_query_stmt)).scalars().all())

                op_query_stmt = (
                    select(Operation.trace_id)
                    .where(
                        Operation.trace_id.isnot(None),
                        or_(
                            Operation.trace_id == query,
                            Operation.operation_id == query,
                            Operation.ticket_id == query,
                            Operation.device_id == query,
                            Operation.job_id == query,
                            Operation.kind.ilike(pattern),
                            Operation.tool_name.ilike(pattern),
                            Operation.command_name.ilike(pattern),
                            Operation.error_code.ilike(pattern),
                            Operation.error_message.ilike(pattern),
                        ),
                    )
                    .order_by(Operation.queued_at.desc())
                    .limit(limit)
                )
                _remember((await self.session.execute(op_query_stmt)).scalars().all())

                device_query_stmt = (
                    select(Device.device_id)
                    .where(
                        or_(
                            Device.device_id == query,
                            Device.hostname.ilike(pattern),
                            Device.os.ilike(pattern),
                        )
                    )
                    .limit(limit)
                )
                device_ids = [
                    item
                    for item in (await self.session.execute(device_query_stmt)).scalars().all()
                    if _compact_text(item)
                ]
                if device_ids:
                    device_op_stmt = (
                        select(Operation.trace_id)
                        .where(Operation.trace_id.isnot(None), Operation.device_id.in_(device_ids))
                        .order_by(Operation.queued_at.desc())
                        .limit(limit)
                    )
                    _remember((await self.session.execute(device_op_stmt)).scalars().all())

                runtime_query_stmt = (
                    select(AgentRuntimeAudit)
                    .where(
                        or_(
                            AgentRuntimeAudit.device_id == query,
                            AgentRuntimeAudit.event_type.ilike(pattern),
                            AgentRuntimeAudit.source.ilike(pattern),
                            AgentRuntimeAudit.severity.ilike(pattern),
                            AgentRuntimeAudit.details_json.cast(sa.Text).ilike(pattern),
                        )
                    )
                    .order_by(AgentRuntimeAudit.created_at.desc(), AgentRuntimeAudit.id.desc())
                    .limit(limit)
                )
                runtime_query_rows = (await self.session.execute(runtime_query_stmt)).scalars().all()
                _remember(await self._trace_ids_for_runtime_audits(runtime_query_rows))

                agent_event_query_stmt = (
                    select(AgentObserverEvent.trace_id)
                    .where(
                        AgentObserverEvent.trace_id.isnot(None),
                        or_(
                            AgentObserverEvent.device_id == query,
                            AgentObserverEvent.trace_id == query,
                            AgentObserverEvent.operation_id == query,
                            AgentObserverEvent.ticket_id == query,
                            AgentObserverEvent.event_id.ilike(pattern),
                            AgentObserverEvent.event_type.ilike(pattern),
                            AgentObserverEvent.component.ilike(pattern),
                            AgentObserverEvent.stage.ilike(pattern),
                            AgentObserverEvent.status.ilike(pattern),
                            AgentObserverEvent.root_kind.ilike(pattern),
                            AgentObserverEvent.tool_name.ilike(pattern),
                            AgentObserverEvent.module_name.ilike(pattern),
                            AgentObserverEvent.attrs_json.cast(sa.Text).ilike(pattern),
                        ),
                    )
                    .order_by(AgentObserverEvent.created_at.desc(), AgentObserverEvent.id.desc())
                    .limit(limit)
                )
                _remember((await self.session.execute(agent_event_query_stmt)).scalars().all())

                if filters.root_kind in (None, "playbook_run"):
                    playbook_query_stmt = (
                        select(PlaybookRun.id)
                        .join(PlaybookStepRun, PlaybookStepRun.playbook_run_id == PlaybookRun.id, isouter=True)
                        .join(PlaybookStep, PlaybookStepRun.playbook_step_id == PlaybookStep.id, isouter=True)
                        .where(
                            or_(
                                sa.cast(PlaybookRun.id, sa.Text).ilike(pattern),
                                PlaybookRun.device_id == query,
                                PlaybookRun.status.ilike(pattern),
                                PlaybookRun.trigger_type.ilike(pattern),
                                PlaybookRun.error_code.ilike(pattern),
                                PlaybookRun.error_message.ilike(pattern),
                                PlaybookRun.context_json.cast(sa.Text).ilike(pattern),
                                sa.cast(PlaybookStepRun.id, sa.Text).ilike(pattern),
                                PlaybookStepRun.status.ilike(pattern),
                                PlaybookStepRun.operation_id == query,
                                PlaybookStepRun.input_json.cast(sa.Text).ilike(pattern),
                                PlaybookStepRun.output_json.cast(sa.Text).ilike(pattern),
                                PlaybookStepRun.error_json.cast(sa.Text).ilike(pattern),
                                PlaybookStep.step_key.ilike(pattern),
                                PlaybookStep.type.ilike(pattern),
                                PlaybookStep.tool.ilike(pattern),
                            )
                        )
                        .group_by(PlaybookRun.id)
                        .order_by(func.max(PlaybookRun.scheduled_at).desc())
                        .limit(limit)
                    )
                    _remember([
                        _playbook_run_trace_id(item)
                        for item in (await self.session.execute(playbook_query_stmt)).scalars().all()
                    ])

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

        if len(candidates) < limit:
            runtime_stmt = select(AgentRuntimeAudit)
            runtime_filters = []
            if filters.ticket_id:
                runtime_filters.append(AgentRuntimeAudit.ticket_id == filters.ticket_id)
            if filters.operation_id:
                runtime_filters.append(AgentRuntimeAudit.operation_id == filters.operation_id)
            if filters.device_id:
                runtime_filters.append(AgentRuntimeAudit.device_id == filters.device_id)
            if filters.status:
                runtime_filters.append(AgentRuntimeAudit.severity == filters.status)
            if filters.route:
                runtime_filters.append(AgentRuntimeAudit.details_json["route"].astext == filters.route)
            if filters.lookback_hours:
                window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(filters.lookback_hours), 1))
                runtime_filters.append(AgentRuntimeAudit.created_at >= window_start)
            if runtime_filters:
                runtime_stmt = runtime_stmt.where(*runtime_filters)
            runtime_stmt = runtime_stmt.order_by(AgentRuntimeAudit.created_at.desc(), AgentRuntimeAudit.id.desc()).limit(limit)
            runtime_rows = list((await self.session.execute(runtime_stmt)).scalars().all())
            if filters.root_kind:
                runtime_rows = [
                    row
                    for row in runtime_rows
                    if _runtime_audit_root_kind(row) == filters.root_kind
                ]
            _remember(await self._trace_ids_for_runtime_audits(runtime_rows))

        if len(candidates) < limit:
            agent_event_stmt = select(AgentObserverEvent.trace_id).where(AgentObserverEvent.trace_id.isnot(None))
            if filters.ticket_id:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.ticket_id == filters.ticket_id)
            if filters.operation_id:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.operation_id == filters.operation_id)
            if filters.device_id:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.device_id == filters.device_id)
            if filters.status:
                agent_event_stmt = agent_event_stmt.where(
                    or_(AgentObserverEvent.severity == filters.status, AgentObserverEvent.status == filters.status)
                )
            if filters.root_kind:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.root_kind == filters.root_kind)
            if filters.tool_name:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.tool_name == filters.tool_name)
            if filters.module_name:
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.module_name == filters.module_name)
            if filters.lookback_hours:
                window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(filters.lookback_hours), 1))
                agent_event_stmt = agent_event_stmt.where(AgentObserverEvent.created_at >= window_start)
            agent_event_stmt = agent_event_stmt.order_by(AgentObserverEvent.created_at.desc(), AgentObserverEvent.id.desc()).limit(limit)
            _remember((await self.session.execute(agent_event_stmt)).scalars().all())

        if len(candidates) < limit and filters.root_kind in (None, "playbook_run"):
            playbook_stmt = select(PlaybookRun.id)
            if filters.playbook_run_id:
                playbook_stmt = playbook_stmt.where(PlaybookRun.id == filters.playbook_run_id)
            if filters.device_id:
                playbook_stmt = playbook_stmt.where(PlaybookRun.device_id == filters.device_id)
            if filters.status:
                playbook_stmt = playbook_stmt.where(PlaybookRun.status == filters.status)
            if filters.lookback_hours:
                window_start = datetime.now(timezone.utc) - timedelta(hours=max(int(filters.lookback_hours), 1))
                playbook_stmt = playbook_stmt.where(
                    or_(PlaybookRun.scheduled_at >= window_start, PlaybookRun.finished_at >= window_start)
                )
            if filters.step_run_id:
                playbook_stmt = playbook_stmt.join(PlaybookStepRun, PlaybookStepRun.playbook_run_id == PlaybookRun.id).where(
                    PlaybookStepRun.id == filters.step_run_id
                )
            playbook_stmt = playbook_stmt.order_by(PlaybookRun.scheduled_at.desc(), PlaybookRun.id.desc()).limit(limit)
            _remember([
                _playbook_run_trace_id(item)
                for item in (await self.session.execute(playbook_stmt)).scalars().all()
            ])

        if not candidates:
            recent_stmt = (
                select(Operation.trace_id)
                .where(Operation.trace_id.isnot(None))
                .order_by(Operation.queued_at.desc())
                .limit(limit)
            )
            _remember((await self.session.execute(recent_stmt)).scalars().all())

        return candidates[:limit]

    async def _trace_ids_for_runtime_audits(self, audits: Iterable[AgentRuntimeAudit]) -> list[Optional[str]]:
        rows = list(audits)
        if not rows:
            return []

        operation_ids = {
            operation_id
            for operation_id in (_compact_text(row.operation_id) for row in rows)
            if operation_id
        }
        ticket_ids = {
            ticket_id
            for ticket_id in (_compact_text(row.ticket_id) for row in rows)
            if ticket_id
        }
        operation_trace_ids: dict[str, str] = {}
        ticket_trace_ids: dict[str, str] = {}
        if operation_ids:
            op_rows = (
                await self.session.execute(
                    select(Operation.operation_id, Operation.trace_id).where(
                        Operation.operation_id.in_(operation_ids),
                        Operation.trace_id.isnot(None),
                    )
                )
            ).all()
            operation_trace_ids = {
                operation_id: trace_id
                for operation_id, trace_id in op_rows
                if operation_id and trace_id
            }
        if ticket_ids:
            ticket_rows = (
                await self.session.execute(
                    select(Ticket.ticket_id, Ticket.observer_root_trace_id).where(
                        Ticket.ticket_id.in_(ticket_ids),
                        Ticket.observer_root_trace_id.isnot(None),
                    )
                )
            ).all()
            ticket_trace_ids = {
                ticket_id: trace_id
                for ticket_id, trace_id in ticket_rows
                if ticket_id and trace_id
            }

        trace_ids: list[Optional[str]] = []
        for row in rows:
            operation_id = _compact_text(row.operation_id)
            ticket_id = _compact_text(row.ticket_id)
            if operation_id and operation_id in operation_trace_ids:
                trace_ids.append(operation_trace_ids[operation_id])
            elif ticket_id and ticket_id in ticket_trace_ids:
                trace_ids.append(ticket_trace_ids[ticket_id])
            else:
                trace_ids.append(_runtime_audit_trace_id(row.id))
        return trace_ids

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

        playbook_run_id = _playbook_run_id_from_trace_id(trace_id)
        if playbook_run_id is not None:
            playbook_sources = await self._collect_playbook_run_sources(playbook_run_id)
            if not playbook_sources.empty:
                return playbook_sources

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
        agent_events: list[AgentObserverEvent] = []
        operation_ids = [item.operation_id for item in operations if item.operation_id]
        if operation_ids:
            runtime_audits = (
                await self.session.execute(
                    select(AgentRuntimeAudit)
                    .where(AgentRuntimeAudit.operation_id.in_(operation_ids))
                    .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
                )
            ).scalars().all()
            agent_events = (
                await self.session.execute(
                    select(AgentObserverEvent)
                    .where(or_(AgentObserverEvent.trace_id == trace_id, AgentObserverEvent.operation_id.in_(operation_ids)))
                    .order_by(AgentObserverEvent.created_at.asc(), AgentObserverEvent.id.asc())
                )
            ).scalars().all()
        else:
            agent_events = (
                await self.session.execute(
                    select(AgentObserverEvent)
                    .where(AgentObserverEvent.trace_id == trace_id)
                    .order_by(AgentObserverEvent.created_at.asc(), AgentObserverEvent.id.asc())
                )
            ).scalars().all()

        if not any((operations, ticket_events, device_events, runtime_audits, agent_events)):
            runtime_audits = await self._collect_runtime_audit_trace_sources(trace_id)

        return TraceProjectionSources(
            operations=list(operations),
            ticket_events=list(ticket_events),
            device_events=list(device_events),
            runtime_audits=list(runtime_audits),
            agent_events=list(agent_events),
        )

    async def _collect_playbook_run_sources(self, playbook_run_id: int) -> TraceProjectionSources:
        playbook_run = await self.session.get(PlaybookRun, playbook_run_id)
        if playbook_run is None:
            return TraceProjectionSources([], [], [], [], [])

        step_rows = (
            await self.session.execute(
                select(PlaybookStepRun, PlaybookStep)
                .join(PlaybookStep, PlaybookStepRun.playbook_step_id == PlaybookStep.id)
                .where(PlaybookStepRun.playbook_run_id == playbook_run_id)
                .order_by(PlaybookStepRun.id.asc())
            )
        ).all()
        operations = (
            await self.session.execute(
                select(Operation)
                .where(Operation.playbook_run_id == playbook_run_id)
                .order_by(Operation.queued_at.asc(), Operation.operation_id.asc())
            )
        ).scalars().all()
        operation_ids = [item.operation_id for item in operations if item.operation_id]
        runtime_audits: list[AgentRuntimeAudit] = []
        agent_events: list[AgentObserverEvent] = []
        if operation_ids:
            runtime_audits = (
                await self.session.execute(
                    select(AgentRuntimeAudit)
                    .where(AgentRuntimeAudit.operation_id.in_(operation_ids))
                    .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
                )
            ).scalars().all()
            agent_events = (
                await self.session.execute(
                    select(AgentObserverEvent)
                    .where(AgentObserverEvent.operation_id.in_(operation_ids))
                    .order_by(AgentObserverEvent.created_at.asc(), AgentObserverEvent.id.asc())
                )
            ).scalars().all()
        return TraceProjectionSources(
            operations=list(operations),
            ticket_events=[],
            device_events=[],
            runtime_audits=list(runtime_audits),
            agent_events=list(agent_events),
            playbook_run=playbook_run,
            playbook_step_runs=[(row[0], row[1]) for row in step_rows],
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
        agent_events: list[AgentObserverEvent] = []
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
            agent_events = (
                await self.session.execute(
                    select(AgentObserverEvent)
                    .where(or_(AgentObserverEvent.operation_id.in_(operation_ids), AgentObserverEvent.ticket_id == ticket.ticket_id))
                    .order_by(AgentObserverEvent.created_at.asc(), AgentObserverEvent.id.asc())
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
            agent_events = (
                await self.session.execute(
                    select(AgentObserverEvent)
                    .where(AgentObserverEvent.ticket_id == ticket.ticket_id)
                    .order_by(AgentObserverEvent.created_at.asc(), AgentObserverEvent.id.asc())
                )
            ).scalars().all()

        return TraceProjectionSources(
            operations=list(operations),
            ticket_events=list(ticket_events),
            device_events=list(device_events),
            runtime_audits=list(runtime_audits),
            agent_events=list(agent_events),
            root_ticket=ticket,
        )

    async def _collect_runtime_audit_trace_sources(self, trace_id: str) -> list[AgentRuntimeAudit]:
        audit_id = _runtime_audit_id_from_trace_id(trace_id)
        if audit_id is None:
            return []
        anchor = await self.session.get(AgentRuntimeAudit, audit_id)
        if anchor is None:
            return []
        if _compact_text(anchor.operation_id) or _compact_text(anchor.ticket_id):
            return []
        anchor_kind = _runtime_audit_root_kind(anchor)
        started_at = anchor.created_at - RUNTIME_AUDIT_PROJECTION_WINDOW
        finished_at = anchor.created_at + RUNTIME_AUDIT_PROJECTION_WINDOW
        rows = (
            await self.session.execute(
                select(AgentRuntimeAudit)
                .where(
                    AgentRuntimeAudit.device_id == anchor.device_id,
                    AgentRuntimeAudit.operation_id.is_(None),
                    AgentRuntimeAudit.ticket_id.is_(None),
                    AgentRuntimeAudit.created_at >= started_at,
                    AgentRuntimeAudit.created_at <= finished_at,
                )
                .order_by(AgentRuntimeAudit.created_at.asc(), AgentRuntimeAudit.id.asc())
            )
        ).scalars().all()
        return [
            row
            for row in rows
            if _runtime_audit_root_kind(row) == anchor_kind
        ]

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
            *[item.created_at for item in sources.agent_events if item.created_at],
            *[item.received_at for item in sources.agent_events if item.received_at],
            *[
                timestamp
                for timestamp in (
                    getattr(sources.playbook_run, "scheduled_at", None),
                    getattr(sources.playbook_run, "started_at", None),
                    getattr(sources.playbook_run, "finished_at", None),
                )
                if timestamp
            ],
            *[
                timestamp
                for step_run, _step in (sources.playbook_step_runs or [])
                for timestamp in (step_run.started_at, step_run.finished_at)
                if timestamp
            ],
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
            sources.playbook_run.device_id if sources.playbook_run is not None else (
                primary_operation.device_id if primary_operation else next(
                    (item.device_id for item in [*sources.ticket_events, *sources.device_events, *sources.runtime_audits, *sources.agent_events] if getattr(item, "device_id", None)),
                    None,
                )
            )
        )
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
                        "ticket_title": root_ticket.title,
                        "ticket_status": root_ticket.status,
                        "observer_root_trace_id": root_ticket.observer_root_trace_id,
                    },
                }
            )

        if sources.playbook_run is not None:
            playbook_run = sources.playbook_run
            root_span_id = _trace_scoped_uuid(trace_id, f"playbook_run:{playbook_run.id}")
            payloads.append(
                {
                    "span_id": root_span_id,
                    "trace_id": trace_id,
                    "parent_span_id": None,
                    "source_type": "playbook_run",
                    "source_ref": str(playbook_run.id),
                    "name": "playbook.run",
                    "kind": "internal",
                    "component": "playbook",
                    "event_type": playbook_run.status,
                    "module_name": None,
                    "tool_name": None,
                    "status": _span_status_from_playbook_status(playbook_run.status),
                    "started_at": playbook_run.started_at or playbook_run.scheduled_at,
                    "finished_at": playbook_run.finished_at,
                    "duration_ms": _duration_ms(playbook_run.started_at or playbook_run.scheduled_at, playbook_run.finished_at),
                    "attrs_json": {
                        "playbook_run_id": playbook_run.id,
                        "playbook_version_id": playbook_run.playbook_version_id,
                        "device_id": playbook_run.device_id,
                        "trigger_type": playbook_run.trigger_type,
                        "status": playbook_run.status,
                        "error_code": playbook_run.error_code,
                        "error_message": playbook_run.error_message,
                        "context_json": redact_sensitive_payload(playbook_run.context_json or {}),
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

        for step_run, step in (sources.playbook_step_runs or []):
            linked_operation_span_id = operation_span_ids.get(step_run.operation_id or "")
            span_id = _trace_scoped_uuid(trace_id, f"playbook_step_run:{step_run.id}")
            module_name, tool_name = _split_tool_name(step.tool)
            redacted_input = redact_sensitive_payload(step_run.input_json or {})
            redacted_output = redact_sensitive_payload(step_run.output_json or {})
            redacted_error = redact_sensitive_payload(step_run.error_json or {})
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": root_span_id,
                    "source_type": "playbook_step_run",
                    "source_ref": str(step_run.id),
                    "name": f"playbook.step.{step.step_key}",
                    "kind": "internal",
                    "component": "playbook",
                    "event_type": step_run.status,
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "status": _span_status_from_playbook_status(step_run.status),
                    "started_at": step_run.started_at,
                    "finished_at": step_run.finished_at,
                    "duration_ms": _duration_ms(step_run.started_at, step_run.finished_at),
                    "attrs_json": {
                        "playbook_run_id": step_run.playbook_run_id,
                        "playbook_step_run_id": step_run.id,
                        "playbook_step_id": step.id,
                        "step_key": step.step_key,
                        "step_type": step.type,
                        "operation_id": step_run.operation_id,
                        "attempt": step_run.attempt,
                        "input_json": redacted_input,
                        "output_json": redacted_output,
                        "error_json": redacted_error,
                    },
                }
            )
            if linked_operation_span_id:
                links.append(
                    {
                        "span_id": span_id,
                        "linked_trace_id": trace_id,
                        "linked_span_id": linked_operation_span_id,
                        "reason": "playbook_step_operation",
                        "attrs_json": {
                            "operation_id": step_run.operation_id,
                            "playbook_step_run_id": step_run.id,
                        },
                    }
                )

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

        for event in sources.agent_events:
            linked_operation_span_id = operation_span_ids.get(event.operation_id or "")
            span_id = _trace_scoped_uuid(trace_id, f"agent_observer_event:{event.id}")
            attrs = redact_sensitive_payload(event.attrs_json or {})
            payloads.append(
                {
                    "span_id": span_id,
                    "trace_id": trace_id,
                    "parent_span_id": linked_operation_span_id or root_span_id,
                    "source_type": "agent_observer_event",
                    "source_ref": str(event.id),
                    "name": f"agent.telemetry.{event.event_type}",
                    "kind": "event",
                    "component": event.component or "agent",
                    "event_type": event.event_type,
                    "module_name": event.module_name,
                    "tool_name": event.tool_name,
                    "status": _span_status_from_severity(event.severity) if not event.status else _span_status_from_severity(event.severity),
                    "started_at": event.started_at or event.created_at,
                    "finished_at": event.finished_at or event.created_at,
                    "duration_ms": event.duration_ms or _duration_ms(event.started_at, event.finished_at),
                    "attrs_json": {
                        "agent_observer_event_id": event.id,
                        "event_id": event.event_id,
                        "severity": event.severity,
                        "stage": event.stage,
                        "status": event.status,
                        "root_kind": event.root_kind,
                        "attrs_json": attrs,
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
                        "attrs_json": {"operation_id": event.operation_id},
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
            *[item.created_at for item in sources.agent_events],
            *[
                timestamp
                for timestamp in (
                    getattr(sources.playbook_run, "scheduled_at", None),
                    getattr(sources.playbook_run, "started_at", None),
                    getattr(sources.playbook_run, "finished_at", None),
                )
                if timestamp
            ],
            *[
                timestamp
                for step_run, _step in (sources.playbook_step_runs or [])
                for timestamp in (step_run.started_at, step_run.finished_at)
                if timestamp
            ],
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
                *[item.created_at for item in sources.agent_events],
                *[
                    timestamp
                    for timestamp in (getattr(sources.playbook_run, "finished_at", None),)
                    if timestamp
                ],
                *[step_run.finished_at for step_run, _step in (sources.playbook_step_runs or []) if step_run.finished_at],
            ]
            finished_at = max(terminal_times) if terminal_times else None

        attrs_json = {
            "root_scope": "ticket" if root_ticket else ("runtime_audit" if sources.runtime_audits and not primary_operation else "execution"),
            "source_counts": {
                "operations": len(sources.operations),
                "ticket_events": len(sources.ticket_events),
                "device_events": len(sources.device_events),
                "agent_runtime_audit": len(sources.runtime_audits),
                "agent_observer_events": len(sources.agent_events),
                "playbook_step_runs": len(sources.playbook_step_runs or []),
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
                        *[item.tool_name for item in sources.agent_events],
                    ]
                    if value
                }
            ),
        }
        if sources.agent_events:
            attrs_json["agent_event_types"] = sorted(
                {
                    str(item.event_type or "").strip()
                    for item in sources.agent_events
                    if str(item.event_type or "").strip()
                }
            )
        if sources.runtime_audits:
            attrs_json["runtime_event_types"] = sorted(
                {
                    str(item.event_type or "").strip()
                    for item in sources.runtime_audits
                    if str(item.event_type or "").strip()
                }
            )
            attrs_json["runtime_sources"] = sorted(
                {
                    str(item.source or "").strip()
                    for item in sources.runtime_audits
                    if str(item.source or "").strip()
                }
            )
        if sources.playbook_run is not None:
            attrs_json["playbook_run_id"] = sources.playbook_run.id
            attrs_json["playbook_version_id"] = sources.playbook_run.playbook_version_id
            attrs_json["playbook_status"] = sources.playbook_run.status
            attrs_json["playbook_step_statuses"] = sorted(
                {
                    str(step_run.status or "").strip()
                    for step_run, _step in (sources.playbook_step_runs or [])
                    if str(step_run.status or "").strip()
                }
            )
        if root_ticket is not None:
            attrs_json["ticket_status"] = root_ticket.status
            attrs_json["ticket_code"] = root_ticket.ticket_code
            attrs_json["ticket_title"] = root_ticket.title
            attrs_json["observer_root_trace_id"] = root_ticket.observer_root_trace_id

        return payloads, links, {
            "root_span_id": root_span_id,
            "root_kind": "ticket" if root_ticket is not None else (
                "playbook_run" if sources.playbook_run is not None else (
                primary_operation.kind if primary_operation else (
                    sources.ticket_events[0].event_type if sources.ticket_events else (
                        sources.agent_events[0].root_kind if sources.agent_events else _runtime_root_kind_from_audits(sources.runtime_audits)
                    )
                )
                )
            ),
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
        if sources.playbook_run is not None and str(sources.playbook_run.status or "").strip().lower() == "failed":
            error_kind = _compact_text(sources.playbook_run.error_code) or "PLAYBOOK_RUN_FAILED"
            message_norm = _normalize_message(sources.playbook_run.error_message or error_kind)
            signature = self._make_error_signature(
                error_kind=error_kind,
                component="playbook",
                module_name=None,
                tool_name=None,
                exception_type=None,
                failure_stage="playbook_run",
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("playbook_run", str(sources.playbook_run.id))),
                    "error_signature": signature,
                    "device_id": sources.playbook_run.device_id,
                    "ticket_id": None,
                    "operation_id": None,
                    "component": "playbook",
                    "module_name": None,
                    "tool_name": None,
                    "error_kind": error_kind,
                    "exception_type": None,
                    "failure_stage": "playbook_run",
                    "severity": "error",
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1((message_norm or "").encode("utf-8")).hexdigest()[:16] if message_norm else None,
                    "attrs_json": {
                        "playbook_run_id": sources.playbook_run.id,
                        "playbook_version_id": sources.playbook_run.playbook_version_id,
                        "status": sources.playbook_run.status,
                    },
                    "created_at": sources.playbook_run.finished_at or sources.playbook_run.started_at or sources.playbook_run.scheduled_at,
                }
            )

        for step_run, step in (sources.playbook_step_runs or []):
            if str(step_run.status or "").strip().lower() != "failed":
                continue
            details = redact_sensitive_payload(step_run.error_json or {})
            module_name, tool_name = _split_tool_name(step.tool)
            error_kind = _compact_text(details.get("code")) or "PLAYBOOK_STEP_FAILED"
            exception_type = _compact_text(details.get("exception_type"))
            failure_stage = _compact_text(details.get("stage")) or _compact_text(step.type) or "playbook_step"
            message_norm = _normalize_message(details.get("message") or error_kind)
            signature = self._make_error_signature(
                error_kind=error_kind,
                component="playbook",
                module_name=module_name,
                tool_name=tool_name,
                exception_type=exception_type,
                failure_stage=failure_stage,
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("playbook_step_run", str(step_run.id))),
                    "error_signature": signature,
                    "device_id": sources.playbook_run.device_id if sources.playbook_run is not None else None,
                    "ticket_id": None,
                    "operation_id": step_run.operation_id,
                    "component": "playbook",
                    "module_name": module_name,
                    "tool_name": tool_name,
                    "error_kind": error_kind,
                    "exception_type": exception_type,
                    "failure_stage": failure_stage,
                    "severity": "error",
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1(json.dumps(details, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
                    "attrs_json": {
                        "playbook_run_id": step_run.playbook_run_id,
                        "playbook_step_run_id": step_run.id,
                        "step_key": step.step_key,
                        "step_type": step.type,
                        "error_json": details,
                    },
                    "created_at": step_run.finished_at or step_run.started_at,
                }
            )

        for audit in sources.runtime_audits:
            if not _runtime_audit_is_problem(audit):
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

        for event in sources.agent_events:
            severity = str(event.severity or "").strip().lower()
            if severity not in PROBLEM_AUDIT_SEVERITIES:
                continue
            details = redact_sensitive_payload(event.attrs_json or {})
            error_kind = _compact_text(details.get("error_kind")) or event.event_type
            exception_type = _compact_text(details.get("exception_type"))
            failure_stage = _compact_text(event.stage) or _compact_text(event.status) or event.event_type
            message_norm = _normalize_message(details.get("message") or details.get("reason") or event.event_type)
            signature = self._make_error_signature(
                error_kind=error_kind,
                component=event.component or "agent",
                module_name=event.module_name,
                tool_name=event.tool_name,
                exception_type=exception_type,
                failure_stage=failure_stage,
                message_norm=message_norm,
            )
            occurrences.append(
                {
                    "trace_id": trace_id,
                    "span_id": span_ids_by_source.get(("agent_observer_event", str(event.id))),
                    "error_signature": signature,
                    "device_id": event.device_id,
                    "ticket_id": event.ticket_id,
                    "operation_id": event.operation_id,
                    "component": event.component or "agent",
                    "module_name": event.module_name,
                    "tool_name": event.tool_name,
                    "error_kind": error_kind,
                    "exception_type": exception_type,
                    "failure_stage": failure_stage,
                    "severity": "error" if severity == "critical" else severity,
                    "message_norm": message_norm,
                    "stack_hash": hashlib.sha1(json.dumps(details, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
                    "attrs_json": {"event_id": event.event_id, "event_type": event.event_type, "attrs_json": details},
                    "created_at": event.created_at,
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
        if sources.playbook_run is not None:
            playbook_status = str(sources.playbook_run.status or "").strip().lower()
            if playbook_status in {"pending", "running"}:
                return "running"
            if playbook_status == "failed":
                return "error"
            if playbook_status in {"success", "succeeded"}:
                return "ok"
        if operation_statuses & ACTIVE_OPERATION_STATUSES:
            return "running"
        if operation_statuses & ERROR_OPERATION_STATUSES:
            return "error"
        if any(str(item.severity or "").strip().lower() in ERROR_AUDIT_SEVERITIES for item in sources.runtime_audits):
            return "error"
        if any(str(item.severity or "").strip().lower() in (ERROR_AUDIT_SEVERITIES | {"critical"}) for item in sources.agent_events):
            return "error"
        if any(_runtime_audit_is_problem(item) for item in sources.runtime_audits):
            return "warning"
        if any(str(item.severity or "").strip().lower() == "warning" for item in sources.agent_events):
            return "warning"
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
        if base_status == "ok" and any(str(item.get("severity") or "").strip().lower() == "warning" for item in occurrences):
            return "warning"
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

    def _select_hot_traces(self, traces: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        def _rank(item: dict[str, Any]) -> tuple[int, int, int, str]:
            status = str(item.get("status") or "").strip().lower()
            error_count = int(item.get("error_count") or 0)
            is_error = 1 if error_count > 0 or status in {"error", "failed", "timed_out"} else 0
            is_active = 1 if status in ACTIVE_OPERATION_STATUSES or status == "running" else 0
            is_dangerous = 1 if str(item.get("root_kind") or "") in DANGEROUS_ROOT_KINDS else 0
            return (is_error + is_dangerous, is_active, error_count, str(item.get("started_at") or ""))

        ordered = sorted(traces, key=_rank, reverse=True)
        hot = [item for item in ordered if _rank(item)[0] > 0 or _rank(item)[1] > 0]
        if len(hot) < limit:
            seen = {item.get("trace_id") for item in hot}
            hot.extend(item for item in ordered if item.get("trace_id") not in seen)
        return hot[:limit]

    async def _summarize_dangerous_flows(self, filters: TraceOverlayFilters, *, limit: int) -> list[dict[str, Any]]:
        lookback_hours = max(int(filters.lookback_hours or 24), 1)
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
        rows = (
            await self.session.execute(
                stmt.order_by(Operation.queued_at.desc()).limit(max(limit * 40, 40))
            )
        ).scalars().all()

        grouped: dict[str, dict[str, Any]] = {}

        def _ensure_flow(root_kind: str) -> dict[str, Any]:
            item = grouped.get(root_kind)
            if item is None:
                item = grouped[root_kind] = {
                    "root_kind": root_kind,
                    "operations_count": 0,
                    "runtime_audit_count": 0,
                    "error_count": 0,
                    "timeout_count": 0,
                    "retried_count": 0,
                    "active_count": 0,
                    "latest_operation_at": None,
                    "latest_event_at": None,
                    "sample_trace_ids": [],
                }
            return item

        for operation in rows:
            root_kind = _compact_text(operation.kind) or "unknown"
            item = _ensure_flow(root_kind)
            item["operations_count"] += 1
            status = str(operation.status or "").strip().lower()
            if status in {"failed", "timed_out", "canceled"}:
                item["error_count"] += 1
            if status == "timed_out":
                item["timeout_count"] += 1
            if int(operation.retry_count or 0) > 0:
                item["retried_count"] += 1
            if status in ACTIVE_OPERATION_STATUSES:
                item["active_count"] += 1
            latest_at = _operation_finished_at(operation) or operation.queued_at
            if latest_at and (item["latest_operation_at"] is None or latest_at > item["latest_operation_at"]):
                item["latest_operation_at"] = latest_at
            if latest_at and (item["latest_event_at"] is None or latest_at > item["latest_event_at"]):
                item["latest_event_at"] = latest_at
            trace_id = _compact_text(operation.trace_id)
            if trace_id and trace_id not in item["sample_trace_ids"] and len(item["sample_trace_ids"]) < 5:
                item["sample_trace_ids"].append(trace_id)

        runtime_stmt = select(AgentRuntimeAudit).where(AgentRuntimeAudit.created_at >= window_start)
        if filters.ticket_id:
            runtime_stmt = runtime_stmt.where(AgentRuntimeAudit.ticket_id == filters.ticket_id)
        if filters.operation_id:
            runtime_stmt = runtime_stmt.where(AgentRuntimeAudit.operation_id == filters.operation_id)
        if filters.device_id:
            runtime_stmt = runtime_stmt.where(AgentRuntimeAudit.device_id == filters.device_id)
        runtime_rows = (
            await self.session.execute(
                runtime_stmt.order_by(AgentRuntimeAudit.created_at.desc(), AgentRuntimeAudit.id.desc()).limit(max(limit * 40, 40))
            )
        ).scalars().all()
        if filters.root_kind:
            runtime_rows = [row for row in runtime_rows if _runtime_audit_root_kind(row) == filters.root_kind]
        runtime_trace_ids = await self._trace_ids_for_runtime_audits(runtime_rows)
        for audit, trace_id in zip(runtime_rows, runtime_trace_ids):
            root_kind = _runtime_audit_root_kind(audit)
            if root_kind not in DANGEROUS_ROOT_KINDS:
                continue
            item = _ensure_flow(root_kind)
            item["runtime_audit_count"] += 1
            severity = str(audit.severity or "").strip().lower()
            if severity in ERROR_AUDIT_SEVERITIES or _runtime_audit_is_problem(audit):
                item["error_count"] += 1
            if severity in ACTIVE_OPERATION_STATUSES:
                item["active_count"] += 1
            if audit.created_at and (item["latest_event_at"] is None or audit.created_at > item["latest_event_at"]):
                item["latest_event_at"] = audit.created_at
            if item["latest_operation_at"] is None and audit.created_at:
                item["latest_operation_at"] = audit.created_at
            if trace_id and trace_id not in item["sample_trace_ids"] and len(item["sample_trace_ids"]) < 5:
                item["sample_trace_ids"].append(trace_id)

        items = [
            {
                "root_kind": item["root_kind"],
                "operations_count": item["operations_count"],
                "runtime_audit_count": item["runtime_audit_count"],
                "error_count": item["error_count"],
                "timeout_count": item["timeout_count"],
                "retried_count": item["retried_count"],
                "active_count": item["active_count"],
                "latest_operation_at": _iso(item["latest_operation_at"]),
                "latest_event_at": _iso(item["latest_event_at"]),
                "sample_trace_ids": item["sample_trace_ids"],
            }
            for item in grouped.values()
        ]
        items.sort(
            key=lambda entry: (
                entry["error_count"],
                entry["timeout_count"],
                entry["retried_count"],
                entry["active_count"],
                entry["operations_count"],
                entry.get("runtime_audit_count") or 0,
                entry["latest_event_at"] or entry["latest_operation_at"] or "",
            ),
            reverse=True,
        )
        return items[:limit]
