from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .manifest import SERVER_NAME, get_manifest
from .schemas import TOOL_SCHEMAS, controlled_error, redact_and_bound, validate_tool_schemas
from .tools.context_tools import helpdesk_context_freshness, helpdesk_context_search
from .tools.db_tools import helpdesk_db_health
from .tools.observer_tools import observer_debug_bundle, observer_ticket_summary, observer_trace_detail
from .tools.runtime_tools import observer_presence_snapshot, observer_runtime_status
from .tools.tech_tools import helpdesk_locate

ToolHandler = Callable[[dict[str, Any] | None], Awaitable[dict[str, Any]]]

server = Server(SERVER_NAME)

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "helpdesk_db_health": helpdesk_db_health,
    "helpdesk_context_search": helpdesk_context_search,
    "helpdesk_context_freshness": helpdesk_context_freshness,
    "helpdesk_locate": helpdesk_locate,
    "observer_debug_bundle": observer_debug_bundle,
    "observer_trace_detail": observer_trace_detail,
    "observer_ticket_summary": observer_ticket_summary,
    "observer_runtime_status": observer_runtime_status,
    "observer_presence_snapshot": observer_presence_snapshot,
}


def build_tools() -> list[Tool]:
    validate_tool_schemas()
    return [
        Tool(
            name=name,
            description=_tool_description(name),
            inputSchema=TOOL_SCHEMAS[name],
        )
        for name in get_manifest()["tools"]
    ]


async def dispatch_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name == "helpdesk_mcp_manifest":
        return {"status": "ok", "manifest": get_manifest()}
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        return controlled_error("UNKNOWN_TOOL", f"Unknown tool: {name}", tool=name)
    try:
        return await handler(arguments or {})
    except Exception as exc:
        return controlled_error("TOOL_CALL_FAILED", "Tool call failed", tool=name, exception_type=type(exc).__name__)


def _json_text(payload: Any, *, redact: bool = True) -> list[TextContent]:
    safe_payload = redact_and_bound(payload) if redact else payload
    return [TextContent(type="text", text=json.dumps(safe_payload, ensure_ascii=False, indent=2, default=str))]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return build_tools()


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None = None) -> list[TextContent]:
    return _json_text(await dispatch_tool(name, arguments), redact=name != "helpdesk_mcp_manifest")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def _tool_description(name: str) -> str:
    descriptions = {
        "helpdesk_db_health": "Read-only PostgreSQL reachability check through project DB bootstrap.",
        "helpdesk_context_search": "Search the deterministic local Context Index without shelling out.",
        "helpdesk_context_freshness": "Report Context Index freshness; does not rebuild.",
        "helpdesk_locate": "Locate ticket, device, operation or trace context from DB evidence.",
        "observer_debug_bundle": "Build a bounded read-only observer debug bundle for one locator input.",
        "observer_trace_detail": "Return observer trace detail from the service layer.",
        "observer_ticket_summary": "Return compact ticket-scoped observer summary.",
        "observer_runtime_status": "Return persisted runtime status when available, otherwise controlled partial.",
        "observer_presence_snapshot": "Return persisted agent presence snapshots and DB last_seen evidence.",
        "helpdesk_mcp_manifest": "Return the helpdesk-server-debug MCP manifest.",
    }
    return descriptions.get(name, name)


if __name__ == "__main__":
    asyncio.run(main())
