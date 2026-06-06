from __future__ import annotations

from copy import deepcopy
from typing import Any

SERVER_NAME = "helpdesk-server-debug"
MODE = "debug_readonly"

TOOL_NAMES = [
    "helpdesk_db_health",
    "helpdesk_context_search",
    "helpdesk_context_freshness",
    "helpdesk_locate",
    "observer_debug_bundle",
    "observer_trace_detail",
    "observer_ticket_summary",
    "observer_runtime_status",
    "observer_presence_snapshot",
    "helpdesk_mcp_manifest",
]

MUTATION_FLAGS = {
    "allow_business_mutation": False,
    "allow_observer_rebuild": False,
    "allow_ws_rpc": False,
    "allow_run_tool": False,
    "allow_device_outbox_writes": False,
    "allow_approvals": False,
}

SAFETY_FLAGS = {
    "redaction_required": True,
    "no_raw_tokens": True,
    "no_business_mutation": True,
    "no_device_outbox_writes": True,
    "no_run_tool": True,
    "no_http_api_proxy": True,
}


def get_manifest() -> dict[str, Any]:
    return deepcopy(
        {
            "name": SERVER_NAME,
            "transport": "stdio",
            "command": "python",
            "args": ["-m", "mcp_helpdesk_server.server"],
            "mode": MODE,
            "required_env": [],
            "optional_env": [
                "DATABASE_URL",
                "MCP_HELPDESK_MODE",
                "MCP_HELPDESK_MAX_ROWS",
                "MCP_HELPDESK_CONTEXT_INDEX_PATH",
            ],
            "tools": TOOL_NAMES,
            "modes": {MODE: MUTATION_FLAGS},
            "safety": SAFETY_FLAGS,
        }
    )
