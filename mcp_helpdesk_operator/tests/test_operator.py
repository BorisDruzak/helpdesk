import sys

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import ImageContent

from mcp_helpdesk_operator.server import tool_request


TICKET = "11111111-1111-4111-8111-111111111111"
OPERATION = "22222222-2222-4222-8222-222222222222"


def test_exact_lookup_and_explicit_internal_note():
    assert tool_request("ticket_get", {"ticket": "t-000002"})[1].endswith("/T-000002")
    method, path, body, _ = tool_request("ticket_reply", {
        "ticket": TICKET, "text": "Проверил очередь", "visibility": "internal", "message_id": OPERATION,
    })
    assert (method, path.rsplit("/", 1)[-1]) == ("POST", "messages")
    assert body == {"text": "Проверил очередь", "visibility": "internal", "message_id": OPERATION}


def test_clarification_uses_a_single_status_request_and_stable_id():
    method, path, body, _ = tool_request("ticket_transition", {
        "ticket": TICKET, "action": "ask_user", "text": "Пришлите скриншот", "operation_id": OPERATION,
    })
    assert (method, path.rsplit("/", 1)[-1]) == ("POST", "status")
    assert body == {"to_status": "waiting_on_user", "public_comment": "Пришлите скриншот", "operation_id": OPERATION}


def test_solution_does_not_close_by_default():
    _, _, body, _ = tool_request("ticket_transition", {
        "ticket": TICKET, "action": "resolve", "text": "Очередь снова доступна", "operation_id": OPERATION,
    })
    assert body["requester_resolution_summary"] == "Очередь снова доступна"
    assert body.get("close_after_resolve", False) is False


def test_mutations_require_canonical_ticket_id_and_no_arbitrary_http_paths():
    with pytest.raises(ValueError):
        tool_request("ticket_start", {"ticket": "T-000002", "operation_id": OPERATION})
    with pytest.raises(ValueError):
        tool_request("ticket_get", {"ticket": "../admin"})


@pytest.mark.asyncio
async def test_stdio_tools_call_authenticated_http_and_return_raster(tmp_path):
    token = "hdo_" + "a" * 43
    credential = tmp_path / "operator.token"
    credential.write_text(token, encoding="ascii")

    async def get_ticket(request):
        assert request.headers.get("Authorization") == f"Bearer {token}"
        assert request.match_info["ticket"] == "T-000002"
        return web.json_response({"status": "success", "data": {"ticket_id": TICKET}})

    async def attachment(request):
        assert request.headers.get("Authorization") == f"Bearer {token}"
        assert request.match_info["ticket"] == TICKET
        assert request.match_info["artifact"] == OPERATION
        assert request.headers["Range"].startswith("bytes=0-")
        return web.Response(body=b"fixture", content_type="image/png")

    app = web.Application()
    app.router.add_get("/api/web/support/tickets/{ticket}", get_ticket)
    app.router.add_get("/api/web/support/tickets/{ticket}/attachments/{artifact}", attachment)
    async with TestServer(app) as http:
        parameters = StdioServerParameters(
            command=sys.executable, args=["-m", "mcp_helpdesk_operator.server"],
            env={"HELPDESK_OPERATOR_BASE_URL": str(http.make_url("/")), "HELPDESK_OPERATOR_TOKEN_FILE": str(credential)},
        )
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 10
                ticket = await session.call_tool("ticket_get", {"ticket": "T-000002"})
                assert ticket.structuredContent == {"status": "success", "data": {"ticket_id": TICKET}}
                result = await session.call_tool("ticket_attachment_get", {"ticket": TICKET, "artifact_id": OPERATION})
                assert not result.isError
                assert isinstance(result.content[0], ImageContent)
