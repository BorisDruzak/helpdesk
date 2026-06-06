from __future__ import annotations

from typing import Any

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.schemas import bool_arg, controlled_error, int_arg, redact_and_bound, text_arg


async def helpdesk_locate(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    query = text_arg(args, "q")
    if not query:
        return controlled_error("QUERY_REQUIRED", "q is required")
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import locate_debug_context

        async with get_session() as session:
            payload = await locate_debug_context(
                session,
                q=query,
                limit=int_arg(args, "limit", 10, minimum=1, maximum=25),
                include_traces=bool_arg(args, "include_traces", True),
                include_logs=bool_arg(args, "include_logs", False),
            )
            await session.rollback()
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("LOCATE_FAILED", "Helpdesk locate failed", exception_type=type(exc).__name__)
