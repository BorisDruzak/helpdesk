#!/usr/bin/env python3
"""Local fixture server for Playwright checks of the new support workspace."""

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
    return json_success(
        {
            "user_login": SUPPORT_LOGIN,
            "actor_role": SUPPORT_ACTOR_ROLE,
            "auth_type": "ui_token",
        }
    )


async def handle_session_login(request: web.Request) -> web.Response:
    payload = await request.json()
    if payload.get("login") != SUPPORT_LOGIN or payload.get("password") != SUPPORT_PASSWORD:
        return json_error("Неверный логин или пароль.", status=401, error_code="INVALID_CREDENTIALS")

    response = json_success(
        {
            "user_login": SUPPORT_LOGIN,
            "actor_role": SUPPORT_ACTOR_ROLE,
            "auth_type": "ui_token",
        }
    )
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
