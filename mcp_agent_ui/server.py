#!/usr/bin/env python3
"""
MCP-сервер для взаимодействия с UI Bridge агента (pc_agent).

Вызывает HTTP API UI Bridge (по умолчанию http://127.0.0.1:8765).
Агент должен быть запущен с включённым UI Bridge (ui.enabled: true).

Переменные окружения:
  AGENT_UI_BASE_URL — базовый URL UI Bridge (по умолчанию http://127.0.0.1:8765)
"""

import asyncio
import json
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

BASE_URL = os.environ.get("AGENT_UI_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
DEFAULT_TIMEOUT = 30.0

server = Server("agent-ui-bridge")


def _tool_result(text: str) -> list[TextContent]:
    return [TextContent(type="text", text=text)]


def _format_response(data: Any) -> str:
    if isinstance(data, (dict, list)):
        return json.dumps(data, ensure_ascii=False, indent=2)
    return str(data)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="agent_ui_health",
            description="Проверка доступности UI Bridge агента (GET /health). Возвращает status, service, subscribers.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="agent_ui_events",
            description="Получить одно событие из UI Bridge (long-poll GET /ui/events). Таймаут до 30 сек. События: job_started, consent_required и др.",
            inputSchema={
                "type": "object",
                "properties": {
                    "timeout_sec": {
                        "type": "number",
                        "description": "Таймаут ожидания в секундах (по умолчанию 30)",
                        "default": 30,
                    },
                },
            },
        ),
        Tool(
            name="agent_ui_consent_decision",
            description="Отправить решение по запросу согласия (POST /ui/consent_decision). То же действие, что кнопки Approve/Reject в GUI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Идентификатор задачи"},
                    "consent_token": {"type": "string", "description": "Токен согласия"},
                    "approved": {"type": "boolean", "description": "true — одобрить, false — отклонить"},
                    "reason": {"type": "string", "description": "Причина (опционально)"},
                },
                "required": ["job_id", "consent_token", "approved"],
            },
        ),
        Tool(
            name="agent_ui_stop_recording",
            description="Остановить запись экрана по operation_id (POST /ui/stop_recording). Эквивалент кнопки STOP в GUI.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation_id": {"type": "string", "description": "Идентификатор операции записи"},
                },
                "required": ["operation_id"],
            },
        ),
        Tool(
            name="agent_ui_get_settings",
            description="Получить текущие настройки агента для GUI (GET /ui/settings).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="agent_ui_update_settings",
            description="Обновить настройки агента (POST /ui/settings). Тело — объект с полями для обновления.",
            inputSchema={
                "type": "object",
                "properties": {
                    "settings": {
                        "type": "object",
                        "description": "Объект с полями настроек (например autostart_gui, server_url)",
                    },
                },
                "required": ["settings"],
            },
        ),
        Tool(
            name="agent_ui_test_connection",
            description="Проверить подключение к серверу (POST /ui/settings/test_connection).",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "object", "description": "Опциональный JSON для теста"},
                },
            },
        ),
        Tool(
            name="agent_ui_restart",
            description="Запросить перезапуск агента (POST /ui/agent/restart). Работает только если обработчик настроен.",
            inputSchema={
                "type": "object",
                "properties": {
                    "payload": {"type": "object", "description": "Опциональный JSON"},
                },
            },
        ),
        Tool(
            name="agent_ui_request_support",
            description="Отправить запрос в поддержку (POST /ui/request_support). Опционально: title, reason, severity, context.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "reason": {"type": "string"},
                    "severity": {"type": "string"},
                    "context": {"type": "object"},
                },
            },
        ),
        Tool(
            name="agent_ui_chat_send",
            description="Отправить сообщение в чат тикета (POST /ui/chat_send). То же действие, что отправка сообщения в GUI. Требуются ticket_id и text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "Идентификатор тикета"},
                    "text": {"type": "string", "description": "Текст сообщения"},
                    "from_role": {"type": "string", "description": "Роль отправителя (по умолчанию user)", "default": "user"},
                    "attachment_refs": {"type": "array", "items": {"type": "string"}, "description": "Список artifact_id вложений"},
                    "metadata": {"type": "object", "description": "Метаданные сообщения"},
                },
                "required": ["ticket_id", "text"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=DEFAULT_TIMEOUT) as client:
        try:
            if name == "agent_ui_health":
                r = await client.get("/health")
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_events":
                timeout = arguments.get("timeout_sec", 30)
                r = await client.get("/ui/events", timeout=timeout)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_consent_decision":
                payload = {
                    "job_id": arguments["job_id"],
                    "consent_token": arguments["consent_token"],
                    "approved": bool(arguments["approved"]),
                }
                if arguments.get("reason") is not None:
                    payload["reason"] = arguments["reason"]
                r = await client.post("/ui/consent_decision", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_stop_recording":
                r = await client.post(
                    "/ui/stop_recording",
                    json={"operation_id": arguments["operation_id"]},
                )
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_get_settings":
                r = await client.get("/ui/settings")
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_update_settings":
                payload = arguments.get("settings") if "settings" in arguments else arguments
                if not payload:
                    return _tool_result("Ошибка: укажите объект settings с полями для обновления.")
                r = await client.post("/ui/settings", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_test_connection":
                payload = arguments.get("payload", {})
                r = await client.post("/ui/settings/test_connection", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_restart":
                payload = arguments.get("payload", {})
                r = await client.post("/ui/agent/restart", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_request_support":
                payload = {
                    k: v
                    for k in ("title", "reason", "severity", "context")
                    if (v := arguments.get(k)) is not None
                }
                r = await client.post("/ui/request_support", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

            if name == "agent_ui_chat_send":
                payload = {
                    "ticket_id": arguments["ticket_id"],
                    "text": arguments["text"],
                }
                if arguments.get("from_role") is not None:
                    payload["from_role"] = arguments["from_role"]
                if arguments.get("attachment_refs") is not None:
                    payload["attachment_refs"] = arguments["attachment_refs"]
                if arguments.get("metadata") is not None:
                    payload["metadata"] = arguments["metadata"]
                r = await client.post("/ui/chat_send", json=payload)
                r.raise_for_status()
                return _tool_result(_format_response(r.json()))

        except httpx.HTTPStatusError as e:
            try:
                body = e.response.json()
                return _tool_result(
                    f"HTTP {e.response.status_code}\n{_format_response(body)}"
                )
            except Exception:
                return _tool_result(
                    f"HTTP {e.response.status_code}\n{e.response.text or str(e)}"
                )
        except httpx.ConnectError as e:
            return _tool_result(
                f"Ошибка подключения к UI Bridge ({BASE_URL}): {e}. "
                "Убедитесь, что агент запущен с ui.enabled: true."
            )
        except httpx.TimeoutException as e:
            return _tool_result(f"Таймаут запроса к {BASE_URL}: {e}")
        except Exception as e:
            return _tool_result(f"Ошибка: {e}")

    raise ValueError(f"Неизвестный инструмент: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
