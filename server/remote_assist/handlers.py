from __future__ import annotations

from aiohttp import web
from loguru import logger

import config
from access_control.service import can
from app.db import get_session
from remote_assist.policy import get_remote_assist_mode_permission, normalize_remote_assist_mode
from remote_assist.service import RemoteAssistError, RemoteAssistService, remote_session_to_dict


def _error_response(exc: RemoteAssistError) -> web.Response:
    return web.json_response(
        {"status": "error", "error_code": exc.error_code, "error": exc.message},
        status=exc.status,
    )


def _server_error(error_code: str, message: str, *, status: int = 500) -> web.Response:
    return web.json_response({"status": "error", "error_code": error_code, "error": message}, status=status)


async def _read_json(request: web.Request) -> dict:
    if not request.can_read_body:
        return {}
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _signaling_url(request: web.Request, session_id: str) -> str:
    public = str(config.SERVER_PUBLIC_BASE_URL or "").strip()
    if public.startswith("https://"):
        base = "wss://" + public[len("https://") :]
    elif public.startswith("http://"):
        base = "ws://" + public[len("http://") :]
    else:
        scheme = "wss" if request.secure else "ws"
        base = f"{scheme}://{request.host}"
    return f"{base.rstrip('/')}/ws/remote-assist/{session_id}"


async def _require_remote_permission(session, auth_context, permission_code: str) -> web.Response | None:
    if await can(session, auth_context, permission_code):
        return None
    return web.json_response(
        {
            "status": "error",
            "error_code": "PERMISSION_DENIED",
            "error": "Permission denied",
            "required_permission": permission_code,
        },
        status=403,
    )


async def handle_remote_assist_request(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    ticket_id = request.match_info["ticket_id"]
    data = await _read_json(request)
    device_id = str(data.get("device_id") or "").strip()
    mode = normalize_remote_assist_mode(str(data.get("mode") or "view_only"))
    reason = str(data.get("reason") or "").strip() or None
    duration_minutes = data.get("duration_minutes")
    if not device_id:
        return _server_error("DEVICE_REQUIRED", "device_id is required", status=400)
    try:
        duration_value = int(duration_minutes) if duration_minutes is not None else None
    except (TypeError, ValueError):
        return _server_error("INVALID_DURATION", "duration_minutes must be an integer", status=400)

    try:
        async with get_session() as session:
            denied = await _require_remote_permission(session, auth_context, "remote_assist.request")
            if denied is not None:
                return denied
            mode_permission = get_remote_assist_mode_permission(mode)
            if mode_permission != "remote_assist.request":
                denied = await _require_remote_permission(session, auth_context, mode_permission)
                if denied is not None:
                    return denied
            service = RemoteAssistService(session)
            remote_session = await service.request_session(
                state=request.app["state"],
                ticket_id=ticket_id,
                device_id=device_id,
                operator_id=auth_context.actor_id,
                requester_id=None,
                mode=mode,
                reason=reason,
                duration_minutes=duration_value,
            )
            await session.commit()
            try:
                await service.send_request_to_agent(state=request.app["state"], remote_session=remote_session)
                await session.commit()
            except Exception as exc:
                logger.warning(f"[remote_assist] consent command failed: session_id={remote_session.id} error={exc}")
                await service.fail_session(
                    session_id=remote_session.id,
                    actor_type="system",
                    actor_id=None,
                    error_code="DEVICE_OFFLINE",
                    error_message="Failed to deliver consent prompt",
                )
                await session.commit()
                raise RemoteAssistError("DEVICE_OFFLINE", "Failed to deliver request to device", status=409) from exc
            return web.json_response(
                {
                    "status": "ok",
                    "data": {
                        "session_id": remote_session.id,
                        "status": remote_session.status,
                        "expires_at": remote_session.expires_at.isoformat(),
                        "message": "Запрос отправлен пользователю",
                    },
                }
            )
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] request failed: ticket_id={ticket_id} error={exc}")
        return _server_error("REMOTE_ASSIST_REQUEST_FAILED", "Remote Assist request failed")


async def handle_remote_assist_approve(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    if auth_context.actor_role != "agent":
        return _server_error("PERMISSION_DENIED", "Agent authentication required", status=403)
    session_id = request.match_info["session_id"]
    try:
        async with get_session() as session:
            service = RemoteAssistService(session)
            remote_session, agent_token = await service.approve_session(session_id=session_id, device_id=auth_context.actor_id)
            await session.commit()
            return web.json_response(
                {
                    "status": "ok",
                    "data": {
                        "session_id": remote_session.id,
                        "status": remote_session.status,
                        "agent_signaling_url": _signaling_url(request, remote_session.id),
                        "agent_token": agent_token,
                        "ice_servers": (remote_session.ice_config or {}).get("ice_servers", []),
                        "mode": remote_session.mode,
                    },
                }
            )
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] approve failed: session_id={session_id} error={exc}")
        return _server_error("REMOTE_ASSIST_APPROVE_FAILED", "Remote Assist approve failed")


async def handle_remote_assist_deny(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    if auth_context.actor_role != "agent":
        return _server_error("PERMISSION_DENIED", "Agent authentication required", status=403)
    session_id = request.match_info["session_id"]
    data = await _read_json(request)
    try:
        async with get_session() as session:
            service = RemoteAssistService(session)
            remote_session = await service.deny_session(
                session_id=session_id,
                device_id=auth_context.actor_id,
                reason=str(data.get("reason") or "user_denied"),
            )
            await session.commit()
            return web.json_response({"status": "ok", "data": remote_session_to_dict(remote_session)})
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] deny failed: session_id={session_id} error={exc}")
        return _server_error("REMOTE_ASSIST_DENY_FAILED", "Remote Assist deny failed")


async def handle_remote_assist_viewer(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    session_id = request.match_info["session_id"]
    try:
        async with get_session() as session:
            denied = await _require_remote_permission(session, auth_context, "remote_assist.view")
            if denied is not None:
                return denied
            service = RemoteAssistService(session)
            remote_session, token = await service.get_viewer_info(
                session_id=session_id,
                operator_id=auth_context.actor_id,
                is_admin=auth_context.actor_role == "admin",
            )
            await session.commit()
            data = remote_session_to_dict(remote_session)
            data.update(
                {
                    "signaling_url": _signaling_url(request, remote_session.id),
                    "token": token,
                    "turn_warning": not bool((remote_session.ice_config or {}).get("ice_servers")),
                }
            )
            return web.json_response({"status": "ok", "data": data})
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] viewer failed: session_id={session_id} error={exc}")
        return _server_error("REMOTE_ASSIST_VIEWER_FAILED", "Remote Assist viewer lookup failed")


async def handle_remote_assist_end(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    session_id = request.match_info["session_id"]
    data = await _read_json(request)
    reason = str(data.get("reason") or "finished")
    try:
        async with get_session() as session:
            service = RemoteAssistService(session)
            remote_session = await service.repo.get(session_id)
            if remote_session is None:
                raise RemoteAssistError("SESSION_NOT_FOUND", "Remote Assist session not found", status=404)
            if auth_context.actor_role == "agent" and auth_context.actor_id != remote_session.device_id:
                raise RemoteAssistError("PERMISSION_DENIED", "Agent device does not match session", status=403)
            if auth_context.actor_role != "agent":
                denied = await _require_remote_permission(session, auth_context, "remote_assist.view")
                if denied is not None:
                    return denied
            remote_session = await service.end_session(
                session_id=session_id,
                actor_type=auth_context.actor_role,
                actor_id=auth_context.actor_id,
                reason=reason,
            )
            await session.commit()
            return web.json_response({"status": "ok", "data": remote_session_to_dict(remote_session)})
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] end failed: session_id={session_id} error={exc}")
        return _server_error("REMOTE_ASSIST_END_FAILED", "Remote Assist end failed")


async def handle_remote_assist_fail(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    session_id = request.match_info["session_id"]
    data = await _read_json(request)
    error_code = str(data.get("error_code") or "WEBRTC_FAILED").strip() or "WEBRTC_FAILED"
    error_message = str(data.get("error_message") or "Remote Assist failed").strip() or "Remote Assist failed"
    try:
        async with get_session() as session:
            service = RemoteAssistService(session)
            remote_session = await service.repo.get(session_id)
            if remote_session is None:
                raise RemoteAssistError("SESSION_NOT_FOUND", "Remote Assist session not found", status=404)
            if auth_context.actor_role == "agent" and auth_context.actor_id != remote_session.device_id:
                raise RemoteAssistError("PERMISSION_DENIED", "Agent device does not match session", status=403)
            if auth_context.actor_role != "agent":
                denied = await _require_remote_permission(session, auth_context, "remote_assist.view")
                if denied is not None:
                    return denied
            remote_session = await service.fail_session(
                session_id=session_id,
                actor_type=auth_context.actor_role,
                actor_id=auth_context.actor_id,
                error_code=error_code,
                error_message=error_message,
            )
            await session.commit()
            return web.json_response({"status": "ok", "data": remote_session_to_dict(remote_session)})
    except RemoteAssistError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception(f"[remote_assist] fail failed: session_id={session_id} error={exc}")
        return _server_error("REMOTE_ASSIST_FAIL_FAILED", "Remote Assist fail update failed")


async def handle_remote_assist_status(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        async with get_session() as session:
            service = RemoteAssistService(session)
            remote_session = await service.repo.get(session_id)
            if remote_session is None:
                raise RemoteAssistError("SESSION_NOT_FOUND", "Remote Assist session not found", status=404)
            return web.json_response({"status": "ok", "data": remote_session_to_dict(remote_session)})
    except RemoteAssistError as exc:
        return _error_response(exc)


async def handle_remote_assist_ticket_sessions(request: web.Request) -> web.Response:
    auth_context = request.get("auth_context")
    if auth_context is None:
        return _server_error("AUTH_REQUIRED", "Authentication required", status=401)
    ticket_id = request.match_info["ticket_id"]
    try:
        async with get_session() as session:
            denied = await _require_remote_permission(session, auth_context, "remote_assist.view")
            if denied is not None:
                return denied
            service = RemoteAssistService(session)
            sessions = await service.repo.list_for_ticket(ticket_id, limit=30)
            return web.json_response({"status": "ok", "data": {"sessions": [remote_session_to_dict(item) for item in sessions]}})
    except Exception as exc:
        logger.exception(f"[remote_assist] list failed: ticket_id={ticket_id} error={exc}")
        return _server_error("REMOTE_ASSIST_LIST_FAILED", "Remote Assist sessions lookup failed")
