from __future__ import annotations

from datetime import datetime

from aiohttp import web
from loguru import logger

from app.db import get_session
from auth.middleware import require_auth
from observer.integrity_service import ObserverIntegrityService
from web_api.dto.common import SuccessResponse, json_model_response


def _int_query(value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


def _str_query(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dt_query(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


@require_auth("admin", "support", "auditor")
async def handle_web_admin_observer_integrity(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            payload = await ObserverIntegrityService(session, state=request.app.get("state")).list_events(
                severity=_str_query(request.query.get("severity")),
                status=_str_query(request.query.get("status")),
                device_id=_str_query(request.query.get("device_id")),
                ticket_id=_str_query(request.query.get("ticket_id")),
                operation_id=_str_query(request.query.get("operation_id")),
                event_type=_str_query(request.query.get("event_type")),
                source=_str_query(request.query.get("source")),
                since=_dt_query(request.query.get("since")),
                limit=_int_query(request.query.get("limit"), default=100, minimum=1, maximum=500),
            )
    except Exception as exc:
        logger.exception(f"[observer_integrity] list failed: {exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Failed to load observer integrity events",
                "error_code": "OBSERVER_INTEGRITY_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[dict](data=payload))


@require_auth("admin", "support")
async def handle_web_admin_observer_integrity_scan(request: web.Request) -> web.Response:
    run_id = _str_query(request.query.get("run_id"))
    try:
        if request.can_read_body:
            body = await request.json()
            if isinstance(body, dict):
                run_id = _str_query(body.get("run_id")) or run_id
    except Exception:
        pass
    try:
        async with get_session() as session:
            result = await ObserverIntegrityService(session, state=request.app.get("state")).run_scan(run_id=run_id)
            await session.commit()
            payload = {
                "run_id": result.run_id,
                "generated": result.generated,
                "active": result.active,
                "suppressed": result.suppressed,
                "resolved": result.resolved,
                "event_ids": result.event_ids,
            }
    except Exception as exc:
        logger.exception(f"[observer_integrity] scan failed: {exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Failed to run observer integrity scan",
                "error_code": "OBSERVER_INTEGRITY_SCAN_FAILED",
            },
            status=500,
        )
    return json_model_response(SuccessResponse[dict](data=payload))
