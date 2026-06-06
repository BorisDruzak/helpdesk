from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.schemas import controlled_error, int_arg, ok, text_arg


def _context_db_path() -> Path:
    raw = os.getenv("MCP_HELPDESK_CONTEXT_INDEX_PATH", "").strip()
    return Path(raw).expanduser().resolve() if raw else bootstrap.repo_root() / "artifacts" / "context_index" / "pc_client.sqlite"


async def helpdesk_context_search(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    query = text_arg(args, "query")
    if not query:
        return controlled_error("QUERY_REQUIRED", "query is required")
    limit = int_arg(args, "limit", 10, minimum=1, maximum=50)
    kind = text_arg(args, "kind")
    profile = text_arg(args, "profile") or "default"
    try:
        bootstrap.configure_paths()
        from scripts import context_index

        results = context_index.search_index(
            db_path=_context_db_path(),
            query=query,
            limit=limit,
            kind=kind,
            profile=profile,
        )
        compact = [
            {
                "kind": item.get("kind"),
                "title": item.get("title") or item.get("name"),
                "name": item.get("name"),
                "path": item.get("path"),
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
                "summary": item.get("summary") or item.get("snippet") or item.get("text"),
                "score": item.get("score") or item.get("rank"),
            }
            for item in results
        ]
        return ok({"query": query, "limit": limit, "kind": kind, "profile": profile, "results": compact})
    except Exception as exc:
        return controlled_error("CONTEXT_SEARCH_FAILED", "Context index search failed", exception_type=type(exc).__name__)


async def helpdesk_context_freshness(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        bootstrap.configure_paths()
        from scripts import context_index

        status = context_index.freshness_status(workspace=bootstrap.repo_root(), db_path=_context_db_path())
        stale_sources = [
            *status.get("changed_paths", []),
            *status.get("missing_paths", []),
            *status.get("new_paths", []),
        ]
        return ok(
            {
                "status": "stale" if status.get("stale") else "ok",
                "db_path": str(_context_db_path()),
                "exists": bool(status.get("exists")),
                "reason": status.get("reason"),
                "stale_sources_count": len(stale_sources),
                "stale_sources": stale_sources[:25],
                "recommended_command": "python scripts/build_context_index.py --force"
                if status.get("stale")
                else None,
            }
        )
    except Exception as exc:
        return controlled_error("CONTEXT_FRESHNESS_FAILED", "Context index freshness check failed", exception_type=type(exc).__name__)
