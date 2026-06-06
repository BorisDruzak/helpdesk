from __future__ import annotations

import re
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Device, DeviceOutbox, DevicePresenceSnapshot, ObserverTrace, Operation, Ticket, TicketApproval
from observer.service import ObserverOverlayService, TraceOverlayFilters
from shared.redaction import redact_sensitive_payload

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
TICKET_CODE_RE = re.compile(r"^T-\d{3,}$", re.IGNORECASE)
ACTIVE_TICKET_STATUSES = {
    "new",
    "queued",
    "assigned",
    "in_progress",
    "waiting_on_user",
    "waiting_on_internal_team",
    "waiting_on_vendor",
    "waiting_on_approval",
    "scheduled",
}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
FAILED_OPERATION_STATUSES = {"failed", "timed_out"}
SEVERITY_RANK = {"ok": 0, "info": 1, "unknown": 2, "warning": 3, "critical": 4}


@dataclass(slots=True)
class ObserverDebugFilters:
    q: str | None = None
    trace_id: str | None = None
    ticket_id: str | None = None
    operation_id: str | None = None
    device_id: str | None = None
    route: str | None = None
    playbook_run_id: int | None = None
    step_run_id: int | None = None
    lookback_hours: int | None = 24
    include_runtime_snapshot: bool = True
    include_presence_snapshot: bool = True
    include_logs: bool = False
    limit: int = 20

    def has_locator(self) -> bool:
        return any(
            [
                self.q,
                self.trace_id,
                self.ticket_id,
                self.operation_id,
                self.device_id,
                self.route,
                self.playbook_run_id,
                self.step_run_id,
            ]
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None


def _safe_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _limit(value: int | None, *, default: int, cap: int) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, cap))


def _safe_link(label: str, href: str, kind: str) -> dict[str, str]:
    return {"label": label, "href": href, "kind": kind}


def _severity_max(values: list[str]) -> str:
    if not values:
        return "unknown"
    return max(values, key=lambda value: SEVERITY_RANK.get(value, 2))


async def _counts_for_ticket(session: AsyncSession, ticket_id: str) -> tuple[int, int]:
    approvals = await session.scalar(
        select(func.count())
        .select_from(TicketApproval)
        .where(and_(TicketApproval.ticket_id == ticket_id, TicketApproval.status == "requested"))
    )
    consent = await session.scalar(
        select(func.count())
        .select_from(Operation)
        .where(and_(Operation.ticket_id == ticket_id, Operation.status == "waiting_consent"))
    )
    return int(approvals or 0), int(consent or 0)


async def _counts_for_device(session: AsyncSession, device_id: str) -> tuple[int, int, int]:
    now = datetime.now(timezone.utc)
    failed = await session.scalar(
        select(func.count())
        .select_from(Operation)
        .where(and_(Operation.device_id == device_id, Operation.status.in_(list(FAILED_OPERATION_STATUSES))))
    )
    stuck = await session.scalar(
        select(func.count())
        .select_from(Operation)
        .where(
            and_(
                Operation.device_id == device_id,
                Operation.status.in_(list(ACTIVE_OPERATION_STATUSES)),
                Operation.queued_at < now - timedelta(minutes=10),
            )
        )
    )
    outbox = await session.scalar(
        select(func.count())
        .select_from(DeviceOutbox)
        .where(and_(DeviceOutbox.device_id == device_id, DeviceOutbox.status.in_(["pending", "sent"])))
    )
    return int(failed or 0), int(stuck or 0), int(outbox or 0)


def _ticket_match(ticket: Ticket, *, pending_approvals: int, waiting_consent: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    ticket_open = str(ticket.status) in ACTIVE_TICKET_STATUSES
    sla_risk = bool(
        ticket.first_response_breached_at
        or ticket.resolution_breached_at
        or (ticket.first_response_due_at and ticket.first_response_due_at <= now)
        or (ticket.resolution_due_at and ticket.resolution_due_at <= now)
    )
    severity = "warning" if ticket_open or sla_risk or pending_approvals or waiting_consent else "ok"
    links = [_safe_link("Open ticket", f"/app/tickets/{ticket.ticket_id}", "ticket")]
    if ticket.device_id:
        links.append(_safe_link("Device Operations", f"/app/admin/device-operations/{ticket.device_id}", "device_operations"))
    return {
        "kind": "ticket",
        "id": ticket.ticket_id,
        "title": f"{ticket.ticket_code} · {ticket.title}",
        "status": ticket.status,
        "severity": severity,
        "reason": "Ticket is active or has SLA/approval/consent signals." if severity == "warning" else "Ticket found.",
        "context": {
            "ticket_id": ticket.ticket_id,
            "ticket_code": ticket.ticket_code,
            "device_id": ticket.device_id,
            "requester_id": ticket.requester_id,
            "queue_id": ticket.queue_id,
            "assignee_id": ticket.assignee_id,
        },
        "signals": {
            "ticket_open": ticket_open,
            "ticket_sla_risk": sla_risk,
            "pending_approval": pending_approvals > 0,
            "pending_consent": waiting_consent > 0,
        },
        "links": links,
    }


def _device_match(device: Device, *, failed_count: int, stuck_count: int, outbox_backlog: int, kind: str = "device") -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stale = bool(device.last_seen_at and device.last_seen_at < now - timedelta(minutes=15))
    severity = "warning" if stale or failed_count or stuck_count or outbox_backlog else "ok"
    return {
        "kind": kind,
        "id": device.device_id,
        "title": device.hostname or device.device_id,
        "status": "db_last_seen_stale" if stale else "db_last_seen_recent",
        "severity": severity,
        "reason": "Device found using DB evidence. Live websocket state is unavailable in debug_readonly MCP.",
        "context": {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "agent_online": None,
            "last_seen_at": _iso(device.last_seen_at),
            "live_state_source": "unavailable_in_debug_readonly_mcp",
        },
        "signals": {
            "stale_agent": stale,
            "failed_operation": failed_count > 0,
            "stuck_operation": stuck_count > 0,
            "outbox_backlog": outbox_backlog > 0,
        },
        "links": [
            _safe_link("Device Operations", f"/app/admin/device-operations/{device.device_id}", "device_operations"),
            _safe_link("Observer", f"/app/admin/observer?device_id={quote(device.device_id)}", "observer"),
        ],
    }


def _operation_match(operation: Operation) -> dict[str, Any]:
    failed = str(operation.status) in FAILED_OPERATION_STATUSES
    stuck = str(operation.status) in ACTIVE_OPERATION_STATUSES
    severity = "critical" if failed else ("warning" if stuck else "ok")
    title = operation.tool_name or operation.command_name or operation.kind
    reason = _safe_text(operation.error_code or operation.status)
    if operation.error_message and not reason:
        reason = "operation has error_message redacted"
    return {
        "kind": "operation",
        "id": operation.operation_id,
        "title": title,
        "status": operation.status,
        "severity": severity,
        "reason": reason,
        "context": {
            "ticket_id": operation.ticket_id,
            "device_id": operation.device_id,
            "operation_id": operation.operation_id,
            "trace_id": operation.trace_id,
            "tool_name": title,
        },
        "signals": {
            "failed_operation": failed,
            "stuck_operation": stuck,
            "waiting_consent": operation.status == "waiting_consent",
        },
        "links": [
            *([_safe_link("Open ticket", f"/app/tickets/{operation.ticket_id}", "ticket")] if operation.ticket_id else []),
            _safe_link("Observer", f"/app/admin/observer?operation_id={quote(operation.operation_id)}", "observer"),
        ],
    }


def _trace_match(trace: ObserverTrace) -> dict[str, Any]:
    has_errors = bool(trace.error_count or str(trace.status).lower() in {"failed", "error"})
    return {
        "kind": "trace",
        "id": trace.trace_id,
        "title": str((trace.attrs_json or {}).get("title") or trace.root_kind or trace.trace_id),
        "status": trace.status,
        "severity": "warning" if has_errors else "ok",
        "reason": "Observer trace found.",
        "context": {
            "ticket_id": trace.ticket_id,
            "device_id": trace.device_id,
            "operation_id": trace.operation_id,
            "trace_id": trace.trace_id,
        },
        "signals": {"observer_errors": has_errors},
        "links": [_safe_link("Observer", f"/app/admin/observer?trace_id={quote(trace.trace_id)}", "observer")],
    }


def _diagnosis_for_matches(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "No match found. Check ticket code, hostname, device_id, operation_id or trace_id."
    signals: dict[str, bool] = {}
    for match in matches:
        raw = match.get("signals") if isinstance(match.get("signals"), dict) else {}
        for key, value in raw.items():
            signals[str(key)] = bool(signals.get(str(key)) or value)
    reasons = [
        label
        for key, label in [
            ("stale_agent", "DB last_seen is stale"),
            ("outbox_backlog", "device outbox backlog exists"),
            ("failed_operation", "failed operation exists"),
            ("stuck_operation", "stuck/running operation exists"),
            ("waiting_consent", "operation is waiting for consent"),
            ("pending_approval", "pending approval exists"),
            ("ticket_sla_risk", "SLA risk exists"),
            ("observer_errors", "observer has errors"),
        ]
        if signals.get(key)
    ]
    if reasons:
        return "Likely cause: " + ", ".join(reasons[:5]) + "."
    return str(matches[0].get("reason") or "Context found.")


async def locate_debug_context(
    session: AsyncSession,
    *,
    q: str,
    limit: int = 10,
    include_traces: bool = True,
    include_logs: bool = False,
) -> dict[str, Any]:
    normalized = str(q or "").strip()
    if not normalized:
        return {"status": "error", "error_code": "QUERY_REQUIRED", "message": "q is required"}
    capped_limit = _limit(limit, default=10, cap=25)
    broad = len(normalized) >= 4
    matches: list[dict[str, Any]] = []

    ticket_conditions = []
    if UUID_RE.match(normalized):
        ticket_conditions.append(Ticket.ticket_id == normalized)
    if TICKET_CODE_RE.match(normalized):
        ticket_conditions.append(func.lower(Ticket.ticket_code) == normalized.lower())
    if broad:
        ticket_conditions.append(Ticket.title.ilike(f"%{normalized}%"))
    if ticket_conditions:
        tickets = (
            await session.execute(
                select(Ticket).where(or_(*ticket_conditions)).order_by(Ticket.updated_at.desc()).limit(capped_limit)
            )
        ).scalars().all()
        for ticket in tickets:
            approvals, consent = await _counts_for_ticket(session, ticket.ticket_id)
            matches.append(_ticket_match(ticket, pending_approvals=approvals, waiting_consent=consent))

    device_conditions = []
    if UUID_RE.match(normalized):
        device_conditions.append(Device.device_id == normalized)
    if broad:
        device_conditions.append(or_(func.lower(Device.hostname) == normalized.lower(), Device.hostname.ilike(f"%{normalized}%")))
    if device_conditions and len(matches) < capped_limit:
        devices = (
            await session.execute(
                select(Device)
                .where(and_(Device.deleted_at.is_(None), or_(*device_conditions)))
                .order_by(Device.last_seen_at.desc())
                .limit(capped_limit - len(matches))
            )
        ).scalars().all()
        for device in devices:
            failed, stuck, outbox = await _counts_for_device(session, device.device_id)
            kind = "hostname" if device.hostname and normalized.lower() in device.hostname.lower() else "device"
            matches.append(_device_match(device, failed_count=failed, stuck_count=stuck, outbox_backlog=outbox, kind=kind))

    if (UUID_RE.match(normalized) or broad) and len(matches) < capped_limit:
        operation = await session.get(Operation, normalized)
        if operation is not None:
            matches.append(_operation_match(operation))

    if include_traces and (UUID_RE.match(normalized) or len(normalized) >= 8) and len(matches) < capped_limit:
        trace = await session.get(ObserverTrace, normalized)
        if trace is not None:
            matches.append(_trace_match(trace))

    logs_payload: dict[str, Any] | None = None
    if include_logs:
        logs_payload = {
            "status": "logs_unavailable",
            "message": "In-memory server logs require live aiohttp runtime and are not available in debug_readonly MCP.",
        }

    matches = [redact_sensitive_payload(item) for item in matches[:capped_limit]]
    return {
        "status": "ok",
        "query": q,
        "normalized_query": normalized,
        "generated_at": _now_iso(),
        "matches": matches,
        "logs": logs_payload,
        "summary": {
            "match_count": len(matches),
            "highest_severity": _severity_max([str(match.get("severity") or "unknown") for match in matches]),
            "primary_diagnosis": _diagnosis_for_matches(matches),
            "confidence": "partial" if logs_payload else ("fresh" if matches else "unknown"),
        },
    }


def _overlay_filters(filters: ObserverDebugFilters) -> TraceOverlayFilters:
    return TraceOverlayFilters(
        query=filters.q,
        trace_id=filters.trace_id,
        ticket_id=filters.ticket_id,
        operation_id=filters.operation_id,
        device_id=filters.device_id,
        route=filters.route,
        playbook_run_id=filters.playbook_run_id,
        step_run_id=filters.step_run_id,
        lookback_hours=filters.lookback_hours,
    )


async def observer_trace_detail(
    session: AsyncSession,
    trace_id: str,
    *,
    include_agent_actions: bool = False,
) -> dict[str, Any]:
    trace_id = str(trace_id or "").strip()
    if not trace_id:
        return {"status": "error", "error_code": "TRACE_ID_REQUIRED", "message": "trace_id is required"}
    detail = await ObserverOverlayService(session).get_trace_detail(trace_id)
    if detail is None:
        return {"status": "error", "error_code": "OBSERVER_TRACE_NOT_FOUND", "message": "Observer trace context not found"}
    payload: dict[str, Any] = {"status": "ok", **detail}
    if include_agent_actions:
        payload["agent_actions_warning"] = (
            "agent actions require live server runtime and are not available in debug_readonly MCP"
        )
    return redact_sensitive_payload(payload)


async def observer_ticket_summary(
    session: AsyncSession,
    ticket_id: str,
    *,
    trace_limit: int = 8,
    signature_limit: int = 6,
    span_limit: int = 12,
    occurrence_limit: int = 6,
) -> dict[str, Any]:
    ticket_id = str(ticket_id or "").strip()
    if not ticket_id:
        return {"status": "error", "error_code": "TICKET_ID_REQUIRED", "message": "ticket_id is required"}
    payload = await ObserverOverlayService(session).get_ticket_observer_summary(
        ticket_id,
        trace_limit=_limit(trace_limit, default=8, cap=25),
        signature_limit=_limit(signature_limit, default=6, cap=25),
        span_limit=_limit(span_limit, default=12, cap=50),
        occurrence_limit=_limit(occurrence_limit, default=6, cap=50),
    )
    return redact_sensitive_payload({"status": "ok", **payload})


async def runtime_snapshot(session: AsyncSession, *, process_kind: str | None = None, include_details: bool = True) -> dict[str, Any]:
    return {
        "status": "partial",
        "runtime_snapshot_available": False,
        "process_kind": process_kind,
        "include_details": bool(include_details),
        "message": "Persisted server runtime snapshots are not implemented yet",
        "recommended_next_step": "implement server_runtime_snapshots before live runtime status is trusted",
        "confidence": "unknown",
    }


async def agent_presence_snapshot(
    session: AsyncSession,
    *,
    device_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    capped_limit = _limit(limit, default=50, cap=200)
    stmt = select(DevicePresenceSnapshot).order_by(DevicePresenceSnapshot.collected_at.desc()).limit(capped_limit)
    if device_id:
        stmt = (
            select(DevicePresenceSnapshot)
            .where(DevicePresenceSnapshot.device_id == device_id)
            .order_by(DevicePresenceSnapshot.collected_at.desc())
            .limit(capped_limit)
        )
    rows = (await session.execute(stmt)).scalars().all()
    devices: dict[str, dict[str, Any]] = {}
    if device_id:
        device = await session.get(Device, device_id)
        if device is not None:
            devices[device.device_id] = {
                "device_id": device.device_id,
                "hostname": device.hostname,
                "db_last_seen_at": _iso(device.last_seen_at),
                "db_last_handshake_at": _iso(device.last_handshake_at),
            }
    elif rows:
        device_ids = sorted({row.device_id for row in rows if row.device_id})
        if device_ids:
            device_rows = (await session.execute(select(Device).where(Device.device_id.in_(device_ids)))).scalars().all()
            devices = {
                item.device_id: {
                    "device_id": item.device_id,
                    "hostname": item.hostname,
                    "db_last_seen_at": _iso(item.last_seen_at),
                    "db_last_handshake_at": _iso(item.last_handshake_at),
                }
                for item in device_rows
            }
    snapshots = [
        {
            "id": row.id,
            "device_id": row.device_id,
            "collected_at": _iso(row.collected_at),
            "received_at": _iso(row.received_at),
            "session_state": row.session_state,
            "current_user": row.current_user,
            "idle_seconds": row.idle_seconds,
            "locked": row.locked,
            "snapshot": row.snapshot,
            "device_db_evidence": devices.get(row.device_id),
        }
        for row in rows
    ]
    return redact_sensitive_payload(
        {
            "status": "ok" if snapshots else "partial",
            "presence_snapshot_available": bool(snapshots),
            "confidence": "db_snapshot" if snapshots else "unknown",
            "message": None if snapshots else "No persisted agent presence snapshots found",
            "live_ws_state": "unavailable_in_debug_readonly_mcp",
            "device_id": device_id,
            "device_db_evidence": devices.get(device_id) if device_id else None,
            "snapshots": snapshots,
            "limits": {"limit": capped_limit, "returned": len(snapshots)},
        }
    )


async def observer_debug_bundle_v2(session: AsyncSession, filters: ObserverDebugFilters) -> dict[str, Any]:
    if not filters.has_locator():
        return {
            "status": "error",
            "error_code": "LOCATOR_INPUT_REQUIRED",
            "message": "Provide q, trace_id, ticket_id, operation_id, device_id, route, playbook_run_id or step_run_id.",
        }
    limit = _limit(filters.limit, default=20, cap=100)
    service = ObserverOverlayService(session)
    overlay_filters = _overlay_filters(filters)
    related_traces = await service.search_traces(overlay_filters, limit=limit)
    primary_trace_id = filters.trace_id or (related_traces[0].get("trace_id") if related_traces else None)
    primary_detail = await service.get_trace_detail(primary_trace_id) if primary_trace_id else None
    primary_trace = primary_detail.get("trace") if primary_detail else None
    ticket_id = filters.ticket_id or (primary_trace or {}).get("ticket_id")
    device_id = filters.device_id or (primary_trace or {}).get("device_id")
    operation_id = filters.operation_id or (primary_trace or {}).get("operation_id")

    locator = None
    if filters.q:
        locator = await locate_debug_context(
            session,
            q=filters.q,
            limit=min(limit, 25),
            include_traces=True,
            include_logs=filters.include_logs,
        )

    signatures = await service.search_signatures(
        TraceOverlayFilters(
            trace_id=(primary_trace or {}).get("trace_id"),
            ticket_id=ticket_id,
            device_id=device_id,
            operation_id=operation_id,
            lookback_hours=filters.lookback_hours,
        ),
        limit=min(limit, 25),
    )
    degradations = await service.search_degradations(
        TraceOverlayFilters(
            ticket_id=ticket_id,
            device_id=device_id,
            operation_id=operation_id,
            lookback_hours=filters.lookback_hours or 24,
        ),
        limit=min(limit, 25),
    )
    runtime = await runtime_snapshot(session) if filters.include_runtime_snapshot else None
    presence = (
        await agent_presence_snapshot(session, device_id=device_id, limit=min(limit, 200))
        if filters.include_presence_snapshot
        else None
    )
    ticket_context = await _load_ticket_context(session, ticket_id) if ticket_id else None
    device_context = await _load_device_context(session, device_id) if device_id else None
    error_occurrences = primary_detail.get("error_occurrences", []) if primary_detail else []
    status = "ok" if primary_detail else ("partial" if related_traces or locator else "error")
    if status == "error":
        primary_diagnosis = "No observer trace context found for the provided filters."
    elif error_occurrences:
        primary_diagnosis = "Primary trace contains error occurrences; inspect matching signatures before retry."
    elif related_traces:
        primary_diagnosis = "Observer traces found; inspect primary trace and related traces."
    else:
        primary_diagnosis = "Context is partial; use locator matches and DB evidence."
    payload = {
        "status": status,
        "query": filters.q,
        "filters": {key: value for key, value in asdict(filters).items() if value not in (None, False)},
        "confidence": "fresh" if primary_detail else ("partial" if related_traces or locator else "unknown"),
        "primary_diagnosis": primary_diagnosis,
        "runtime_snapshot": runtime,
        "presence_snapshot": presence,
        "locator": locator,
        "primary_trace": primary_trace,
        "related_traces": related_traces,
        "spans": primary_detail.get("spans", []) if primary_detail else [],
        "span_links": primary_detail.get("span_links", []) if primary_detail else [],
        "error_occurrences": error_occurrences,
        "signatures": signatures,
        "degradations": degradations,
        "ticket": ticket_context,
        "device": device_context,
        "agent_audit": [],
        "recent_logs": [
            {
                "status": "logs_unavailable",
                "message": "Live in-memory logs are not available in debug_readonly MCP.",
            }
        ]
        if filters.include_logs
        else [],
        "recommended_next_checks": _recommended_next_checks(primary_trace, error_occurrences, runtime, presence),
        "limits": {"limit": limit, "related_traces": len(related_traces), "redaction": "recursive"},
        "redaction": {"applied": True},
    }
    return redact_sensitive_payload(payload)


async def _load_ticket_context(session: AsyncSession, ticket_id: str) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(
                Ticket.ticket_id,
                Ticket.ticket_code,
                Ticket.title,
                Ticket.status,
                Ticket.priority,
                Ticket.device_id,
                Ticket.updated_at,
            ).where(Ticket.ticket_id == ticket_id)
        )
    ).mappings().first()
    if not row:
        return None
    return {
        "ticket_id": row["ticket_id"],
        "ticket_code": row["ticket_code"],
        "title": row["title"],
        "status": row["status"],
        "priority": row["priority"],
        "device_id": row["device_id"],
        "updated_at": _iso(row["updated_at"]),
    }


async def _load_device_context(session: AsyncSession, device_id: str) -> dict[str, Any] | None:
    row = (
        await session.execute(
            select(
                Device.device_id,
                Device.hostname,
                Device.agent_version,
                Device.protocol_version,
                Device.last_seen_at,
            ).where(Device.device_id == device_id)
        )
    ).mappings().first()
    if not row:
        return None
    return {
        "device_id": row["device_id"],
        "hostname": row["hostname"],
        "agent_version": row["agent_version"],
        "protocol_version": row["protocol_version"],
        "db_last_seen_at": _iso(row["last_seen_at"]),
        "live_ws_state": "unavailable_in_debug_readonly_mcp",
    }


def _recommended_next_checks(
    primary_trace: dict[str, Any] | None,
    error_occurrences: list[dict[str, Any]],
    runtime: dict[str, Any] | None,
    presence: dict[str, Any] | None,
) -> list[str]:
    checks: list[str] = []
    status = str((primary_trace or {}).get("status") or "").lower()
    if error_occurrences or status in {"failed", "timed_out", "error"}:
        checks.append("Inspect error_occurrences and matching signatures before retry.")
    if status in {"running", "accepted", "queued", "sent"}:
        checks.append("Inspect operation delivery, outbox, and persisted presence evidence.")
    if runtime and runtime.get("status") == "partial":
        checks.append("Persisted runtime snapshots are unavailable; verify server runtime before trusting live state.")
    if presence and presence.get("status") == "partial":
        checks.append("Presence snapshot is missing or stale; use device DB last_seen only as historical evidence.")
    if not checks:
        checks.append("Open primary observer trace detail and related traces.")
    return checks
