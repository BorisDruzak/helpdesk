"""Read-only observability endpoints for admin tech panel."""
from __future__ import annotations

import asyncio
import hashlib
import json
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
from app.repos.observer_settings_repo import ObserverSettingsRepo
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from config import (
    OPERATION_DELIVERY_TIMEOUT,
    OPERATION_ACCEPTED_TIMEOUT,
    OPERATION_EXECUTION_TIMEOUT,
)
from tech.dismiss_store import dismiss_alert, is_alert_dismissed
from tech.log_buffer import list_log_records, remove_log_record
from websocket.protocol import send_ws_command, send_ws_rpc_request
from observer.service import ObserverOverlayService, TraceOverlayFilters
from shared.redaction import redact_sensitive_payload


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


def _parse_bool(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


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


def _seconds_since(dt: Optional[datetime], *, now: Optional[datetime] = None) -> Optional[int]:
    if not dt:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - dt).total_seconds()))


def _label_provisioning_state(state: Optional[str]) -> str:
    mapping = {
        "active": "Токен активен",
        "unprovisioned": "Ожидает выдачи токена",
        "token_revoked": "Токен отозван",
        "reprovision_required": "Нужна перепривязка",
    }
    return mapping.get(state or "", state or "Неизвестно")


def _label_update_state(update_summary: dict[str, Any]) -> str:
    status = str(update_summary.get("last_update_operation_status") or "").strip().lower()
    if not status:
        return "Обновлений не запускалось"
    mapping = {
        "queued": "Обновление в очереди",
        "sent": "Команда обновления отправлена",
        "accepted": "Агент принял обновление",
        "running": "Идёт обновление",
        "success": "Обновление завершено успешно",
        "failed": "Обновление завершилось ошибкой",
        "timed_out": "Обновление зависло по таймауту",
        "canceled": "Обновление отменено",
    }
    return mapping.get(status, f"Статус обновления: {status}")


def _label_audit_event(event_type: Optional[str]) -> str:
    mapping = {
        "handshake_ok": "Handshake успешен",
        "invalid_token": "Неверный токен",
        "token_revoked": "Токен отозван",
        "agent_offline": "Агент отключился",
        "connection_request_created": "Запрос на подключение создан",
        "connection_request_approved": "Запрос на подключение одобрен",
        "connection_request_rejected": "Запрос на подключение отклонён",
        "update_requested": "Запрошено обновление агента",
        "update_failed": "Обновление завершилось ошибкой",
        "update_handshake_confirmed": "Обновление подтверждено handshake",
        "user_created": "Пользователь создан",
        "user_updated": "Пользователь обновлён",
        "password_changed": "Пароль изменён",
        "user_deactivated": "Пользователь деактивирован",
        "login_success": "Успешный вход",
        "login_failed": "Неудачная попытка входа",
        "server_runtime_start": "Запуск сервера",
        "server_runtime_stop": "Остановка сервера",
        "server_runtime_restart": "Перезапуск сервера",
        "server_runtime_smoke": "Smoke-проверка сервера",
    }
    key = str(event_type or "").strip()
    if key in mapping:
        return mapping[key]
    if not key:
        return "Событие"
    return key.replace("_", " ").capitalize()


def _severity_badge(severity: Optional[str]) -> dict[str, str]:
    value = str(severity or "info").strip().lower()
    mapping = {
        "info": {"label": "Инфо", "class_name": "info"},
        "warning": {"label": "Предупреждение", "class_name": "warning"},
        "error": {"label": "Ошибка", "class_name": "error"},
        "critical": {"label": "Критично", "class_name": "critical"},
    }
    return mapping.get(value, {"label": value or "Инфо", "class_name": value or "info"})


def _serialize_problem_log(item: dict[str, Any]) -> dict[str, Any]:
    badge = _severity_badge(item.get("level"))
    return {
        "id": item.get("id"),
        "timestamp": item.get("timestamp"),
        "level": str(item.get("level") or "").lower(),
        "level_label": badge["label"],
        "level_class": badge["class_name"],
        "message": item.get("message") or "",
        "module": item.get("module") or "",
        "function": item.get("function") or "",
        "file_path": item.get("file_path") or "",
        "line": item.get("line") or 0,
    }


def _log_location_label(record: dict[str, Any]) -> str:
    return ".".join(part for part in [record.get("module"), record.get("function")] if part)


def _is_noisy_log_alert(record: dict[str, Any]) -> bool:
    message = str(record.get("message") or "").strip().lower()
    location = _log_location_label(record).lower()
    noisy_patterns = (
        "ui websocket disconnected",
        "websocket disconnected",
        "websocket connection closed",
        "client disconnected",
        "connection reset by peer",
        "cannot write to closing transport",
    )
    if any(pattern in message for pattern in noisy_patterns):
        return True
    if "ws_ui" in location and ("disconnect" in message or "closed" in message):
        return True
    return False


def _humanize_log_summary(record: dict[str, Any]) -> str:
    level_label = _severity_badge(record.get("level"))["label"]
    message = str(record.get("message") or "").strip()
    lowered = message.lower()
    if "ui websocket disconnected" in lowered or "websocket disconnected" in lowered:
        return "UI-клиент закрыл WebSocket-соединение"
    if "connection reset by peer" in lowered:
        return "Удалённая сторона разорвала соединение"
    if "invalid token" in lowered:
        return "Обнаружен неверный токен агента"
    if not message:
        return f"{level_label}: проблема в логах"
    return f"{level_label}: {message}"


def _serialize_agent_audit_row(item: AgentRuntimeAudit) -> dict[str, Any]:
    badge = _severity_badge(item.severity)
    return {
        "id": item.id,
        "device_id": item.device_id,
        "event_type": item.event_type,
        "event_label": _label_audit_event(item.event_type),
        "severity": item.severity,
        "severity_label": badge["label"],
        "severity_class": badge["class_name"],
        "source": item.source,
        "operation_id": item.operation_id,
        "ticket_id": item.ticket_id,
        "actor_id": item.actor_id,
        "actor_role": item.actor_role,
        "details_json": redact_sensitive_payload(item.details_json or {}),
        "created_at": _iso(item.created_at),
    }


def _serialize_user_audit_row(row: UiUserAudit) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_login": row.user_login,
        "action": row.action,
        "action_label": _label_audit_event(row.action),
        "actor_id": row.actor_id,
        "details_json": redact_sensitive_payload(row.details_json or {}),
        "created_at": _iso(row.created_at),
    }


def _label_operation_status(status: Optional[str]) -> str:
    mapping = {
        "queued": "В очереди",
        "sent": "Отправлено агенту",
        "accepted": "Принято агентом",
        "running": "Выполняется",
        "waiting_consent": "Ждёт подтверждения",
        "cancel_requested": "Запрошена отмена",
        "succeeded": "Успешно",
        "success": "Успешно",
        "failed": "Ошибка",
        "timed_out": "Таймаут",
        "canceled": "Отменено",
    }
    key = str(status or "").strip().lower()
    return mapping.get(key, key or "Неизвестно")


def _label_outbox_status(status: Optional[str]) -> str:
    mapping = {
        "pending": "Ожидает отправки",
        "sent": "Отправлено",
        "delivered": "Доставлено",
        "failed": "Ошибка доставки",
    }
    key = str(status or "").strip().lower()
    return mapping.get(key, key or "Неизвестно")


def _serialize_operation_row(op: Operation) -> dict[str, Any]:
    return {
        "operation_id": op.operation_id,
        "device_id": op.device_id,
        "ticket_id": op.ticket_id,
        "kind": op.kind,
        "status": op.status,
        "status_label": _label_operation_status(op.status),
        "actor_role": op.actor_role,
        "tool_name": op.tool_name,
        "command_name": op.command_name,
        "error_code": op.error_code,
        "error_message": op.error_message,
        "result_summary": op.result_summary,
        "queued_at": _iso(op.queued_at),
        "sent_at": _iso(op.sent_at),
        "started_at": _iso(op.started_at),
        "finished_at": _iso(op.finished_at),
        "deadline_at": _iso(op.deadline_at),
    }


def _serialize_outbox_row(row: DeviceOutbox) -> dict[str, Any]:
    return {
        "id": row.id,
        "command_id": row.command_id,
        "command": row.command,
        "status": row.status,
        "status_label": _label_outbox_status(row.status),
        "operation_id": row.operation_id,
        "retry_count": int(row.retry_count or 0),
        "max_retries": int(row.max_retries or 0),
        "error_code": row.error_code,
        "error_message": row.error_message,
        "created_at": _iso(row.created_at),
        "sent_at": _iso(row.sent_at),
        "delivered_at": _iso(row.delivered_at),
        "failed_at": _iso(row.failed_at),
    }


def _alert_summary_ru(kind: str, summary: str, details: Optional[dict[str, Any]] = None) -> str:
    details = details or {}
    if kind == "device_stale":
        return f"Обнаружены неактивные агенты: {details.get('stale_count', 0)} шт."
    if kind == "connection_request_stuck_pending":
        return f"Есть зависшие запросы на подключение: {details.get('pending_stale_count', 0)} шт."
    if kind == "invalid_token_burst":
        return f"Всплеск ошибок токена: {summary.rsplit(':', 1)[-1].strip()}"
    if kind == "update_waiting_handshake_confirm_too_long":
        return summary.replace("updates are waiting too long", "обновлений слишком долго ждут подтверждения handshake")
    if kind == "operation_queued_too_long":
        return "Есть операции, слишком долго стоящие в очереди"
    if kind == "operation_sent_too_long":
        return "Есть операции, отправленные агенту слишком давно"
    if kind == "operation_in_progress_too_long":
        return "Есть операции, которые слишком долго выполняются"
    if kind == "outbox_backlog_high":
        return summary.replace("Outbox backlog is high", "Высокая очередь команд outbox")
    if kind == "watchdog_not_running":
        return summary.replace("is not running", "не запущен")
    if kind == "postgres_slow":
        return summary.replace("PostgreSQL latency is high", "Высокая задержка PostgreSQL")
    return summary


def _build_log_alerts(limit: int = 10) -> list[dict[str, Any]]:
    records = list_log_records(levels=("warning", "error", "critical"), limit=limit)
    alerts: list[dict[str, Any]] = []
    for record in records:
        if _is_noisy_log_alert(record):
            continue
        location = _log_location_label(record)
        summary = _humanize_log_summary(record)
        details = {}
        if location:
            details["источник"] = location
        if record.get("line"):
            details["строка"] = record["line"]
        if record.get("module"):
            details["модуль"] = record["module"]
        alerts.append(
            _alert(
                severity=record.get("level") or "warning",
                kind="runtime_log_problem",
                entity_type="log",
                entity_id=str(record.get("id") or location or "server"),
                summary=summary,
                details=details,
                related_log_id=str(record.get("id") or ""),
            )
        )
    return alerts


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
    related_log_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    normalized_details = details or {}
    payload = json.dumps(
        {
            "severity": severity,
            "kind": kind,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "summary": summary,
            "details": normalized_details,
            "related_log_id": related_log_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    fingerprint = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    aid = f"{kind}:{entity_type}:{entity_id}:{fingerprint}"
    return {
        "id": aid,
        "severity": severity,
        "kind": kind,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "summary": summary,
        "details": normalized_details,
        "detected_at": now,
        "link": link,
        "related_log_id": related_log_id,
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
                summary=f"Обнаружены неактивные агенты: {stale_count} шт.",
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
                summary=f"Есть зависшие запросы на подключение: {old_pending} шт.",
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
                summary=f"Всплеск ошибок токена: {invalid_recent} событий",
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
                summary=f"Обновления слишком долго ждут подтверждения handshake: {update_waiting_confirm} шт.",
                link="/admin#agent-updates",
            )
        )
    if queued_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_queued_too_long", entity_type="operation", entity_id="queued", summary=f"Операции слишком долго стоят в очереди: {queued_stuck} шт."))
    if sent_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_sent_too_long", entity_type="operation", entity_id="sent", summary=f"Операции слишком долго в статусе 'Отправлено': {sent_stuck} шт."))
    if in_progress_stuck > 0:
        alerts.append(_alert(severity="warning", kind="operation_in_progress_too_long", entity_type="operation", entity_id="in_progress", summary=f"Операции слишком долго выполняются: {in_progress_stuck} шт."))
    if outbox_backlog >= outbox_backlog_warn:
        alerts.append(
            _alert(
                severity="warning",
                kind="outbox_backlog_high",
                entity_type="outbox",
                entity_id="device_outbox",
                summary=f"Высокая очередь команд outbox: {outbox_backlog}",
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
                    summary=f"Сервис контроля '{kind}' не запущен",
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
                        summary=f"Высокая задержка PostgreSQL: {latency_ms:.1f} мс",
                        details={"latency_ms": latency_ms, "threshold_ms": slow_ms},
                    )
                )

            total_devices = await session.scalar(
                select(func.count()).select_from(Device).where(Device.deleted_at.is_(None))
            ) or 0
            stale_count = await session.scalar(
                select(func.count()).select_from(Device).where(
                    and_(
                        Device.deleted_at.is_(None),
                        Device.last_seen_at.isnot(None),
                        Device.last_seen_at < (now - timedelta(seconds=stale_sec)),
                    )
                )
            ) or 0
            unresolved_pending_filter = and_(
                ConnectionRequest.status == "pending",
                ~_active_agent_token_exists_for_connection_request(now),
                exists(
                    select(Device.device_id).where(
                        and_(
                            Device.device_id == ConnectionRequest.device_id,
                            Device.deleted_at.is_(None),
                        )
                    )
                ),
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

            connected_ids = list(state.connected_agents.keys())
            if connected_ids:
                online_count = await session.scalar(
                    select(func.count()).select_from(Device).where(
                        and_(Device.deleted_at.is_(None), Device.device_id.in_(connected_ids))
                    )
                ) or 0
            else:
                online_count = 0
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

            problem_logs = [
                _serialize_problem_log(item)
                for item in list_log_records(levels=("warning", "error", "critical"), limit=20)
            ]
            alerts.extend(_build_log_alerts(limit=8))
            alerts = [item for item in alerts if not is_alert_dismissed(str(item.get("id") or ""))]
            observer_runtime = request.app._state.get("observer_refresh_runtime")
            observer_runtime_status = (
                observer_runtime.status_snapshot()
                if observer_runtime is not None
                else {"enabled": False, "running": False, "health": {"status": "down"}}
            )

            overview = {
                "service_health": {
                    "api": "ok",
                    "ws_ui": "ok",
                    "ui_ws_connections": int(len(state.ui_connections)),
                    "agent_ws_connections": int(len(state.connected_agents)),
                    "device_dispatch": "ok" if request.app.get("outbox_sender") else "degraded",
                    "operation_watchdog": "ok" if getattr(request.app.get("operation_watchdog"), "_running", False) else "down",
                    "ticket_sla_watchdog": "ok" if getattr(request.app.get("ticket_sla_watchdog"), "_running", False) else "down",
                    "ticket_auto_close_watchdog": "ok" if getattr(request.app.get("ticket_auto_close_watchdog"), "_running", False) else "down",
                    "observer_refresh_runtime": observer_runtime_status.get("health", {}).get("status") or "unknown",
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
                "observer_health": observer_runtime_status,
                "alerts": alerts,
                "problem_logs": problem_logs,
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
                summary="Проверка PostgreSQL завершилась ошибкой",
                details={"error": str(exc)},
            )
        )
        return {
            "service_health": {
                "api": "degraded",
                "ws_ui": "unknown",
                "ui_ws_connections": int(len(state.ui_connections)),
                "agent_ws_connections": int(len(state.connected_agents)),
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
                "events": [_serialize_agent_audit_row(i) for i in items],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_agent_timeline(request: web.Request) -> web.Response:
    device_id = request.match_info["device_id"]
    now = datetime.now(timezone.utc)
    stale_sec = _threshold("TECH_DEVICE_STALE_SECONDS", 300)
    async with get_session() as session:
        device = await session.scalar(select(Device).where(Device.device_id == device_id))
        if not device:
            return web.json_response({"status": "error", "error": "Device not found"}, status=404)
        repo = AgentRuntimeAuditRepo(session)
        events = await repo.list_feed(device_id=device_id, limit=200)
        serialized_events = [_serialize_agent_audit_row(e) for e in events]
        update_events = [item for item in serialized_events if str(item.get("event_type") or "").startswith("update_")]
        auth_events = [
            item
            for item in serialized_events
            if "token" in str(item.get("event_type") or "") or str(item.get("event_type") or "").startswith("connection_request_")
        ]
        handshake_events = [
            item
            for item in serialized_events
            if "handshake" in str(item.get("event_type") or "") or item.get("event_type") in {"agent_offline"}
        ]
        last_errors = [
            item for item in serialized_events if str(item.get("severity") or "").lower() in {"warning", "error", "critical"}
        ][:10]
        recent_operations = (
            await session.execute(
                select(Operation).where(Operation.device_id == device_id).order_by(Operation.queued_at.desc()).limit(20)
            )
        ).scalars().all()
        recent_outbox = (
            await session.execute(
                select(DeviceOutbox).where(DeviceOutbox.device_id == device_id).order_by(DeviceOutbox.created_at.desc()).limit(20)
            )
        ).scalars().all()
        outbox_counts = {}
        for status in ("pending", "sent", "failed", "delivered"):
            outbox_counts[status] = int(
                await session.scalar(
                    select(func.count()).select_from(DeviceOutbox).where(
                        and_(DeviceOutbox.device_id == device_id, DeviceOutbox.status == status)
                    )
                )
                or 0
            )
        pending_consents_count = int(
            await session.scalar(
                select(func.count()).select_from(Operation).where(
                    and_(Operation.device_id == device_id, Operation.status == "waiting_consent")
                )
            )
            or 0
        )
        issue_summary: list[str] = []
        if not request.app["state"].is_agent_online(device_id):
            issue_summary.append("Агент сейчас офлайн.")
        if device.last_seen_at and device.last_seen_at < (now - timedelta(seconds=stale_sec)):
            issue_summary.append("Агент давно не выходил на связь.")
        if outbox_counts["failed"] > 0:
            issue_summary.append(f"Есть ошибки доставки команд: {outbox_counts['failed']} шт.")
        if pending_consents_count > 0:
            issue_summary.append(f"Есть команды, ожидающие подтверждения: {pending_consents_count} шт.")
        problem_logs = [
            _serialize_problem_log(item)
            for item in list_log_records(
                levels=("warning", "error", "critical"),
                limit=20,
                contains=device_id,
            )
        ]
        if not problem_logs and device.hostname:
            problem_logs = [
                _serialize_problem_log(item)
                for item in list_log_records(
                    levels=("warning", "error", "critical"),
                    limit=20,
                    contains=device.hostname,
                )
            ]
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
                    "last_seen_age_sec": _seconds_since(device.last_seen_at, now=now),
                    "last_handshake_age_sec": _seconds_since(device.last_handshake_at, now=now),
                    "stale": bool(device.last_seen_at and device.last_seen_at < (now - timedelta(seconds=stale_sec))),
                    "pending_consents_count": pending_consents_count,
                },
                "events": serialized_events,
                "auth_timeline": auth_events,
                "handshake_timeline": handshake_events,
                "update_timeline": update_events,
                "auth_summary": {"events_count": len(auth_events)},
                "update_summary": {"events_count": len(update_events)},
                "recent_operations": [_serialize_operation_row(op) for op in recent_operations],
                "outbox_summary": {
                    "counts": outbox_counts,
                    "recent": [_serialize_outbox_row(row) for row in recent_outbox],
                },
                "last_errors": last_errors,
                "problem_logs": problem_logs,
                "issue_summary": issue_summary,
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
                "events": [_serialize_user_audit_row(r) for r in rows],
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_logs(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=50, cap=200)
    raw_levels = request.query.get("levels") or "warning,error,critical"
    levels = [item.strip().lower() for item in raw_levels.split(",") if item.strip()]
    contains = request.query.get("contains")
    logs = [
        _serialize_problem_log(item)
        for item in list_log_records(levels=levels, limit=limit, contains=contains)
    ]
    return web.json_response({"status": "ok", "logs": logs})


@require_auth("admin", "support")
async def handle_tech_dismiss_item(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid JSON"}, status=400)

    item_type = str(payload.get("item_type") or "").strip().lower()
    item_id = str(payload.get("item_id") or "").strip()
    related_log_id = str(payload.get("related_log_id") or "").strip()
    if item_type not in {"log", "alert"} or not item_id:
        return web.json_response(
            {"status": "error", "error": "item_type and item_id are required"},
            status=400,
        )

    if item_type == "log":
        removed = remove_log_record(item_id)
        if not removed:
            return web.json_response({"status": "error", "error": "Log item not found"}, status=404)
        return web.json_response({"status": "ok", "item_type": item_type, "item_id": item_id})

    dismiss_alert(item_id)
    if related_log_id:
        remove_log_record(related_log_id)
    return web.json_response(
        {
            "status": "ok",
            "item_type": item_type,
            "item_id": item_id,
            "related_log_id": related_log_id or None,
        }
    )


@require_auth("admin", "support")
async def handle_tech_agent_action(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    device_id = request.match_info["device_id"]
    data = await request.json()
    action = str(data.get("action") or "").strip().lower()
    actor_role = getattr(auth_context, "actor_role", None) or "admin"

    try:
        if action == "get_status":
            response = await send_ws_command(
                state=request.app["state"],
                device_id=device_id,
                command="get_status",
                params={},
                actor_role=actor_role,
                timeout=30,
            )
        elif action == "get_history":
            params: dict[str, Any] = {"limit": _parse_query_limit(data.get("limit"), default=20, cap=200)}
            if data.get("module"):
                params["module"] = str(data["module"]).strip()
            response = await send_ws_command(
                state=request.app["state"],
                device_id=device_id,
                command="get_history",
                params=params,
                actor_role=actor_role,
                timeout=30,
            )
        elif action == "list_tasks":
            response = await send_ws_rpc_request(
                state=request.app["state"],
                device_id=device_id,
                method="list_tasks",
                params={},
                actor_role=actor_role,
                timeout=30,
            )
        elif action == "refresh_toolset":
            response = await send_ws_command(
                state=request.app["state"],
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role=actor_role,
                timeout=30,
            )
        else:
            return web.json_response(
                {"status": "error", "error": f"Unsupported tech action: {action}"},
                status=400,
            )
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc)}, status=404)
    except asyncio.TimeoutError:
        return web.json_response({"status": "error", "error": "Таймаут ожидания ответа от агента"}, status=504)

    payload = response.get("payload") if isinstance(response, dict) and "payload" in response else response
    return web.json_response({"status": "ok", "action": action, "result": payload})


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


def _trace_filters_from_request(request: web.Request) -> TraceOverlayFilters:
    return TraceOverlayFilters(
        trace_id=_compact_query_value(request.query.get("trace_id")),
        ticket_id=_compact_query_value(request.query.get("ticket_id")),
        job_id=_compact_query_value(request.query.get("job_id")),
        operation_id=_compact_query_value(request.query.get("operation_id")),
        device_id=_compact_query_value(request.query.get("device_id")),
        root_kind=_compact_query_value(request.query.get("root_kind")),
        tool_name=_compact_query_value(request.query.get("tool_name")),
        module_name=_compact_query_value(request.query.get("module_name")),
        error_signature=_compact_query_value(request.query.get("error_signature")),
        status=_compact_query_value(request.query.get("status")),
        min_duration_ms=_parse_query_int(request.query.get("min_duration_ms")),
        min_retry_count=_parse_query_int(request.query.get("min_retry_count")),
        min_timeout_rate=_parse_query_ratio(request.query.get("min_timeout_rate")),
        min_retry_rate=_parse_query_ratio(request.query.get("min_retry_rate")),
        min_slow_rate=_parse_query_ratio(request.query.get("min_slow_rate")),
        lookback_hours=_parse_query_int(request.query.get("lookback_hours")),
    )


def _compact_query_value(raw: Optional[str]) -> Optional[str]:
    value = str(raw or "").strip()
    return value or None


def _parse_query_int(raw: Optional[str]) -> Optional[int]:
    value = _compact_query_value(raw)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_query_ratio(raw: Optional[str]) -> Optional[float]:
    value = _compact_query_value(raw)
    if value is None:
        return None
    try:
        ratio = float(value)
    except (TypeError, ValueError):
        return None
    if ratio > 1:
        ratio = ratio / 100.0
    if ratio < 0:
        return None
    return min(ratio, 1.0)


def _extract_action_trace_entries(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = response.get("payload") if isinstance(response, dict) else None
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("observations"), dict):
        entries = data["observations"].get("entries")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
    observations = payload.get("observations")
    if isinstance(observations, dict):
        entries = observations.get("entries")
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
    return []


def _serialize_trace_filters(filters: TraceOverlayFilters) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_name in filters.__dataclass_fields__:
        value = getattr(filters, field_name)
        if value is not None:
            payload[field_name] = value
    return payload


@require_auth("admin")
async def handle_observer_settings_get(request: web.Request) -> web.Response:
    async with get_session() as session:
        repo = ObserverSettingsRepo(session)
        settings = await repo.get_settings()
        await session.commit()
    return web.json_response({"status": "ok", "settings": settings})


@require_auth("admin")
async def handle_observer_settings_patch(request: web.Request) -> web.Response:
    payload = await request.json()
    if not isinstance(payload, dict):
        return web.json_response({"status": "error", "error": "JSON object expected"}, status=400)
    async with get_session() as session:
        repo = ObserverSettingsRepo(session)
        settings = await repo.set_settings(payload)
        await session.commit()
    runtime = request.app._state.get("observer_refresh_runtime")
    if runtime is not None:
        await runtime.reload_settings()
    return web.json_response({"status": "ok", "settings": settings})


@require_auth("admin", "support", "auditor")
async def handle_tech_traces_runtime(request: web.Request) -> web.Response:
    runtime = request.app._state.get("observer_refresh_runtime")
    if runtime is None:
        async with get_session() as session:
            settings = await ObserverSettingsRepo(session).get_settings()
            await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "runtime": {"enabled": False, "running": False, "settings": settings, "health": {"status": "down"}},
            }
        )
    return web.json_response({"status": "ok", "runtime": runtime.status_snapshot()})


@require_auth("admin", "support", "auditor")
async def handle_tech_observer_quick(request: web.Request) -> web.Response:
    filters = _trace_filters_from_request(request)
    hot_limit = _parse_query_limit(request.query.get("hot_limit"), default=8, cap=20)
    signature_limit = _parse_query_limit(request.query.get("signature_limit"), default=6, cap=20)
    degradation_limit = _parse_query_limit(request.query.get("degradation_limit"), default=6, cap=20)
    flow_limit = _parse_query_limit(request.query.get("flow_limit"), default=6, cap=20)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        payload = await service.get_quick_diagnosis(
            filters,
            hot_limit=hot_limit,
            signature_limit=signature_limit,
            degradation_limit=degradation_limit,
            flow_limit=flow_limit,
        )
        await session.commit()
    payload["status"] = "ok"
    payload["filters"] = _serialize_trace_filters(filters)
    return web.json_response(payload)


@require_auth("admin", "support", "auditor")
async def handle_tech_traces_search(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=50, cap=200)
    filters = _trace_filters_from_request(request)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        traces = await service.search_traces(filters, limit=limit)
        await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "count": len(traces),
                "filters": _serialize_trace_filters(filters),
                "traces": traces,
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_trace_detail(request: web.Request) -> web.Response:
    trace_id = request.match_info["trace_id"]
    include_agent_actions = _parse_bool(request.query.get("include_agent_actions"))
    action_limit = _parse_query_limit(request.query.get("action_limit"), default=50, cap=200)
    action_sync_enabled = True
    action_sync_limit = action_limit

    async with get_session() as session:
        observer_settings = await ObserverSettingsRepo(session).get_settings()
        await session.commit()
    action_sync_enabled = bool(observer_settings.get("action_sync_enabled", True))
    action_sync_limit = max(1, min(int(observer_settings.get("action_sync_limit", action_limit) or action_limit), 500))
    action_limit = min(action_limit, action_sync_limit)

    async with get_session() as session:
        service = ObserverOverlayService(session)
        detail = await service.get_trace_detail(trace_id)
        if detail is None:
            await session.rollback()
            return web.json_response({"status": "error", "error": "Trace not found"}, status=404)
        await session.commit()

    agent_actions: list[dict[str, Any]] = []
    agent_actions_error: Optional[str] = None
    if include_agent_actions:
        device_id = detail["trace"].get("device_id")
        if device_id:
            try:
                operation_source_refs = {
                    str(span.get("source_ref") or "").strip()
                    for span in detail.get("spans", [])
                    if span.get("source_type") == "operation"
                }
                params = {
                    "trace_id": trace_id,
                    "ticket_id": detail["trace"].get("ticket_id"),
                    "limit": action_limit,
                }
                if len(operation_source_refs) == 1:
                    params["operation_id"] = next(iter(operation_source_refs))
                response = await send_ws_rpc_request(
                    state=request.app["state"],
                    device_id=device_id,
                    method="search_action_trace",
                    params=params,
                    actor_role="support",
                    timeout=20,
                )
                agent_actions = [redact_sensitive_payload(item) for item in _extract_action_trace_entries(response)]
                if agent_actions and action_sync_enabled:
                    async with get_session() as sync_session:
                        sync_service = ObserverOverlayService(sync_session)
                        await sync_service.sync_agent_action_spans(trace_id, agent_actions)
                        detail = await sync_service.get_trace_detail(trace_id)
                        await sync_session.commit()
            except Exception as exc:
                agent_actions_error = str(exc)

    detail["status"] = "ok"
    detail["agent_actions"] = agent_actions
    detail["agent_actions_error"] = agent_actions_error
    detail["observer_settings"] = {
        "action_sync_enabled": action_sync_enabled,
        "action_sync_limit": action_sync_limit,
    }
    return web.json_response(detail)


@require_auth("admin", "support", "auditor")
async def handle_tech_signatures_search(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=50, cap=200)
    filters = _trace_filters_from_request(request)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        signatures = await service.search_signatures(filters, limit=limit)
        await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "count": len(signatures),
                "filters": _serialize_trace_filters(filters),
                "signatures": signatures,
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_degradations_search(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=50, cap=200)
    filters = _trace_filters_from_request(request)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        items = await service.search_degradations(filters, limit=limit)
        await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "count": len(items),
                "filters": _serialize_trace_filters(filters),
                "items": items,
            }
        )


@require_auth("admin", "support", "auditor")
async def handle_tech_signature_detail(request: web.Request) -> web.Response:
    error_signature = request.match_info["error_signature"]
    limit = _parse_query_limit(request.query.get("limit"), default=100, cap=500)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        detail = await service.get_signature_detail(error_signature, limit=limit)
        if detail is None:
            await session.rollback()
            return web.json_response({"status": "error", "error": "Signature not found"}, status=404)
        await session.commit()
        detail["status"] = "ok"
        return web.json_response(detail)


@require_auth("admin", "support", "auditor")
async def handle_tech_traces_rebuild(request: web.Request) -> web.Response:
    limit = _parse_query_limit(request.query.get("limit"), default=50, cap=200)
    filters = _trace_filters_from_request(request)
    async with get_session() as session:
        service = ObserverOverlayService(session)
        projected = await service.rebuild_traces(filters, limit=limit)
        await session.commit()
        return web.json_response(
            {
                "status": "ok",
                "projected_count": len(projected),
                "trace_ids": projected,
            }
        )
