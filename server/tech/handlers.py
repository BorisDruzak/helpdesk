"""Read-only observability endpoints for admin tech panel."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from aiohttp import web
from sqlalchemy import select, func, and_, or_, text, exists
from sqlalchemy.exc import SQLAlchemyError

from auth.middleware import require_auth
from app.db import get_session
from app.db.models import (
    Device,
    ConnectionRequest,
    Operation,
    DeviceOutbox,
    Ticket,
    TicketEvent,
    UiUserAudit,
    UiUser,
    AgentRuntimeAudit,
    AgentToken,
    TicketAdminAudit,
)
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from config import (
    OPERATION_DELIVERY_TIMEOUT,
    OPERATION_ACCEPTED_TIMEOUT,
    OPERATION_EXECUTION_TIMEOUT,
)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _parse_query_limit(raw: Optional[str], *, default: int, cap: int) -> int:
    try:
        v = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        v = default
    return max(1, min(int(v), cap))


def _pool_status_safe(bind: Any) -> Optional[str]:
    pool = getattr(bind, "pool", None)
    if pool is None:
        return None
    status_fn = getattr(pool, "status", None)
    if not callable(status_fn):
        return None
    try:
        return str(status_fn())
    except Exception:
        return None


def _active_agent_token_exists_for_connection_request(now: datetime):
    return exists(
        select(AgentToken.token_hash).where(
            and_(
                AgentToken.device_id == ConnectionRequest.device_id,
                AgentToken.revoked_at.is_(None),
                or_(AgentToken.expires_at.is_(None), AgentToken.expires_at > now),
            )
        )
    )


def _lifecycle_event_icon(kind: str) -> str:
    k = (kind or "").lower()
    if k in ("ticket_created",):
        return "🎫"
    if k in ("ticket_assigned", "assigned"):
        return "👤"
    if k in ("ticket_status_changed", "status_changed"):
        return "🔄"
    if k in ("sla_breached",):
        return "⚠️"
    if k in ("sla_reminder_sent",):
        return "⏰"
    if k in ("chat_message", "ticket_chat_message"):
        return "💬"
    if "tool" in k or k in ("run_tool", "command_queued"):
        return "🔧"
    if "invalid" in k or "error" in k:
        return "❌"
    return "📌"


def _ticket_status_from_payload(payload: dict[str, Any]) -> str:
    return str(
        payload.get("status_after")
        or payload.get("to_status")
        or payload.get("new_value")
        or payload.get("status")
        or ""
    ).strip().lower()


def _ticket_assignee_from_payload(payload: dict[str, Any]) -> str:
    return str(
        payload.get("assignee_id")
        or payload.get("new_value")
        or payload.get("after")
        or payload.get("to")
        or ""
    ).strip()


def _lifecycle_links(
    *,
    ticket_id: str,
    device_id: Optional[str],
    operation_id: Optional[str],
) -> list[dict[str, str]]:
    links: list[dict[str, str]] = [
        {
            "rel": "ticket",
            "label": "Тикет",
            "href": f"/ticket.html?ticket_id={ticket_id}",
        }
    ]
    if device_id:
        links.append(
            {
                "rel": "device",
                "label": "Устройство",
                "href": f"/admin#device-{device_id}",
            }
        )
    if operation_id:
        oid = str(operation_id)
        short = oid[:8] if len(oid) > 8 else oid
        suffix = "…" if len(oid) > 8 else ""
        links.append(
            {
                "rel": "operation",
                "label": f"Операция {short}{suffix}",
                "href": f"/ticket.html?ticket_id={ticket_id}",
            }
        )
    return links


def _milestone_rail(milestones: dict[str, Optional[str]]) -> list[dict[str, Any]]:
    order: list[tuple[str, str, str]] = [
        ("created", "Создан", "🎫"),
        ("first_response", "Первый ответ", "💬"),
        ("assigned", "Назначен", "👤"),
        ("in_progress", "В работе", "⚙️"),
        ("waiting_user", "Ждём пользователя", "⏸️"),
        ("waiting_external", "Ждём внешнюю сторону", "🏢"),
        ("resolved", "Решён", "✅"),
        ("closed", "Закрыт", "🔒"),
    ]
    rail: list[dict[str, Any]] = []
    for key, label, icon in order:
        at = milestones.get(key)
        rail.append({"key": key, "label": label, "icon": icon, "at": at, "reached": bool(at)})
    return rail


def _sla_lane_from_marks(sla_marks: dict[str, Optional[str]]) -> list[dict[str, Any]]:
    specs: list[tuple[str, str, str]] = [
        ("first_response_due", "Срок первого ответа (SLA)", "⏱️"),
        ("first_response_breached", "Просрочен первый ответ", "❗"),
        ("resolution_due", "Срок решения (SLA)", "⏱️"),
        ("resolution_breached", "Просрочено решение", "❗"),
    ]
    lane: list[dict[str, Any]] = []
    for key, label, icon in specs:
        at = sla_marks.get(key)
        if at:
            lane.append({"key": key, "kind": "sla", "label": label, "icon": icon, "at": at})
    return lane


def _threshold(name: str, default_sec: int) -> int:
    # Optional config override without hard dependency.
    import config

    return int(getattr(config, name, default_sec))


def _alert(
    *,
    severity: str,
    kind: str,
    entity_type: str,
    entity_id: str,
    summary: str,
    details: dict | None = None,
    link: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    aid = f"{kind}:{entity_type}:{entity_id}"
    return {
        "id": aid,
        "severity": severity,
        "kind": kind,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "details": details or {},
        "detected_at": now,
        "link": link,
    }


def _build_alerts_from_metrics(
    *,
    stale_count: int,
    stale_sec: int,
    old_pending: int,
    invalid_recent: int,
    invalid_burst_count: int,
    invalid_burst_window_sec: int,
    update_waiting_confirm: int,
    queued_stuck: int,
    sent_stuck: int,
    in_progress_stuck: int,
    outbox_backlog: int,
    outbox_backlog_warn: int,
    watchdog_states: dict[str, bool],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if stale_count > 0:
        alerts.append(
            _alert(
                severity="warning",
                kind="device_stale",
                entity_type="fleet",
                entity_id="devices",
                summary=f"{stale_count} stale devices detected",
                details={"stale_count": stale_count, "threshold_seconds": stale_sec},
                link="/admin#devices",
            )
        )
    if old_pending > 0:
        alerts.append(
            _alert(
                severity="warning",
                kind="connection_request_stuck_pending",
                entity_type="connection_requests",
                entity_id="pending",
                summary=f"{old_pending} pending connection requests are stale",
                details={"pending_stale_count": old_pending},
                link="/admin#devices",
            )
        )
    if invalid_recent >= invalid_burst_count:
        alerts.append(
            _alert(
                severity="critical",
                kind="invalid_token_burst",
                entity_type="auth",
                entity_id="agents",
                summary=f"Invalid token burst detected: {invalid_recent} events",
                details={"window_seconds": invalid_burst_window_sec},
            )
        )
    if update_waiting_confirm > 0:
        alerts.append(
            _alert(
                severity="warning",
                kind="update_waiting_handshake_confirm_too_long",
                entity_type="operation",
                entity_id="agent_update",
                summary=f"{update_waiting_confirm} updates are waiting too long",
                link="/admin#agent-updates",
            )
        )
    if queued_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_queued_too_long", entity_type="operation", entity_id="queued", summary=f"{queued_stuck} queued operations stuck"))
    if sent_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_sent_too_long", entity_type="operation", entity_id="sent", summary=f"{sent_stuck} sent operations stuck"))
    if in_progress_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_in_progress_too_long", entity_type="operation", entity_id="in_progress", summary=f"{in_progress_stuck} running operations exceeded deadline"))
    if outbox_backlog >= outbox_backlog_warn:
        alerts.append(
            _alert(
                severity="warning",
                kind="outbox_backlog_high",
                entity_type="outbox",
                entity_id="device_outbox",
                summary=f"Outbox backlog is high: {outbox_backlog}",
            )
        )
    for kind, running in watchdog_states.items():
        if not running:
            alerts.append(
                _alert(
                    severity="critical",
                    kind="watchdog_not_running",
                    entity_type="service",
                    entity_id=kind,
                    summary=f"{kind} is not running",
                )
            )
    return alerts


async def _build_overview(request: web.Request) -> dict[str, Any]:
    state = request.app["state"]
    now = datetime.now(timezone.utc)
    stale_sec = _threshold("TECH_DEVICE_STALE_SECONDS", 300)
    pending_stuck_sec = _threshold("TECH_CONNECTION_REQUEST_STUCK_SECONDS", 300)
    invalid_burst_window_sec = _threshold("TECH_INVALID_TOKEN_BURST_WINDOW_SECONDS", 600)
    invalid_burst_count = _threshold("TECH_INVALID_TOKEN_BURST_COUNT", 5)
    outbox_backlog_warn = _threshold("TECH_OUTBOX_BACKLOG_WARN", 100)

    alerts: list[dict[str, Any]] = []

    postgres_health = {"reachable": False, "latency_ms": None, "database": None, "pool_status": None, "error": None}
    db_started = datetime.now(timezone.utc)
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
            latency_ms = (datetime.now(timezone.utc) - db_started).total_seconds() * 1000.0
            bind = session.get_bind()
            postgres_health.update(
                {
                    "reachable": True,
                    "latency_ms": round(latency_ms, 2),
                    "database": str(getattr(getattr(bind, "url", None), "database", "")) or None,
                    "pool_status": _pool_status_safe(bind),
                }
            )
            slow_ms = _threshold("TECH_POSTGRES_SLOW_MS", 250)
            if latency_ms > slow_ms:
                alerts.append(
                    _alert(
                        severity="warning",
                        kind="postgres_slow",
                        entity_type="postgres",
                        entity_id="primary",
                        summary=f"PostgreSQL latency is high: {latency_ms:.1f} ms",
                        details={"latency_ms": latency_ms, "threshold_ms": slow_ms},
                    )
                )

            total_devices = await session.scalar(select(func.count()).select_from(Device)) or 0
            stale_count = await session.scalar(
                select(func.count()).select_from(Device).where(
                    and_(
                        Device.last_seen_at.isnot(None),
                        Device.last_seen_at < (now - timedelta(seconds=stale_sec)),
                    )
                )
            ) or 0
            unresolved_pending_filter = and_(
                ConnectionRequest.status == "pending",
                ~_active_agent_token_exists_for_connection_request(now),
            )
            pending_conn = await session.scalar(
                select(func.count()).select_from(ConnectionRequest).where(unresolved_pending_filter)
            ) or 0
            invalid_recent = await session.scalar(
                select(func.count()).select_from(TicketEvent).where(
                    and_(
                        TicketEvent.event_type == "agent_invalid_token",
                        TicketEvent.created_at >= (now - timedelta(seconds=invalid_burst_window_sec)),
                    )
                )
            ) or 0

            # fallback to runtime audit for invalid_token burst
            invalid_runtime_recent = await session.scalar(
                select(func.count()).select_from(AgentRuntimeAudit).where(
                    and_(
                        AgentRuntimeAudit.event_type == "invalid_token",
                        AgentRuntimeAudit.created_at >= (now - timedelta(seconds=invalid_burst_window_sec)),
                    )
                )
            ) or 0
            invalid_recent = max(int(invalid_recent), int(invalid_runtime_recent))

            online_count = len(state.connected_agents)
            offline_count = max(int(total_devices) - int(online_count), 0)

            active_updates = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.kind == "agent_update",
                        Operation.status.in_(["queued", "sent", "accepted", "running"]),
                    )
                )
            ) or 0
            update_waiting_confirm = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.kind == "agent_update",
                        Operation.status.in_(["queued", "sent", "accepted", "running"]),
                        Operation.queued_at < (now - timedelta(seconds=_threshold("TECH_UPDATE_CONFIRM_WAIT_SECONDS", 600))),
                    )
                )
            ) or 0
            failed_recent = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.kind == "agent_update",
                        Operation.status == "failed",
                        Operation.finished_at >= (now - timedelta(hours=24)),
                    )
                )
            ) or 0
            timed_out_recent = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.status == "timed_out",
                        Operation.finished_at >= (now - timedelta(hours=24)),
                    )
                )
            ) or 0

            queued_stuck = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.status == "queued",
                        Operation.queued_at < (now - timedelta(seconds=OPERATION_DELIVERY_TIMEOUT)),
                    )
                )
            ) or 0
            sent_stuck = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.status == "sent",
                        Operation.sent_at.isnot(None),
                        Operation.sent_at < (now - timedelta(seconds=OPERATION_ACCEPTED_TIMEOUT)),
                    )
                )
            ) or 0
            in_progress_stuck = await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(
                        Operation.status.in_(["accepted", "running"]),
                        Operation.deadline_at.isnot(None),
                        Operation.deadline_at < now,
                    )
                )
            ) or 0
            outbox_backlog = await session.scalar(
                select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.status.in_(["pending", "sent"]))
            ) or 0

            reprovision_required_count = await session.scalar(
                select(func.count()).select_from(Device).where(
                    ~exists(
                        select(1).where(
                            and_(
                                AgentToken.device_id == Device.device_id,
                                AgentToken.revoked_at.is_(None),
                            )
                        )
                    )
                )
            ) or 0

            # Прокси для «неуспешной доставки»: записи outbox со status=failed за 24ч (не все NACK попадают в БД).
            outbox_failed_recent = await session.scalar(
                select(func.count()).select_from(DeviceOutbox).where(
                    and_(
                        DeviceOutbox.status == "failed",
                        DeviceOutbox.failed_at.isnot(None),
                        DeviceOutbox.failed_at >= (now - timedelta(hours=24)),
                    )
                )
            ) or 0

            failed_logins_recent = await session.scalar(
                select(func.count()).select_from(UiUserAudit).where(
                    and_(
                        UiUserAudit.action == "login_failed",
                        UiUserAudit.created_at >= (now - timedelta(hours=24)),
                    )
                )
            ) or 0
            ui_logins_recent = await session.scalar(
                select(func.count()).select_from(UiUserAudit).where(
                    and_(
                        UiUserAudit.action == "login_success",
                        UiUserAudit.created_at >= (now - timedelta(hours=24)),
                    )
                )
            ) or 0
            locked_users_count = await session.scalar(
                select(func.count()).select_from(UiUser).where(
                    and_(UiUser.locked_until.isnot(None), UiUser.locked_until > now)
                )
            ) or 0
            admin_changes_recent = await session.scalar(
                select(func.count()).select_from(TicketAdminAudit).where(
                    TicketAdminAudit.created_at >= (now - timedelta(hours=24))
                )
            ) or 0
            old_pending = await session.scalar(
                select(func.count()).select_from(ConnectionRequest).where(
                    and_(
                        unresolved_pending_filter,
                        ConnectionRequest.last_request_at < (now - timedelta(seconds=pending_stuck_sec)),
                    )
                )
            ) or 0
            stale_pending_rows = (
                await session.execute(
                    select(ConnectionRequest)
                    .where(
                        and_(
                            unresolved_pending_filter,
                            ConnectionRequest.last_request_at < (now - timedelta(seconds=pending_stuck_sec)),
                        )
                    )
                    .order_by(ConnectionRequest.last_request_at.asc())
                    .limit(10)
                )
            ).scalars().all()
            watchdog_states = {
                "operation_watchdog": bool(getattr(request.app.get("operation_watchdog"), "_running", False)),
                "ticket_sla_watchdog": bool(getattr(request.app.get("ticket_sla_watchdog"), "_running", False)),
                "ticket_auto_close_watchdog": bool(getattr(request.app.get("ticket_auto_close_watchdog"), "_running", False)),
            }
            alerts.extend(
                _build_alerts_from_metrics(
                        stale_count=int(stale_count),
                        stale_sec=stale_sec,
                        old_pending=int(old_pending),
                        invalid_recent=int(invalid_recent),
                        invalid_burst_count=invalid_burst_count,
                    invalid_burst_window_sec=invalid_burst_window_sec,
                    update_waiting_confirm=int(update_waiting_confirm),
                    queued_stuck=int(queued_stuck),
                    sent_stuck=int(sent_stuck),
                    in_progress_stuck=int(in_progress_stuck),
                    outbox_backlog=int(outbox_backlog),
                    outbox_backlog_warn=outbox_backlog_warn,
                        watchdog_states=watchdog_states,
                    )
                )
            if stale_pending_rows:
                for alert in alerts:
                    if alert["kind"] == "connection_request_stuck_pending":
                        alert["details"]["samples"] = [
                            {
                                "device_id": row.device_id,
                                "created_at": _iso(row.created_at),
                                "last_request_at": _iso(row.last_request_at),
                                "hostname": row.hostname,
                                "ip_address": row.ip_address,
                            }
                            for row in stale_pending_rows
                        ]
                        break

            overview = {
                "service_health": {
                    "api": "ok",
                    "ws_ui": "ok",
                    "ui_ws_connections": int(len(state.ui_connections)),
                    "device_dispatch": "ok" if request.app.get("outbox_sender") else "degraded",
                    "operation_watchdog": "ok" if getattr(request.app.get("operation_watchdog"), "_running", False) else "down",
                    "ticket_sla_watchdog": "ok" if getattr(request.app.get("ticket_sla_watchdog"), "_running", False) else "down",
                    "ticket_auto_close_watchdog": "ok" if getattr(request.app.get("ticket_auto_close_watchdog"), "_running", False) else "down",
                },
                "postgres_health": postgres_health,
                "agent_health": {
                    "online_count": int(online_count),
                    "offline_count": int(offline_count),
                    "stale_count": int(stale_count),
                    "pending_connection_requests": int(pending_conn),
                    "invalid_token_recent": int(invalid_recent),
                    "reprovision_required_count": int(reprovision_required_count),
                },
                "update_health": {
                    "in_progress": int(active_updates),
                    "awaiting_handshake_confirm": int(update_waiting_confirm),
                    "failed_recent": int(failed_recent),
                    "timed_out_recent": int(timed_out_recent),
                },
                "operations_health": {
                    "queued_stuck": int(queued_stuck),
                    "sent_stuck": int(sent_stuck),
                    "in_progress_stuck": int(in_progress_stuck),
                    "recent_nack_count": int(outbox_failed_recent),
                },
                "audit_counters": {
                    "failed_logins_recent": int(failed_logins_recent),
                    "locked_users_count": int(locked_users_count),
                    "ui_logins_recent": int(ui_logins_recent),
                    "admin_changes_recent": int(admin_changes_recent),
                },
                "alerts": alerts,
            }
            return overview
    except SQLAlchemyError as exc:
        postgres_health["error"] = str(exc)
        alerts.append(
            _alert(
                severity="critical",
                kind="postgres_unreachable",
                entity_type="postgres",
                entity_id="primary",
                summary="PostgreSQL probe failed",
                details={"error": str(exc)},
            )
        )
        return {
            "service_health": {
                "api": "degraded",
                "ws_ui": "unknown",
                "ui_ws_connections": int(len(state.ui_connections)),
                "device_dispatch": "ok",
                "operation_watchdog": "unknown",
                "ticket_sla_watchdog": "unknown",
                "ticket_auto_close_watchdog": "unknown",
            },
            "postgres_health": postgres_health,
            "agent_health": {},
            "update_health": {},
            "operations_health": {},
            "audit_counters": {},
            "alerts": alerts,
        }


@require_auth("admin", "support", "auditor")
async def handle_tech_overview(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "overview": await _build_overview(request)})


@require_auth("admin", "support", "auditor")
async def handle_tech_alerts(request: web.Request) -> web.Response:
    overview = await _build_overview(request)
    return web.json_response({"status": "ok", "alerts": overview.get("alerts", [])})


@require_auth("admin", "support", "auditor")
async def handle_tech_agents_audit(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=100, cap=500)
    async with get_session() as session:
        repo = AgentRuntimeAuditRepo(session)
        items = await repo.list_feed(
            device_id=request.query.get("device_id"),
            event_type=request.query.get("event_type"),
            severity=request.query.get("severity"),
            dt_from=_parse_dt(request.query.get("from")),
            dt_to=_parse_dt(request.query.get("to")),
            limit=limit,
        )
        return web.json_response(
            {
                "status": "ok",
                "events": [
                    {
                        "id": i.id,
                        "device_id": i.device_id,
                        "event_type": i.event_type,
                        "severity": i.severity,
                        "source": i.source,
                        "operation_id": i.operation_id,
                        "ticket_id": i.ticket_id,
                        "actor_id": i.actor_id,
                        "actor_role": i.actor_role,
                        "details_json": i.details_json or {},
                        "created_at": _iso(i.created_at),
                    }
                    for i in items
                ],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_agent_timeline(request: web.Request) -> web.Response:
    device_id = request.match_info["device_id"]
    async with get_session() as session:
        device = await session.scalar(select(Device).where(Device.device_id == device_id))
        if not device:
            return web.json_response({"status": "error", "error": "Device not found"}, status=404)
        repo = AgentRuntimeAuditRepo(session)
        events = await repo.list_feed(device_id=device_id, limit=200)
        update_events = [e for e in events if e.event_type.startswith("update_")]
        auth_events = [e for e in events if "token" in e.event_type or "handshake" in e.event_type]
        return web.json_response(
            {
                "status": "ok",
                "device": {
                    "device_id": device.device_id,
                    "hostname": device.hostname,
                    "last_seen_at": _iso(device.last_seen_at),
                    "last_handshake_at": _iso(device.last_handshake_at),
                    "agent_version": device.agent_version,
                },
                "current_state": {
                    "online": bool(request.app["state"].is_agent_online(device_id)),
                    "last_seen_at": _iso(device.last_seen_at),
                },
                "events": [
                    {
                        "event_type": e.event_type,
                        "severity": e.severity,
                        "at": _iso(e.created_at),
                        "details": e.details_json or {},
                    }
                    for e in events
                ],
                "auth_summary": {"events_count": len(auth_events)},
                "update_summary": {"events_count": len(update_events)},
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_ticket_lifecycle(request: web.Request) -> web.Response:
    ticket_ref = request.match_info["ticket_id"]
    title_map = {
        "ticket_created": "Создан",
        "ticket_assigned": "Назначен исполнитель",
        "assigned": "Назначен исполнитель",
        "assignee_changed": "Назначен исполнитель",
        "ticket_status_changed": "Изменен статус",
        "status_changed": "Изменен статус",
        "routing_applied": "Routing applied",
        "queue_changed": "Queue changed",
        "sla_breached": "SLA нарушен",
        "sla_reminder_sent": "SLA напоминание",
        "chat_message": "Сообщение в чате",
        "tool_call_started": "Tool call started",
        "tool_call_result": "Tool call result",
    }
    async with get_session() as session:
        ticket = await session.scalar(
            select(Ticket).where(or_(Ticket.ticket_id == ticket_ref, Ticket.ticket_code == ticket_ref))
        )
        if not ticket:
            return web.json_response({"status": "error", "error": "Ticket not found"}, status=404)
        ticket_id = ticket.ticket_id
        events = (
            await session.execute(
                select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.created_at.asc()).limit(500)
            )
        ).scalars().all()
        related_ops = (
            await session.execute(
                select(Operation).where(Operation.ticket_id == ticket_id).order_by(Operation.queued_at.desc()).limit(200)
            )
        ).scalars().all()
        milestones = {
            "created": _iso(ticket.created_at),
            "first_response": _iso(ticket.first_response_at),
            "assigned": None,
            "in_progress": None,
            "waiting_user": None,
            "waiting_external": None,
            "resolved": _iso(ticket.resolved_at),
            "closed": _iso(ticket.closed_at),
        }
        timeline = []
        for ev in events:
            payload = ev.payload if isinstance(ev.payload, dict) else {}
            status_after = (
                payload.get("status_after")
                or payload.get("to_status")
                or payload.get("new_value")
            )
            actor_label = payload.get("actor_label") or payload.get("actor_id") or payload.get("role") or "Система"
            op_id = ev.operation_id or payload.get("operation_id")
            dev_id = ev.device_id or ticket.device_id
            timeline.append(
                {
                    "id": ev.id,
                    "kind": ev.event_type,
                    "title": title_map.get(ev.event_type, ev.event_type.replace("_", " ").capitalize()),
                    "icon": _lifecycle_event_icon(ev.event_type),
                    "actor_label": actor_label,
                    "at": _iso(ev.created_at),
                    "status_before": payload.get("status_before"),
                    "status_after": status_after,
                    "device_id": dev_id,
                    "operation_id": op_id,
                    "links": _lifecycle_links(ticket_id=ticket_id, device_id=dev_id, operation_id=op_id),
                    "details": payload,
                }
            )
            if ev.event_type in ("ticket_assigned", "assigned", "assignee_changed") and not milestones["assigned"]:
                assigned_to = _ticket_assignee_from_payload(payload)
                if assigned_to:
                    milestones["assigned"] = _iso(ev.created_at)
            if ev.event_type in ("ticket_status_changed", "status_changed"):
                after = _ticket_status_from_payload(payload)
                if after in ("triaged", "in_progress") and not milestones["in_progress"]:
                    milestones["in_progress"] = _iso(ev.created_at)
                if after == "waiting_on_user" and not milestones["waiting_user"]:
                    milestones["waiting_user"] = _iso(ev.created_at)
                if after in ("waiting_on_vendor", "waiting_external") and not milestones["waiting_external"]:
                    milestones["waiting_external"] = _iso(ev.created_at)

        if ticket.assignee_id and not milestones["assigned"]:
            assignee_event = next(
                (
                    ev
                    for ev in events
                    if ev.event_type == "assignee_changed"
                    and _ticket_assignee_from_payload(ev.payload if isinstance(ev.payload, dict) else {})
                ),
                None,
            )
            if assignee_event:
                milestones["assigned"] = _iso(assignee_event.created_at)
        if ticket.status in ("triaged", "in_progress") and not milestones["in_progress"]:
            status_event = next(
                (
                    ev
                    for ev in events
                    if ev.event_type in ("ticket_status_changed", "status_changed")
                    and _ticket_status_from_payload(ev.payload if isinstance(ev.payload, dict) else {}) in ("triaged", "in_progress")
                ),
                None,
            )
            if status_event:
                milestones["in_progress"] = _iso(status_event.created_at)
        if ticket.status == "waiting_on_user" and not milestones["waiting_user"]:
            wait_event = next(
                (
                    ev
                    for ev in events
                    if ev.event_type in ("ticket_status_changed", "status_changed")
                    and _ticket_status_from_payload(ev.payload if isinstance(ev.payload, dict) else {}) == "waiting_on_user"
                ),
                None,
            )
            if wait_event:
                milestones["waiting_user"] = _iso(wait_event.created_at)
        if ticket.status in ("waiting_on_vendor", "waiting_external") and not milestones["waiting_external"]:
            wait_external_event = next(
                (
                    ev
                    for ev in events
                    if ev.event_type in ("ticket_status_changed", "status_changed")
                    and _ticket_status_from_payload(ev.payload if isinstance(ev.payload, dict) else {}) in ("waiting_on_vendor", "waiting_external")
                ),
                None,
            )
            if wait_external_event:
                milestones["waiting_external"] = _iso(wait_external_event.created_at)

        sla_marks = {
            "first_response_due": _iso(ticket.first_response_due_at),
            "first_response_breached": _iso(ticket.first_response_breached_at),
            "resolution_due": _iso(ticket.resolution_due_at),
            "resolution_breached": _iso(ticket.resolution_breached_at),
        }
        related_filtered = [
            op
            for op in related_ops
            if op.kind in ("agent_update", "tool_call", "command", "cancel_operation")
        ]
        return web.json_response(
            {
                "status": "ok",
                "ticket": {
                    "ticket_id": ticket.ticket_id,
                    "ticket_code": ticket.ticket_code,
                    "title": ticket.title,
                    "status": ticket.status,
                    "device_id": ticket.device_id,
                    "assignee_id": ticket.assignee_id,
                    "queue_id": ticket.queue_id,
                },
                "current_state": {
                    "status": ticket.status,
                    "updated_at": _iso(ticket.updated_at),
                    "assignee_id": ticket.assignee_id,
                    "queue_id": ticket.queue_id,
                },
                "milestones": milestones,
                "milestone_rail": _milestone_rail(milestones),
                "sla_marks": sla_marks,
                "sla_lane": _sla_lane_from_marks(sla_marks),
                "timeline": timeline,
                "related_operations": [
                    {
                        "operation_id": op.operation_id,
                        "kind": op.kind,
                        "status": op.status,
                        "queued_at": _iso(op.queued_at),
                        "finished_at": _iso(op.finished_at),
                        "device_id": op.device_id,
                        "icon": "🔧" if op.kind == "agent_update" else "⚡",
                        "links": _lifecycle_links(
                            ticket_id=ticket_id,
                            device_id=op.device_id,
                            operation_id=op.operation_id,
                        ),
                    }
                    for op in related_filtered
                ],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_users_audit(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=100, cap=500)
    async with get_session() as session:
        rows = (
            await session.execute(select(UiUserAudit).order_by(UiUserAudit.created_at.desc()).limit(limit))
        ).scalars().all()
        return web.json_response(
            {
                "status": "ok",
                "events": [
                    {
                        "id": r.id,
                        "user_login": r.user_login,
                        "action": r.action,
                        "actor_id": r.actor_id,
                        "details_json": r.details_json or {},
                        "created_at": _iso(r.created_at),
                    }
                    for r in rows
                ],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_admin_config_audit(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=100, cap=500)
    async with get_session() as session:
        repo = TicketAdminAuditRepo(session)
        rows = await repo.list_audit(
            entity_type=request.query.get("entity_type"),
            entity_id=request.query.get("entity_id"),
            actor_id=request.query.get("actor_id"),
            limit=limit,
            offset=0,
        )
        return web.json_response(
            {
                "status": "ok",
                "events": [
                    {
                        "id": r.id,
                        "entity_type": r.entity_type,
                        "entity_id": r.entity_id,
                        "action": r.action,
                        "actor_id": r.actor_id,
                        "actor_role": r.actor_role,
                        "before_json": r.before_json,
                        "after_json": r.after_json,
                        "trace_id": r.trace_id,
                        "created_at": _iso(r.created_at),
                    }
                    for r in rows
                ],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_operations_stuck(request: web.Request) -> web.Response:
    now = datetime.now(timezone.utc)
    queued_sec = _threshold("TECH_OPERATION_QUEUED_STUCK_SECONDS", OPERATION_DELIVERY_TIMEOUT)
    sent_sec = _threshold("TECH_OPERATION_SENT_STUCK_SECONDS", OPERATION_ACCEPTED_TIMEOUT)
    running_sec = _threshold("TECH_OPERATION_RUNNING_STUCK_SECONDS", OPERATION_EXECUTION_TIMEOUT)
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Operation).where(
                    or_(
                        and_(Operation.status == "queued", Operation.queued_at < (now - timedelta(seconds=queued_sec))),
                        and_(Operation.status == "sent", Operation.sent_at.isnot(None), Operation.sent_at < (now - timedelta(seconds=sent_sec))),
                        and_(Operation.status.in_(["accepted", "running"]), Operation.started_at.isnot(None), Operation.started_at < (now - timedelta(seconds=running_sec))),
                    )
                ).order_by(Operation.queued_at.asc()).limit(500)
            )
        ).scalars().all()
        return web.json_response(
            {
                "status": "ok",
                "operations": [
                    {
                        "operation_id": op.operation_id,
                        "device_id": op.device_id,
                        "ticket_id": op.ticket_id,
                        "kind": op.kind,
                        "status": op.status,
                        "queued_at": _iso(op.queued_at),
                        "sent_at": _iso(op.sent_at),
                        "started_at": _iso(op.started_at),
                        "deadline_at": _iso(op.deadline_at),
                    }
                    for op in rows
                ],
            }
        )
