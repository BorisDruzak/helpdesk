from __future__ import annotations

from dataclasses import asdict
from typing import Any

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.schemas import bool_arg, controlled_error, int_arg, redact_and_bound, text_arg


async def observer_trace_detail(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    trace_id = text_arg(args, "trace_id")
    if not trace_id:
        return controlled_error("TRACE_ID_REQUIRED", "trace_id is required")
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import observer_trace_detail as load_detail

        async with get_session() as session:
            payload = await load_detail(
                session,
                trace_id,
                include_agent_actions=bool_arg(args, "include_agent_actions", False),
            )
            await session.rollback()
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("OBSERVER_TRACE_DETAIL_FAILED", "Observer trace detail failed", exception_type=type(exc).__name__)


async def observer_ticket_summary(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    ticket_id = text_arg(args, "ticket_id")
    if not ticket_id:
        return controlled_error("TICKET_ID_REQUIRED", "ticket_id is required")
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import observer_ticket_summary as load_summary

        async with get_session() as session:
            payload = await load_summary(
                session,
                ticket_id,
                trace_limit=int_arg(args, "trace_limit", 8, maximum=25),
                signature_limit=int_arg(args, "signature_limit", 6, maximum=25),
                span_limit=int_arg(args, "span_limit", 12, maximum=50),
                occurrence_limit=int_arg(args, "occurrence_limit", 6, maximum=50),
            )
            await session.rollback()
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("OBSERVER_TICKET_SUMMARY_FAILED", "Observer ticket summary failed", exception_type=type(exc).__name__)


async def observer_debug_bundle(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = arguments or {}
    try:
        await bootstrap.ensure_db_started()
        from app.db import get_session
        from observer.debug_facade import ObserverDebugFilters, observer_debug_bundle_v2

        filters = ObserverDebugFilters(
            q=text_arg(args, "q"),
            trace_id=text_arg(args, "trace_id"),
            ticket_id=text_arg(args, "ticket_id"),
            operation_id=text_arg(args, "operation_id"),
            device_id=text_arg(args, "device_id"),
            route=text_arg(args, "route"),
            playbook_run_id=_optional_int(args, "playbook_run_id"),
            step_run_id=_optional_int(args, "step_run_id"),
            lookback_hours=int_arg(args, "lookback_hours", 24, minimum=1, maximum=168),
            include_runtime_snapshot=bool_arg(args, "include_runtime_snapshot", True),
            include_presence_snapshot=bool_arg(args, "include_presence_snapshot", True),
            include_logs=bool_arg(args, "include_logs", False),
            limit=int_arg(args, "limit", 20, minimum=1, maximum=100),
        )
        async with get_session() as session:
            payload = await observer_debug_bundle_v2(session, filters)
            await session.rollback()
            payload.setdefault("filters", asdict(filters))
            return redact_and_bound(payload)
    except Exception as exc:
        return controlled_error("OBSERVER_DEBUG_BUNDLE_FAILED", "Observer debug bundle failed", exception_type=type(exc).__name__)


def _optional_int(args: dict[str, Any], key: str) -> int | None:
    value = args.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
