from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
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
    TicketEvent,
)


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
    tool_name: Optional[str] = None
    module_name: Optional[str] = None
    error_signature: Optional[str] = None
    status: Optional[str] = None


@dataclass(slots=True)
class TraceProjectionSources:
    operations: list[Operation]
    ticket_events: list[TicketEvent]
    device_events: list[DeviceEvent]
    runtime_audits: list[AgentRuntimeAudit]

    @property
    def empty(self) -> bool:
        return not any((self.operations, self.ticket_events, self.device_events, self.runtime_audits))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _duration_ms(started_at: Optional[datetime], finished_at: Optional[datetime]) -> Optional[int]:
    if not started_at or not finished_at:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


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


def _span_status_from_operation(status: Optional[str]) -> str:
    key = str(status or "").strip().lower()
    if key in ERROR_OPERATION_STATUSES:
        return "error"
    if key in ACTIVE_OPERATION_STATUSES:
        return "running"
    if key == "canceled":
        return "canceled"
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
        stmt = select(ObserverTrace)
        if filters.trace_id:
            stmt = stmt.where(ObserverTrace.trace_id == filters.trace_id)
        if filters.ticket_id:
            stmt = stmt.where(ObserverTrace.ticket_id == filters.ticket_id)
        if filters.job_id:
            stmt = stmt.where(ObserverTrace.job_id == filters.job_id)
        if filters.operation_id:
            stmt = stmt.where(ObserverTrace.operation_id == filters.operation_id)
        if filters.device_id:
            stmt = stmt.where(ObserverTrace.device_id == filters.device_id)
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
        stmt = stmt.order_by(ObserverTrace.started_at.desc()).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._serialize_trace(row) for row in rows]

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

    async def search_signatures(self, filters: TraceOverlayFilters, *, limit: int = 50) -> list[dict[str, Any]]:
        await self._ensure_projected(filters, limit=limit, force=False)
        stmt = select(ObserverErrorSignature)
        if filters.error_signature:
            stmt = stmt.where(ObserverErrorSignature.error_signature == filters.error_signature)
        if filters.module_name:
            stmt = stmt.where(ObserverErrorSignature.module_name == filters.module_name)
        if filters.tool_name:
            stmt = stmt.where(ObserverErrorSignature.tool_name == filters.tool_name)
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

        op_stmt = select(Operation.trace_id).where(Operation.trace_id.isnot(None))
        if filters.ticket_id:
            op_stmt = op_stmt.where(Operation.ticket_id == filters.ticket_id)
        if filters.job_id:
            op_stmt = op_stmt.where(Operation.job_id == filters.job_id)
        if filters.operation_id:
            op_stmt = op_stmt.where(Operation.operation_id == filters.operation_id)
        if filters.device_id:
            op_stmt = op_stmt.where(Operation.device_id == filters.device_id)
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

    async def _collect_sources(self, trace_id: str) -> TraceProjectionSources:
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

        primary_operation = sources.operations[0] if sources.operations else None
        primary_ticket = primary_operation.ticket_id if primary_operation else next((item.ticket_id for item in sources.ticket_events), None)
        primary_device = primary_operation.device_id if primary_operation else next(
            (item.device_id for item in [*sources.ticket_events, *sources.device_events, *sources.runtime_audits] if getattr(item, "device_id", None)),
            None,
        )
        primary_job_id = primary_operation.job_id if primary_operation else None

        for index, operation in enumerate(sources.operations):
            module_name, tool_name = _split_tool_name(operation.tool_name)
            span_id = _trace_scoped_uuid(trace_id, f"operation:{operation.operation_id}")
            parent_span_id = None
            if index > 0 and primary_operation:
                parent_span_id = operation_span_ids.get(primary_operation.operation_id)
            finished_at = operation.canceled_at or operation.finished_at or operation.started_at or operation.accepted_at or operation.sent_at or operation.queued_at
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
                        "error_code": operation.error_code,
                        "error_message": operation.error_message,
                        "result_summary": operation.result_summary,
                    },
                }
            )
            payloads.extend(self._build_operation_stage_spans(trace_id, operation, span_id))

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
            module_name = _compact_text((audit.details_json or {}).get("module_name"))
            tool_name = _compact_text((audit.details_json or {}).get("tool_name"))
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
                        "details_json": audit.details_json or {},
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
                *[item.canceled_at or item.finished_at for item in sources.operations if (item.canceled_at or item.finished_at)],
                *[item.created_at for item in sources.ticket_events],
                *[item.created_at for item in sources.device_events],
                *[item.created_at for item in sources.runtime_audits],
            ]
            finished_at = max(terminal_times) if terminal_times else None

        attrs_json = {
            "source_counts": {
                "operations": len(sources.operations),
                "ticket_events": len(sources.ticket_events),
                "device_events": len(sources.device_events),
                "agent_runtime_audit": len(sources.runtime_audits),
            },
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

        return payloads, links, {
            "root_span_id": root_span_id,
            "root_kind": primary_operation.kind if primary_operation else (sources.ticket_events[0].event_type if sources.ticket_events else "trace"),
            "ticket_id": primary_ticket,
            "device_id": primary_device,
            "operation_id": primary_operation.operation_id if primary_operation else None,
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
            details = audit.details_json or {}
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
            "attrs_json": trace.attrs_json or {},
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
            "attrs_json": span.attrs_json or {},
        }

    def _serialize_span_link(self, link: ObserverSpanLink) -> dict[str, Any]:
        return {
            "id": link.id,
            "span_id": link.span_id,
            "linked_trace_id": link.linked_trace_id,
            "linked_span_id": link.linked_span_id,
            "reason": link.reason,
            "attrs_json": link.attrs_json or {},
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
            "attrs_json": signature.attrs_json or {},
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
            "attrs_json": occurrence.attrs_json or {},
            "created_at": _iso(occurrence.created_at),
        }
