from __future__ import annotations

from datetime import datetime, timezone

from aiohttp import web

from auth.middleware import require_auth
from app.db import get_session
from mcp_helpdesk_server.manifest import get_manifest
from mcp_helpdesk_server.tools.context_tools import helpdesk_context_freshness
from mcp_helpdesk_server.tools.db_tools import helpdesk_db_health
from observer.debug_facade import runtime_snapshot
from shared.redaction import redact_sensitive_payload


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@require_auth("admin", "support", "auditor")
async def handle_ai_integration_mcp_status(request: web.Request) -> web.Response:
    async with get_session() as session:
        runtime_status = await runtime_snapshot(session, process_kind="server", include_details=True)

    payload = {
        "status": "ok",
        "generated_at": _now_iso(),
        "mcp": {
            "manifest": get_manifest(),
            "db_health": await helpdesk_db_health({}),
            "context_freshness": await helpdesk_context_freshness({}),
            "runtime_status": runtime_status,
            "reload": {
                "required_after_deploy": True,
                "codex_restart_recommended": True,
                "status_text": "Reload or restart Codex MCP connection after deploy so stdio processes import fresh code.",
            },
        },
    }
    return web.json_response(redact_sensitive_payload(payload))
