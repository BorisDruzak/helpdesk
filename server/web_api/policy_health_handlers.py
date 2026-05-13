from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from auth.middleware import require_auth
from tickets.policy_health_service import PolicyHealthService


@require_auth("admin", "auditor")
async def handle_web_admin_policy_health(request: web.Request) -> web.Response:
    try:
        async with get_session() as session:
            payload = await PolicyHealthService(session).list_health()
        return web.json_response(payload)
    except Exception as exc:
        logger.exception("[policy_health] failed to build dashboard")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "auditor")
async def handle_web_admin_policy_health_detail(request: web.Request) -> web.Response:
    template_code = str(request.match_info.get("template_code") or "").strip()
    try:
        async with get_session() as session:
            payload = await PolicyHealthService(session).get_health(template_code)
        if payload is None:
            return web.json_response({"status": "error", "error": "not_found"}, status=404)
        return web.json_response(payload)
    except Exception:
        logger.exception("[policy_health] failed to build template detail")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)


@require_auth("admin", "auditor")
async def handle_web_admin_policy_health_simulate(request: web.Request) -> web.Response:
    try:
        raw_payload = await request.json()
        if not isinstance(raw_payload, dict):
            return web.json_response({"status": "error", "error": "validation_error"}, status=400)
        async with get_session() as session:
            payload = await PolicyHealthService(session).simulate(raw_payload)
        return web.json_response(payload)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": "validation_error", "details": str(exc)}, status=400)
    except Exception:
        logger.exception("[policy_health] failed to run simulation")
        return web.json_response({"status": "error", "error": "internal_error"}, status=500)
