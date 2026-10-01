"""Read-only Tech Panel v2 snapshot/readiness read model."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from aiohttp import web
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

import config
from app.db import get_session
from app.db.models import (
    AgentRuntimeAudit,
    Device,
    Operation,
    Ticket,
)
from app.repos.observer_integrity_repo import ObserverIntegrityRepo
from domain_ports import DomainPortContainer
from domain_ports.endpoint import EndpointDeviceProjection, EndpointDeviceRef
import auth.middleware as auth_middleware
from config import OPERATION_ACCEPTED_TIMEOUT, OPERATION_DELIVERY_TIMEOUT, OPERATION_EXECUTION_TIMEOUT

Status = str

SENSITIVE_KEY_RE = re.compile(r"(password|passwd|token|secret|key|database_url|dsn|credential)", re.IGNORECASE)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool_config(name: str, default: bool = False) -> bool:
    return bool(getattr(config, name, default))


def _str_config(name: str, default: str = "") -> str:
    return str(getattr(config, name, default) or "").strip()


def collect_config_values() -> dict[str, Any]:
    return {
        "APP_ENV": _str_config("APP_ENV", "dev"),
        "ENABLE_DB_PERSISTENCE": _bool_config("ENABLE_DB_PERSISTENCE", True),
        "PILOT_STAND_MODE": _bool_config("PILOT_STAND_MODE", False),
        "REQUIRE_HTTPS": _bool_config("REQUIRE_HTTPS", False),
        "REQUIRE_WSS": _bool_config("REQUIRE_WSS", False),
        "AUTH_ALLOW_QUERY_TOKEN": _bool_config("AUTH_ALLOW_QUERY_TOKEN", False),
        "AUTH_UI_DB_USERS_ENABLED": _bool_config("AUTH_UI_DB_USERS_ENABLED", True),
        "AUTH_UI_CONFIG_FALLBACK_ENABLED": _bool_config("AUTH_UI_CONFIG_FALLBACK_ENABLED", False),
        "WEB_SESSION_COOKIE_SECURE": _bool_config("WEB_SESSION_COOKIE_SECURE", True),
        "WEB_SESSION_COOKIE_HTTPONLY": _bool_config("WEB_SESSION_COOKIE_HTTPONLY", True),
        "WEB_SESSION_COOKIE_SAMESITE": _str_config("WEB_SESSION_COOKIE_SAMESITE", "Lax"),
        "TECH_BACKUP_STATUS_PATH": _str_config("TECH_BACKUP_STATUS_PATH"),
        "TECH_RESTORE_DRILL_STATUS_PATH": _str_config("TECH_RESTORE_DRILL_STATUS_PATH"),
        "TECH_RELEASE_STATUS_PATH": _str_config("TECH_RELEASE_STATUS_PATH"),
        "TECH_BUSINESS_SMOKE_STATUS_PATH": _str_config("TECH_BUSINESS_SMOKE_STATUS_PATH"),
        "REQUIRE_BACKUP_RESTORE_EVIDENCE": _bool_config("REQUIRE_BACKUP_RESTORE_EVIDENCE", False),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _status_from_bool(ok: bool, *, blocked: bool = False) -> Status:
    if ok:
        return "ok"
    return "blocked" if blocked else "warning"


def _gate(
    key: str,
    title: str,
    status: Status,
    severity: str,
    description: str,
    *,
    evidence: str | None = None,
    action_label: str | None = None,
    action_href: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "status": status,
        "severity": severity,
        "description": description,
        "evidence": evidence,
        "action_label": action_label,
        "action_href": action_href,
    }


def aggregate_readiness(gates: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = [item for item in gates if item.get("status") == "blocked"]
    warnings = [item for item in gates if item.get("status") in {"warning", "unknown"}]
    if blockers:
        status = "blocked"
    elif warnings:
        status = "degraded"
    else:
        status = "ready"
    ok_count = sum(1 for item in gates if item.get("status") == "ok")
    score = round((ok_count / len(gates)) * 100) if gates else None
    return {"status": status, "score": score, "blockers": blockers, "warnings": warnings, "gates": gates}


def _pilot_block_or_warn(config_values: dict[str, Any]) -> Status:
    app_env = str(config_values.get("APP_ENV") or "").strip().lower()
    strict_profile = app_env in {"pilot", "prod"} or bool(config_values.get("PILOT_STAND_MODE"))
    return "blocked" if strict_profile else "warning"


def build_readiness_gates(
    *,
    config_values: dict[str, Any],
    database: dict[str, Any],
    security: dict[str, Any],
    runtime: dict[str, Any],
    agents: dict[str, Any],
    smoke: dict[str, Any],
) -> list[dict[str, Any]]:
    pilot_status = _pilot_block_or_warn(config_values)
    gates: list[dict[str, Any]] = []

    persistence_enabled = bool(config_values.get("ENABLE_DB_PERSISTENCE"))
    gates.append(
        _gate(
            "db_persistence_enabled",
            "DB persistence включён",
            "ok" if persistence_enabled else "blocked",
            "critical" if not persistence_enabled else "info",
            "Пилотный стенд должен работать с PostgreSQL persistence, а не с dev-like режимом.",
            evidence=f"ENABLE_DB_PERSISTENCE={str(persistence_enabled).lower()}",
        )
    )

    postgres_reachable = bool(database.get("reachable"))
    gates.append(
        _gate(
            "postgres_reachable",
            "PostgreSQL доступен",
            "ok" if postgres_reachable else "blocked",
            "critical" if not postgres_reachable else "info",
            "Snapshot делает lightweight health check через существующий overview; Traceback наружу не отдаётся.",
            evidence=f"reachable={str(postgres_reachable).lower()}",
        )
    )

    fallback_enabled = bool(config_values.get("AUTH_UI_CONFIG_FALLBACK_ENABLED"))
    gates.append(
        _gate(
            "auth_no_dev_fallback",
            "Auth без config fallback",
            "ok" if not fallback_enabled else pilot_status,
            "critical" if fallback_enabled and pilot_status == "blocked" else ("warning" if fallback_enabled else "info"),
            "Для pilot-like режима UI auth не должен деградировать в config/in-memory fallback.",
            evidence=f"AUTH_UI_CONFIG_FALLBACK_ENABLED={str(fallback_enabled).lower()}",
        )
    )

    query_token_allowed = bool(config_values.get("AUTH_ALLOW_QUERY_TOKEN"))
    gates.append(
        _gate(
            "query_token_disabled",
            "Query-token auth запрещён",
            "ok" if not query_token_allowed else pilot_status,
            "critical" if query_token_allowed and pilot_status == "blocked" else ("warning" if query_token_allowed else "info"),
            "Token через query string небезопасен для pilot-like стенда.",
            evidence=f"AUTH_ALLOW_QUERY_TOKEN={str(query_token_allowed).lower()}",
        )
    )

    https = bool(config_values.get("REQUIRE_HTTPS"))
    wss = bool(config_values.get("REQUIRE_WSS"))
    gates.append(
        _gate(
            "https_wss_required",
            "HTTPS/WSS policy включена",
            "ok" if https and wss else pilot_status,
            "critical" if pilot_status == "blocked" and not (https and wss) else ("warning" if not (https and wss) else "info"),
            "Панель не угадывает TLS по текущему request без доверенного proxy config; gate основан на явных policy flags.",
            evidence=f"REQUIRE_HTTPS={str(https).lower()}, REQUIRE_WSS={str(wss).lower()}",
        )
    )

    cookie_secure = bool(config_values.get("WEB_SESSION_COOKIE_SECURE"))
    cookie_httponly = bool(config_values.get("WEB_SESSION_COOKIE_HTTPONLY", True))
    samesite = str(config_values.get("WEB_SESSION_COOKIE_SAMESITE") or "").strip().lower()
    cookie_ok = cookie_secure and cookie_httponly and samesite in {"strict", "lax", "none"}
    gates.append(
        _gate(
            "session_cookie_flags",
            "Session cookie flags заданы",
            "ok" if cookie_ok else pilot_status,
            "critical" if pilot_status == "blocked" and not cookie_ok else ("warning" if not cookie_ok else "info"),
            "Для pilot-like web-session cookie должны быть явно видны Secure, HttpOnly и SameSite.",
            evidence=f"Secure={cookie_secure}, HttpOnly={cookie_httponly}, SameSite={samesite or 'unknown'}",
        )
    )

    migrations_status = str(database.get("migrations_status") or "unknown").lower()
    gates.append(
        _gate(
            "migrations_current",
            "Alembic current == head",
            migrations_status if migrations_status in {"ok", "warning", "blocked", "unknown"} else "unknown",
            "critical" if migrations_status == "blocked" else ("warning" if migrations_status != "ok" else "info"),
            "В web request не запускаются alembic shell-команды; используется только безопасный marker/status источник.",
            evidence=f"current={database.get('alembic_current') or 'unknown'}, head={database.get('alembic_head') or 'unknown'}",
        )
    )

    restore = database.get("last_restore_drill") if isinstance(database.get("last_restore_drill"), dict) else None
    restore_required = bool(config_values.get("REQUIRE_BACKUP_RESTORE_EVIDENCE"))
    restore_ok = str((restore or {}).get("status") or "").lower() == "success"
    restore_status = "ok" if restore_ok or not restore_required else pilot_status
    gates.append(
        _gate(
            "backup_restore_drill",
            "Restore drill подтверждён",
            restore_status,
            "critical" if restore_status == "blocked" else ("warning" if restore_required and not restore_ok else "info"),
            "Панель читает marker restore drill; restore из браузера не запускается.",
            evidence=f"required={str(restore_required).lower()}, status={str((restore or {}).get('status') or 'missing')}",
        )
    )

    business = smoke.get("last_business_smoke") if isinstance(smoke.get("last_business_smoke"), dict) else None
    business_status_raw = str((business or {}).get("status") or smoke.get("status") or "unknown").lower()
    business_ok = business_status_raw in {"success", "ok", "passed"}
    gates.append(
        _gate(
            "business_smoke",
            "Business smoke пройден",
            "ok" if business_ok else ("blocked" if business_status_raw in {"failed", "error", "blocked"} else pilot_status),
            "critical" if business_status_raw in {"failed", "error", "blocked"} or pilot_status == "blocked" else "warning",
            "Последний business acceptance читается из marker-файла; отсутствие marker-а считается gap.",
            evidence=f"status={business_status_raw}",
        )
    )
    endpoint = next((item for item in runtime.get("services", []) if item.get("key") == "endpoint_dependency"), None)
    if endpoint is not None:
        gates.append(_gate("endpoint_dependency", "Зависимость Endpoint", "ok" if endpoint.get("status") == "ok" else "warning",
            "warning", "Состояние Endpoint не определяет liveness основного Helpdesk.", evidence=endpoint.get("details")))
    return gates


def build_database_snapshot_from_overview(overview: dict[str, Any]) -> dict[str, Any]:
    health = overview.get("postgres_health") if isinstance(overview.get("postgres_health"), dict) else {}
    database = {
        "persistence_enabled": _bool_config("ENABLE_DB_PERSISTENCE", True),
        "reachable": bool(health.get("reachable")),
        "latency_ms": health.get("latency_ms") if isinstance(health.get("latency_ms"), (int, float)) else None,
        "database": health.get("database") if isinstance(health.get("database"), str) else None,
        "pool_status": health.get("pool_status") if isinstance(health.get("pool_status"), str) else None,
        "alembic_current": None,
        "alembic_head": None,
        "migrations_status": "unknown",
        "last_backup": None,
        "last_restore_drill": None,
    }
    if not database["reachable"]:
        database["migrations_status"] = "blocked" if database["persistence_enabled"] else "unknown"
    return database


def _read_marker(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        marker_path = Path(path).expanduser()
        if not marker_path.exists() or not marker_path.is_file():
            return None
        payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _safe_marker_value(payload: dict[str, Any] | None, key: str) -> Any:
    if not payload or SENSITIVE_KEY_RE.search(key):
        return None
    value = payload.get(key)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return None


def _marker_subset(payload: dict[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if not payload:
        return None
    result = {key: _safe_marker_value(payload, key) for key in keys}
    return {key: value for key, value in result.items() if value is not None}


def build_release_snapshot(config_values: dict[str, Any] | None = None) -> dict[str, Any]:
    values = config_values or collect_config_values()
    payload = _read_marker(str(values.get("TECH_RELEASE_STATUS_PATH") or ""))
    safe = _marker_subset(
        payload,
        ("branch", "commit", "deployed_at", "webapp_bundle_commit", "gate", "dirty", "remote_profile", "alembic_current", "alembic_head"),
    ) or {}
    gate = str(safe.get("gate") or "unknown").lower()
    if gate not in {"full", "quick", "bypassed", "unknown"}:
        gate = "unknown"
    return {
        "branch": safe.get("branch"),
        "commit": safe.get("commit"),
        "deployed_at": safe.get("deployed_at"),
        "webapp_bundle_commit": safe.get("webapp_bundle_commit"),
        "gate": gate,
        "dirty": safe.get("dirty") if isinstance(safe.get("dirty"), bool) else None,
        "remote_profile": safe.get("remote_profile"),
        "alembic_current": safe.get("alembic_current"),
        "alembic_head": safe.get("alembic_head"),
    }


def build_backup_status(config_values: dict[str, Any] | None = None) -> dict[str, Any] | None:
    values = config_values or collect_config_values()
    return _marker_subset(_read_marker(str(values.get("TECH_BACKUP_STATUS_PATH") or "")), ("status", "finished_at", "target", "duration_seconds", "artifact"))


def build_restore_drill_status(config_values: dict[str, Any] | None = None) -> dict[str, Any] | None:
    values = config_values or collect_config_values()
    return _marker_subset(
        _read_marker(str(values.get("TECH_RESTORE_DRILL_STATUS_PATH") or "")),
        ("status", "finished_at", "target", "duration_seconds", "artifact"),
    )


def build_smoke_snapshot(config_values: dict[str, Any] | None = None) -> dict[str, Any]:
    values = config_values or collect_config_values()
    business = _marker_subset(
        _read_marker(str(values.get("TECH_BUSINESS_SMOKE_STATUS_PATH") or "")),
        ("status", "started_at", "finished_at", "steps", "artifact"),
    )
    status_raw = str((business or {}).get("status") or "unknown").lower()
    if status_raw in {"success", "ok", "passed"}:
        status = "ok"
    elif status_raw in {"failed", "error", "blocked"}:
        status = "blocked"
    else:
        status = "unknown"
    return {"last_health_smoke": None, "last_business_smoke": business, "status": status}


def _runtime_state_name(value: bool | None) -> str:
    if value is True:
        return "running"
    if value is False:
        return "down"
    return "unknown"


def build_runtime_snapshot(request: web.Request, overview: dict[str, Any], config_values: dict[str, Any]) -> dict[str, Any]:
    service_health = overview.get("service_health") if isinstance(overview.get("service_health"), dict) else {}
    def service(key: str, title: str, status: str | None, details: str | None = None) -> dict[str, Any]:
        mapped = str(status or "unknown").lower()
        if mapped in {"ok", "running", "healthy", "success"}:
            normalized = "ok"
        elif mapped in {"down", "error", "failed"}:
            normalized = "down"
        elif mapped in {"degraded", "warning", "enabled_not_running"}:
            normalized = "degraded"
        else:
            normalized = "unknown"
        return {"key": key, "title": title, "status": normalized, "details": details, "last_seen_at": None}

    schedulers = {
        "operation_watchdog": _runtime_state_name(bool(getattr(request.app.get("operation_watchdog"), "_running", False))),
        "ticket_sla_watchdog": _runtime_state_name(bool(getattr(request.app.get("ticket_sla_watchdog"), "_running", False))),
        "ticket_auto_close_watchdog": _runtime_state_name(bool(getattr(request.app.get("ticket_auto_close_watchdog"), "_running", False))),
        "observer_refresh_runtime": str(service_health.get("observer_refresh_runtime") or "unknown"),
    }
    return {
        "services": [
            service("api", "API", str(service_health.get("api") or "unknown")),
            service("ws_ui", "UI WebSocket", str(service_health.get("ws_ui") or "unknown")),
            service("operation_watchdog", "Operation watchdog", schedulers["operation_watchdog"]),
            service("ticket_sla_watchdog", "Ticket SLA watchdog", schedulers["ticket_sla_watchdog"]),
            service("ticket_auto_close_watchdog", "Ticket auto-close watchdog", schedulers["ticket_auto_close_watchdog"]),
            service("observer_refresh_runtime", "Observer refresh runtime", schedulers["observer_refresh_runtime"]),
        ],
        "web_sockets": {
            "ui_connections": _safe_int(service_health.get("ui_ws_connections")),
        },
        "schedulers": schedulers,
        "scheduler_details": {},
    }


async def build_endpoint_dependency_snapshot(*, database_reachable: bool, endpoint_port: Any = None) -> dict[str, Any]:
    """Read one saved device through the typed adapter, never treat config as live health."""
    signal = {"key": "endpoint_dependency", "title": "Зависимость Endpoint", "status": "unknown",
              "details": "Доступность не проверена: PostgreSQL недоступен.", "last_seen_at": None}
    if not database_reachable:
        return signal
    try:
        port = endpoint_port if endpoint_port is not None else DomainPortContainer.from_config().endpoint
        availability = await asyncio.wait_for(port.availability(), timeout=2.0)
        if availability.status != "available":
            signal.update(status="degraded", details="Адаптер Endpoint не готов; основной Helpdesk работает отдельно.")
            return signal
        async with get_session() as session:
            device_ref = await session.scalar(select(Ticket.endpoint_device_ref)
                .where(Ticket.endpoint_device_ref.is_not(None))
                .order_by(Ticket.updated_at.desc(), Ticket.ticket_id.desc()).limit(1))
        if not device_ref:
            signal["details"] = "Доступность не проверена: нет сохранённой привязки устройства."
            return signal
        target = EndpointDeviceRef(external_id=device_ref)
        result = await asyncio.wait_for(port.read_device(target), timeout=2.0)
        if isinstance(result, EndpointDeviceProjection) and result.device == target and not result.retired:
            signal.update(status="ok", details="Endpoint HTTPS API ответил на read-only запрос; выполнение агентом не проверяется.", last_seen_at=_now_iso())
        else:
            signal.update(status="degraded", details="Endpoint не подтвердил безопасную проекцию устройства; основной Helpdesk работает отдельно.")
    except Exception:
        # Transport, timeout, configuration and projection failures must not escape to core liveness.
        signal.update(status="degraded", details="Проверка зависимости Endpoint недоступна; основной Helpdesk работает отдельно.")
    return signal


async def build_security_snapshot(overview: dict[str, Any], config_values: dict[str, Any], database_reachable: bool) -> dict[str, Any]:
    audit = overview.get("audit_counters") if isinstance(overview.get("audit_counters"), dict) else {}
    fallback_enabled = bool(config_values.get("AUTH_UI_CONFIG_FALLBACK_ENABLED"))
    query_allowed = bool(config_values.get("AUTH_ALLOW_QUERY_TOKEN"))
    cookie_secure = bool(config_values.get("WEB_SESSION_COOKIE_SECURE"))
    cookie_httponly = bool(config_values.get("WEB_SESSION_COOKIE_HTTPONLY", True))
    samesite = str(config_values.get("WEB_SESSION_COOKIE_SAMESITE") or "").strip().lower()
    cookie_status = "ok" if cookie_secure and cookie_httponly and samesite in {"strict", "lax", "none"} else "warning"
    return {
        "auth_mode": {
            "db_users_enabled": bool(config_values.get("AUTH_UI_DB_USERS_ENABLED")),
            "config_fallback_enabled": fallback_enabled,
            "in_memory_fallback_possible": fallback_enabled,
            "status": "warning" if fallback_enabled else "ok",
            "notes": ["config fallback включён"] if fallback_enabled else ["DB users mode активен"],
        },
        "session_cookie": {
            "secure": cookie_secure,
            "httponly": cookie_httponly,
            "samesite": samesite or "unknown",
            "status": cookie_status,
            "notes": [] if cookie_status == "ok" else ["Secure/HttpOnly/SameSite не полностью подтверждены config introspection"],
        },
        "token_channels": {
            "query_token_allowed": query_allowed,
            "query_token_attempts_recent": auth_middleware.get_query_token_auth_attempts(window_seconds=3600),
            "status": "warning" if query_allowed else "ok",
        },
        "audit": {
            "failed_logins_recent": _safe_int(audit.get("failed_logins_recent")),
            "locked_users_count": _safe_int(audit.get("locked_users_count")),
        },
    }


async def build_agents_snapshot(overview: dict[str, Any], config_values: dict[str, Any], database_reachable: bool) -> dict[str, Any]:
    """One bounded provider read. No local telemetry or invented zero counts."""
    from domain_ports.endpoint_context import EndpointDeviceFleet
    try:
        outcome = await DomainPortContainer.from_config().endpoint.list_device_fleet(limit=250)
    except Exception:
        outcome = None
    if not isinstance(outcome, EndpointDeviceFleet):
        return {"source": "endpoint", "status": "unknown", "error_code": getattr(outcome, "code", "unavailable"),
                "total": None, "online": None, "offline": None, "retired": None, "has_more": None}
    active = [item for item in outcome.items if item.device.retired_at is None]
    online = sum(item.device.online for item in active)
    return {"source": "endpoint", "status": "available", "error_code": None,
            "total": len(outcome.items), "online": online, "offline": len(active)-online,
            "retired": len(outcome.items)-len(active),
            "has_more": outcome.next_cursor is not None}


async def build_operations_snapshot(overview: dict[str, Any], database_reachable: bool) -> dict[str, Any]:
    health = overview.get("operations_health") if isinstance(overview.get("operations_health"), dict) else {}
    items: list[dict[str, Any]] = []
    waiting_consent = None
    recent_failed = None
    outbox_backlog = None
    if database_reachable:
        try:
            now = datetime.now(timezone.utc)
            async with get_session() as session:
                waiting_consent = _safe_int(
                    await session.scalar(select(func.count()).select_from(Operation).where(Operation.status == "waiting_consent"))
                )
                recent_failed = _safe_int(
                    await session.scalar(
                        select(func.count()).select_from(Operation).where(
                            and_(Operation.status.in_(["failed", "timed_out"]), Operation.finished_at >= (now - timedelta(hours=24)))
                        )
                    )
                )
                rows = (
                    await session.execute(
                        select(Operation)
                        .where(
                            or_(
                                and_(Operation.status == "queued", Operation.queued_at < (now - timedelta(seconds=OPERATION_DELIVERY_TIMEOUT))),
                                and_(Operation.status == "sent", Operation.sent_at.isnot(None), Operation.sent_at < (now - timedelta(seconds=OPERATION_ACCEPTED_TIMEOUT))),
                                and_(Operation.status.in_(["accepted", "running"]), Operation.started_at.isnot(None), Operation.started_at < (now - timedelta(seconds=OPERATION_EXECUTION_TIMEOUT))),
                            )
                        )
                        .order_by(Operation.queued_at.asc())
                        .limit(50)
                    )
                ).scalars().all()
                items = [
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
                ]
        except SQLAlchemyError:
            pass
    return {
        "queued_stuck": _safe_int(health.get("queued_stuck")),
        "sent_stuck": _safe_int(health.get("sent_stuck")),
        "running_stuck": _safe_int(health.get("in_progress_stuck") or health.get("running_stuck")),
        "waiting_consent": waiting_consent,
        "recent_failed": recent_failed,
        "outbox_backlog": outbox_backlog,
        "recent_nack_count": _safe_int(health.get("recent_nack_count")),
        "items": items,
    }


async def build_observer_integrity_snapshot(database_reachable: bool) -> dict[str, Any]:
    if not database_reachable:
        return {
            "status": "unknown",
            "active_by_severity": {"critical": 0, "error": 0, "warning": 0, "info": 0},
            "active_total": 0,
            "suppressed_total": 0,
            "top_active": [],
        }
    try:
        async with get_session() as session:
            summary = await ObserverIntegrityRepo(session).summary(limit=5)
    except SQLAlchemyError:
        return {
            "status": "unknown",
            "active_by_severity": {"critical": 0, "error": 0, "warning": 0, "info": 0},
            "active_total": 0,
            "suppressed_total": 0,
            "top_active": [],
        }
    active_by_severity = summary.get("active_by_severity") if isinstance(summary.get("active_by_severity"), dict) else {}
    critical = _safe_int(active_by_severity.get("critical"))
    error = _safe_int(active_by_severity.get("error"))
    warning = _safe_int(active_by_severity.get("warning"))
    status = "critical" if critical else ("error" if error else ("warning" if warning else "ok"))
    return {
        "status": status,
        "active_by_severity": {
            "critical": critical,
            "error": error,
            "warning": warning,
            "info": _safe_int(active_by_severity.get("info")),
        },
        "active_total": _safe_int(summary.get("active_total")),
        "suppressed_total": _safe_int(summary.get("suppressed_total")),
        "top_active": summary.get("top_active") if isinstance(summary.get("top_active"), list) else [],
    }


def build_logs_snapshot(overview: dict[str, Any]) -> dict[str, Any]:
    logs = overview.get("problem_logs") if isinstance(overview.get("problem_logs"), list) else []
    error_count = sum(1 for item in logs if str(item.get("level") or "").lower() == "error")
    warning_count = sum(1 for item in logs if str(item.get("level") or "").lower() == "warning")
    critical_count = sum(1 for item in logs if str(item.get("level") or "").lower() == "critical")
    return {"problem_logs": logs, "error_count": error_count, "warning_count": warning_count, "critical_count": critical_count}


def _links() -> dict[str, Any]:
    return {
        "observer": "/app/admin/observer",
        "inventory": "/app/admin/inventory",
        "device_operations": "/app/admin/device",
        "command_center": "/app/support",
        "approval_center": "/app/support/approvals",
        "logs": "/app/admin/tech?tab=logs",
    }


async def build_tech_panel_v2_snapshot(request: web.Request, overview: dict[str, Any]) -> dict[str, Any]:
    config_values = collect_config_values()
    database = build_database_snapshot_from_overview(overview)
    release = build_release_snapshot(config_values)
    if release.get("alembic_current") or release.get("alembic_head"):
        database["alembic_current"] = release.get("alembic_current")
        database["alembic_head"] = release.get("alembic_head")
        database["migrations_status"] = "ok" if release.get("alembic_current") == release.get("alembic_head") else "blocked"
    database["last_backup"] = build_backup_status(config_values)
    database["last_restore_drill"] = build_restore_drill_status(config_values)
    runtime = build_runtime_snapshot(request, overview, config_values)
    runtime["services"].append(await build_endpoint_dependency_snapshot(database_reachable=bool(database.get("reachable"))))
    security = await build_security_snapshot(overview, config_values, bool(database.get("reachable")))
    agents = await build_agents_snapshot(overview, config_values, bool(database.get("reachable")))
    operations = await build_operations_snapshot(overview, bool(database.get("reachable")))
    observer_integrity = await build_observer_integrity_snapshot(bool(database.get("reachable")))
    logs = build_logs_snapshot(overview)
    smoke = build_smoke_snapshot(config_values)
    gates = build_readiness_gates(
        config_values=config_values,
        database=database,
        security=security,
        runtime=runtime,
        agents=agents,
        smoke=smoke,
    )
    return {
        "generated_at": _now_iso(),
        "readiness": aggregate_readiness(gates),
        "security": security,
        "runtime": runtime,
        "database": database,
        "agents": agents,
        "operations": operations,
        "observer_integrity": observer_integrity,
        "logs": logs,
        "alerts": overview.get("alerts") if isinstance(overview.get("alerts"), list) else [],
        "release": {key: value for key, value in release.items() if key not in {"alembic_current", "alembic_head"}},
        "smoke": smoke,
        "links": _links(),
    }
