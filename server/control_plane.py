from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import sys

import aiohttp
from aiohttp import web
from loguru import logger

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from app.db import get_session, init_db, shutdown_db
from app.repos.ui_users_repo import UiUsersRepo
from auth.context import AuthContext, AuthType
from auth.middleware import extract_token_from_header
from auth.service import AuthService
from config import DATABASE_URL
from runtime_control import (
    SERVER_UNIT,
    controller_allowed_origins,
    filter_log_entries,
    format_log_entries_as_text,
    get_unit_status,
    list_journal_entries,
    load_control_state,
    run_action_and_wait,
    smoke_server,
    update_last_server_action,
)

CONTROL_HOST = "0.0.0.0"
CONTROL_PORT = 8667
CONTROL_API_PREFIX = "/api/control"
STATE_KEY = web.AppKey("control_state", SimpleNamespace)
STARTED_AT_KEY = web.AppKey("control_started_at", str)
ACTION_LOCK_KEY = web.AppKey("control_action_lock", asyncio.Lock)
RUNTIME_STATE_KEY = web.AppKey("control_runtime_state", dict)


def _cors_origin_for_request(request: web.Request) -> str | None:
    origin = str(request.headers.get("Origin") or "").strip().rstrip("/")
    if origin and origin in controller_allowed_origins():
        return origin
    return None


def _apply_cors(request: web.Request, response: web.StreamResponse) -> web.StreamResponse:
    origin = _cors_origin_for_request(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Max-Age"] = "600"
    return response


@web.middleware
async def control_cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return _apply_cors(request, web.Response(status=204))
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = exc
    except Exception:
        logger.exception("[control_plane] unhandled request error")
        response = web.json_response({"status": "error", "error": "Internal server error"}, status=500)
    return _apply_cors(request, response)


@web.middleware
async def control_auth_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return await handler(request)
    token = extract_token_from_header(request)
    auth_context = None
    if token:
        auth_service = AuthService(request.app[STATE_KEY])
        token_info = await auth_service.verify_agent_token(token)
        if token_info:
            auth_context = AuthContext(
                actor_id=token_info["device_id"],
                actor_role="agent",
                auth_type=AuthType.AGENT_TOKEN,
                token=token,
            )
        else:
            token_info = await auth_service.verify_ui_token(token)
            if token_info:
                auth_context = AuthContext(
                    actor_id=token_info["user_login"],
                    actor_role=token_info["actor_role"],
                    auth_type=AuthType.UI_TOKEN,
                    token=token,
                )
    if not auth_context:
        return web.json_response(
            {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
            status=401,
        )
    request["auth_context"] = auth_context
    return await handler(request)


def require_control_auth(*allowed_roles: str):
    def decorator(handler):
        async def wrapper(request: web.Request):
            auth_context: AuthContext | None = request.get("auth_context")
            if not auth_context:
                return web.json_response(
                    {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
                    status=401,
                )
            if allowed_roles and auth_context.actor_role not in allowed_roles:
                return web.json_response(
                    {"status": "error", "error": "Insufficient permissions", "error_code": "FORBIDDEN"},
                    status=403,
                )
            return await handler(request)

        return wrapper

    return decorator


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _record_runtime_audit(
    *,
    user_login: str,
    action: str,
    actor_id: str,
    details: dict[str, Any],
) -> None:
    async with get_session() as session:
        repo = UiUsersRepo(session)
        await repo._audit(user_login, action, actor_id, details)
        await session.commit()


async def _fetch_main_server_health(request: web.Request) -> dict[str, Any]:
    token = request.headers.get("Authorization", "")
    headers = {"Authorization": token} if token else {}
    timeout = aiohttp.ClientTimeout(total=3)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get("http://127.0.0.1:8666/api/admin/tech/overview", headers=headers) as response:
            payload = await response.json(content_type=None)
            return {
                "reachable": response.ok and isinstance(payload, dict) and payload.get("status") == "ok",
                "status_code": response.status,
                "overview": payload.get("overview") if isinstance(payload, dict) else None,
            }


@require_control_auth("admin", "support", "auditor")
async def handle_control_status(request: web.Request) -> web.Response:
    runtime_state = request.app[RUNTIME_STATE_KEY]
    current_action = runtime_state.get("current_action")
    pending_action = current_action.get("action") if isinstance(current_action, dict) else None
    status = get_unit_status("server", pending_action=pending_action)
    state = load_control_state()
    server_state = {
        **status,
        "controller_started_at": request.app[STARTED_AT_KEY],
        "controller_uptime_sec": max(
            0,
            int((datetime.now(timezone.utc) - datetime.fromisoformat(request.app[STARTED_AT_KEY])).total_seconds()),
        ),
        "current_action": current_action,
        "last_action": state.get("last_server_action"),
        "last_restart_reason": ((state.get("last_server_action") or {}).get("reason")),
    }
    try:
        server_state["main_server_health"] = await _fetch_main_server_health(request)
    except Exception as exc:
        server_state["main_server_health"] = {"reachable": False, "error": str(exc), "overview": None}
    return web.json_response({"status": "ok", "server": server_state})


@require_control_auth("admin", "support", "auditor")
async def handle_control_logs(request: web.Request) -> web.Response:
    try:
        limit = max(10, min(int(request.query.get("limit", "200")), 500))
    except (TypeError, ValueError):
        limit = 200
    levels = [item.strip().lower() for item in str(request.query.get("levels") or "").split(",") if item.strip()]
    contains = request.query.get("contains")
    entries = filter_log_entries(list_journal_entries("server", lines=limit), levels=levels, contains=contains)
    return web.json_response({"status": "ok", "logs": entries, "count": len(entries), "unit": SERVER_UNIT})


@require_control_auth("admin", "support", "auditor")
async def handle_control_logs_download(request: web.Request) -> web.Response:
    try:
        limit = max(10, min(int(request.query.get("limit", "300")), 1000))
    except (TypeError, ValueError):
        limit = 300
    levels = [item.strip().lower() for item in str(request.query.get("levels") or "").split(",") if item.strip()]
    contains = request.query.get("contains")
    entries = filter_log_entries(list_journal_entries("server", lines=limit), levels=levels, contains=contains)
    response = web.Response(
        text=format_log_entries_as_text(entries),
        content_type="text/plain",
        charset="utf-8",
    )
    response.headers["Content-Disposition"] = 'attachment; filename="pc-client-server.log"'
    return response


@require_control_auth("admin")
async def handle_control_action(request: web.Request) -> web.Response:
    auth_context: AuthContext = request["auth_context"]
    try:
        payload = await request.json()
    except Exception:
        return web.json_response({"status": "error", "error": "Invalid JSON"}, status=400)

    action = str(payload.get("action") or "").strip().lower()
    reason = str(payload.get("reason") or "").strip() or None
    if action not in {"start", "stop", "restart", "smoke"}:
        return web.json_response({"status": "error", "error": "Unsupported action"}, status=400)

    runtime_state = request.app[RUNTIME_STATE_KEY]
    lock: asyncio.Lock = request.app[ACTION_LOCK_KEY]
    if lock.locked():
        return web.json_response(
            {
                "status": "error",
                "error": "Another server action is already running",
                "current_action": runtime_state.get("current_action"),
            },
            status=409,
        )

    requested_at = _now_iso()
    runtime_state["current_action"] = {
        "action": action,
        "reason": reason,
        "requested_at": requested_at,
        "actor_id": auth_context.actor_id,
        "actor_role": auth_context.actor_role,
    }
    update_last_server_action(
        action=action,
        reason=reason,
        actor_id=auth_context.actor_id,
        actor_role=auth_context.actor_role,
        status="running",
        requested_at=requested_at,
    )

    async with lock:
        try:
            if action == "smoke":
                await asyncio.to_thread(smoke_server)
                result = {"display_state": "running", "smoke": "ok"}
            else:
                result = await asyncio.to_thread(run_action_and_wait, "server", action)
            completed_at = _now_iso()
            update_last_server_action(
                action=action,
                reason=reason,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                status="ok",
                requested_at=requested_at,
                completed_at=completed_at,
            )
            await _record_runtime_audit(
                user_login=auth_context.actor_id,
                action=f"server_runtime_{action}",
                actor_id=auth_context.actor_id,
                details={
                    "reason": reason,
                    "requested_at": requested_at,
                    "completed_at": completed_at,
                    "result": result,
                },
            )
            return web.json_response({"status": "ok", "action": action, "result": result})
        except Exception as exc:
            completed_at = _now_iso()
            update_last_server_action(
                action=action,
                reason=reason,
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
                status="error",
                error=str(exc),
                requested_at=requested_at,
                completed_at=completed_at,
            )
            await _record_runtime_audit(
                user_login=auth_context.actor_id,
                action=f"server_runtime_{action}",
                actor_id=auth_context.actor_id,
                details={
                    "reason": reason,
                    "requested_at": requested_at,
                    "completed_at": completed_at,
                    "error": str(exc),
                },
            )
            logger.exception("[control_plane] server action failed")
            return web.json_response({"status": "error", "error": str(exc), "action": action}, status=500)
        finally:
            runtime_state["current_action"] = None


async def handle_options(_: web.Request) -> web.Response:
    return web.Response(status=204)


async def _startup_control_plane(_: web.Application) -> None:
    await init_db(DATABASE_URL)


async def _cleanup_control_plane(_: web.Application) -> None:
    await shutdown_db()


def create_control_app(*, initialize_db: bool = True) -> web.Application:
    app = web.Application(middlewares=[control_cors_middleware, control_auth_middleware])
    app[STATE_KEY] = SimpleNamespace(users={})
    app[STARTED_AT_KEY] = _now_iso()
    app[ACTION_LOCK_KEY] = asyncio.Lock()
    app[RUNTIME_STATE_KEY] = {"current_action": None}
    if initialize_db:
        app.on_startup.append(_startup_control_plane)
        app.on_cleanup.append(_cleanup_control_plane)
    app.router.add_route("OPTIONS", "/{tail:.*}", handle_options)
    app.router.add_get(f"{CONTROL_API_PREFIX}/server/status", handle_control_status)
    app.router.add_get(f"{CONTROL_API_PREFIX}/server/logs", handle_control_logs)
    app.router.add_get(f"{CONTROL_API_PREFIX}/server/logs/download", handle_control_logs_download)
    app.router.add_post(f"{CONTROL_API_PREFIX}/server/actions", handle_control_action)
    return app


def main() -> None:
    web.run_app(create_control_app(), host=CONTROL_HOST, port=CONTROL_PORT)


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        main()
