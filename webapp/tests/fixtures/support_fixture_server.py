#!/usr/bin/env python3
"""Local fixture server for Playwright checks of the new support/admin workspaces."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import itertools
import json
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
SUPPORT_PERMISSIONS = [
    "workspace.support.view",
    "ticket.queue.view",
    "ticket.detail.view",
    "ticket.comment.public",
    "ticket.comment.internal",
    "ticket.status.change",
    "ticket.playbook.run",
    "ticket.tool.run",
    "module.tool.run.low_risk",
    "module.tool.run.high_risk",
    "ticket.passport.manage",
    "settings.view",
]
ADMIN_PERMISSIONS = [
    "workspace.admin.view",
    *SUPPORT_PERMISSIONS,
    "admin.inventory.view",
    "admin.registry.view",
    "admin.modules.view",
    "admin.forms.view",
    "admin.playbooks.view",
    "admin.observer.view",
    "admin.access.view",
]


def now_iso(*, minutes: int = 0) -> str:
    return (datetime(2026, 4, 20, 8, 0, tzinfo=FIXTURE_TZ) + timedelta(minutes=minutes)).isoformat()


def build_fixture_state() -> dict:
    return {
        "message_counter": itertools.count(200),
        "operation_counter": itertools.count(1),
        "saved_view_counter": itertools.count(1),
        "session_user": None,
        "ws_ticket_subscribers": {},
        "ws_device_subscribers": {},
        "support_queue_saved_views": [],
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
            "modules": {
                "summary": {
                    "visible_count": 2,
                    "preferred_count": 1,
                    "invalid_count": 1,
                    "missing_files_count": 1,
                },
                "rollout_settings": {
                    "preferred_version_rollout_mode": "installed_devices",
                    "preferred_version_rollout_mode_label": "Обновлять установленные устройства",
                    "sync_after_preferred_change": False,
                },
                "families": [
                    {
                        "module_name": "network_ping",
                        "preferred_version": "1.2.0",
                        "preferred_assigned": True,
                        "latest_version": "1.2.1",
                        "owner_scope": "vendor",
                        "module_api_version": "2.0.0",
                        "validation_status": "warning",
                        "validation_status_label": "Есть предупреждения",
                        "version_count": 2,
                        "tools_count": 2,
                        "platforms": ["windows_amd64", "linux_alt_x86_64"],
                        "tool_ids": ["network_ping.ping", "network_ping.trace"],
                        "warnings_count": 1,
                        "has_missing_files": False,
                        "versions": [
                            {
                                "version": "1.2.1",
                                "created_at": now_iso(minutes=12),
                                "uploaded_by": ADMIN_LOGIN,
                                "manifest_version": 2,
                                "module_api_version": "2.0.0",
                                "owner_scope": "vendor",
                                "validation_status": "warning",
                                "validation_status_label": "Есть предупреждения",
                                "preflight_status": "passed",
                                "preflight_status_label": "Проверен",
                                "is_preferred": False,
                                "tools_count": 2,
                                "platforms": ["windows_amd64", "linux_alt_x86_64"],
                                "tool_ids": ["network_ping.ping", "network_ping.trace"],
                                "warnings_count": 1,
                                "file_exists": True,
                            },
                            {
                                "version": "1.2.0",
                                "created_at": now_iso(minutes=4),
                                "uploaded_by": ADMIN_LOGIN,
                                "manifest_version": 2,
                                "module_api_version": "2.0.0",
                                "owner_scope": "vendor",
                                "validation_status": "passed",
                                "validation_status_label": "Проверен",
                                "preflight_status": "passed",
                                "preflight_status_label": "Проверен",
                                "is_preferred": True,
                                "tools_count": 2,
                                "platforms": ["windows_amd64", "linux_alt_x86_64"],
                                "tool_ids": ["network_ping.ping", "network_ping.trace"],
                                "warnings_count": 0,
                                "file_exists": True,
                            },
                        ],
                    },
                    {
                        "module_name": "observer_canary",
                        "preferred_version": None,
                        "preferred_assigned": False,
                        "latest_version": "0.9.0",
                        "owner_scope": "internal",
                        "module_api_version": "1.0.0",
                        "validation_status": "failed",
                        "validation_status_label": "Ошибка валидации",
                        "version_count": 1,
                        "tools_count": 1,
                        "platforms": ["windows_amd64"],
                        "tool_ids": ["observer.canary"],
                        "warnings_count": 2,
                        "has_missing_files": True,
                        "versions": [
                            {
                                "version": "0.9.0",
                                "created_at": now_iso(minutes=-55),
                                "uploaded_by": ADMIN_LOGIN,
                                "manifest_version": 2,
                                "module_api_version": "1.0.0",
                                "owner_scope": "internal",
                                "validation_status": "failed",
                                "validation_status_label": "Ошибка валидации",
                                "preflight_status": "failed",
                                "preflight_status_label": "Ошибка валидации",
                                "is_preferred": False,
                                "tools_count": 1,
                                "platforms": ["windows_amd64"],
                                "tool_ids": ["observer.canary"],
                                "warnings_count": 2,
                                "file_exists": False,
                            }
                        ],
                    },
                ],
            },
            "forms_builder": {
                "summary": {
                    "pack_key": "request_forms",
                    "version": "1.0.3",
                    "title": "Каталог заявок",
                    "description": "Рабочий каталог входящих форм для helpdesk.",
                    "forms_count": 2,
                    "fields_count": 5,
                    "required_fields_count": 2,
                    "last_published_at": now_iso(minutes=8),
                    "last_published_by": ADMIN_LOGIN,
                },
                "forms": [
                    {
                        "key": "printer",
                        "request_kind": "printer",
                        "title": "Печать / принтер",
                        "description": "Проблемы печати и очереди.",
                        "fields": [
                            {
                                "key": "room",
                                "label": "Кабинет",
                                "type": "text",
                                "type_label": "Текст",
                                "required": True,
                                "placeholder": "214",
                                "help_text": "Укажите кабинет, где стоит принтер.",
                                "options": [],
                                "visible_when": None,
                            },
                            {
                                "key": "printer_model",
                                "label": "Модель",
                                "type": "text",
                                "type_label": "Текст",
                                "required": False,
                                "placeholder": "HP LaserJet",
                                "help_text": "",
                                "options": [],
                                "visible_when": None,
                            },
                        ],
                    },
                    {
                        "key": "site_system",
                        "request_kind": "site_system",
                        "title": "Сайт / система",
                        "description": "Проблемы с внутренней системой.",
                        "fields": [
                            {
                                "key": "issue_kind",
                                "label": "Тип проблемы",
                                "type": "select",
                                "type_label": "Список",
                                "required": True,
                                "placeholder": "",
                                "help_text": "",
                                "options": [
                                    {"value": "site_down", "label": "Сайт не открывается"},
                                    {"value": "auth", "label": "Не удаётся войти"},
                                ],
                                "visible_when": None,
                            },
                            {
                                "key": "system_name",
                                "label": "Система",
                                "type": "text",
                                "type_label": "Текст",
                                "required": True,
                                "placeholder": "CRM",
                                "help_text": "",
                                "options": [],
                                "visible_when": None,
                            },
                            {
                                "key": "affected_scope",
                                "label": "У кого проблема",
                                "type": "radio",
                                "type_label": "Переключатель",
                                "required": False,
                                "placeholder": "",
                                "help_text": "",
                                "options": [
                                    {"value": "single", "label": "У одного"},
                                    {"value": "all", "label": "У всех"},
                                ],
                                "visible_when": {
                                    "field": "issue_kind",
                                    "equals": "site_down",
                                    "values": [],
                                },
                            },
                        ],
                    },
                ],
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
                            "required_permission": "module.tool.run.low_risk",
                            "allowed_roles": ["support"],
                            "policy_labels": ["permission:module.tool.run.low_risk", "roles:support", "consent:not_required"],
                            "domain": "network",
                            "tool_kind": "diagnostic",
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


async def broadcast_fixture_message(subscribers: set[web.WebSocketResponse], payload: dict) -> None:
    stale: list[web.WebSocketResponse] = []
    for ws in list(subscribers):
        if ws.closed:
            stale.append(ws)
            continue
        try:
            await ws.send_json(payload)
        except Exception:
            stale.append(ws)

    for ws in stale:
        subscribers.discard(ws)


async def broadcast_fixture_ticket_event(state: dict, ticket_id: str, payload: dict) -> None:
    subscribers = state["ws_ticket_subscribers"].get(ticket_id)
    if not subscribers:
        return
    await broadcast_fixture_message(subscribers, payload)


async def broadcast_fixture_device_event(state: dict, device_id: str, payload: dict) -> None:
    subscribers = state["ws_device_subscribers"].get(device_id)
    if not subscribers:
        return
    await broadcast_fixture_message(subscribers, payload)


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
        device = deepcopy(item)
        device.setdefault(
            "identity_summary",
            {
                "machine_id": device["device_id"],
                "install_id": f"install-{device['device_id']}",
                "machine_id_source": "windows_machine_guid" if device["device_id"] == "device-1" else "linux_machine_id",
                "identity_scheme": "machine_id_v1",
                "source_label": "Windows MachineGuid" if device["device_id"] == "device-1" else "Linux machine-id",
                "is_stable": True,
            },
        )
        device.setdefault(
            "duplicate_warning",
            {
                "kind": "hostname_has_env_uuid_duplicates",
                "severity": "info",
                "title": "Есть старые тестовые дубли",
                "description": "Для hostname WS-01 найден env_uuid-дубль.",
                "duplicate_count": 2,
                "cleanup_available": True,
            }
            if device["device_id"] == "device-1"
            else None,
        )
        devices.append(device)
    return {
        "query": query,
        "status_filter": status_filter,
        "summary": {
            "visible_count": len(devices),
            "online_count": sum(1 for item in devices if item["online"]),
            "rollout_targets": len(state["admin"]["rollout"]),
            "duplicate_hosts": 1,
            "cleanup_candidates": 1,
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


def build_admin_device_tokens_payload(state: dict, device_id: str) -> dict:
    tokens_by_device = state["admin"].setdefault(
        "device_tokens",
        {
            "device-1": [
                {
                    "token_hash": "token-hash-active",
                    "token_prefix": "tok-act",
                    "created_at": now_iso(minutes=1),
                    "expires_at": now_iso(minutes=5000),
                    "revoked_at": None,
                    "last_used_at": now_iso(minutes=30),
                    "is_active": True,
                },
                {
                    "token_hash": "token-hash-revoked",
                    "token_prefix": "tok-old",
                    "created_at": now_iso(minutes=-100),
                    "expires_at": now_iso(minutes=4000),
                    "revoked_at": now_iso(minutes=5),
                    "last_used_at": now_iso(minutes=4),
                    "is_active": False,
                },
            ],
            "device-2": [],
        },
    )
    tokens = deepcopy(tokens_by_device.get(device_id, []))
    return {
        "device_id": device_id,
        "summary": {
            "total_count": len(tokens),
            "active_count": sum(1 for item in tokens if item["is_active"]),
            "revoked_count": sum(1 for item in tokens if not item["is_active"]),
        },
        "tokens": tokens,
    }


def admin_module_rollout_mode_label(mode: str) -> str:
    if mode == "installed_devices":
        return "Обновлять установленные устройства"
    return "Только вручную"


def find_admin_module_family(state: dict, module_name: str) -> dict | None:
    for family in state["admin"]["modules"]["families"]:
        if family["module_name"] == module_name:
            return family
    return None


def update_admin_modules_rollout_settings(
    state: dict,
    *,
    preferred_version_rollout_mode: str | None = None,
    sync_after_preferred_change: bool | None = None,
) -> dict:
    settings = state["admin"]["modules"]["rollout_settings"]
    if preferred_version_rollout_mode is not None:
        settings["preferred_version_rollout_mode"] = preferred_version_rollout_mode
        settings["preferred_version_rollout_mode_label"] = admin_module_rollout_mode_label(
            preferred_version_rollout_mode
        )
    if sync_after_preferred_change is not None:
        settings["sync_after_preferred_change"] = sync_after_preferred_change
    return deepcopy(settings)


def set_admin_module_preferred_version(state: dict, *, module_name: str, version: str | None) -> tuple[dict | None, str | None]:
    family = find_admin_module_family(state, module_name)
    if not family:
        return None, "MODULE_NOT_FOUND"

    target_version = None
    if version is not None:
        for item in family["versions"]:
            if item["version"] == version:
                target_version = item
                break
        if target_version is None:
            return None, "VERSION_NOT_FOUND"
        if not target_version.get("file_exists", False):
            return None, "MODULE_ARCHIVE_MISSING"

    for item in family["versions"]:
        item["is_preferred"] = version is not None and item["version"] == version

    family["preferred_version"] = version
    family["preferred_assigned"] = version is not None

    settings = state["admin"]["modules"]["rollout_settings"]
    desired_updates = 0
    sync_enqueued = 0
    refresh_enqueued = 0
    if version is not None and settings["preferred_version_rollout_mode"] == "installed_devices":
        desired_updates = 2
        if settings["sync_after_preferred_change"]:
            sync_enqueued = desired_updates
            refresh_enqueued = desired_updates

    payload = {
        "module_name": module_name,
        "preferred_version": version,
        "updated_at": now_iso(minutes=32),
        "updated_by": ADMIN_LOGIN,
        "message": (
            f"Preferred-версия для {module_name} снята."
            if version is None
            else f"Preferred-версия для {module_name} обновлена на {version}."
        ),
        "rollout_summary": {
            "mode": settings["preferred_version_rollout_mode"],
            "should_sync": settings["sync_after_preferred_change"],
            "desired_updates": desired_updates,
            "sync_enqueued": sync_enqueued,
            "refresh_enqueued": refresh_enqueued,
        },
    }
    return payload, None


def build_admin_modules_payload(state: dict, query: str) -> dict:
    payload = deepcopy(state["admin"]["modules"])
    modules = payload["families"]
    if query:
        query_lower = query.lower()
        modules = [
            item
            for item in modules
            if query_lower in item["module_name"].lower()
            or any(query_lower in tool_id.lower() for tool_id in item.get("tool_ids", []))
            or any(query_lower in version["version"].lower() for version in item.get("versions", []))
        ]
    payload["summary"]["visible_count"] = len(modules)
    payload["summary"]["preferred_count"] = sum(1 for item in modules if item.get("preferred_assigned"))
    payload["summary"]["invalid_count"] = sum(
        1 for item in modules if item.get("validation_status") in {"warning", "failed"}
    )
    payload["summary"]["missing_files_count"] = sum(1 for item in modules if item.get("has_missing_files"))
    return {
        "query": query,
        "summary": payload["summary"],
        "rollout_settings": payload["rollout_settings"],
        "modules": modules,
    }


def build_admin_forms_payload(state: dict) -> dict:
    payload = deepcopy(state["admin"]["forms_builder"])
    return {
        "summary": payload["summary"],
        "capabilities": {
            "current_endpoint": "/api/web/admin/forms/current",
            "save_endpoint": "/api/web/admin/forms/save",
            "field_type_options": [
                {"value": "text", "label": "Текст"},
                {"value": "textarea", "label": "Большой текст"},
                {"value": "select", "label": "Список"},
                {"value": "radio", "label": "Переключатель"},
                {"value": "checkbox", "label": "Флажок"},
            ],
        },
        "forms": payload["forms"],
    }


def save_admin_forms_payload(state: dict, payload: dict) -> dict:
    forms = deepcopy(payload.get("forms") or [])
    fields_count = sum(len(form.get("fields") or []) for form in forms)
    required_fields_count = sum(
        1
        for form in forms
        for field in (form.get("fields") or [])
        if field.get("required")
    )
    current_version = str(state["admin"]["forms_builder"]["summary"]["version"])
    version_parts = [int(part) for part in current_version.split(".")]
    version_parts[-1] += 1
    next_version = ".".join(str(part) for part in version_parts)
    normalized_forms = []
    for form in forms:
        normalized_fields = []
        for field in form.get("fields") or []:
            normalized_fields.append(
                {
                    "key": str(field.get("key") or ""),
                    "label": str(field.get("label") or ""),
                    "type": str(field.get("type") or "text"),
                    "type_label": {
                        "text": "Текст",
                        "textarea": "Большой текст",
                        "select": "Список",
                        "radio": "Переключатель",
                        "checkbox": "Флажок",
                    }.get(str(field.get("type") or "text"), "Текст"),
                    "required": bool(field.get("required", False)),
                    "placeholder": str(field.get("placeholder") or ""),
                    "help_text": str(field.get("help_text") or ""),
                    "options": deepcopy(field.get("options") or []),
                    "visible_when": deepcopy(field.get("visible_when")) if field.get("visible_when") else None,
                }
            )
        normalized_forms.append(
            {
                "key": str(form.get("key") or ""),
                "request_kind": str(form.get("request_kind") or form.get("key") or ""),
                "title": str(form.get("title") or ""),
                "description": str(form.get("description") or ""),
                "fields": normalized_fields,
            }
        )

    state["admin"]["forms_builder"] = {
        "summary": {
            "pack_key": "request_forms",
            "version": next_version,
            "title": str(payload.get("title") or "Каталог заявок"),
            "description": str(payload.get("description") or ""),
            "forms_count": len(normalized_forms),
            "fields_count": fields_count,
            "required_fields_count": required_fields_count,
            "last_published_at": now_iso(minutes=30 + len(normalized_forms)),
            "last_published_by": ADMIN_LOGIN,
        },
        "forms": normalized_forms,
    }
    return {
        "summary": deepcopy(state["admin"]["forms_builder"]["summary"]),
        "forms": deepcopy(state["admin"]["forms_builder"]["forms"]),
        "message": (
            f"Каталог опубликован как версия {next_version}. "
            "Изменения уже активны в /help и в интерфейсе агента."
        ),
    }


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


def build_ticket_playbooks(ticket_state: dict) -> dict:
    ticket_id = ticket_state["ticket"]["ticket_id"]
    device_id = ticket_state["ticket"].get("device_id")
    return {
        "ticket_id": ticket_id,
        "device_id": device_id,
        "diagnostic_policy": {
            "suggested_playbooks": ["diagnose.profile_sync"],
            "auto_run_enabled": False,
            "auto_run_priorities": [],
            "requester_consent_required": False,
            "high_risk_consent_required": True,
            "attach_to_timeline": True,
            "attach_to_passport": True,
            "attach_as_evidence": True,
            "reroute_by_result": {},
        },
        "playbooks": [
            {
                "playbook_version_id": 1,
                "key": "diagnose.profile_sync",
                "name": "Диагностика синхронизации профиля",
                "domain": "identity",
                "version": "1.0",
                "status": "published",
                "blocks_count": 3,
                "required_tools": ["network.diagnostics"],
                "missing_tools": [],
                "missing_params": [],
                "can_run": bool(device_id),
                "readiness_label": "Готов к запуску" if device_id else "Нет устройства",
                "updated_at": now_iso(minutes=20),
            }
        ],
        "recent_runs": [],
    }


def build_ticket_passport(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": "draft",
        "passport": None,
        "requirements": {
            "required_sections": ["problem", "root_cause", "solution", "verification"],
            "require_official_passport": True,
            "missing_facts": [
                {
                    "required_fact": "root_cause",
                    "section_key": "cause",
                    "source": "passport",
                    "current_value": None,
                    "requester_visible_label": "Причина установлена",
                    "severity": "warning",
                    "candidate_count": 0,
                    "blocking_for_closure": True,
                }
            ],
            "missing_count": 1,
            "blocking_missing_count": 1,
            "export_preview": {},
            "knowledge_draft_hints": {},
        },
        "evidence": [],
        "actions": [],
        "approvals": [],
        "related_objects": [],
    }


def build_ticket_passport_readiness(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "status": "draft",
        "done": 1,
        "total": 4,
        "items": [
            {"key": "problem_identified", "label": "Проблема идентифицирована", "status": "done"},
            {"key": "cause_found", "label": "Причина установлена", "status": "pending"},
            {"key": "solution_applied", "label": "Решение применено", "status": "pending"},
            {"key": "verified_and_closed", "label": "Проверка и закрытие", "status": "pending"},
        ],
    }


def build_ticket_sla_ola() -> dict:
    return {
        "first_response": {
            "due_at": now_iso(minutes=18),
            "remaining_seconds": 1080,
            "target_seconds": 1800,
            "status": "ok",
        },
        "resolution": {
            "due_at": now_iso(minutes=240),
            "remaining_seconds": 14400,
            "target_seconds": 28800,
            "status": "ok",
        },
        "ola_ack": {
            "due_at": now_iso(minutes=30),
            "remaining_seconds": 1800,
            "target_seconds": 3600,
            "status": "ok",
        },
        "ola_processing": {
            "due_at": now_iso(minutes=120),
            "remaining_seconds": 7200,
            "target_seconds": 14400,
            "status": "ok",
        },
    }


def build_ticket_knowledge(ticket_state: dict) -> dict:
    ticket = ticket_state["ticket"]
    return {
        "ticket_id": ticket["ticket_id"],
        "similar_tickets": [
            {
                "id": "ticket-kb-1",
                "number": "T-199991",
                "subject": "Профиль не синхронизируется после обновления",
                "resolution_summary": "Проверить доступность policy-сервера и перезапустить sync job.",
            }
        ],
        "articles": [
            {
                "id": "KB-PROFILE-SYNC",
                "title": "Проверка синхронизации рабочего профиля",
                "url": "/app/knowledge/KB-PROFILE-SYNC",
            }
        ],
        "ai_summary": {
            "text": "AI-рекомендация / Бета: проверьте канал до policy-сервера и последний sync job перед изменениями.",
            "sources": ["KB-PROFILE-SYNC", "T-199991"],
            "confidence": "medium",
            "source_count": 2,
        },
        "diagnostics": {
            "provider": "fixture_knowledge_provider",
            "provider_version": "local-v1",
            "provider_status": "ok",
            "external_provider_status": "not_configured",
            "fallback_reason": None,
            "catalog_entry_count": 1,
            "query_tokens": ["profile", "sync"],
            "source_counts": {"manual_kb": 1, "catalog": 0, "similar_ticket": 1},
            "query_signals": ["fixture_kb", "similar_ticket"],
            "article_matches": {
                "KB-PROFILE-SYNC": {"source_type": "manual_kb", "score": 90, "match_reasons": ["fixture_kb"]}
            },
            "similar_ticket_matches": {
                "ticket-kb-1": {"source_type": "similar_ticket", "score": 80, "match_reasons": ["similar_ticket"]}
            },
        },
    }


def build_ticket_closure_plan(ticket_id: str) -> dict:
    return {
        "ticket_id": ticket_id,
        "ready_for_resolution": False,
        "missing_count": 1,
        "total": 4,
        "evidence_candidate_count": 0,
        "recommended_next_action": "Заполнить причину",
        "blockers": [
            {
                "key": "root_cause",
                "label": "Причина установлена",
                "met": False,
                "detail": "Укажите причину перед закрытием.",
                "source": "passport",
                "action_kind": "edit_resolution",
                "action_label": "Заполнить решение",
                "severity": "warning",
                "candidate_count": 0,
                "fact_key": "root_cause",
                "blocking_for_closure": True,
            }
        ],
    }


def build_ticket_workspace(state: dict, ticket_id: str) -> dict:
    ticket_state = state["tickets"][ticket_id]
    return {
        "detail": build_ticket_detail(state, ticket_id),
        "tools": deepcopy(ticket_state["tools"]),
        "playbooks": build_ticket_playbooks(ticket_state),
        "passport": build_ticket_passport(ticket_id),
        "knowledge": build_ticket_knowledge(ticket_state),
        "sla_ola": build_ticket_sla_ola(),
        "passport_readiness": build_ticket_passport_readiness(ticket_id),
        "closure_plan": build_ticket_closure_plan(ticket_id),
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
            "default_workspace": "support",
            "available_workspaces": ["support"],
            "permissions": SUPPORT_PERMISSIONS,
        }
    elif payload.get("login") == ADMIN_LOGIN and payload.get("password") == ADMIN_PASSWORD:
        session_user = {
            "user_login": ADMIN_LOGIN,
            "actor_role": ADMIN_ACTOR_ROLE,
            "auth_type": "ui_token",
            "default_workspace": "admin",
            "available_workspaces": ["admin", "support"],
            "permissions": ADMIN_PERMISSIONS,
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


async def handle_realtime_bootstrap(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return json_success(
        {
            "transport": "ws_ui_bridge",
            "auth_mode": "session_cookie",
            "hello_message_type": "ui_hello",
            "socket_url": "/ws_ui",
            "ping_interval_ms": 20000,
            "channels": [
                {
                    "channel": "support.queue",
                    "scope": "ticket",
                    "subscribe_message_type": "subscribe_ticket",
                    "unsubscribe_message_type": "unsubscribe_ticket",
                    "supports_catchup": True,
                    "supports_live_only": True,
                },
                {
                    "channel": "ticket.stream",
                    "scope": "ticket",
                    "subscribe_message_type": "subscribe_ticket",
                    "unsubscribe_message_type": "unsubscribe_ticket",
                    "supports_catchup": True,
                    "supports_live_only": True,
                },
                {
                    "channel": "admin.devices",
                    "scope": "device",
                    "subscribe_message_type": "subscribe_device",
                    "unsubscribe_message_type": "unsubscribe_device",
                    "supports_catchup": True,
                    "supports_live_only": True,
                },
                {
                    "channel": "tech.feed",
                    "scope": "device",
                    "subscribe_message_type": "subscribe_device",
                    "unsubscribe_message_type": "unsubscribe_device",
                    "supports_catchup": True,
                    "supports_live_only": True,
                },
            ],
        }
    )


async def handle_ws_ui(request: web.Request) -> web.StreamResponse:
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    state = request.app["fixture_state"]
    authenticated = False
    ticket_subscriptions: set[str] = set()
    device_subscriptions: set[str] = set()

    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT:
                continue

            data = json.loads(msg.data)
            message_type = data.get("type")

            if message_type == "ui_hello":
                unauthorized = require_session(request)
                if unauthorized:
                    await ws.send_json({"type": "error", "error": "Authentication required"})
                    await ws.close()
                    return ws

                authenticated = True
                session_user = state.get("session_user") or {
                    "user_login": SUPPORT_LOGIN,
                    "actor_role": SUPPORT_ACTOR_ROLE,
                    "default_workspace": "support",
                    "available_workspaces": ["support"],
                }
                await ws.send_json(
                    {
                        "type": "ui_hello_ack",
                        "connection_id": "fixture-connection",
                        "role": session_user["actor_role"],
                    }
                )
                continue

            if not authenticated:
                await ws.send_json(
                    {
                        "type": "error",
                        "error": "Authentication required. Send ui_hello first.",
                    }
                )
                continue

            if message_type == "subscribe_ticket":
                ticket_id = str(data.get("ticket_id") or "").strip()
                since_event_id = int(data.get("since_event_id", 0) or 0)
                if not ticket_id:
                    await ws.send_json({"type": "error", "error": "Missing ticket_id"})
                    continue

                ticket_subscriptions.add(ticket_id)
                state["ws_ticket_subscribers"].setdefault(ticket_id, set()).add(ws)
                await ws.send_json(
                    {
                        "type": "catchup_done",
                        "scope": "ticket",
                        "id": ticket_id,
                        "last_event_id": since_event_id,
                        "truncated": False,
                    }
                )
                await ws.send_json(
                    {
                        "type": "subscribe_ack",
                        "ticket_id": ticket_id,
                        "since_event_id": since_event_id,
                    }
                )
                continue

            if message_type == "unsubscribe_ticket":
                ticket_id = str(data.get("ticket_id") or "").strip()
                ticket_subscriptions.discard(ticket_id)
                state["ws_ticket_subscribers"].get(ticket_id, set()).discard(ws)
                await ws.send_json({"type": "unsubscribe_ack", "ticket_id": ticket_id})
                continue

            if message_type == "subscribe_device":
                device_id = str(data.get("device_id") or "").strip()
                since_event_id = int(data.get("since_event_id", 0) or 0)
                if not device_id:
                    await ws.send_json({"type": "error", "error": "Missing device_id"})
                    continue

                device_subscriptions.add(device_id)
                state["ws_device_subscribers"].setdefault(device_id, set()).add(ws)
                await ws.send_json(
                    {
                        "type": "catchup_done",
                        "scope": "device",
                        "id": device_id,
                        "last_event_id": since_event_id,
                        "truncated": False,
                    }
                )
                await ws.send_json(
                    {
                        "type": "subscribe_ack",
                        "device_id": device_id,
                        "since_event_id": since_event_id,
                    }
                )
                continue

            if message_type == "unsubscribe_device":
                device_id = str(data.get("device_id") or "").strip()
                device_subscriptions.discard(device_id)
                state["ws_device_subscribers"].get(device_id, set()).discard(ws)
                await ws.send_json({"type": "unsubscribe_ack", "device_id": device_id})
                continue

            if message_type == "ping":
                await ws.send_json({"type": "pong", "ts": now_iso(minutes=30)})
                continue

            await ws.send_json({"type": "error", "error": f"Unknown message type: {message_type}"})
    finally:
        for ticket_id in ticket_subscriptions:
            state["ws_ticket_subscribers"].get(ticket_id, set()).discard(ws)
        for device_id in device_subscriptions:
            state["ws_device_subscribers"].get(device_id, set()).discard(ws)

    return ws


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


async def handle_support_workspace_summary(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    tickets = list(state["tickets"].values())
    return json_success(
        {
            "views": {
                "needs_action": sum(1 for ticket in tickets if ticket["requires_operator_action"]),
                "sla_risk": 0,
                "unassigned": sum(1 for ticket in tickets if not ticket.get("assignee_id")),
                "requester_replied": sum(1 for ticket in tickets if ticket.get("unread_user_messages", 0) > 0),
            },
            "queues": [
                {
                    "id": "queue-l1",
                    "code": "l1",
                    "name": "Линия поддержки L1",
                    "count": len(tickets),
                }
            ],
            "smart_view_counts": [],
            "smart_view_options": [],
        }
    )


def command_center_item(ticket: dict) -> dict:
    return {
        "id": f"operator-action:{ticket['id']}",
        "ticket_id": ticket["id"],
        "ticket_number": ticket["code"],
        "title": ticket["title"],
        "status": ticket["status"],
        "priority": ticket["priority"],
        "queue": "Линия поддержки L1",
        "assignee": ticket.get("assignee_id"),
        "requester_name": ticket.get("requester_name"),
        "service_code": "profile-sync",
        "offering_code": "support",
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
        "next_action_owner": "support",
        "next_action_due_at": None,
        "requires_operator_action": ticket.get("requires_operator_action", False),
        "unread_user_messages": ticket.get("unread_user_messages", 0),
        "sla": {"state": "unknown", "due_at": None, "remaining_seconds": None},
        "ola": {"state": "unknown", "due_at": None, "remaining_seconds": None},
        "operation": None,
        "agent": {
            "device_id": ticket.get("device_id"),
            "connection_state": "online" if ticket.get("device_id") else "unknown",
            "last_seen_at": now_iso(minutes=12) if ticket.get("device_id") else None,
        },
        "diagnostics": {"recommended": True, "profile_code": "profile_sync", "reason": "Проверить sync job."},
        "closure": {"blocked": True, "missing_count": 1, "primary_blocker": "Нужна причина решения."},
        "similar_group": None,
        "reason": "Требуется действие оператора по следующему шагу.",
        "href": f"/app/tickets/{ticket['id']}",
    }


async def handle_support_command_center(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    items = [
        command_center_item(ticket)
        for ticket in state["tickets"].values()
        if ticket.get("requires_operator_action")
    ]
    return json_success(
        {
            "generated_at": now_iso(minutes=35),
            "scope": request.query.get("scope", "team"),
            "filters": {
                "queue": request.query.get("queue"),
                "assignee": request.query.get("assignee"),
                "query": request.query.get("query"),
                "window_hours": int(request.query.get("window_hours", "24")),
                "limit_per_section": int(request.query.get("limit_per_section", "8")),
            },
            "summary": {
                "total_attention_items": len(items),
                "critical_count": 0,
                "warning_count": len(items),
                "info_count": 0,
                "new_unassigned_count": 0,
                "operator_action_count": len(items),
                "unread_user_messages_count": 0,
                "sla_risk_count": 0,
                "ola_risk_count": 0,
                "pending_approval_count": 0,
                "pending_consent_count": 0,
                "failed_operation_count": 0,
                "agent_offline_active_count": 0,
                "diagnostics_recommended_count": len(items),
                "closure_blocked_count": len(items),
                "similar_spikes_count": 0,
            },
            "sections": [
                {
                    "key": "operator_action",
                    "title": "Действия оператора",
                    "description": "Тикеты, где следующий шаг принадлежит поддержке.",
                    "severity": "warning",
                    "count": len(items),
                    "updated_at": now_iso(minutes=35),
                    "items": items,
                    "action": {"label": "Открыть очередь", "href": "/app/tickets"},
                }
            ]
            if items
            else [],
            "metadata": {"fixture": True},
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


async def handle_support_queue_saved_views(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    views = request.app["fixture_state"]["support_queue_saved_views"]
    default_view = next((view for view in views if view.get("is_default")), None)
    return json_success(
        {
            "views": deepcopy(views),
            "default_view_id": default_view["id"] if default_view else None,
            "default_columns": default_view["columns"] if default_view else [
                "number",
                "subject",
                "requester",
                "priority",
                "status",
                "next_action",
                "sla",
                "queue",
                "assignee",
                "last_event",
                "unread",
            ],
        }
    )


async def handle_support_queue_saved_view_create(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    body = await request.json()
    view = {
        "id": f"fixture-view-{next(state['saved_view_counter'])}",
        "name": body.get("name") or "Saved view",
        "scope": body.get("scope") or "personal",
        "owner_actor_id": SUPPORT_LOGIN,
        "queue_id": body.get("queue_id"),
        "filters": body.get("filters") or {},
        "columns": body.get("columns") or [],
        "sort": body.get("sort") or [],
        "is_favorite": bool(body.get("is_favorite")),
        "is_default": bool(body.get("is_default")),
        "created_at": now_iso(minutes=0),
        "updated_at": now_iso(minutes=0),
        "created_by": SUPPORT_LOGIN,
        "updated_by": SUPPORT_LOGIN,
    }
    if view["is_default"]:
        for existing in state["support_queue_saved_views"]:
            existing["is_default"] = False
    state["support_queue_saved_views"].insert(0, view)
    return json_success(deepcopy(view))


async def handle_support_queue_saved_view_update(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    view_id = request.match_info["view_id"]
    body = await request.json()
    for view in state["support_queue_saved_views"]:
        if view["id"] != view_id:
            continue
        view.update(
            {
                "name": body.get("name") or view["name"],
                "scope": body.get("scope") or view["scope"],
                "queue_id": body.get("queue_id"),
                "filters": body.get("filters") or {},
                "columns": body.get("columns") or [],
                "sort": body.get("sort") or [],
                "is_favorite": bool(body.get("is_favorite")),
                "is_default": bool(body.get("is_default")),
                "updated_at": now_iso(minutes=1),
                "updated_by": SUPPORT_LOGIN,
            }
        )
        if view["is_default"]:
            for existing in state["support_queue_saved_views"]:
                if existing["id"] != view_id:
                    existing["is_default"] = False
        return json_success(deepcopy(view))
    raise web.HTTPNotFound()


async def handle_support_queue_saved_view_delete(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    view_id = request.match_info["view_id"]
    state["support_queue_saved_views"] = [
        view for view in state["support_queue_saved_views"] if view["id"] != view_id
    ]
    return json_success({"deleted": True, "id": view_id})


async def handle_support_ticket_detail(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_detail(state, ticket_id))


async def handle_support_ticket_workspace(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_workspace(state, ticket_id))


async def handle_support_ticket_tools(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(deepcopy(state["tickets"][ticket_id]["tools"]))


async def handle_support_ticket_playbooks(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_playbooks(state["tickets"][ticket_id]))


async def handle_support_ticket_knowledge(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_knowledge(state["tickets"][ticket_id]))


async def handle_support_ticket_passport(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    ticket_id = request.match_info["ticket_id"]
    state = request.app["fixture_state"]
    if ticket_id not in state["tickets"]:
        raise web.HTTPNotFound()
    return json_success(build_ticket_passport(ticket_id))


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
    await broadcast_fixture_ticket_event(
        state,
        ticket_id,
        {
            "type": "ticket_event_committed",
            "ticket_id": ticket_id,
            "event_id": message["event_id"],
            "event_type": "chat_message",
            "operation_id": None,
            "agent_seq": None,
            "ts": timestamp,
            "payload": {
                "message_id": message_id,
                "text": message["text"],
            },
        },
    )
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
    await broadcast_fixture_ticket_event(
        state,
        ticket_id,
        {
            "type": "ticket_event_committed",
            "ticket_id": ticket_id,
            "event_id": next(state["message_counter"]),
            "event_type": "status_changed",
            "operation_id": None,
            "agent_seq": None,
            "ts": ticket_state["ticket"]["updated_at"],
            "payload": {
                "status": to_status,
                "status_label": ticket_state["ticket"]["status_label"],
            },
        },
    )
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
    await broadcast_fixture_ticket_event(
        state,
        ticket_id,
        {
            "type": "ticket_event_committed",
            "ticket_id": ticket_id,
            "event_id": result_event["event_id"],
            "event_type": "tool_call_result",
            "operation_id": operation_id,
            "agent_seq": None,
            "ts": finished_at,
            "payload": {
                "tool_name": tool_name,
                "status": "success",
            },
        },
    )
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
                "forms_builder",
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


async def handle_admin_device_tokens(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    return json_success(build_admin_device_tokens_payload(state, request.match_info["device_id"]))


async def handle_admin_device_token_revoke(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    device_id = request.match_info["device_id"]
    data = await request.json()
    token_hash = str(data.get("token_hash") or "")
    tokens = build_admin_device_tokens_payload(state, device_id)["tokens"]
    for item in tokens:
        if item["token_hash"] == token_hash:
            item["is_active"] = False
            item["revoked_at"] = now_iso(minutes=40)
    state["admin"].setdefault("device_tokens", {})[device_id] = tokens
    return json_success(build_admin_device_tokens_payload(state, device_id))


async def handle_web_settings(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return json_success(
        {
            "capabilities": {"can_write": True, "actor_role": ADMIN_ACTOR_ROLE},
            "overview": {
                "queues_count": 1,
                "active_queues_count": 1,
                "routing_rules_count": 0,
                "active_routing_rules_count": 0,
                "sla_policies_count": 0,
                "calendars_count": 0,
                "resolution_codes_count": 0,
                "audit_records_count": 0,
            },
            "routing_builder": {"operators": [], "fields": [], "forms": []},
            "ticket_settings": {
                "internal_statuses": [
                    {
                        "value": "new",
                        "label": "Новая",
                        "requester_status": "open",
                        "requester_label": "Открыто",
                        "next_action_owner": "support",
                        "stage": "intake",
                        "waits": False,
                        "terminal": False,
                    }
                ],
                "requester_statuses": [{"value": "open", "label": "Открыто", "internal_statuses": ["new"]}],
                "next_action_owners": [{"value": "support", "label": "Поддержка", "internal_statuses": ["new"]}],
                "workflow_profiles": [
                    {
                        "ticket_type": "incident",
                        "label": "Инцидент",
                        "purpose": "Fixture workflow for Playwright.",
                        "suggested_path": ["new", "resolved"],
                        "allowed_statuses": ["new", "resolved"],
                        "required_create_fields": [],
                        "required_resolve_fields": ["resolution_code"],
                        "requires_approval": False,
                        "requires_change_plan": False,
                        "requires_action_log": True,
                        "evidence_required_for_priorities": ["P1"],
                        "transitions": {"new": ["resolved"]},
                    }
                ],
                "ticket_types": [
                    {
                        "code": "incident",
                        "version": "1.0",
                        "title": "Инцидент",
                        "description": "Fixture ticket type.",
                        "default_workflow_profile_id": "incident",
                        "default_priority_policy_code": None,
                        "default_routing_policy_code": None,
                        "default_sla_policy_id": None,
                        "default_sla_policy_code": None,
                        "default_ola_policy_code": None,
                        "default_approval_policy_code": None,
                        "default_diagnostic_policy_code": None,
                        "default_closure_policy_code": None,
                        "default_visibility_policy_code": None,
                        "default_notification_policy_code": None,
                        "default_reporting_policy_code": None,
                        "feature_flags": {},
                    }
                ],
                "request_templates": [],
                "process_schema": [
                    {
                        "key": "intake",
                        "label": "Приём",
                        "meaning": "Первичная обработка обращения.",
                        "source": "fixture",
                        "ui_surface": "settings",
                        "status": "active",
                    }
                ],
                "support_lines": [
                    {
                        "code": "l1",
                        "label": "Линия поддержки L1",
                        "competence_depth": "basic",
                        "routing_role": "owner",
                        "status": "active",
                    }
                ],
                "priority_model": {
                    "direct_user_priority_choice": False,
                    "impact_levels": ["low"],
                    "urgency_levels": ["normal"],
                    "importance_sources": ["service"],
                    "modifiers": [],
                },
                "governance": {
                    "fsm_mode": "strict",
                    "legacy_role_fields": False,
                    "auto_close_hours": 72,
                    "resolution_validation_mode": "required",
                    "require_root_cause_priorities": ["P1"],
                    "evidence_gate_enabled": True,
                    "passport_enabled": True,
                    "requester_confirmation_required": False,
                },
                "operational_flags": {
                    "admin_config_api_enabled": True,
                    "admin_config_write_enabled": True,
                    "auditor_role_enabled": True,
                    "sla_calendar_enabled": True,
                    "ola_enabled": True,
                    "retention_enabled": False,
                    "retention_dry_run": True,
                    "events_hot_retention_days": 30,
                    "admin_audit_hot_retention_days": 30,
                    "take_queue_mode": "common",
                    "take_queue_common_code": "l1",
                    "take_queue_test_code": "l1-test",
                },
            },
            "queues": [],
            "routing_rules": [],
            "sla_policies": [],
            "calendars": [],
            "resolution_codes": [],
            "audit": [],
        }
    )


async def handle_notification_preferences(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return web.json_response(
        {
            "status": "ok",
            "preferences": {
                "mute_internal": False,
                "muted_event_types": [],
                "suppress_self": True,
            },
        }
    )


async def handle_notifications(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return web.json_response(
        {
            "status": "ok",
            "notifications": [
                {
                    "id": 1,
                    "actor_id": "fixture",
                    "ticket_id": "ticket-1",
                    "event_type": "device_fingerprint_mismatch",
                    "payload": {"message": "fingerprint mismatch"},
                    "is_read": False,
                    "created_at": now_iso(minutes=45),
                    "read_at": None,
                }
            ],
        }
    )


async def handle_admin_tech_alerts(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    return web.json_response(
        {
            "status": "ok",
            "alerts": [
                {
                    "kind": "inventory_env_uuid_duplicates",
                    "severity": "warning",
                    "title": "env_uuid-дубли",
                    "description": "Найдены тестовые дубли ADMIN-2.",
                    "action": "/app/admin/inventory",
                }
            ],
        }
    )


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


async def handle_admin_modules(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    query = str(request.query.get("query", "") or "").strip()
    return json_success(build_admin_modules_payload(state, query))


async def handle_admin_forms_current(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    return json_success(build_admin_forms_payload(state))


async def handle_admin_forms_save(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    payload = await request.json()
    return json_success(save_admin_forms_payload(state, payload))


async def handle_admin_modules_rollout_settings_patch(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    payload = await request.json()
    rollout_mode = payload.get("preferred_version_rollout_mode")
    if rollout_mode is not None and rollout_mode not in {"manual", "installed_devices"}:
        return json_error("Некорректный режим preferred-rollout", status=400, error_code="VALIDATION_ERROR")
    sync_after = payload.get("sync_after_preferred_change")
    if sync_after is not None:
        sync_after = bool(sync_after)
    settings = update_admin_modules_rollout_settings(
        state,
        preferred_version_rollout_mode=rollout_mode,
        sync_after_preferred_change=sync_after,
    )
    return json_success(settings)


async def handle_admin_module_preferred_patch(request: web.Request) -> web.Response:
    unauthorized = require_session(request)
    if unauthorized:
        return unauthorized
    state = request.app["fixture_state"]
    module_name = request.match_info["module_name"]
    payload = await request.json()
    version = payload.get("version")
    if version is not None:
        version = str(version).strip() or None
    action_payload, error_code = set_admin_module_preferred_version(state, module_name=module_name, version=version)
    if error_code == "MODULE_NOT_FOUND":
        return json_error("Семейство модулей не найдено", status=404, error_code=error_code)
    if error_code == "VERSION_NOT_FOUND":
        return json_error("Версия модуля не найдена в реестре", status=404, error_code=error_code)
    if error_code == "MODULE_ARCHIVE_MISSING":
        return json_error(
            "Архив для этой версии отсутствует, нужен повторный upload",
            status=409,
            error_code=error_code,
        )
    return json_success(action_payload)


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
    state["admin"]["device_updates"][device_id] = deepcopy(payload)
    await broadcast_fixture_device_event(
        state,
        device_id,
        {
            "type": "operation_updated",
            "operation_id": operation_id,
            "ticket_id": None,
            "device_id": device_id,
            "status": "queued",
            "updated_at": now_iso(minutes=19),
            "error": None,
        },
    )
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
            web.get("/api/web/realtime/bootstrap", handle_realtime_bootstrap),
            web.get("/api/web/support/bootstrap", handle_support_bootstrap),
            web.get("/api/web/support/workspace/summary", handle_support_workspace_summary),
            web.get("/api/web/support/command-center", handle_support_command_center),
            web.get("/api/web/support/queue", handle_support_queue),
            web.get("/api/web/support/queue/saved-views", handle_support_queue_saved_views),
            web.post("/api/web/support/queue/saved-views", handle_support_queue_saved_view_create),
            web.put("/api/web/support/queue/saved-views/{view_id}", handle_support_queue_saved_view_update),
            web.delete("/api/web/support/queue/saved-views/{view_id}", handle_support_queue_saved_view_delete),
            web.get("/api/web/support/tickets/{ticket_id}/workspace", handle_support_ticket_workspace),
            web.get("/api/web/support/tickets/{ticket_id}/knowledge-suggestions", handle_support_ticket_knowledge),
            web.get("/api/web/support/tickets/{ticket_id}/playbooks", handle_support_ticket_playbooks),
            web.get("/api/web/support/tickets/{ticket_id}/passport", handle_support_ticket_passport),
            web.get("/api/web/support/tickets/{ticket_id}", handle_support_ticket_detail),
            web.get("/api/web/support/tickets/{ticket_id}/tools", handle_support_ticket_tools),
            web.post("/api/web/support/tickets/{ticket_id}/messages", handle_support_ticket_message),
            web.post("/api/web/support/tickets/{ticket_id}/status", handle_support_ticket_status),
            web.post("/api/web/support/tickets/{ticket_id}/tools/run", handle_support_ticket_tool_run),
            web.get("/api/web/admin/bootstrap", handle_admin_bootstrap),
            web.get("/api/web/admin/observer/quick", handle_admin_observer_quick),
            web.get("/api/web/admin/observer/traces", handle_admin_observer_traces),
            web.get("/api/web/admin/observer/traces/{trace_id}", handle_admin_observer_trace_detail),
            web.get("/api/web/admin/forms/current", handle_admin_forms_current),
            web.post("/api/web/admin/forms/save", handle_admin_forms_save),
            web.get("/api/web/admin/modules", handle_admin_modules),
            web.patch("/api/web/admin/modules/rollout_settings", handle_admin_modules_rollout_settings_patch),
            web.patch("/api/web/admin/modules/{module_name}/preferred", handle_admin_module_preferred_patch),
            web.get("/api/web/admin/devices", handle_admin_devices),
            web.get("/api/web/admin/devices/{device_id}/tokens", handle_admin_device_tokens),
            web.post("/api/web/admin/devices/{device_id}/tokens/revoke", handle_admin_device_token_revoke),
            web.get("/api/web/admin/devices/{device_id}/updates", handle_admin_device_updates),
            web.post("/api/web/admin/devices/{device_id}/updates/run", handle_admin_device_update_run),
            web.get("/api/web/settings", handle_web_settings),
            web.get("/api/notifications/preferences", handle_notification_preferences),
            web.post("/api/notifications/preferences", handle_notification_preferences),
            web.get("/api/notifications", handle_notifications),
            web.get("/api/admin/tech/alerts", handle_admin_tech_alerts),
            web.get("/api/web/notifications/preferences", handle_notification_preferences),
            web.post("/api/web/notifications/preferences", handle_notification_preferences),
            web.get("/api/web/notifications", handle_notifications),
            web.get("/api/web/admin/tech/alerts", handle_admin_tech_alerts),
            web.get("/assets/{asset_path:.*}", handle_webapp_asset),
            web.get("/favicon.svg", handle_webapp_public_asset),
            web.get("/ws_ui", handle_ws_ui),
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
