from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_helpdesk_server.manifest import MODE, TOOL_NAMES, get_manifest
from mcp_helpdesk_server.server import dispatch_tool


def test_manifest_json_parses_and_matches_python_manifest() -> None:
    json_manifest = json.loads(Path("docs/mcp/helpdesk-server-debug.manifest.json").read_text(encoding="utf-8"))
    python_manifest = get_manifest()

    assert json_manifest["name"] == "helpdesk-server-debug"
    assert json_manifest["transport"] == "stdio"
    assert json_manifest["mode"] == MODE
    assert json_manifest["tools"] == python_manifest["tools"] == TOOL_NAMES
    assert json_manifest["modes"] == python_manifest["modes"]
    assert json_manifest["safety"] == python_manifest["safety"]


def test_manifest_tools_unique_and_debug_readonly_disables_mutations() -> None:
    manifest = get_manifest()
    assert len(manifest["tools"]) == len(set(manifest["tools"]))
    flags = manifest["modes"]["debug_readonly"]
    assert flags["allow_business_mutation"] is False
    assert flags["allow_observer_rebuild"] is False
    assert flags["allow_ws_rpc"] is False
    assert flags["allow_run_tool"] is False
    assert flags["allow_device_outbox_writes"] is False
    assert flags["allow_approvals"] is False


def test_manifest_contains_no_raw_secret_examples() -> None:
    raw = json.dumps(get_manifest(), ensure_ascii=False).lower()
    assert "postgresql+asyncpg://" not in raw
    assert "password@" not in raw
    assert "token=" not in raw


@pytest.mark.asyncio
async def test_manifest_tool_preserves_boolean_safety_flags() -> None:
    payload = await dispatch_tool("helpdesk_mcp_manifest", {})

    assert payload["status"] == "ok"
    assert payload["manifest"]["safety"]["no_raw_tokens"] is True
