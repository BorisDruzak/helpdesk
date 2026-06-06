from __future__ import annotations

from mcp_helpdesk_server.manifest import TOOL_NAMES
from mcp_helpdesk_server.schemas import TOOL_SCHEMAS
from mcp_helpdesk_server.server import build_tools


def test_list_tools_returns_all_expected_tool_names() -> None:
    tools = build_tools()
    assert [tool.name for tool in tools] == TOOL_NAMES


def test_every_tool_has_object_input_schema() -> None:
    for tool in build_tools():
        schema = tool.inputSchema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert tool.name in TOOL_SCHEMAS


def test_required_fields_are_declared_for_required_inputs() -> None:
    assert TOOL_SCHEMAS["helpdesk_context_search"]["required"] == ["query"]
    assert TOOL_SCHEMAS["helpdesk_locate"]["required"] == ["q"]
    assert TOOL_SCHEMAS["observer_trace_detail"]["required"] == ["trace_id"]
    assert TOOL_SCHEMAS["observer_ticket_summary"]["required"] == ["ticket_id"]
