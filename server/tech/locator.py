"""Read-only quick locator for Tech Panel v2.1."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from aiohttp import web
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_session
from app.db.models import Device, ObserverTrace, Operation, Ticket, TicketApproval
from tech.log_buffer import list_log_records


UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
TICKET_CODE_RE = re.compile(r"^T-\d{3,}$", re.IGNORECASE)
SECRET_TEXT_RE = re.compile(
    r"(?i)(password|passwd|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*[^,\s;]+"
)
ACTIVE_TICKET_STATUSES = {"new", "queued", "assigned", "in_progress", "waiting_on_user", "waiting_on_internal_team", "waiting_on_vendor", "waiting_on_approval", "scheduled"}
ACTIVE_OPERATION_STATUSES = {"queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"}
FAILED_OPERATION_STATUSES = {"failed", "timed_out"}
SEVERITY_RANK = {"ok": 0, "info": 1, "unknown": 2, "warning": 3, "critical": 4}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _normalize_query(raw: str | None) -> str:
    return str(raw or "").strip()


def _redact_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return SECRET_TEXT_RE.sub(lambda match: f"{match.group(1)}=***REDACTED***", text)[:500]


def _safe_link(label: str, href: str, kind: str) -> dict[str, str]:
    return {"label": label, "href": href, "kind": kind}


def _severity_max(values: list[str]) -> str:
    if not values:
        return "unknown"
    return max(values, key=lambda value: SEVERITY_RANK.get(value, 2))


def _is_online(request: web.Request, device_id: str) -> bool | None:
    state = request.app.get("state") if hasattr(request, "app") else None
    checker = getattr(state, "is_agent_online", None)
    if callable(checker):
        try:
            return bool(checker(device_id))
        except Exception:
            return None
    connected = getattr(state, "connected_agents", None)
    if isinstance(connected, dict):
        return device_id in connected
    return None


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
    links = [
        _safe_link("Открыть тикет", f"/app/tickets/{ticket.ticket_id}", "ticket"),
        _safe_link("Approval Center", f"/app/support/approvals?ticket_id={quote(ticket.ticket_id)}", "approval_center"),
    ]
    if ticket.device_id:
        links.append(_safe_link("Device card", f"/app/admin/device?device={ticket.device_id}", "device_card"))
    return {
        "kind": "ticket",
        "id": ticket.ticket_id,
        "title": f"{ticket.ticket_code} · {ticket.title}",
        "status": ticket.status,
        "severity": severity,
        "reason": "Тикет открыт, проверьте SLA, согласования и связанное устройство." if ticket_open else "Тикет найден.",
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


def _device_match(request: web.Request, device: Device, *, failed_count: int, stuck_count: int, kind: str = "device") -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    stale = bool(device.last_seen_at and device.last_seen_at < now - timedelta(minutes=15))
    online = _is_online(request, device.device_id)
    severity = "warning" if stale or failed_count or stuck_count else "ok"
    return {
        "kind": kind,
        "id": device.device_id,
        "title": device.hostname or device.device_id,
        "status": "online" if online else ("offline" if online is False else "unknown"),
        "severity": severity,
        "reason": "Устройство найдено; проверьте Endpoint и последние операции.",
        "context": {
            "device_id": device.device_id,
            "hostname": device.hostname,
            "agent_online": online,
            "last_seen_at": _iso(device.last_seen_at),
        },
        "signals": {
            "agent_offline": online is False,
            "stale_agent": stale,
            "failed_operation": failed_count > 0,
            "stuck_operation": stuck_count > 0,
        },
        "links": [
            _safe_link("Device card", f"/app/admin/device?device={device.device_id}", "device_card"),
            _safe_link("Inventory", f"/app/admin/inventory?device_id={quote(device.device_id)}", "inventory"),
            _safe_link("Observer", f"/app/admin/observer?device_id={quote(device.device_id)}", "observer"),
        ],
    }


def _operation_match(operation: Operation) -> dict[str, Any]:
    failed = str(operation.status) in FAILED_OPERATION_STATUSES
    stuck = str(operation.status) in ACTIVE_OPERATION_STATUSES
    waiting_consent = operation.status == "waiting_consent"
    severity = "critical" if failed else ("warning" if stuck else "ok")
    reason_parts = [operation.status]
    error = _redact_text(operation.error_message or operation.error_code)
    if error:
        reason_parts.append(error)
    links = [
        _safe_link("Операция", f"/app/admin/operations/{quote(operation.operation_id)}", "operation"),
        _safe_link("Observer", f"/app/admin/observer?operation_id={quote(operation.operation_id)}", "observer"),
    ]
    if operation.ticket_id:
        links.insert(0, _safe_link("Открыть тикет", f"/app/tickets/{operation.ticket_id}", "ticket"))
    if operation.device_id:
        links.append(_safe_link("Device card", f"/app/admin/device?device={operation.device_id}", "device_card"))
    return {
        "kind": "operation",
        "id": operation.operation_id,
        "title": operation.tool_name or operation.command_name or operation.kind,
        "status": operation.status,
        "severity": severity,
        "reason": " · ".join(part for part in reason_parts if part),
        "context": {
            "ticket_id": operation.ticket_id,
            "device_id": operation.device_id,
            "operation_id": operation.operation_id,
            "trace_id": operation.trace_id,
            "tool_name": operation.tool_name or operation.command_name,
            "operation_status": operation.status,
        },
        "signals": {
            "failed_operation": failed,
            "stuck_operation": stuck,
            "waiting_consent": waiting_consent,
            "pending_consent": waiting_consent,
        },
        "links": links,
    }


def _trace_match(trace: ObserverTrace) -> dict[str, Any]:
    has_errors = bool(trace.error_count or str(trace.status).lower() in {"failed", "error"})
    title = str((trace.attrs_json or {}).get("title") or trace.root_kind or trace.trace_id)
    return {
        "kind": "trace",
        "id": trace.trace_id,
        "title": title,
        "status": trace.status,
        "severity": "warning" if has_errors else "ok",
        "reason": _redact_text((trace.attrs_json or {}).get("latest_error")) or "Observer trace найден.",
        "context": {
            "ticket_id": trace.ticket_id,
            "device_id": trace.device_id,
            "operation_id": trace.operation_id,
            "trace_id": trace.trace_id,
        },
        "signals": {"observer_errors": has_errors},
        "links": [_safe_link("Observer", f"/app/admin/observer?trace_id={quote(trace.trace_id)}", "observer")],
    }


def _log_matches(query: str, *, limit: int) -> list[dict[str, Any]]:
    if len(query) < 4:
        return []
    lowered = query.lower()
    matches: list[dict[str, Any]] = []
    for record in list_log_records(limit=200):
        level = str(record.get("level") or "").lower()
        if level not in {"warning", "error", "critical"}:
            continue
        message = str(record.get("message") or "")
        if lowered not in message.lower():
            continue
        severity = "critical" if level == "critical" else ("warning" if level == "warning" else "critical")
        matches.append(
            {
                "kind": "log",
                "id": str(record.get("id") or record.get("timestamp") or len(matches)),
                "title": f"{level}: {_redact_text(message) or 'log'}",
                "status": level,
                "severity": severity,
                "reason": "Проблемная строка найдена в in-memory log buffer.",
                "context": {},
                "signals": {"observer_errors": level in {"error", "critical"}},
                "links": [_safe_link("Открыть логи", "/app/admin/tech?tab=logs", "logs")],
            }
        )
        if len(matches) >= limit:
            break
    return matches


def _diagnosis_for_matches(matches: list[dict[str, Any]]) -> str | None:
    if not matches:
        return None
    signals: dict[str, bool] = {}
    kinds: set[str] = set()
    for match in matches:
        kinds.add(str(match.get("kind") or "unknown"))
        raw_signals = match.get("signals") if isinstance(match.get("signals"), dict) else {}
        for key, value in raw_signals.items():
            signals[str(key)] = signals.get(str(key), False) or bool(value)
    reasons: list[str] = []
    if signals.get("agent_offline"):
        reasons.append("агент offline")
    if signals.get("stale_agent"):
        reasons.append("агент stale")
    if signals.get("failed_operation"):
        reasons.append("есть failed operation")
    if signals.get("stuck_operation"):
        reasons.append("есть stuck operation")
    if signals.get("waiting_consent") or signals.get("pending_consent"):
        reasons.append("операция ждёт consent")
    if signals.get("pending_approval"):
        reasons.append("есть pending approval")
    if signals.get("ticket_sla_risk"):
        reasons.append("есть SLA risk")
    if signals.get("observer_errors"):
        reasons.append("Observer показывает ошибки")
    if reasons:
        return "Вероятная причина: " + ", ".join(reasons[:5]) + "."
    if "ticket" in kinds:
        return "Вероятная причина: тикет найден без критичных runtime-сигналов."
    if "device" in kinds or "hostname" in kinds:
        return "Вероятная причина: устройство найдено без критичных runtime-сигналов."
    return str(matches[0].get("reason") or "Контекст найден.")


async def _counts_for_ticket(session: Any, ticket_id: str) -> tuple[int, int]:
    approvals = await session.scalar(
        select(func.count()).select_from(TicketApproval).where(and_(TicketApproval.ticket_id == ticket_id, TicketApproval.status == "requested"))
    )
    consent = await session.scalar(
        select(func.count()).select_from(Operation).where(and_(Operation.ticket_id == ticket_id, Operation.status == "waiting_consent"))
    )
    return int(approvals or 0), int(consent or 0)


async def _counts_for_device(session: Any, device_id: str) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    failed = await session.scalar(
        select(func.count()).select_from(Operation).where(and_(Operation.device_id == device_id, Operation.status.in_(list(FAILED_OPERATION_STATUSES))))
    )
    stuck = await session.scalar(
        select(func.count()).select_from(Operation).where(
            and_(
                Operation.device_id == device_id,
                Operation.status.in_(list(ACTIVE_OPERATION_STATUSES)),
                Operation.queued_at < now - timedelta(minutes=10),
            )
        )
    )
    return int(failed or 0), int(stuck or 0)


async def locate_tech_query(
    request: web.Request,
    *,
    query: str,
    limit: int = 10,
    include_logs: bool = True,
    include_traces: bool = True,
) -> dict[str, Any]:
    normalized = _normalize_query(query)
    if not normalized:
        raise ValueError("q is required")
    capped_limit = max(1, min(int(limit or 10), 25))
    broad = len(normalized) >= 4
    matches: list[dict[str, Any]] = []

    try:
        async with get_session() as session:
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
                    failed, stuck = await _counts_for_device(session, device.device_id)
                    kind = "hostname" if device.hostname and normalized.lower() in device.hostname.lower() else "device"
                    matches.append(_device_match(request, device, failed_count=failed, stuck_count=stuck, kind=kind))

            if (UUID_RE.match(normalized) or broad) and len(matches) < capped_limit:
                operation = await session.get(Operation, normalized)
                if operation is not None:
                    matches.append(_operation_match(operation))

            if include_traces and (UUID_RE.match(normalized) or len(normalized) >= 8) and len(matches) < capped_limit:
                trace = await session.get(ObserverTrace, normalized)
                if trace is not None:
                    matches.append(_trace_match(trace))
    except SQLAlchemyError:
        matches.append(
            {
                "kind": "unknown",
                "id": normalized,
                "title": "Locator DB lookup failed",
                "status": "unknown",
                "severity": "unknown",
                "reason": "Не удалось выполнить DB lookup; проверьте health PostgreSQL.",
                "context": {},
                "signals": {},
                "links": [_safe_link("Открыть техпанель", "/app/admin/tech", "logs")],
            }
        )

    if include_logs and len(matches) < capped_limit:
        matches.extend(_log_matches(normalized, limit=capped_limit - len(matches)))

    matches = matches[:capped_limit]
    primary = None
    if not matches:
        primary = "По запросу ничего не найдено. Проверьте ticket code, hostname, device_id, operation_id или trace_id."
    else:
        primary = _diagnosis_for_matches(matches) or matches[0]["reason"]
    return {
        "status": "ok",
        "query": query,
        "normalized_query": normalized,
        "generated_at": _now_iso(),
        "matches": matches,
        "summary": {
            "match_count": len(matches),
            "highest_severity": _severity_max([str(match.get("severity") or "unknown") for match in matches]),
            "primary_diagnosis": primary,
        },
    }
