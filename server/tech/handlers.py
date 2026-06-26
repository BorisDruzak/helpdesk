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
    RegistryAsset,
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
from tech.locator import locate_tech_query
from tech.log_buffer import list_log_records, remove_log_record
from tech.snapshot import build_tech_panel_v2_snapshot
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
        "connection_request_policy_rejected": "Запрос на подключение отклонён политикой",
        "connection_request_token_delivered": "Токен подключения доставлен агенту",
        "connection_request_token_limit": "Лимит токенов подключения",
        "connection_request_approval_waiting_delivery": "Одобрение ожидает доставки токена",
        "device_fingerprint_mismatch": "Отпечаток устройства не совпал",
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
    env_uuid_duplicate_groups: int = 0,
    devices_without_location: int = 0,
    watchdog_states: dict[str, bool] | None = None,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    watchdog_states = watchdog_states or {}
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
    if env_uuid_duplicate_groups > 0:
        alerts.append(
            _alert(
                severity="warning",
                kind="inventory_env_uuid_duplicates",
                entity_type="inventory",
                entity_id="devices",
                summary=f"Найдены env_uuid-дубли hostname: {env_uuid_duplicate_groups} групп.",
                details={"duplicate_groups": env_uuid_duplicate_groups},
                link="/app/admin/inventory",
            )
        )
    if devices_without_location > 0:
        alerts.append(
            _alert(
                severity="warning",
                kind="inventory_devices_without_location",
                entity_type="inventory",
                entity_id="devices",
                summary=f"Устройства без кабинета/локации: {devices_without_location} шт.",
                details={"devices_without_location": devices_without_location},
                link="/app/admin/registry",
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

            active_device_rows = (
                await session.execute(
                    select(Device.hostname, Device.device_metadata).where(Device.deleted_at.is_(None))
                )
            ).all()
            env_uuid_by_hostname: dict[str, int] = {}
            for hostname_value, metadata_value in active_device_rows:
                metadata = metadata_value if isinstance(metadata_value, dict) else {}
                if str(metadata.get("machine_id_source") or "").strip().lower() != "env_uuid":
                    continue
                hostname_key = str(hostname_value or metadata.get("hostname") or "").strip().lower()
                if not hostname_key:
                    continue
                env_uuid_by_hostname[hostname_key] = env_uuid_by_hostname.get(hostname_key, 0) + 1
            env_uuid_duplicate_groups = sum(1 for count in env_uuid_by_hostname.values() if count > 1)
            devices_without_location = await session.scalar(
                select(func.count()).select_from(RegistryAsset).where(
                    and_(
                        RegistryAsset.asset_type == "pc",
                        RegistryAsset.status == "active",
                        RegistryAsset.location_id.is_(None),
                    )
                )
            ) or 0

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
                    env_uuid_duplicate_groups=int(env_uuid_duplicate_groups),
                    devices_without_location=int(devices_without_location),
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
                "inventory_quality": {
                    "env_uuid_duplicate_groups": int(env_uuid_duplicate_groups),
                    "devices_without_location": int(devices_without_location),
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
async def handle_tech_snapshot(request: web.Request) -> web.Response:
    overview = await _build_overview(request)
    return web.json_response(await build_tech_panel_v2_snapshot(request, overview))


@require_auth("admin", "support", "auditor")
async def handle_tech_locate(request: web.Request) -> web.Response:
    query = str(request.query.get("q") or "").strip()
    if not query:
        return web.json_response(
            {"status": "error", "error": "q is required", "error_code": "VALIDATION_ERROR"},
            status=400,
        )
    limit = _parse_query_limit(request.query.get("limit"), default=10, cap=25)
    include_logs = request.query.get("include_logs", "true").lower() not in {"0", "false", "no", "off"}
    include_traces = request.query.get("include_traces", "true").lower() not in {"0", "false", "no", "off"}
    try:
        return web.json_response(
            await locate_tech_query(
                request,
                query=query,
                limit=limit,
                include_logs=include_logs,
                include_traces=include_traces,
            )
        )
    except ValueError as exc:
        return web.json_response(
            {"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"},
            status=400,
        )


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
                if after == "in_progress" and not milestones["in_progress"]:
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
        if ticket.status == "in_progress" and not milestones["in_progress"]:
            status_event = next(
                (
                    ev
                    for ev in events
                    if ev.event_type in ("ticket_status_changed", "status_changed")
                    and _ticket_status_from_payload(ev.payload if isinstance(ev.payload, dict) else {}) == "in_progress"
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
        query=_compact_query_value(request.query.get("q") or request.query.get("query")),
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
        playbook_run_id=_parse_query_int(request.query.get("playbook_run_id")),
        step_run_id=_parse_query_int(request.query.get("step_run_id")),
        route=_compact_query_value(request.query.get("route")),
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


_ACTION_TRACE_TOP_LEVEL_FIELDS = (
    "ts",
    "source",
    "action",
    "category",
    "stage",
    "status",
    "summary",
    "action_id",
    "parent_action_id",
    "trace_id",
    "ticket_id",
    "operation_id",
    "message_id",
    "tool_name",
    "request_id",
)
_ACTION_TRACE_DETAIL_PRIORITY_KEYS = (
    "module_name",
    "method_name",
    "tool_name",
    "step",
    "status",
    "duration_ms",
    "elapsed_ms",
    "exit_code",
    "error",
    "exception_type",
)


def _compact_agent_action_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if len(text) <= 240:
        return text
    return f"{text[:237]}..."


def _compact_agent_action_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            "_type": "object",
            "_keys": [str(key) for key in list(value.keys())[:12]],
            "_size": len(value),
        }
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        return {
            "_type": "array",
            "_size": len(items),
            "_sample": [_compact_agent_action_scalar(item) for item in items[:3] if not isinstance(item, (dict, list, tuple, set))],
        }
    return _compact_agent_action_scalar(value)


def _compact_agent_action_details(details: Any) -> dict[str, Any]:
    if not isinstance(details, dict):
        return {}
    compact: dict[str, Any] = {}
    for key in _ACTION_TRACE_DETAIL_PRIORITY_KEYS:
        if key in details:
            compact[key] = _compact_agent_action_value(details.get(key))
    for key, value in details.items():
        if len(compact) >= 12:
            break
        key_text = str(key)
        if key_text in compact:
            continue
        compact[key_text] = _compact_agent_action_value(value)
    if len(details) > len(compact):
        compact["_omitted_keys"] = max(0, len(details) - len(compact))
    return compact


def _compact_agent_action_entry(entry: dict[str, Any]) -> dict[str, Any]:
    compact = {
        field: _compact_agent_action_scalar(entry.get(field))
        for field in _ACTION_TRACE_TOP_LEVEL_FIELDS
        if entry.get(field) is not None
    }
    compact["details"] = _compact_agent_action_details(entry.get("details"))
    return redact_sensitive_payload(compact)


def _serialize_trace_filters(filters: TraceOverlayFilters) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field_name in filters.__dataclass_fields__:
        value = getattr(filters, field_name)
        if value is not None:
            payload[field_name] = value
    return payload


def _observer_trace_filter_has_values(filters: TraceOverlayFilters) -> bool:
    return any(getattr(filters, field_name) is not None for field_name in filters.__dataclass_fields__)


def _serialize_device_context(device: Optional[Device]) -> Optional[dict[str, Any]]:
    if device is None:
        return None
    metadata = redact_sensitive_payload(device.device_metadata or {})
    return {
        "device_id": device.device_id,
        "hostname": device.hostname,
        "os": device.os,
        "agent_version": device.agent_version,
        "protocol_version": device.protocol_version,
        "tools_version": device.tools_version,
        "current_toolset_hash": device.current_toolset_hash,
        "first_seen_at": _iso(device.first_seen_at),
        "last_seen_at": _iso(device.last_seen_at),
        "last_handshake_at": _iso(device.last_handshake_at),
        "deleted_at": _iso(device.deleted_at),
        "metadata": metadata,
    }


def _serialize_ticket_context(ticket: Optional[Ticket]) -> Optional[dict[str, Any]]:
    if ticket is None:
        return None
    return {
        "ticket_id": ticket.ticket_id,
        "ticket_code": ticket.ticket_code,
        "device_id": ticket.device_id,
        "title": ticket.title,
        "status": ticket.status,
        "priority": ticket.priority,
        "requester_id": ticket.requester_id,
        "assignee_id": ticket.assignee_id,
        "queue_id": ticket.queue_id,
        "observer_root_trace_id": ticket.observer_root_trace_id,
        "created_at": _iso(ticket.created_at),
        "updated_at": _iso(ticket.updated_at),
        "resolved_at": _iso(ticket.resolved_at),
        "closed_at": _iso(ticket.closed_at),
    }


def _serialize_agent_audit_item(item: AgentRuntimeAudit) -> dict[str, Any]:
    return {
        "id": item.id,
        "device_id": item.device_id,
        "event_type": item.event_type,
        "event_label": _label_audit_event(item.event_type),
        "severity": item.severity,
        "severity_label": _severity_badge(item.severity)["label"],
        "source": item.source,
        "operation_id": item.operation_id,
        "ticket_id": item.ticket_id,
        "actor_id": item.actor_id,
        "actor_role": item.actor_role,
        "details_json": redact_sensitive_payload(item.details_json or {}),
        "created_at": _iso(item.created_at),
    }


async def _load_agent_actions_for_trace(
    *,
    request: web.Request,
    trace_id: str,
    detail: dict[str, Any],
    action_limit: int,
) -> tuple[list[dict[str, Any]], Optional[str]]:
    device_id = detail.get("trace", {}).get("device_id")
    if not device_id:
        return [], None
    try:
        operation_source_refs = {
            str(span.get("source_ref") or "").strip()
            for span in detail.get("spans", [])
            if span.get("source_type") == "operation"
        }
        params = {
            "trace_id": trace_id,
            "ticket_id": detail.get("trace", {}).get("ticket_id"),
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
        return [_compact_agent_action_entry(item) for item in _extract_action_trace_entries(response)], None
    except Exception as exc:
        return [], str(exc)


async def _sync_agent_action_spans_with_timeout(
    *,
    trace_id: str,
    agent_actions: list[dict[str, Any]],
    timeout_sec: float = 5.0,
) -> Optional[dict[str, Any]]:
    async def _sync() -> Optional[dict[str, Any]]:
        async with get_session() as sync_session:
            sync_service = ObserverOverlayService(sync_session)
            await sync_service.sync_agent_action_spans(trace_id, agent_actions)
            detail = await sync_service.get_trace_detail(trace_id)
            await sync_session.commit()
            return detail

    return await asyncio.wait_for(_sync(), timeout=max(0.5, float(timeout_sec)))


def _bundle_next_checks(
    *,
    primary_trace: Optional[dict[str, Any]],
    error_occurrences: list[dict[str, Any]],
    agent_actions_error: Optional[str],
) -> list[str]:
    checks: list[str] = []
    if primary_trace:
        status = str(primary_trace.get("status") or "").lower()
        if status in {"running", "queued", "accepted"}:
            checks.append("Check operation delivery state and agent connectivity for this device.")
        if int(primary_trace.get("error_count") or 0) > 0 or status in {"failed", "error", "timed_out"}:
            checks.append("Open error_occurrences and matching signatures before retrying the flow.")
    if error_occurrences:
        checks.append("Compare this trace with signatures/degradations to detect repeated failures.")
    if agent_actions_error:
        checks.append("Agent action trace could not be loaded; verify that the agent is online and RPC works.")
    if not checks:
        checks.append("Review spans and recent agent audit events for the next narrow failure point.")
    return checks


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
async def handle_tech_observer_search(request: web.Request) -> web.Response:
    query = _compact_query_value(request.query.get("q") or request.query.get("query"))
    if not query:
        return web.json_response({"status": "error", "error": "q is required"}, status=400)
    limit = _parse_query_limit(request.query.get("limit"), default=20, cap=100)
    base_filters = _trace_filters_from_request(request)
    trace_candidates: dict[str, dict[str, Any]] = {}
    signature_candidates: dict[str, dict[str, Any]] = {}
    async with get_session() as session:
        service = ObserverOverlayService(session)
        trace_filter_variants = [
            base_filters,
            TraceOverlayFilters(operation_id=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(ticket_id=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(device_id=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(trace_id=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(tool_name=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(module_name=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(error_signature=query, lookback_hours=base_filters.lookback_hours),
        ]
        for filters in trace_filter_variants:
            for item in await service.search_traces(filters, limit=limit):
                trace_id = str(item.get("trace_id") or "").strip()
                if trace_id and trace_id not in trace_candidates:
                    trace_candidates[trace_id] = item
            if len(trace_candidates) >= limit:
                break
        signature_filter_variants = [
            TraceOverlayFilters(error_signature=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(tool_name=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(module_name=query, lookback_hours=base_filters.lookback_hours),
            TraceOverlayFilters(query=query, lookback_hours=base_filters.lookback_hours),
        ]
        for filters in signature_filter_variants:
            for item in await service.search_signatures(filters, limit=limit):
                signature_id = str(item.get("error_signature") or "").strip()
                if signature_id and signature_id not in signature_candidates:
                    signature_candidates[signature_id] = item
        await session.commit()

    traces = list(trace_candidates.values())[:limit]
    signatures = list(signature_candidates.values())[:limit]
    return web.json_response(
        {
            "status": "ok",
            "query": query,
            "filters": _serialize_trace_filters(base_filters),
            "summary": {
                "trace_count": len(traces),
                "signature_count": len(signatures),
            },
            "traces": traces,
            "signatures": signatures,
            "recommended_next_checks": [
                "Open the most recent matching trace detail.",
                "If several traces share one signature, inspect degradations before rerun.",
            ],
        }
    )


@require_auth("admin", "support", "auditor")
async def handle_tech_diagnostics_bundle(request: web.Request) -> web.Response:
    filters = _trace_filters_from_request(request)
    if not _observer_trace_filter_has_values(filters):
        return web.json_response(
            {"status": "error", "error": "Provide trace_id, ticket_id, operation_id, device_id or q."},
            status=400,
        )
    include_agent_actions = _parse_bool(request.query.get("include_agent_actions"))
    action_limit = _parse_query_limit(request.query.get("action_limit"), default=80, cap=200)
    trace_limit = _parse_query_limit(request.query.get("trace_limit"), default=20, cap=100)
    primary_detail: Optional[dict[str, Any]] = None
    related_traces: list[dict[str, Any]] = []
    device_payload: Optional[dict[str, Any]] = None
    ticket_payload: Optional[dict[str, Any]] = None
    signatures: list[dict[str, Any]] = []
    degradations: list[dict[str, Any]] = []
    agent_audit: list[dict[str, Any]] = []
    primary_trace: Optional[dict[str, Any]] = None

    async with get_session() as session:
        service = ObserverOverlayService(session)
        related_traces = await service.search_traces(filters, limit=trace_limit)
        primary_trace_id = filters.trace_id or (related_traces[0]["trace_id"] if related_traces else None)
        if primary_trace_id:
            primary_detail = await service.get_trace_detail(primary_trace_id)

        primary_trace = primary_detail.get("trace") if primary_detail else (related_traces[0] if related_traces else None)
        primary_trace_context = primary_trace or {}
        if primary_trace and not related_traces:
            related_traces = [primary_trace]
        device_id = primary_trace_context.get("device_id") or filters.device_id
        ticket_id = primary_trace_context.get("ticket_id") or filters.ticket_id
        operation_id = primary_trace_context.get("operation_id") or filters.operation_id
        device_payload = _serialize_device_context(await session.get(Device, device_id)) if device_id else None
        ticket_payload = _serialize_ticket_context(await session.get(Ticket, ticket_id)) if ticket_id else None

        signature_filters = TraceOverlayFilters(
            trace_id=primary_trace_context.get("trace_id") or filters.trace_id,
            ticket_id=ticket_id,
            device_id=device_id,
            operation_id=operation_id,
            lookback_hours=filters.lookback_hours,
        )
        signatures = await service.search_signatures(signature_filters, limit=10)
        degradations = await service.search_degradations(
            TraceOverlayFilters(
                ticket_id=ticket_id,
                device_id=device_id,
                operation_id=operation_id,
                tool_name=primary_trace_context.get("tool_name") or filters.tool_name,
                lookback_hours=filters.lookback_hours or 24,
            ),
            limit=10,
        )

        audit_stmt = select(AgentRuntimeAudit)
        audit_conditions = []
        if device_id:
            audit_conditions.append(AgentRuntimeAudit.device_id == device_id)
        if ticket_id:
            audit_conditions.append(AgentRuntimeAudit.ticket_id == ticket_id)
        if operation_id:
            audit_conditions.append(AgentRuntimeAudit.operation_id == operation_id)
        if audit_conditions:
            audit_stmt = audit_stmt.where(or_(*audit_conditions))
        audit_rows = (
            await session.execute(audit_stmt.order_by(AgentRuntimeAudit.created_at.desc()).limit(30))
        ).scalars().all()
        agent_audit = [_serialize_agent_audit_item(item) for item in audit_rows]
        await session.commit()

    agent_actions: list[dict[str, Any]] = []
    agent_actions_error: Optional[str] = None
    if include_agent_actions and primary_detail:
        agent_actions, agent_actions_error = await _load_agent_actions_for_trace(
            request=request,
            trace_id=primary_detail["trace"]["trace_id"],
            detail=primary_detail,
            action_limit=action_limit,
        )

    log_filter = (
        filters.query
        or filters.operation_id
        or filters.ticket_id
        or filters.device_id
        or filters.trace_id
        or filters.error_signature
    )
    recent_logs = [_serialize_problem_log(item) for item in list_log_records(levels=["error", "warning"], limit=30, contains=log_filter)]
    if not recent_logs:
        recent_logs = [_serialize_problem_log(item) for item in list_log_records(levels=["error", "warning"], limit=15)]

    error_occurrences = primary_detail.get("error_occurrences", []) if primary_detail else []
    trace_id = primary_trace.get("trace_id") if primary_trace else None
    return web.json_response(
        {
            "status": "ok",
            "filters": _serialize_trace_filters(filters),
            "summary": {
                "primary_trace_id": trace_id,
                "related_trace_count": len(related_traces),
                "span_count": len(primary_detail.get("spans", [])) if primary_detail else 0,
                "error_count": len(error_occurrences),
                "agent_action_count": len(agent_actions),
                "agent_audit_count": len(agent_audit),
                "recent_log_count": len(recent_logs),
            },
            "runtime": request.app._state.get("observer_refresh_runtime").status_snapshot()
            if request.app._state.get("observer_refresh_runtime") is not None
            else {"enabled": False, "running": False, "health": {"status": "down"}},
            "device": device_payload,
            "ticket": ticket_payload,
            "primary_trace": primary_trace,
            "related_traces": related_traces,
            "spans": primary_detail.get("spans", []) if primary_detail else [],
            "span_links": primary_detail.get("span_links", []) if primary_detail else [],
            "error_occurrences": error_occurrences,
            "agent_actions": agent_actions,
            "agent_actions_error": agent_actions_error,
            "signatures": signatures,
            "degradations": degradations,
            "recent_logs": recent_logs,
            "agent_audit": agent_audit,
            "links": {
                "trace_detail": f"/api/admin/tech/traces/{trace_id}" if trace_id else None,
                "traces": "/api/admin/tech/traces",
                "observer_search": "/api/admin/tech/observer/search",
                "ticket_observer": f"/api/tickets/{primary_trace.get('ticket_id')}/observer"
                if primary_trace and primary_trace.get("ticket_id")
                else None,
            },
            "recommended_next_checks": _bundle_next_checks(
                primary_trace=primary_trace,
                error_occurrences=error_occurrences,
                agent_actions_error=agent_actions_error,
            ),
        }
    )


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
    sync_agent_actions = _parse_bool(request.query.get("sync_agent_actions"))
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
                agent_actions = [_compact_agent_action_entry(item) for item in _extract_action_trace_entries(response)]
                if agent_actions and action_sync_enabled and sync_agent_actions:
                    synced_detail = await _sync_agent_action_spans_with_timeout(
                        trace_id=trace_id,
                        agent_actions=agent_actions,
                    )
                    if synced_detail is not None:
                        detail = synced_detail
                elif agent_actions and action_sync_enabled:
                    agent_actions_error = "Agent actions loaded without span sync; pass sync_agent_actions=1 to materialize them."
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
