from __future__ import annotations

from typing import Any

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.schemas import bool_arg, controlled_error, int_arg, redact_and_bound, text_arg


async def observer_runtime_status(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import runtime_snapshot

        async with get_session() as session:
            payload = await runtime_snapshot(
                session,
                process_kind=text_arg(args, "process_kind"),
                include_details=bool_arg(args, "include_details", True),
            )
            await session.rollback()
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("RUNTIME_STATUS_FAILED", "Observer runtime status failed", exception_type=type(exc).__name__)


async def observer_presence_snapshot(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import agent_presence_snapshot

        async with get_session() as session:
            payload = await agent_presence_snapshot(
                session,
                device_id=text_arg(args, "device_id"),
                limit=int_arg(args, "limit", 50, minimum=1, maximum=200),
            )
            await session.rollback()
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("PRESENCE_SNAPSHOT_FAILED", "Observer presence snapshot failed", exception_type=type(exc).__name__)
