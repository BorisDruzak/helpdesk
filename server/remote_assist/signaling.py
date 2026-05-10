from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from aiohttp import WSMsgType, web
from loguru import logger

from app.db import get_session
from remote_assist.service import RemoteAssistService, verify_token_hash


ALLOWED_SIGNALING_TYPES = {
    "session.hello",
    "session.ready",
    "session.error",
    "session.end",
    "webrtc.offer",
    "webrtc.answer",
    "webrtc.ice_candidate",
    "webrtc.connection_state",
    "control.state",
    "control.error",
}


def _peer_store(app: web.Application) -> dict[str, dict[str, web.WebSocketResponse]]:
    store = app.get("remote_assist_signaling_peers")
    if not isinstance(store, dict):
        store = {}
        app["remote_assist_signaling_peers"] = store
    return store


async def _reject(code: str, message: str, *, status: int = 403) -> web.Response:
    return web.json_response({"status": "error", "error_code": code, "error": message}, status=status)


async def websocket_remote_assist_handler(request: web.Request) -> web.StreamResponse:
    session_id = request.match_info["session_id"]
    role = str(request.query.get("role") or "").strip().lower()
    token = str(request.query.get("token") or "").strip()
    if role not in {"operator", "agent"}:
        return await _reject("ROLE_INVALID", "Invalid signaling role", status=400)
    if not token:
        return await _reject("TOKEN_INVALID", "Token is required", status=401)

    async with get_session() as db_session:
        service = RemoteAssistService(db_session)
        remote_session = await service.repo.get(session_id)
        if remote_session is None:
            return await _reject("SESSION_NOT_FOUND", "Remote Assist session not found", status=404)
        expected_hash = remote_session.operator_token_hash if role == "operator" else remote_session.agent_token_hash
        if not verify_token_hash(token, expected_hash):
            return await _reject("TOKEN_INVALID", "Invalid signaling token", status=401)
        if remote_session.expires_at <= datetime.now(timezone.utc):
            await service.expire_session(remote_session, actor_type="system", reason="timeout")
            await db_session.commit()
            return await _reject("SESSION_EXPIRED", "Remote Assist session expired", status=409)
        if remote_session.status not in {"approved", "starting", "active"}:
            return await _reject("SESSION_STATUS_INVALID", "Session is not ready for signaling", status=409)
        if remote_session.status == "approved":
            await service.repo.set_status(remote_session, status="starting")
        await service.log_event(
            remote_session,
            f"signaling_connected_{role}",
            actor_type=role,
            actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
            payload={},
            write_timeline=False,
        )
        await db_session.commit()

    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=256 * 1024)
    await ws.prepare(request)

    store = _peer_store(request.app)
    peers = store.setdefault(session_id, {})
    existing = peers.get(role)
    if existing is not None and not existing.closed:
        await ws.send_json({"type": "session.error", "payload": {"error_code": "PEER_ALREADY_CONNECTED"}})
        await ws.close(code=4001, message=b"peer already connected")
        return ws
    peers[role] = ws

    try:
        await ws.send_json(
            {
                "type": "session.hello",
                "session_id": session_id,
                "ts": datetime.now(timezone.utc).isoformat(),
                "payload": {"role": role},
            }
        )
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _handle_signal_message(request, ws, session_id, role, msg.data)
            elif msg.type == WSMsgType.ERROR:
                logger.debug(f"[remote_assist.signaling] ws error: session_id={session_id} role={role} error={ws.exception()}")
                break
    finally:
        if peers.get(role) is ws:
            peers.pop(role, None)
        if not peers:
            store.pop(session_id, None)
        async with get_session() as db_session:
            service = RemoteAssistService(db_session)
            remote_session = await service.repo.get(session_id)
            if remote_session is not None:
                await service.log_event(
                    remote_session,
                    f"{role}_disconnected",
                    actor_type=role,
                    actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
                    payload={},
                    write_timeline=False,
                )
                await db_session.commit()
    return ws


async def _handle_signal_message(
    request: web.Request,
    ws: web.WebSocketResponse,
    session_id: str,
    role: str,
    raw_text: str,
) -> None:
    try:
        message = json.loads(raw_text)
    except ValueError:
        await ws.send_json({"type": "session.error", "payload": {"error_code": "MESSAGE_INVALID"}})
        return
    if not isinstance(message, dict):
        await ws.send_json({"type": "session.error", "payload": {"error_code": "MESSAGE_INVALID"}})
        return
    message_type = str(message.get("type") or "").strip()
    if message_type not in ALLOWED_SIGNALING_TYPES:
        await ws.send_json({"type": "session.error", "payload": {"error_code": "MESSAGE_TYPE_NOT_ALLOWED"}})
        return
    message["session_id"] = session_id
    message.setdefault("ts", datetime.now(timezone.utc).isoformat())

    if message_type == "webrtc.connection_state":
        await _mark_connection_state(session_id, role, message.get("payload") if isinstance(message.get("payload"), dict) else {})
    elif message_type == "session.end":
        await _end_from_signal(session_id, role, message.get("payload") if isinstance(message.get("payload"), dict) else {})
    elif message_type in {"webrtc.offer", "webrtc.answer", "webrtc.ice_candidate"}:
        await _log_signaling_event(session_id, role, message_type)
    elif message_type in {"control.state", "control.error"}:
        await _log_control_event(session_id, role, message_type, message.get("payload") if isinstance(message.get("payload"), dict) else {})

    target_role = "agent" if role == "operator" else "operator"
    peer = _peer_store(request.app).get(session_id, {}).get(target_role)
    if peer is not None and not peer.closed:
        await peer.send_json(message)


async def _mark_connection_state(session_id: str, role: str, payload: dict[str, Any]) -> None:
    state = str(payload.get("state") or "").strip().lower()
    if state not in {"connected", "completed"}:
        return
    async with get_session() as db_session:
        service = RemoteAssistService(db_session)
        remote_session = await service.repo.get(session_id)
        if remote_session is None:
            return
        if remote_session.status != "active":
            await service.repo.set_status(remote_session, status="active")
            await service.log_event(
                remote_session,
                "session_started",
                actor_type=role,
                actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
                payload={"state": state},
                write_timeline=True,
            )
        await service.log_event(
            remote_session,
            "ice_connected",
            actor_type=role,
            actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
            payload={"state": state},
            write_timeline=False,
        )
        await db_session.commit()


async def _log_signaling_event(session_id: str, role: str, message_type: str) -> None:
    event_type = {
        "webrtc.offer": "offer_received",
        "webrtc.answer": "answer_received",
        "webrtc.ice_candidate": "ice_candidate_received",
    }.get(message_type)
    if not event_type:
        return
    async with get_session() as db_session:
        service = RemoteAssistService(db_session)
        remote_session = await service.repo.get(session_id)
        if remote_session is None:
            return
        await service.log_event(
            remote_session,
            event_type,
            actor_type=role,
            actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
            payload={},
            write_timeline=False,
        )
        await db_session.commit()


async def _log_control_event(session_id: str, role: str, message_type: str, payload: dict[str, Any]) -> None:
    if message_type == "control.state":
        event_type = "control_enabled" if bool(payload.get("enabled")) else "control_disabled"
    else:
        event_type = "control_rejected"
    async with get_session() as db_session:
        service = RemoteAssistService(db_session)
        remote_session = await service.repo.get(session_id)
        if remote_session is None:
            return
        await service.log_event(
            remote_session,
            event_type,
            actor_type=role,
            actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
            payload=payload,
            write_timeline=False,
        )
        await db_session.commit()


async def _end_from_signal(session_id: str, role: str, payload: dict[str, Any]) -> None:
    async with get_session() as db_session:
        service = RemoteAssistService(db_session)
        remote_session = await service.repo.get(session_id)
        if remote_session is None:
            return
        await service.end_session(
            session_id=session_id,
            actor_type=role,
            actor_id=remote_session.operator_id if role == "operator" else remote_session.device_id,
            reason=str(payload.get("reason") or f"{role}_ended"),
        )
        await db_session.commit()
