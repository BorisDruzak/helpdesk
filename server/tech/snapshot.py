"""Read-only Tech Panel v2 snapshot/readiness read model."""
from __future__ import annotations

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
    AgentToken,
    ConnectionRequest,
    Device,
    DeviceOutbox,
    Operation,
    ServerConfig,
)
from app.repos.connection_requests_repo import CONNECTION_POLICY_KEY, POLICY_ACCEPT_ALL, POLICY_MANUAL, POLICY_REJECT_ALL
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
        "ENABLE_DB_PERSISTENCE": _bool_config("ENABLE_DB_PERSISTENCE", True),
        "PILOT_STAND_MODE": _bool_config("PILOT_STAND_MODE", False),
        "REQUIRE_HTTPS": _bool_config("REQUIRE_HTTPS", False),
        "REQUIRE_WSS": _bool_config("REQUIRE_WSS", False),
        "AUTH_ALLOW_QUERY_TOKEN": _bool_config("AUTH_ALLOW_QUERY_TOKEN", False),
        "AUTH_UI_DB_USERS_ENABLED": _bool_config("AUTH_UI_DB_USERS_ENABLED", True),
        "AUTH_UI_CONFIG_FALLBACK_ENABLED": _bool_config("AUTH_UI_CONFIG_FALLBACK_ENABLED", False),
        "PILOT_MIN_AGENT_VERSION": _str_config("PILOT_MIN_AGENT_VERSION"),
        "WEB_SESSION_COOKIE_SECURE": _bool_config("WEB_SESSION_COOKIE_SECURE", True),
        "WEB_SESSION_COOKIE_HTTPONLY": _bool_config("WEB_SESSION_COOKIE_HTTPONLY", True),
        "WEB_SESSION_COOKIE_SAMESITE": _str_config("WEB_SESSION_COOKIE_SAMESITE", "Lax"),
        "INVENTORY_REFRESH_SCHEDULER_ENABLED": _bool_config("INVENTORY_REFRESH_SCHEDULER_ENABLED", True),
        "TECH_BACKUP_STATUS_PATH": _str_config("TECH_BACKUP_STATUS_PATH"),
        "TECH_RESTORE_DRILL_STATUS_PATH": _str_config("TECH_RESTORE_DRILL_STATUS_PATH"),
        "TECH_RELEASE_STATUS_PATH": _str_config("TECH_RELEASE_STATUS_PATH"),
        "TECH_BUSINESS_SMOKE_STATUS_PATH": _str_config("TECH_BUSINESS_SMOKE_STATUS_PATH"),
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
    return "blocked" if bool(config_values.get("PILOT_STAND_MODE")) else "warning"


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

    policy = security.get("agent_connection_policy", {}) if isinstance(security.get("agent_connection_policy"), dict) else {}
    mode = str(policy.get("mode") or "").strip().lower()
    policy_ok = mode in {POLICY_MANUAL, POLICY_REJECT_ALL, "controlled"}
    policy_status = "ok" if policy_ok else ("unknown" if not mode else pilot_status)
    gates.append(
        _gate(
            "agent_connection_policy_controlled",
            "Agent connection policy контролируемая",
            policy_status,
            "critical" if policy_status == "blocked" else ("warning" if policy_status != "ok" else "info"),
            "accept_all/implicit provisioning не подходит для пилота без отдельного hardening.",
            evidence=f"mode={mode or 'unknown'}",
            action_label="Открыть approvals",
            action_href="/app/support/approvals",
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
    restore_ok = str((restore or {}).get("status") or "").lower() == "success"
    gates.append(
        _gate(
            "backup_restore_drill",
            "Restore drill подтверждён",
            "ok" if restore_ok else pilot_status,
            "critical" if pilot_status == "blocked" and not restore_ok else ("warning" if not restore_ok else "info"),
            "Панель читает marker restore drill; restore из браузера не запускается.",
            evidence=f"status={str((restore or {}).get('status') or 'missing')}",
        )
    )

    inventory_scheduler = str((runtime.get("schedulers") or {}).get("inventory_scheduler") or "unknown").lower()
    scheduler_details = runtime.get("scheduler_details") if isinstance(runtime.get("scheduler_details"), dict) else {}
    inventory_details = (
        scheduler_details.get("inventory_scheduler")
        if isinstance(scheduler_details.get("inventory_scheduler"), dict)
        else {}
    )
    duplicate_detected = bool(inventory_details.get("duplicate_task_detected"))
    active_task_count = _safe_int(inventory_details.get("active_task_count"))
    if duplicate_detected:
        inventory_gate_status = "blocked" if bool(config_values.get("PILOT_STAND_MODE")) else "warning"
    else:
        inventory_gate_status = "ok" if inventory_scheduler in {"running", "disabled"} else ("warning" if inventory_scheduler else "unknown")
    gates.append(
        _gate(
            "inventory_scheduler_health",
            "Inventory scheduler healthy",
            inventory_gate_status,
            "critical" if inventory_gate_status == "blocked" else ("warning" if inventory_gate_status != "ok" else "info"),
            "Gate показывает, включён ли scheduler и есть ли runtime signal; duplicate-task detection остаётся отдельным hardening.",
            evidence=f"inventory_scheduler={inventory_scheduler or 'unknown'}, active_task_count={active_task_count}, duplicate={str(duplicate_detected).lower()}",
            action_label="Открыть inventory",
            action_href="/app/admin/inventory",
        )
    )

    min_agent = str(config_values.get("PILOT_MIN_AGENT_VERSION") or "").strip()
    below_baseline = agents.get("below_baseline")
    if not min_agent:
        baseline_status = "warning"
        evidence = "PILOT_MIN_AGENT_VERSION not configured"
    elif below_baseline is None:
        baseline_status = "unknown"
        evidence = f"PILOT_MIN_AGENT_VERSION={min_agent}, below_baseline=unknown"
    else:
        baseline_status = "ok" if _safe_int(below_baseline) == 0 else pilot_status
        evidence = f"PILOT_MIN_AGENT_VERSION={min_agent}, below_baseline={below_baseline}"
    gates.append(
        _gate(
            "agent_baseline",
            "Agent baseline соблюдён",
            baseline_status,
            "critical" if baseline_status == "blocked" else ("warning" if baseline_status != "ok" else "info"),
            "Пилот должен понимать, сколько агентов ниже минимальной версии.",
            evidence=evidence,
            action_label="Открыть agent updates",
            action_href="/app/admin/agent-updates",
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
    inventory_runtime = request.app.get("inventory_refresh_runtime")
    inventory_enabled = bool(config_values.get("INVENTORY_REFRESH_SCHEDULER_ENABLED"))
    inventory_runtime_snapshot = None
    if inventory_runtime is not None and callable(getattr(inventory_runtime, "status_snapshot", None)):
        try:
            inventory_runtime_snapshot = inventory_runtime.status_snapshot()
        except Exception:
            inventory_runtime_snapshot = None
    inventory_running = (
        bool(inventory_runtime_snapshot.get("running"))
        if isinstance(inventory_runtime_snapshot, dict)
        else (bool(getattr(inventory_runtime, "_running", False)) if inventory_runtime is not None else False)
    )
    if not inventory_enabled:
        inventory_status = "disabled"
    elif inventory_running:
        inventory_status = "running"
    elif inventory_runtime is None:
        inventory_status = "unknown"
    else:
        inventory_status = "enabled_not_running"

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
        "inventory_scheduler": inventory_status,
        "observer_refresh_runtime": str(service_health.get("observer_refresh_runtime") or "unknown"),
    }
    if not isinstance(inventory_runtime_snapshot, dict):
        inventory_runtime_snapshot = {
            "enabled": inventory_enabled,
            "running": inventory_running,
            "active_task_count": 0,
            "duplicate_task_detected": False,
            "last_tick_at": None,
            "last_error": None,
        }
    return {
        "services": [
            service("api", "API", str(service_health.get("api") or "unknown")),
            service("ws_ui", "UI WebSocket", str(service_health.get("ws_ui") or "unknown")),
            service("agent_ws", "Agent WebSocket", "ok" if _safe_int(service_health.get("agent_ws_connections")) >= 0 else "unknown"),
            service("device_dispatch", "Device dispatch", str(service_health.get("device_dispatch") or "unknown")),
            service("operation_watchdog", "Operation watchdog", schedulers["operation_watchdog"]),
            service("ticket_sla_watchdog", "Ticket SLA watchdog", schedulers["ticket_sla_watchdog"]),
            service("ticket_auto_close_watchdog", "Ticket auto-close watchdog", schedulers["ticket_auto_close_watchdog"]),
            service("inventory_scheduler", "Inventory scheduler", inventory_status),
            service("observer_refresh_runtime", "Observer refresh runtime", schedulers["observer_refresh_runtime"]),
        ],
        "web_sockets": {
            "ui_connections": _safe_int(service_health.get("ui_ws_connections")),
            "agent_connections": _safe_int(service_health.get("agent_ws_connections")),
        },
        "schedulers": schedulers,
        "scheduler_details": {"inventory_scheduler": inventory_runtime_snapshot},
    }


async def _connection_policy_snapshot(database_reachable: bool) -> dict[str, Any]:
    mode: str | None = None
    pending = 0
    stale = 0
    if database_reachable:
        try:
            now = datetime.now(timezone.utc)
            async with get_session() as session:
                row = await session.scalar(select(ServerConfig.value).where(ServerConfig.key == CONNECTION_POLICY_KEY))
                mode = str(row or POLICY_ACCEPT_ALL)
                pending = _safe_int(
                    await session.scalar(select(func.count()).select_from(ConnectionRequest).where(ConnectionRequest.status == "pending"))
                )
                stale = _safe_int(
                    await session.scalar(
                        select(func.count()).select_from(ConnectionRequest).where(
                            and_(ConnectionRequest.status == "pending", ConnectionRequest.last_request_at < (now - timedelta(minutes=5)))
                        )
                    )
                )
        except SQLAlchemyError:
            mode = None
    if mode in {POLICY_MANUAL, POLICY_REJECT_ALL, "controlled"}:
        status = "ok"
    elif mode == POLICY_ACCEPT_ALL:
        status = "warning"
    elif mode:
        status = "warning"
    else:
        status = "unknown"
    return {"mode": mode, "status": status, "pending_requests": pending, "stale_pending_requests": stale}


async def build_security_snapshot(overview: dict[str, Any], config_values: dict[str, Any], database_reachable: bool) -> dict[str, Any]:
    audit = overview.get("audit_counters") if isinstance(overview.get("audit_counters"), dict) else {}
    agent_health = overview.get("agent_health") if isinstance(overview.get("agent_health"), dict) else {}
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
        "agent_connection_policy": await _connection_policy_snapshot(database_reachable),
        "audit": {
            "failed_logins_recent": _safe_int(audit.get("failed_logins_recent")),
            "locked_users_count": _safe_int(audit.get("locked_users_count")),
            "invalid_agent_tokens_recent": _safe_int(agent_health.get("invalid_token_recent")),
        },
    }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value or "")
    return tuple(int(part) for part in parts[:4]) if parts else (0,)


def _is_agent_baseline_candidate(*, protocol_version: str | None, agent_version: str | None) -> bool:
    if str(protocol_version or "").strip().lower() == "pending":
        return False
    return bool(re.search(r"\d+", str(agent_version or "")))


def _version_lt(left: str, right: str) -> bool:
    left_tuple = _version_tuple(left)
    right_tuple = _version_tuple(right)
    length = max(len(left_tuple), len(right_tuple))
    return left_tuple + (0,) * (length - len(left_tuple)) < right_tuple + (0,) * (length - len(right_tuple))


async def _agent_db_enrichment(agent_health: dict[str, Any], config_values: dict[str, Any], database_reachable: bool) -> tuple[int | None, list[dict[str, Any]], list[dict[str, Any]]]:
    min_version = str(config_values.get("PILOT_MIN_AGENT_VERSION") or "").strip()
    below_baseline: int | None = None if not min_version else 0
    problem_devices: list[dict[str, Any]] = []
    below_baseline_devices: list[dict[str, Any]] = []
    if not database_reachable:
        return below_baseline, problem_devices, below_baseline_devices
    try:
        now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(seconds=300)
        async with get_session() as session:
            query = (
                select(Device.device_id, Device.hostname, Device.agent_version, Device.protocol_version, Device.last_seen_at)
                .where(
                    and_(
                        Device.deleted_at.is_(None),
                        or_(
                            Device.last_seen_at < stale_cutoff,
                            ~select(AgentToken.token_hash)
                            .where(and_(AgentToken.device_id == Device.device_id, AgentToken.revoked_at.is_(None)))
                            .exists(),
                        ),
                    )
                )
                .order_by(Device.last_seen_at.asc())
                .limit(20)
            )
            rows = (await session.execute(query)).all()
            for device_id, hostname, agent_version, protocol_version, last_seen_at in rows:
                reasons: list[str] = []
                if last_seen_at and last_seen_at < stale_cutoff:
                    reasons.append("stale")
                if min_version and _is_agent_baseline_candidate(protocol_version=protocol_version, agent_version=agent_version) and _version_lt(str(agent_version or ""), min_version):
                    reasons.append("below baseline")
                problem_devices.append(
                    {
                        "device_id": device_id,
                        "hostname": hostname,
                        "status": "stale" if "stale" in reasons else "warning",
                        "last_seen_at": _iso(last_seen_at),
                        "agent_version": agent_version,
                        "reasons": reasons or ["requires attention"],
                        "href": f"/app/admin/device-operations/{device_id}",
                    }
                )
            if min_version:
                all_versions = (
                    await session.execute(
                        select(Device.device_id, Device.hostname, Device.agent_version, Device.protocol_version, Device.last_seen_at).where(Device.deleted_at.is_(None)).order_by(Device.last_seen_at.desc())
                    )
                ).all()
                below_baseline = 0
                for device_id, hostname, agent_version, protocol_version, last_seen_at in all_versions:
                    if _is_agent_baseline_candidate(protocol_version=protocol_version, agent_version=agent_version) and _version_lt(str(agent_version or ""), min_version):
                        below_baseline += 1
                        if len(below_baseline_devices) < 50:
                            below_baseline_devices.append(
                                {
                                    "device_id": device_id,
                                    "hostname": hostname,
                                    "status": "below_baseline",
                                    "last_seen_at": _iso(last_seen_at),
                                    "agent_version": agent_version,
                                    "reasons": ["below baseline"],
                                    "href": f"/app/admin/device-operations/{device_id}",
                                }
                            )
    except SQLAlchemyError:
        return below_baseline, problem_devices, below_baseline_devices
    return below_baseline, problem_devices, below_baseline_devices


async def build_agents_snapshot(overview: dict[str, Any], config_values: dict[str, Any], database_reachable: bool) -> dict[str, Any]:
    agent = overview.get("agent_health") if isinstance(overview.get("agent_health"), dict) else {}
    update = overview.get("update_health") if isinstance(overview.get("update_health"), dict) else {}
    below_baseline, problem_devices, below_baseline_devices = await _agent_db_enrichment(agent, config_values, database_reachable)
    online = _safe_int(agent.get("online_count") or agent.get("online"))
    offline = _safe_int(agent.get("offline_count") or agent.get("offline"))
    stale = _safe_int(agent.get("stale_count") or agent.get("stale"))
    return {
        "total": online + offline,
        "online": online,
        "offline": offline,
        "stale": stale,
        "pending_connection_requests": _safe_int(agent.get("pending_connection_requests")),
        "reprovision_required": _safe_int(agent.get("reprovision_required_count") or agent.get("reprovision_required")),
        "invalid_token_recent": _safe_int(agent.get("invalid_token_recent")),
        "below_baseline": below_baseline,
        "below_baseline_devices": below_baseline_devices,
        "baseline": {
            "min_version": str(config_values.get("PILOT_MIN_AGENT_VERSION") or "").strip() or None,
            "below_baseline_count": below_baseline,
            "devices": below_baseline_devices,
        },
        "update_in_progress": _safe_int(update.get("in_progress")),
        "update_failed_recent": _safe_int(update.get("failed_recent")),
        "update_timed_out_recent": _safe_int(update.get("timed_out_recent")),
        "awaiting_handshake_confirm": _safe_int(update.get("awaiting_handshake_confirm")),
        "problem_devices": problem_devices,
    }


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
                outbox_backlog = _safe_int(
                    await session.scalar(select(func.count()).select_from(DeviceOutbox).where(DeviceOutbox.status.in_(["pending", "sent"])))
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
        "device_operations": "/app/admin/device-operations",
        "agent_updates": "/app/admin/agent-updates",
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
    security = await build_security_snapshot(overview, config_values, bool(database.get("reachable")))
    agents = await build_agents_snapshot(overview, config_values, bool(database.get("reachable")))
    operations = await build_operations_snapshot(overview, bool(database.get("reachable")))
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
        "logs": logs,
        "alerts": overview.get("alerts") if isinstance(overview.get("alerts"), list) else [],
        "release": {key: value for key, value in release.items() if key not in {"alembic_current", "alembic_head"}},
        "smoke": smoke,
        "links": _links(),
    }
