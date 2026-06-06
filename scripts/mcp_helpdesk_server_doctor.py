#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_helpdesk_server.manifest import get_manifest
from mcp_helpdesk_server.schemas import redact_and_bound
from mcp_helpdesk_server.server import build_tools, dispatch_tool


def _print_json(payload: Any) -> None:
    safe_payload = redact_and_bound(payload)
    if isinstance(payload, dict) and "manifest" in payload and isinstance(safe_payload, dict):
        safe_payload["manifest"] = payload["manifest"]
    print(json.dumps(safe_payload, ensure_ascii=False, indent=2, default=str))


async def _run(args: argparse.Namespace) -> int:
    manifest = get_manifest()
    tools = build_tools()
    payload: dict[str, Any] = {
        "status": "ok",
        "manifest": manifest,
        "tools": [tool.name for tool in tools],
        "tool_count": len(tools),
    }
    if args.db_health:
        payload["db_health"] = await dispatch_tool("helpdesk_db_health", {})
    if args.observer_bundle:
        if not args.q:
            payload["observer_bundle"] = {
                "status": "skipped",
                "reason": "--observer-bundle requires --q with a known ticket_code, trace_id, operation_id or device_id",
            }
        else:
            payload["observer_bundle"] = await dispatch_tool("observer_debug_bundle", {"q": args.q})
    _print_json(payload)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check helpdesk-server-debug MCP server imports and safe tools.")
    parser.add_argument("--db-health", action="store_true", help="Run helpdesk_db_health")
    parser.add_argument("--observer-bundle", action="store_true", help="Run observer_debug_bundle with --q")
    parser.add_argument("--q", help="Known ticket_code, trace_id, operation_id, device_id or hostname for observer bundle")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
