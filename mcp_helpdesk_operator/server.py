from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from uuid import UUID

import aiohttp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, ImageContent, TextContent, Tool, ToolAnnotations
from yarl import URL


SERVER_NAME = "helpdesk-operator"
server = Server(SERVER_NAME)
SUPPORT_PATH = "/api/web/support/tickets"
MAX_CONTENT_BYTES = 8 * 1024 * 1024
RASTER_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
CODE = re.compile(r"T-[0-9]{6,18}", re.ASCII | re.IGNORECASE)
UUID_FIELD = {"type": "string", "format": "uuid"}
TEXT_FIELD = {"type": "string", "minLength": 1, "maxLength": 12000}
CURSOR_FIELD = {"type": "integer", "minimum": 0, "maximum": 2**63 - 1}


def _tool(name, description, fields=None, *, optional=None, lookup=False, write=False):
    fields = {"ticket": {"type": "string", "maxLength": 36} if lookup else UUID_FIELD, **(fields or {})}
    return Tool(
        name=name, description=description,
        inputSchema={
            "type": "object", "properties": {**fields, **(optional or {})},
            "required": list(fields), "additionalProperties": False,
        },
        annotations=ToolAnnotations(
            readOnlyHint=not write, destructiveHint=False, idempotentHint=write, openWorldHint=False,
        ),
    )


TOOLS = {
    tool.name: tool for tool in (
        _tool("ticket_get", "Open a visible ticket by exact T-number or UUID. Returns its UUID, assignee, status, workflow actions, timeline, and device candidates.", lookup=True),
        _tool("ticket_events", "Read ticket events in order. Save next_cursor and repeat while has_more is true. Start at 0 for history.",
              optional={"after": CURSOR_FIELD, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
        _tool("ticket_attachment_get", "Open an authorized attachment belonging to this ticket. Raster screenshots are displayed inline.",
              {"artifact_id": UUID_FIELD}),
        _tool("ticket_start", "Start work through the canonical Helpdesk action. Reuse operation_id if the response is lost.",
              {"operation_id": UUID_FIELD}, write=True),
        _tool("ticket_reply", "Send an employee-visible reply or an explicitly selected internal note. Reuse message_id on retry.",
              {"text": TEXT_FIELD, "visibility": {"type": "string", "enum": ["public", "internal"]}, "message_id": UUID_FIELD}, write=True),
        _tool("ticket_transition", "Ask the requester a question while moving to waiting_on_user, or submit a solution under the ticket's confirmation policy. Reuse operation_id on retry.",
              {"action": {"type": "string", "enum": ["ask_user", "resolve"]}, "text": TEXT_FIELD, "operation_id": UUID_FIELD},
              optional={"resolution_code": {"type": "string", "maxLength": 100},
                        "close_after_resolve": {"type": "boolean"}}, write=True),
        _tool("ticket_device_select", "Select a confirmed device from ticket_get's requester_devices for diagnostics on this ticket.",
              {"device_id": UUID_FIELD}, write=True),
        _tool("ticket_tools", "List the ticket device's Endpoint Tools catalog.",
              optional={"cursor": {"type": "string", "minLength": 1, "maxLength": 1024}}),
        _tool("ticket_tool_run", "Start a catalogued Endpoint Tool using its published version and the expected ticket device. Reuse operation_id on retry.",
              {"device_ref": UUID_FIELD, "module_key": {"type": "string", "pattern": r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){1,7}$", "maxLength": 128},
               "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$", "maxLength": 64}, "operation_id": UUID_FIELD},
              optional={"inputs": {"type": "object", "maxProperties": 8,
                                   "additionalProperties": {"type": ["string", "integer"]}}}, write=True),
        _tool("ticket_tool_result", "Read the current state and result for one Endpoint Tool run on this ticket.",
              {"run_id": UUID_FIELD}),
    )
}


def _ticket_key(value: str, *, allow_code: bool = False) -> str:
    value = value.strip()
    if allow_code and CODE.fullmatch(value):
        return value.upper()
    return str(UUID(value))


def tool_request(name: str, args: dict) -> tuple[str, str, dict | None, dict | None]:
    ticket = _ticket_key(args["ticket"], allow_code=name == "ticket_get")
    path = f"{SUPPORT_PATH}/{ticket}"
    if name == "ticket_get":
        return "GET", path, None, None
    if name == "ticket_events":
        return "GET", f"{path}/events", None, {"after": args.get("after", 0), "limit": args.get("limit", 50)}
    if name == "ticket_attachment_get":
        return "GET", f"{path}/attachments/{UUID(args['artifact_id'])}", None, None
    if name == "ticket_reply":
        text = args["text"].strip()
        if not text:
            raise ValueError("Message text is required")
        return "POST", f"{path}/messages", {
            "text": text, "visibility": args["visibility"], "message_id": str(UUID(args["message_id"])),
        }, None
    if name == "ticket_device_select":
        return "POST", f"{path}/diagnostic-device", {"device_id": str(UUID(args["device_id"]))}, None
    if name == "ticket_tools":
        return "GET", f"{path}/endpoint-tools", None, {"cursor": args["cursor"]} if "cursor" in args else None
    if name == "ticket_tool_run":
        return "POST", f"{path}/endpoint-tools/runs", {
            "schema_version": "endpoint_tool_run_create_v1", "expected_device_ref": str(UUID(args["device_ref"])),
            "module_key": args["module_key"], "version": args["version"],
            "caller_key": str(UUID(args["operation_id"])), "inputs": args.get("inputs", {}),
        }, None
    if name == "ticket_tool_result":
        return "GET", f"{path}/endpoint-tools/runs/{UUID(args['run_id'])}", None, None

    body = {"operation_id": str(UUID(args["operation_id"]))}
    if name == "ticket_start":
        body["to_status"] = "in_progress"
    elif name == "ticket_transition":
        text = args["text"].strip()
        if not text:
            raise ValueError("Transition text is required")
        if args["action"] == "ask_user":
            if "resolution_code" in args or args.get("close_after_resolve"):
                raise ValueError("Resolution fields apply only to the resolve action")
            body.update(to_status="waiting_on_user", public_comment=text)
        elif args["action"] == "resolve":
            body.update(to_status="resolved", requester_resolution_summary=text)
            for field in ("resolution_code", "close_after_resolve"):
                if field in args:
                    body[field] = args[field]
        else:
            raise ValueError("Unsupported transition action")
    else:
        raise ValueError("Unknown tool")
    return "POST", f"{path}/status", body, None


def _configuration() -> tuple[URL, str]:
    base = URL(os.environ.get("HELPDESK_OPERATOR_BASE_URL", ""))
    local = base.host in {"127.0.0.1", "::1", "localhost"}
    if (
        not base.host or base.user is not None or base.query_string or base.fragment or base.path not in {"", "/"}
        or not (base.scheme == "https" or local and base.scheme == "http")
    ):
        raise ValueError("Set HELPDESK_OPERATOR_BASE_URL to the Helpdesk origin")
    token_path = os.environ.get("HELPDESK_OPERATOR_TOKEN_FILE")
    if not token_path:
        raise ValueError("Set HELPDESK_OPERATOR_TOKEN_FILE to the operator credential file")
    try:
        token = Path(token_path).read_text(encoding="utf-8-sig").strip()
    except OSError:
        raise ValueError("Cannot read the Helpdesk operator credential file") from None
    if not re.fullmatch(r"hdo_[A-Za-z0-9_-]{43}", token, re.ASCII):
        raise ValueError("Invalid Helpdesk operator credential format")
    return base, token


async def _read_response(response: aiohttp.ClientResponse) -> bytes:
    body = bytearray()
    async for block in response.content.iter_chunked(65536):
        body.extend(block)
        if len(body) > MAX_CONTENT_BYTES:
            raise ValueError("Helpdesk response exceeds the MCP size limit")
    return bytes(body)


def _json_result(payload: dict, *, error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
        structuredContent=payload, isError=error,
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    return list(TOOLS.values())


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        method, path, body, query = tool_request(name, arguments)
        origin, token = _configuration()
        is_attachment = name == "ticket_attachment_get"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if is_attachment:
            headers.update(Accept="*/*", Range=f"bytes=0-{MAX_CONTENT_BYTES - 1}")
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                method, origin.with_path(path), json=body, params=query, headers=headers, allow_redirects=False,
            ) as response:
                if not 200 <= response.status < 300:
                    error = {"http_status": response.status, "error_code": "HELPDESK_REQUEST_FAILED"}
                    if response.content_type == "application/json":
                        payload = json.loads(await _read_response(response))
                        if isinstance(payload, dict):
                            error.update({k: payload[k] for k in ("error", "error_code") if isinstance(payload.get(k), str)})
                    return _json_result(error, error=True)
                if response.status == 206:
                    complete = re.fullmatch(r"bytes 0-(\d+)/(\d+)", response.headers.get("Content-Range", ""))
                    if complete is None or int(complete[1]) + 1 != int(complete[2]):
                        raise ValueError("Attachment exceeds the MCP size limit")
                data = await _read_response(response)
                if not is_attachment:
                    return _json_result(json.loads(data))
                mime = response.content_type
                encoded = base64.b64encode(data).decode("ascii")
                if mime in RASTER_TYPES:
                    return CallToolResult(content=[ImageContent(type="image", data=encoded, mimeType=mime)])
                return CallToolResult(content=[EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(uri=f"helpdesk://tickets/{arguments['ticket']}/attachments/{arguments['artifact_id']}",
                                                  mimeType=mime, blob=encoded),
                )])
    except (aiohttp.ClientError, asyncio.TimeoutError):
        return _json_result({"error_code": "HELPDESK_UNREACHABLE", "error": "No complete response from Helpdesk"}, error=True)
    except json.JSONDecodeError:
        return _json_result({"error_code": "INVALID_HELPDESK_RESPONSE"}, error=True)
    except ValueError as exc:
        return _json_result({"error_code": "OPERATOR_TOOL_ERROR", "error": str(exc)}, error=True)


async def main() -> None:
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
