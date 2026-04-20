#!/usr/bin/env python3
"""Local fixture server for Playwright checks of the new support/admin workspaces."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import itertools
from pathlib import Path
import sys

from aiohttp import web


REPO_ROOT = Path(__file__).resolve().parents[3]
SERVER_ROOT = REPO_ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from static_pages.webapp_assets import (  # noqa: E402
    handle_webapp_asset,
    handle_webapp_page,
    handle_webapp_public_asset,
)


WEB_SESSION_COOKIE_NAME = "pc_client_web_session"
SESSION_TOKEN = "fixture-support-session"
SUPPORT_LOGIN = "support"
SUPPORT_PASSWORD = "secret"
SUPPORT_ACTOR_ROLE = "support"
SUPPORT_ACTOR_LABEL = "Оператор поддержки"
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "secret"
ADMIN_ACTOR_ROLE = "admin"
ADMIN_ACTOR_LABEL = "Администратор"
FIXTURE_TZ = timezone(timedelta(hours=5))
STATUS_LABELS = {
    "new": "Новая",
    "in_progress": "В работе",
    "waiting_on_user": "Ждём пользователя",
    "resolved": "Решено",
}


def now_iso(*, minutes: int = 0) -> str:
    return (datetime(2026, 4, 20, 8, 0, tzinfo=FIXTURE_TZ) + timedelta(minutes=minutes)).isoformat()


def build_fixture_state() -> dict:
    return {
        "message_counter": itertools.count(200),
        "operation_counter": itertools.count(1),
        "session_user": None,
        "admin": {
            "rollout": [
                {
                    "target": "windows_amd64",
                    "channel": "stable",
                    "version": "2.4.1",
                    "updated_at": now_iso(minutes=20),
                    "updated_by": ADMIN_LOGIN,
                },
                {
                    "target": "linux_alt_x86_64",
                    "channel": "stable",
                    "version": "2.3.9",
                    "updated_at": now_iso(minutes=18),
                    "updated_by": ADMIN_LOGIN,
                },
            ],
            "devices": [
                {
                    "device_id": "device-1",
                    "hostname": "WS-01",
                    "os": "Windows 11",
                    "agent_version": "2.4.0",
                    "target": "windows_amd64",
                    "online": True,
                    "last_seen_at": now_iso(minutes=25),
                    "connection_status_label": "Онлайн",
                    "latest_update": {
                        "status": "completed",
                        "label": "Обновление завершено",
                        "summary": "Устройство на шаг позади rollout",
                    },
                },
                {
                    "device_id": "device-2",
                    "hostname": "LT-02",
                    "os": "ALT Linux",
                    "agent_version": "2.3.7",
                    "target": "linux_alt_x86_64",
                    "online": False,
                    "last_seen_at": now_iso(minutes=-30),
                    "connection_status_label": "Оффлайн",
                    "latest_update": {
                        "status": "pending",
                        "label": "Ожидает rollout",
                        "summary": "Назначен rollout stable/2.3.9",
                    },
                },
            ],
            "device_updates": {
                "device-1": {
                    "device_id": "device-1",
                    "device_label": "WS-01",
                    "online": True,
                    "target": "windows_amd64",
                    "current_version": "2.4.0",
                    "release_channel": "stable",
                    "is_release": True,
                    "summary": {
                        "status": "update_available",
                        "label": "Доступно обновление",
                        "summary": "Серверный rollout рекомендует stable/2.4.1.",
                    },
                    "recommendation": {
                        "update_available": True,
                        "recommendation_source": "assigned_rollout",
                        "recommendation_source_label": "Серверный rollout",
                        "comparison": "newer_release_available",
                        "comparison_label": "Назначена более новая release-версия",
                        "recommended_reason": "assigned_rollout_newer",
                        "recommended_reason_label": "Назначенный rollout новее текущей версии.",
                        "recommended_build": {
                            "target": "windows_amd64",
                            "channel": "stable",
                            "version": "2.4.1",
                        },
                        "assigned_rollout": {
                            "target": "windows_amd64",
                            "channel": "stable",
                            "version": "2.4.1",
                            "updated_at": now_iso(minutes=20),
                            "updated_by": ADMIN_LOGIN,
                        },
                    },
                    "action": {
                        "enabled": True,
                        "label": "Запустить обновление",
                        "reason_required": True,
                        "endpoint": "/api/web/admin/devices/device-1/updates/run",
                    },
                },
                "device-2": {
                    "device_id": "device-2",
                    "device_label": "LT-02",
                    "online": False,
                    "target": "linux_alt_x86_64",
                    "current_version": "2.3.7",
                    "release_channel": "stable",
                    "is_release": True,
                    "summary": {
                        "status": "offline",
                        "label": "Ждёт связи",
                        "summary": "Запуск обновления доступен только когда агент онлайн и может принять команду.",
                    },
                    "recommendation": {
                        "update_available": True,
                        "recommendation_source": "assigned_rollout",
                        "recommendation_source_label": "Серверный rollout",
                        "comparison": "newer_release_available",
                        "comparison_label": "Назначена более новая release-версия",
                        "recommended_reason": "assigned_rollout_newer",
                        "recommended_reason_label": "Назначенный rollout новее текущей версии.",
                        "recommended_build": {
                            "target": "linux_alt_x86_64",
                            "channel": "stable",
                            "version": "2.3.9",
                        },
                        "assigned_rollout": {
                            "target": "linux_alt_x86_64",
                            "channel": "stable",
                            "version": "2.3.9",
                            "updated_at": now_iso(minutes=18),
                            "updated_by": ADMIN_LOGIN,
                        },
                    },
                    "action": {
                        "enabled": False,
                        "label": "Ожидает связи",
                        "reason_required": True,
                        "endpoint": "/api/web/admin/devices/device-2/updates/run",
                    },
                },
            },
            "observer_quick": {
                24: {
                    "summary": {
                        "lookback_hours": 24,
                        "recent_trace_count": 9,
                        "hot_trace_count": 2,
                        "signature_count": 1,
                        "degradation_group_count": 1,
                        "dangerous_flow_count": 1,
                    },
                    "runtime": {
                        "enabled": True,
                        "running": True,
                        "health_status": "ok",
                        "health_status_label": "Норма",
                        "pending_trace_count": 1,
                        "last_projected_at": now_iso(minutes=28),
                        "issues": [],
                    },
                    "hot_traces": [
                        {
                            "trace_id": "trace-update-1",
                            "root_kind": "agent_update",
                            "root_kind_label": "Обновление агента",
                            "status": "failed",
                            "status_label": "Ошибка",
                            "ticket_id": "ticket-1",
                            "device_id": "device-1",
                            "duration_ms": 6400,
                            "error_count": 1,
                            "span_count": 6,
                            "started_at": now_iso(minutes=24),
                            "finished_at": now_iso(minutes=24),
                        },
                        {
                            "trace_id": "trace-tool-1",
                            "root_kind": "tool_call",
                            "root_kind_label": "Инструмент",
                            "status": "running",
                            "status_label": "В работе",
                            "ticket_id": "ticket-1",
                            "device_id": "device-1",
                            "duration_ms": 1800,
                            "error_count": 0,
                            "span_count": 4,
                            "started_at": now_iso(minutes=26),
                            "finished_at": None,
                        },
                    ],
                    "top_signatures": [
                        {
                            "error_signature": "sig-1",
                            "title": "Launcher signature mismatch",
                            "tool_name": "update",
                            "component": "agent_update",
                            "occurrences_count": 4,
                            "affected_devices_count": 2,
                            "last_seen_at": now_iso(minutes=25),
                        }
                    ],
                    "top_degradations": [
                        {
                            "operation_kind": "tool_call",
                            "operation_kind_label": "Инструмент",
                            "tool_name": "network_ping.ping",
                            "operations_count": 7,
                            "timeout_count": 2,
                            "retried_operations_count": 3,
                            "slow_operations_count": 1,
                            "max_duration_ms": 9000,
                            "latest_operation_at": now_iso(minutes=23),
                        }
                    ],
                    "dangerous_flows": [
                        {
                            "root_kind": "agent_update",
                            "root_kind_label": "Обновление агента",
                            "operations_count": 5,
                            "error_count": 2,
                            "timeout_count": 1,
                            "retried_count": 1,
                            "active_count": 0,
                            "latest_operation_at": now_iso(minutes=24),
                        }
                    ],
                    "links": {
                        "quick_endpoint": "/api/admin/tech/observer/quick",
                        "traces_endpoint": "/api/admin/tech/traces",
                        "runtime_endpoint": "/api/admin/tech/traces/runtime",
                    },
                },
                72: {
                    "summary": {
                        "lookback_hours": 72,
                        "recent_trace_count": 14,
                        "hot_trace_count": 3,
                        "signature_count": 2,
                        "degradation_group_count": 2,
                        "dangerous_flow_count": 2,
                    },
                    "runtime": {
                        "enabled": True,
                        "running": True,
                        "health_status": "degraded",
                        "health_status_label": "Есть отставание",
                        "pending_trace_count": 6,
                        "last_projected_at": now_iso(minutes=10),
                        "issues": ["pending_backlog"],
                    },
                    "hot_traces": [],
                    "top_signatures": [],
                    "top_degradations": [],
                    "dangerous_flows": [],
                    "links": {
                        "quick_endpoint": "/api/admin/tech/observer/quick",
                        "traces_endpoint": "/api/admin/tech/traces",
                        "runtime_endpoint": "/api/admin/tech/traces/runtime",
                    },
                },
            },
        },
        "tickets": {
            "ticket-1": {
                "ticket": {
                    "ticket_id": "ticket-1",
                    "ticket_code": "T-200001",
                    "title": "Ошибка синхронизации профиля",
                    "description": "После обновления рабочий профиль перестал синхронизироваться с сервером.",
                    "status": "new",
                    "status_label": STATUS_LABELS["new"],
                    "requester_display_name": "Алексей",
                    "device_id": "device-1",
                    "queue": {
                        "id": 11,
                        "code": "servicedesk_l1",
                        "name": "Линия поддержки L1",
                    },
                    "assignee_id": None,
                    "updated_at": now_iso(minutes=12),
                    "created_at": now_iso(minutes=0),
                    "queue_members": [
                        {"actor_id": SUPPORT_LOGIN, "role_in_queue": "owner"},
                        {"actor_id": "op-l1", "role_in_queue": "member"},
                    ],
                },
                "requester_display_name": "Алексей",
                "queue_code": "servicedesk_l1",
                "requires_operator_action": True,
                "unread_user_messages": 2,
                "observer": {
                    "ticket_summary_endpoint": "/api/tickets/ticket-1/observer",
                    "summary": {
                        "ticket_id": "ticket-1",
                        "root_trace_id": "trace-support-root",
                        "trace_count": 4,
                        "active_trace_count": 1,
                        "error_trace_count": 0,
                        "signature_count": 1,
                        "latest_trace_at": now_iso(minutes=11),
                    },
                },
                "timeline": [
                    {
                        "message_id": "msg-user-1",
                        "event_id": 101,
                        "event_type": "chat_message",
                        "from_role": "user",
                        "sender_display_name": "Алексей",
                        "text": "Профиль зависает на этапе синхронизации и не получает новые политики.",
                        "ts": now_iso(minutes=10),
                        "visibility": "public",
                        "direction": "to_agent",
                        "attachments": [],
                        "reply_to": None,
                        "tool_name": None,
                        "tool_status": None,
                        "result_summary": None,
                        "result_preview": None,
                    },
                    {
                        "message_id": "msg-support-1",
                        "event_id": 102,
                        "event_type": "chat_message",
                        "from_role": "support",
                        "sender_display_name": SUPPORT_ACTOR_LABEL,
                        "text": "Проверяю состояние агента и последний sync job.",
                        "ts": now_iso(minutes=11),
                        "visibility": "public",
                        "direction": "from_support",
                        "attachments": [],
                        "reply_to": None,
                        "tool_name": None,
                        "tool_status": None,
                        "result_summary": None,
                        "result_preview": None,
                    },
                ],
                "snapshot": {
                    "last_event_id": 102,
                    "notification_unread": 1,
                    "presence": {
                        "requester_online": False,
                        "support_online": True,
                        "agent_online": True,
                    },
                    "device": {
                        "device_id": "device-1",
                        "hostname": "ws-l1-01",
                        "os": "Windows 11",
                        "agent_version": "2.4.1",
                        "last_seen_at": now_iso(minutes=12),
                        "online": True,
                    },
                    "latest_operations": [
                        {
                            "operation_id": "op-bootstrap-1",
                            "kind": "run_tool",
                            "status": "succeeded",
                            "tool_name": "network.diagnostics",
                            "command_name": None,
                            "queued_at": now_iso(minutes=8),
                            "finished_at": now_iso(minutes=9),
                            "result_summary": "Агент на связи, канал до policy-сервера отвечает.",
                            "error_message": None,
                        }
                    ],
                },
                "tools": {
                    "ticket_id": "ticket-1",
                    "device_id": "device-1",
                    "tools": [
                        {
                            "tool_name": "network.diagnostics",
                            "module_name": "network",
                            "description": "Быстрая проверка сетевого маршрута и отклика policy-сервера.",
                            "risk_level": "safe_read",
                            "requires_consent": False,
                            "install_required": False,
                            "source": "device",
                            "params_schema": [
                                {
                                    "name": "target",
                                    "label": "Хост",
                                    "description": "Что нужно проверить на маршруте.",
                                    "type": "string",
                                    "required": True,
                                    "default": "fileserver.local",
                                }
                            ],
                            "presets": [
                                {
                                    "preset_id": "domain-default",
                                    "label": "Основной policy-сервер",
                                }
                            ],
                        }
                    ],
                },
            },
            "ticket-2": {
                "ticket": {
                    "ticket_id": "ticket-2",
                    "ticket_code": "T-200002",
                    "title": "Нужно уточнить статус печати",
                    "description": "Пользователь ждёт обновление по офисному принтеру и времени следующего выезда.",
                    "status": "waiting_on_user",
                    "status_label": STATUS_LABELS["waiting_on_user"],
                    "requester_display_name": "Марина",
                    "device_id": None,
                    "queue": {
                        "id": 11,
                        "code": "servicedesk_l1",
                        "name": "Линия поддержки L1",
                    },
                    "assignee_id": SUPPORT_LOGIN,
                    "updated_at": now_iso(minutes=5),
                    "created_at": now_iso(minutes=-15),
                    "queue_members": [
                        {"actor_id": SUPPORT_LOGIN, "role_in_queue": "owner"},
                    ],
                },
                "requester_display_name": "Марина",
                "queue_code": "servicedesk_l1",
                "requires_operator_action": False,
                "unread_user_messages": 0,
                "observer": {
                    "ticket_summary_endpoint": "/api/tickets/ticket-2/observer",
                    "summary": {
                        "ticket_id": "ticket-2",
                        "root_trace_id": "trace-support-ticket-2",
                        "trace_count": 1,
                        "active_trace_count": 0,
                        "error_trace_count": 0,
                        "signature_count": 0,
                        "latest_trace_at": now_iso(minutes=4),
                    },
                },
                "timeline": [
                    {
                        "message_id": "msg-user-2",
                        "event_id": 201,
                        "event_type": "chat_message",
                        "from_role": "user",
                        "sender_display_name": "Марина",
                        "text": "Можно уточнить, когда будет следующий статус по принтеру?",
                        "ts": now_iso(minutes=4),
                        "visibility": "public",
                        "direction": "to_agent",
                        "attachments": [],
                        "reply_to": None,
                        "tool_name": None,
                        "tool_status": None,
                        "result_summary": None,
                        "result_preview": None,
                    }
                ],
                "snapshot": {
                    "last_event_id": 201,
                    "notification_unread": 0,
                    "presence": {
                        "requester_online": True,
                        "support_online": True,
                        "agent_online": False,
                    },
                    "device": {
                        "device_id": None,
                        "hostname": None,
                        "os": None,
                        "agent_version": None,
                        "last_seen_at": None,
                        "online": False,
                    },
                    "latest_operations": [],
                },
                "tools": {
                    "ticket_id": "ticket-2",
                    "device_id": None,
                    "tools": [],
                },
            },
        },
    }


def json_success(data: object) -> web.Response:
    return web.json_response({"status": "success", "data": data})


def json_error(message: str, *, status: int, error_code: str) -> web.Response:
    return web.json_response(
        {"status": "error", "error": message, "error_code": error_code},
        status=status,
    )


def require_session(request: web.Request) -> web.Response | None:
    token = request.cookies.get(WEB_SESSION_COOKIE_NAME)
    if token == SESSION_TOKEN:
        return None
    return json_error("Требуется авторизация.", status=401, error_code="UNAUTHORIZED")


def build_admin_devices_payload(state: dict, *, status_filter: str, query: str) -> dict:
    normalized_query = query.strip().lower()
    devices = []
    for item in state["admin"]["devices"]:
        if status_filter == "online" and not item["online"]:
            continue
        if status_filter == "offline" and item["online"]:
            continue
        haystack = " ".join(
            [
                item["device_id"],
                item["hostname"] or "",
                item["os"] or "",
                item["agent_version"] or "",
                item["target"] or "",
                item["latest_update"]["label"],
                item["latest_update"]["summary"] or "",
            ]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        devices.append(deepcopy(item))
    return {
        "query": query,
        "status_filter": status_filter,
        "summary": {
            "visible_count": len(devices),
            "online_count": sum(1 for item in devices if item["online"]),
            "rollout_targets": len(state["admin"]["rollout"]),
        },
        "filters": {
            "status_options": [
                {"value": "all", "label": "Все устройства"},
                {"value": "online", "label": "Только онлайн"},
                {"value": "offline", "label": "Только офлайн"},
            ]
        },
        "rollout": deepcopy(state["admin"]["rollout"]),
        "devices": devices,
    }


def build_admin_device_updates_payload(state: dict, device_id: str) -> dict | None:
    payload = state["admin"]["device_updates"].get(device_id)
    if not payload:
        return None
    return deepcopy(payload)


def build_admin_observer_quick_payload(state: dict, *, device_id: str | None, lookback_hours: int) -> dict:
    if device_id == "device-2":
        if lookback_hours == 72:
            return {
                "summary": {
                    "lookback_hours": 72,
                    "recent_trace_count": 14,
                    "hot_trace_count": 3,
                    "signature_count": 2,
                    "degradation_group_count": 2,
                    "dangerous_flow_count": 2,
                },
                "runtime": {
                    "enabled": True,
                    "running": True,
                    "health_status": "degraded",
                    "health_status_label": "Есть отставание",
                    "pending_trace_count": 6,
                    "last_projected_at": now_iso(minutes=10),
                    "issues": ["pending_backlog"],
                },
                "hot_traces": [],
                "top_signatures": [],
                "top_degradations": [],
                "dangerous_flows": [],
                "links": {
                    "quick_endpoint": "/api/web/admin/observer/quick",
                    "traces_endpoint": "/api/web/admin/observer/traces",
                    "runtime_endpoint": "/api/admin/tech/traces/runtime",
                },
            }
        return {
            "summary": {
                "lookback_hours": 24,
                "recent_trace_count": 2,
                "hot_trace_count": 1,
                "signature_count": 0,
                "degradation_group_count": 0,
                "dangerous_flow_count": 0,
            },
            "runtime": {
                "enabled": True,
                "running": True,
                "health_status": "ok",
                "health_status_label": "Норма",
                "pending_trace_count": 0,
                "last_projected_at": now_iso(minutes=-5),
                "issues": [],
            },
            "hot_traces": [
                {
                    "trace_id": "trace-linux-1",
                    "root_kind": "tool_call",
                    "root_kind_label": "Инструмент",
                    "status": "succeeded",
                    "status_label": "Успешно",
                    "ticket_id": None,
                    "device_id": "device-2",
                    "operation_id": "op-linux-1",
                    "duration_ms": 1200,
                    "error_count": 0,
                    "span_count": 2,
                    "started_at": now_iso(minutes=-15),
                    "finished_at": now_iso(minutes=-15),
                    "attrs_json": {},
                }
            ],
            "top_signatures": [],
            "top_degradations": [],
            "dangerous_flows": [],
            "links": {
                "quick_endpoint": "/api/web/admin/observer/quick",
                "traces_endpoint": "/api/web/admin/observer/traces",
                "runtime_endpoint": "/api/admin/tech/traces/runtime",
            },
        }

    payload = deepcopy(state["admin"]["observer_quick"].get(lookback_hours) or state["admin"]["observer_quick"][24])
    payload["links"] = {
        "quick_endpoint": "/api/web/admin/observer/quick",
        "traces_endpoint": "/api/web/admin/observer/traces",
        "runtime_endpoint": "/api/admin/tech/traces/runtime",
    }
    for trace in payload.get("hot_traces", []):
        trace.setdefault("operation_id", f"op-{trace['trace_id']}")
        trace.setdefault("job_id", None)
        trace.setdefault("root_span_id", f"span-{trace['trace_id']}")
        trace.setdefault("attrs_json", {})
    return payload


def _admin_observer_trace_filters() -> dict:
    return {
        "status_options": [
            {"value": "all", "label": "Все статусы"},
            {"value": "running", "label": "В работе"},
            {"value": "failed", "label": "С ошибкой"},
            {"value": "succeeded", "label": "Успешно"},
        ],
        "root_kind_options": [
            {"value": "all", "label": "Все потоки"},
            {"value": "agent_update", "label": "Обновление агента"},
            {"value": "tool_call", "label": "Инструмент"},
        ],
    }


def build_admin_observer_traces_payload(
    *,
    device_id: str | None,
    lookback_hours: int,
    status_filter: str,
    root_kind_filter: str,
    limit: int,
) -> dict:
    if device_id == "device-2":
        traces = []
        if lookback_hours < 72:
            traces = [
                {
                    "trace_id": "trace-linux-1",
                    "root_span_id": "span-linux-1",
                    "root_kind": "tool_call",
                    "root_kind_label": "Инструмент",
                    "status": "succeeded",
                    "status_label": "Успешно",
                    "ticket_id": None,
                    "device_id": "device-2",
                    "operation_id": "op-linux-1",
                    "job_id": None,
                    "duration_ms": 1200,
                    "error_count": 0,
                    "span_count": 2,
                    "started_at": now_iso(minutes=-15),
                    "finished_at": now_iso(minutes=-15),
                    "attrs_json": {},
                }
            ]
    else:
        traces = [
            {
                "trace_id": "trace-update-1",
                "root_span_id": "span-root-1",
                "root_kind": "agent_update",
                "root_kind_label": "Обновление агента",
                "status": "failed",
                "status_label": "Ошибка",
                "ticket_id": "ticket-1",
                "device_id": "device-1",
                "operation_id": "op-update-1",
                "job_id": None,
                "duration_ms": 6400,
                "error_count": 1,
                "span_count": 3,
                "started_at": now_iso(minutes=24),
                "finished_at": now_iso(minutes=24),
                "attrs_json": {"flow": "agent_update"},
            },
            {
                "trace_id": "trace-tool-1",
                "root_span_id": "span-root-2",
                "root_kind": "tool_call",
                "root_kind_label": "Инструмент",
                "status": "running",
                "status_label": "В работе",
                "ticket_id": "ticket-1",
                "device_id": "device-1",
                "operation_id": "op-tool-1",
                "job_id": None,
                "duration_ms": 1800,
                "error_count": 0,
                "span_count": 4,
                "started_at": now_iso(minutes=26),
                "finished_at": None,
                "attrs_json": {},
            },
        ]

    if status_filter != "all":
        traces = [trace for trace in traces if trace["status"] == status_filter]
    if root_kind_filter != "all":
        traces = [trace for trace in traces if trace["root_kind"] == root_kind_filter]

    visible_traces = traces[:limit]
    active_count = sum(1 for trace in visible_traces if trace["status"] in {"running", "queued", "sent", "accepted"})
    error_count = sum(1 for trace in visible_traces if trace["error_count"] > 0 or trace["status"] in {"failed", "timed_out"})
    return {
        "query": {
            "device_id": device_id,
            "lookback_hours": lookback_hours,
            "status_filter": status_filter,
            "root_kind_filter": root_kind_filter,
            "limit": limit,
        },
        "summary": {
            "visible_count": len(visible_traces),
            "active_count": active_count,
            "error_count": error_count,
            "selected_trace_id": visible_traces[0]["trace_id"] if visible_traces else None,
        },
        "filters": _admin_observer_trace_filters(),
        "traces": visible_traces,
        "links": {
            "detail_endpoint_template": "/api/web/admin/observer/traces/{trace_id}",
            "runtime_endpoint": "/api/admin/tech/traces/runtime",
        },
    }


def build_admin_observer_trace_detail_payload(trace_id: str) -> dict | None:
    if trace_id == "trace-linux-1":
        return {
            "trace": {
                "trace_id": "trace-linux-1",
                "root_span_id": "span-linux-1",
                "root_kind": "tool_call",
                "root_kind_label": "Инструмент",
                "status": "succeeded",
                "status_label": "Успешно",
                "ticket_id": None,
                "device_id": "device-2",
                "operation_id": "op-linux-1",
                "job_id": None,
                "duration_ms": 1200,
                "error_count": 0,
                "span_count": 2,
                "started_at": now_iso(minutes=-15),
                "finished_at": now_iso(minutes=-15),
                "attrs_json": {},
            },
            "summary": {
                "span_count": 2,
                "error_count": 0,
                "linked_trace_count": 0,
            },
            "spans": [
                {
                    "span_id": "span-linux-1",
                    "trace_id": "trace-linux-1",
                    "parent_span_id": None,
                    "source_type": "operation",
                    "source_ref": "op-linux-1",
                    "name": "operation.tool_call",
                    "kind": "internal",
                    "component": "operation",
                    "event_type": "tool_call",
                    "module_name": "network_ping",
                    "tool_name": "network_ping.ping",
                    "status": "succeeded",
                    "status_label": "Успешно",
                    "started_at": now_iso(minutes=-15),
                    "finished_at": now_iso(minutes=-15),
                    "duration_ms": 1200,
                    "attrs_json": {},
                }
            ],
            "span_links": [],
            "error_occurrences": [],
        }

    if trace_id != "trace-update-1":
        return None

    return {
        "trace": {
            "trace_id": "trace-update-1",
            "root_span_id": "span-root-1",
            "root_kind": "agent_update",
            "root_kind_label": "Обновление агента",
            "status": "failed",
            "status_label": "Ошибка",
            "ticket_id": "ticket-1",
            "device_id": "device-1",
            "operation_id": "op-update-1",
            "job_id": None,
            "duration_ms": 6400,
            "error_count": 1,
            "span_count": 3,
            "started_at": now_iso(minutes=24),
            "finished_at": now_iso(minutes=24),
            "attrs_json": {"flow": "agent_update"},
        },
        "summary": {
            "span_count": 3,
            "error_count": 1,
            "linked_trace_count": 1,
        },
        "spans": [
            {
                "span_id": "span-root-1",
                "trace_id": "trace-update-1",
                "parent_span_id": None,
                "source_type": "operation",
                "source_ref": "op-update-1",
                "name": "operation.agent_update",
                "kind": "internal",
                "component": "operation",
                "event_type": "agent_update",
                "module_name": None,
                "tool_name": None,
                "status": "failed",
                "status_label": "Ошибка",
                "started_at": now_iso(minutes=24),
                "finished_at": now_iso(minutes=24),
                "duration_ms": 6400,
                "attrs_json": {},
            }
        ],
        "span_links": [
            {
                "id": 11,
                "span_id": "span-root-1",
                "linked_trace_id": "trace-followup-1",
                "linked_span_id": "span-followup-1",
                "reason": "child_trace",
                "attrs_json": {"edge": "child"},
                "created_at": now_iso(minutes=24),
            }
        ],
        "error_occurrences": [
            {
                "occurrence_id": "occ-1",
                "trace_id": "trace-update-1",
                "span_id": "span-root-1",
                "error_signature": "sig-1",
                "device_id": "device-1",
                "ticket_id": "ticket-1",
                "operation_id": "op-update-1",
                "component": "agent_update",
                "module_name": None,
                "tool_name": None,
                "error_kind": "runtime_error",
                "exception_type": "RuntimeError",
                "failure_stage": "delivery",
                "severity": "error",
                "severity_label": "Ошибка",
                "message_norm": "update delivery failed",
                "stack_hash": "stack-1",
                "attrs_json": {"code": "DELIVERY_FAILED"},
                "created_at": now_iso(minutes=24),
            }
        ],
    }


def queue_filters() -> dict:
    return {
        "scope_options": [
            {"value": "all", "label": "Все доступные"},
            {"value": "mine", "label": "Только мои"},
        ],
        "status_options": [
            {"value": "all", "label": "Все статусы"},
            {"value": "new", "label": "Новые"},
            {"value": "in_progress", "label": "В работе"},
            {"value": "waiting_on_user", "label": "Ждём пользователя"},
            {"value": "resolved", "label": "Решено"},
        ],
    }


def queue_entry(ticket_state: dict) -> dict:
    ticket = ticket_state["ticket"]
    return {
        "ticket_id": ticket["ticket_id"],
        "ticket_code": ticket["ticket_code"],
        "title": ticket["title"],
        "status": ticket["status"],
        "status_label": ticket["status_label"],
        "queue_code": ticket_state["queue_code"],
        "assignee_id": ticket["assignee_id"],
        "requester_display_name": ticket_state["requester_display_name"],
        "device_id": ticket["device_id"],
        "updated_at": ticket["updated_at"],
        "created_at": ticket["created_at"],
        "requires_operator_action": ticket_state["requires_operator_action"],
        "unread_user_messages": ticket_state["unread_user_messages"],
    }


def filtered_ticket_ids(state: dict, *, scope: str, status_filter: str, query: str) -> list[str]:
    normalized_query = query.strip().lower()
    ticket_ids: list[str] = []
    for ticket_id, ticket_state in state["tickets"].items():
        ticket = ticket_state["ticket"]
        if scope == "mine" and ticket["assignee_id"] != SUPPORT_LOGIN:
            continue
        if status_filter != "all" and ticket["status"] != status_filter:
            continue
        haystack = " ".join(
            [
                ticket["ticket_code"] or "",
                ticket["title"],
                ticket_state["requester_display_name"] or "",
                ticket["device_id"] or "",
            ]
        ).lower()
        if normalized_query and normalized_query not in haystack:
            continue
        ticket_ids.append(ticket_id)

    ticket_ids.sort(key=lambda ticket_id: state["tickets"][ticket_id]["ticket"]["updated_at"], reverse=True)
    return ticket_ids


def build_ticket_detail(state: dict, ticket_id: str) -> dict:
    ticket_state = state["tickets"][ticket_id]
    return {
        "ticket": deepcopy(ticket_state["ticket"]),
        "observer": deepcopy(ticket_state["observer"]),
        "timeline": deepcopy(ticket_state["timeline"]),
        "snapshot": deepcopy(ticket_state["snapshot"]),
        "actions": {
            "status_options": [
                {"value": "in_progress", "label": "Взять в работу"},
                {"value": "waiting_on_user", "label": "Ждём пользователя"},
                {"value": "resolved", "label": "Решено"},
            ],
            "can_send_internal_note": True,
        },
    }


async def handle_session_me(request: web.Request) -> web.Response:
    if request.cookies.get(WEB_SESSION_COOKIE_NAME) != SESSION_TOKEN:
        return json_success(None)
    session_user = request.app["fixture_state"].get("session_user")
    if not session_user:
        return json_success(None)
    return json_success(deepcopy(session_user))


async def handle_session_login(request: web.Request) -> web.Response:
    payload = await request.json()
    if payload.get("login") == SUPPORT_LOGIN and payload.get("password") == SUPPORT_PASSWORD:
        session_user = {
            "user_login": SUPPORT_LOGIN,
            "actor_role": SUPPORT_ACTOR_ROLE,
            "auth_type": "ui_token",
        }
    elif payload.get("login") == ADMIN_LOGIN and payload.get("password") == ADMIN_PASSWORD:
        session_user = {
            "user_login": ADMIN_LOGIN,
            "actor_role": ADMIN_ACTOR_ROLE,
            "auth_type": "ui_token",
        }
    else:
        return json_error("Неверный логин или пароль.", status=401, error_code="INVALID_CREDENTIALS")

    request.app["fixture_state"]["session_user"] = deepcopy(session_user)
    response = json_success(session_user)
    response.set_cookie(
        WEB_SESSION_COOKIE_NAME,
        SESSION_TOKEN,
        httponly=True,
        max_age=24 * 60 * 60,
        path="/",
        samesite="Lax",
    )
    return response


async def handle_session_logout(request: web.Request) -> web.Response:
    request.app["fixture_state"]["session_user"] = None
    response = json_success({"cleared": True})
    response.del_cookie(WEB_SESSION_COOKIE_NAME, path="/")
    return response


async def handle_support_bootstrap(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return json_success(
        {
            "workspace": "support",
            "features": [
                "queue_overview",
                "ticket_workspace",
                "observer_trace",
                "tool_actions",
            ],
            "observer": {
                "ticket_summary_endpoint": "/api/tickets/{ticket_id}/observer",
                "drawer_tab": "trace",
            },
        }
    )


async def handle_support_queue(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    scope = request.query.get("scope", "all")
    status_filter = request.query.get("status", "all")
    query = request.query.get("query", "")
    ticket_ids = filtered_ticket_ids(state, scope=scope, status_filter=status_filter, query=query)
    return json_success(
        {
            "scope": scope,
            "query": query,
            "status_filter": status_filter,
            "summary": {
                "visible_count": len(ticket_ids),
                "selected_ticket_id": ticket_ids[0] if ticket_ids else None,
            },
            "filters": queue_filters(),
            "tickets": [queue_entry(state["tickets"][ticket_id]) for ticket_id in ticket_ids],
        }
    )


async def handle_support_ticket_detail(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_detail(state, ticket_id))


async def handle_support_ticket_tools(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(deepcopy(state["tickets"][ticket_id]["tools"]))


async def handle_support_ticket_message(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()

    ticket_state = state["tickets"][ticket_id]
    payload = await request.json()
    message_id = f"msg-support-{next(state['message_counter'])}"
    timestamp = now_iso(minutes=15)
    message = {
        "message_id": message_id,
        "event_id": next(state["message_counter"]),
        "event_type": "chat_message",
        "from_role": "support",
        "sender_display_name": SUPPORT_ACTOR_LABEL,
        "text": payload.get("text", ""),
        "ts": timestamp,
        "visibility": payload.get("visibility", "public"),
        "direction": "from_support",
        "attachments": [],
        "reply_to": None,
        "tool_name": None,
        "tool_status": None,
        "result_summary": None,
        "result_preview": None,
    }
    ticket_state["timeline"].insert(0, message)
    ticket_state["ticket"]["updated_at"] = timestamp
    ticket_state["snapshot"]["last_event_id"] = message["event_id"]
    return json_success({"ticket_id": ticket_id, "message": deepcopy(message)})


async def handle_support_ticket_status(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()

    payload = await request.json()
    to_status = payload.get("to_status", "new")
    ticket_state = state["tickets"][ticket_id]
    ticket_state["ticket"]["status"] = to_status
    ticket_state["ticket"]["status_label"] = STATUS_LABELS.get(to_status, to_status)
    ticket_state["ticket"]["updated_at"] = now_iso(minutes=16)
    return json_success(
        {
            "ticket_id": ticket_id,
            "status": to_status,
            "status_label": ticket_state["ticket"]["status_label"],
        }
    )


async def handle_support_ticket_tool_run(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()

    ticket_state = state["tickets"][ticket_id]
    payload = await request.json()
    tool_name = payload.get("tool_name") or "unknown.tool"
    params = payload.get("params") or {}
    target = params.get("target", "fileserver.local")
    operation_id = f"op-support-tool-{next(state['operation_counter'])}"
    queued_at = now_iso(minutes=17)
    finished_at = now_iso(minutes=18)
    result_summary = "Сетевой маршрут проверен успешно."
    result_preview = f"{target}\nlatency_ms=12\npolicy_server=ok"

    started_event = {
        "message_id": None,
        "event_id": next(state["message_counter"]),
        "event_type": "tool_call_started",
        "from_role": "system",
        "sender_display_name": "system",
        "text": f"Инструмент {tool_name} поставлен в очередь.",
        "ts": queued_at,
        "visibility": "system",
        "direction": "system",
        "attachments": [],
        "reply_to": None,
        "tool_name": tool_name,
        "tool_status": "queued",
        "result_summary": None,
        "result_preview": None,
    }
    result_event = {
        "message_id": None,
        "event_id": next(state["message_counter"]),
        "event_type": "tool_call_result",
        "from_role": "system",
        "sender_display_name": "system",
        "text": f"Результат инструмента: {tool_name}",
        "ts": finished_at,
        "visibility": "system",
        "direction": "system",
        "attachments": [],
        "reply_to": None,
        "tool_name": tool_name,
        "tool_status": "success",
        "result_summary": result_summary,
        "result_preview": result_preview,
    }
    ticket_state["timeline"].insert(0, result_event)
    ticket_state["timeline"].insert(1, started_event)
    ticket_state["snapshot"]["latest_operations"].insert(
        0,
        {
            "operation_id": operation_id,
            "kind": "run_tool",
            "status": "succeeded",
            "tool_name": tool_name,
            "command_name": None,
            "queued_at": queued_at,
            "finished_at": finished_at,
            "result_summary": result_summary,
            "error_message": None,
        },
    )
    ticket_state["ticket"]["updated_at"] = finished_at
    ticket_state["observer"]["summary"]["latest_trace_at"] = finished_at
    return json_success(
        {
            "ticket_id": ticket_id,
            "device_id": ticket_state["ticket"]["device_id"],
            "tool_name": tool_name,
            "dispatch_status": "queued",
            "operation_id": operation_id,
            "poll_url": f"/api/operations/{operation_id}",
            "trace_id": f"trace-{operation_id}",
            "message": f"Операция {operation_id} поставлена в очередь выполнения.",
        }
    )


async def handle_admin_bootstrap(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return json_success(
        {
            "workspace": "admin",
            "features": [
                "devices_inventory",
                "agent_rollout",
                "modules_workbench",
                "tech_panel",
            ],
            "observer": {
                "quick_endpoint": "/api/web/admin/observer/quick",
                "traces_endpoint": "/api/web/admin/observer/traces",
            },
        }
    )


async def handle_admin_devices(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    status_filter = request.query.get("status", "all")
    query = request.query.get("query", "")
    return json_success(build_admin_devices_payload(state, status_filter=status_filter, query=query))


async def handle_admin_observer_quick(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    device_id = request.query.get("device_id")
    try:
        lookback_hours = int(str(request.query.get("lookback_hours", "24")).strip() or "24")
    except ValueError:
        lookback_hours = 24
    payload = build_admin_observer_quick_payload(state, device_id=device_id, lookback_hours=lookback_hours)
    return json_success(payload)


async def handle_admin_observer_traces(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    device_id = request.query.get("device_id")
    try:
        lookback_hours = int(str(request.query.get("lookback_hours", "24")).strip() or "24")
    except ValueError:
        lookback_hours = 24
    try:
        limit = int(str(request.query.get("limit", "12")).strip() or "12")
    except ValueError:
        limit = 12
    payload = build_admin_observer_traces_payload(
        device_id=device_id,
        lookback_hours=lookback_hours,
        status_filter=request.query.get("status", "all"),
        root_kind_filter=request.query.get("root_kind", "all"),
        limit=limit,
    )
    return json_success(payload)


async def handle_admin_observer_trace_detail(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    trace_id = request.match_info["trace_id"]
    payload = build_admin_observer_trace_detail_payload(trace_id)
    if not payload:
        raise web.HTTPNotFound()
    return json_success(payload)


async def handle_admin_device_updates(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    device_id = request.match_info["device_id"]
    payload = build_admin_device_updates_payload(state, device_id)
    if not payload:
        return json_error("Устройство не найдено", status=404, error_code="DEVICE_NOT_FOUND")
    return json_success(payload)


async def handle_admin_device_update_run(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    device_id = request.match_info["device_id"]
    payload = build_admin_device_updates_payload(state, device_id)
    if not payload:
        return json_error("Устройство не найдено", status=404, error_code="DEVICE_NOT_FOUND")

    body = await request.json()
    reason = str(body.get("reason") or "").strip()
    if not reason:
        return json_error("Укажите причину запуска обновления", status=400, error_code="VALIDATION_ERROR")
    if not payload["action"]["enabled"]:
        return json_error("Устройство сейчас недоступно для update action", status=409, error_code="AGENT_OFFLINE")

    operation_id = f"op-admin-update-{next(state['operation_counter']):03d}"
    build = deepcopy(payload["recommendation"]["recommended_build"])
    payload["summary"] = {
        "status": "queued",
        "label": "Поставлено в очередь",
        "summary": f"Запрос сохранён с причиной: {reason}",
    }
    payload["action"]["label"] = "Повторить rollout"
    return json_success(
        {
            "device_id": device_id,
            "operation_id": operation_id,
            "status": "queued",
            "message": f"Операция {operation_id} поставлена в очередь.",
            "build_source": "assigned_rollout",
            "poll_url": f"/api/operations/{operation_id}",
            "build": build,
        }
    )


def build_app() -> web.Application:
    app = web.Application()
    app["fixture_state"] = build_fixture_state()
    app.add_routes(
        [
            web.get("/api/web/session/me", handle_session_me),
            web.post("/api/web/session/login", handle_session_login),
            web.post("/api/web/session/logout", handle_session_logout),
            web.get("/api/web/support/bootstrap", handle_support_bootstrap),
            web.get("/api/web/support/queue", handle_support_queue),
            web.get("/api/web/support/tickets/{ticket_id}", handle_support_ticket_detail),
            web.get("/api/web/support/tickets/{ticket_id}/tools", handle_support_ticket_tools),
            web.post("/api/web/support/tickets/{ticket_id}/messages", handle_support_ticket_message),
            web.post("/api/web/support/tickets/{ticket_id}/status", handle_support_ticket_status),
            web.post("/api/web/support/tickets/{ticket_id}/tools/run", handle_support_ticket_tool_run),
            web.get("/api/web/admin/bootstrap", handle_admin_bootstrap),
            web.get("/api/web/admin/observer/quick", handle_admin_observer_quick),
            web.get("/api/web/admin/observer/traces", handle_admin_observer_traces),
            web.get("/api/web/admin/observer/traces/{trace_id}", handle_admin_observer_trace_detail),
            web.get("/api/web/admin/devices", handle_admin_devices),
            web.get("/api/web/admin/devices/{device_id}/updates", handle_admin_device_updates),
            web.post("/api/web/admin/devices/{device_id}/updates/run", handle_admin_device_update_run),
            web.get("/assets/{asset_path:.*}", handle_webapp_asset),
            web.get("/favicon.svg", handle_webapp_public_asset),
            web.get("/app", handle_webapp_page),
            web.get("/app/{tail:.*}", handle_webapp_page),
        ]
    )
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"[support-fixture-server] serving on http://{args.host}:{args.port}")
    web.run_app(build_app(), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
