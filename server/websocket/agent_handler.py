"""
WebSocket РѕР±СЂР°Р±РѕС‚С‡РёРє РґР»СЏ Р°РіРµРЅС‚РѕРІ.
"""

import asyncio
import time
import uuid
import json
from datetime import datetime, timezone
from aiohttp import web, WSMsgType
from loguru import logger
from typing import Optional, Tuple, Any
from utils import now_iso
from websocket.protocol import (
    send_ws_command,
    push_chat_event_to_ui,
    send_outbox_ack,
    send_outbox_nack
)
from websocket.batch_ack_manager import BatchAckManager, NackInfo
from websocket.validator import EventValidator
from websocket.command_result_parser import normalize_command_result_payload
from config import ENABLE_DB_PERSISTENCE
from auth.service import AuthService
from auth.context import AuthContext, AuthType

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


async def persist_job_event(job_id: str, event: dict) -> None:
    """
    Persist job event to database (best-effort, non-blocking).
    
    This function attempts to save events to PostgreSQL for persistence
    and replay functionality. If the database is unavailable or disabled,
    it silently continues without raising errors.
    
    Args:
        job_id: Job identifier
        event: Event payload dictionary containing event data
    """
    # Skip if database persistence is disabled
    if not ENABLE_DB_PERSISTENCE:
        return
    
    # Skip if database components are not available
    if not DB_AVAILABLE:
        logger.debug(f"[persist_job_event] DB not available, skipping persistence for job_id={job_id}")
        return
    
    try:
        event_type = event.get("event", "unknown")
        
        # Create database session and persist event
        async with get_session() as session:
            repo = JobEventsRepo(session)
            await repo.add_event(
                job_id=job_id,
                event_type=event_type,
                payload=event
            )
            
        logger.debug(
            f"[persist_job_event] Successfully persisted event: "
            f"job_id={job_id} event_type={event_type}"
        )
    except Exception as e:
        # Log warning but don't raise - best effort persistence
        # Server should continue working even if DB persistence fails
        event_type = event.get("event", "unknown")
        logger.warning(
            f"[persist_job_event] Failed to persist event to DB "
            f"(job_id={job_id}, event_type={event_type}): {e}"
        )


async def handle_handshake(
    ws: web.WebSocketResponse,
    data: dict,
    request: web.Request,
    state: Any,
) -> Tuple[Optional[web.WebSocketResponse], Optional[str], Optional[str], bool]:
    """
    РћР±СЂР°Р±РѕС‚РєР° handshake (Protocol V3).
    Р’РѕР·РІСЂР°С‰Р°РµС‚ (ws РґР»СЏ return РїСЂРё Р·Р°РєСЂС‹С‚РёРё, agent_id, device_id, authenticated) РёР»Рё (None, aid, did, True) РїСЂРё СѓСЃРїРµС…Рµ.
    Р›РѕРіРёРєР° СЂРµР°Р»РёР·РѕРІР°РЅР° РІ РѕСЃРЅРѕРІРЅРѕРј С†РёРєР»Рµ РЅРёР¶Рµ (Р±Р»РѕРє if msg_type == "handshake"); РїСЂРё СЂРµС„Р°РєС‚РѕСЂРёРЅРіРµ РїРµСЂРµРЅРµСЃС‚Рё СЃСЋРґР°.
    """
    return (None, None, None, False)


async def handle_command_result(
    ws: web.WebSocketResponse,
    data: dict,
    state: Any,
    agent_id: Optional[str],
) -> None:
    """РћР±СЂР°Р±РѕС‚РєР° command_result (lifecycle, operations, pending_command_futures). Р›РѕРіРёРєР° РІ Р±Р»РѕРєРµ elif msg_type == "command_result"."""
    pass


async def handle_outbox_item(
    ws: web.WebSocketResponse,
    data: dict,
    state: Any,
    agent_id: Optional[str],
    batch_ack_manager: BatchAckManager,
    event_validator: EventValidator,
) -> None:
    """РћР±СЂР°Р±РѕС‚РєР° outbox_item (device/ticket events, batch ACK/NACK). Р›РѕРіРёРєР° РІ Р±Р»РѕРєРµ elif msg_type == "outbox_item"."""
    pass


async def websocket_handler(request):
    """
    WebSocket РѕР±СЂР°Р±РѕС‚С‡РёРє РґР»СЏ relay-Р°СЂС…РёС‚РµРєС‚СѓСЂС‹ СЃРµСЂРІРµСЂ-Р°РіРµРЅС‚.
    
    РЎРµСЂРІРµСЂ РІС‹СЃС‚СѓРїР°РµС‚ РІ СЂРѕР»Рё СЂРµС‚СЂР°РЅСЃР»СЏС‚РѕСЂР° РєРѕРјР°РЅРґ РјРµР¶РґСѓ РІРµР±-РёРЅС‚РµСЂС„РµР№СЃРѕРј Рё Р°РіРµРЅС‚Р°РјРё.
    Р’СЃСЏ Р»РѕРіРёРєР° СЃР±РѕСЂР° РґР°РЅРЅС‹С… РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ РЅР° СЃС‚РѕСЂРѕРЅРµ Р°РіРµРЅС‚Р° (ws_agent.py).
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    state = request.app['state']
    
    agent_id = None
    device_id = None
    authenticated = False
    
    # Phase B: Batch ACK Manager and Validator
    batch_ack_manager = BatchAckManager()
    event_validator = EventValidator()
    
    logger.info("рџџў РќРѕРІРѕРµ WebSocket СЃРѕРµРґРёРЅРµРЅРёРµ")
    
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type = data.get("type")
                    
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # a) type == "handshake"
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    if msg_type == "handshake":
                        # Phase E: РЎС‚СЂРѕРіР°СЏ РІР°Р»РёРґР°С†РёСЏ protocol_version
                        protocol_version = data.get("protocol_version")
                        
                        # РљР РРўРР§РќРћ: С‚СЂРµР±СѓРµРј ws_ticket_v3 (Phase E)
                        if protocol_version != "ws_ticket_v3":
                            logger.error(
                                f"рџ”ґ Invalid protocol_version: {protocol_version}, "
                                f"expected ws_ticket_v3"
                            )
                            await ws.close(
                                code=4003,
                                message=b"Protocol V3 (ws_ticket_v3) required"
                            )
                            return ws
                        
                        # Phase E: РџСЂРѕРІРµСЂСЏРµРј РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ capabilities
                        meta = data.get("meta", {})
                        capabilities = meta.get("capabilities", [])
                        required_capabilities = {
                            "protocol_v3",
                            "envelope_v3",
                            "outbox_ack_v3"
                        }
                        missing_capabilities = required_capabilities - set(capabilities)
                        
                        if missing_capabilities:
                            logger.error(
                                f"рџ”ґ Missing required capabilities: {missing_capabilities}"
                            )
                            await ws.close(
                                code=4003,
                                message=f"Missing required capabilities: {missing_capabilities}".encode()
                            )
                            return ws
                        
                        # Phase 3: РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ РґР»СЏ Р°СѓС‚РµРЅС‚РёС„РёРєР°С†РёРё С‡РµСЂРµР· Р‘Р”
                        token = data.get("token")
                        logger.debug(
                            f"Handshake: token received=%s prefix=%s",
                            bool(token),
                            token[:12] + "..." if token and len(token) >= 12 else (token or "")
                        )
                        
                        # РР·РІР»РµРєР°РµРј device_id РёР· payload РґР»СЏ РѕС‚СЃР»РµР¶РёРІР°РЅРёСЏ РїРѕРїС‹С‚РѕРє РїРѕРґРєР»СЋС‡РµРЅРёСЏ
                        # РџСЂРѕРІРµСЂСЏРµРј РІ СЂР°Р·РЅС‹С… РјРµСЃС‚Р°С…: РєРѕСЂРµРЅСЊ СЃРѕРѕР±С‰РµРЅРёСЏ, payload, meta
                        payload_device_id = (
                            data.get("device_id") or 
                            data.get("payload", {}).get("device_id") or
                            data.get("payload", {}).get("uuid") or
                            data.get("uuid")
                        )
                        
                        if not token:
                            logger.warning("рџ”ґ РџРѕРїС‹С‚РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Р±РµР· С‚РѕРєРµРЅР°")
                            # РЎРѕС…СЂР°РЅСЏРµРј РїРѕРїС‹С‚РєСѓ РїРѕРґРєР»СЋС‡РµРЅРёСЏ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ РІ admin РїР°РЅРµР»Рё
                            if payload_device_id:
                                state.pending_connections[payload_device_id] = {
                                    "device_id": payload_device_id,
                                    "attempted_at": time.time(),
                                    "ip_address": request.remote,
                                    "user_agent": request.headers.get("User-Agent", ""),
                                    "reason": "no_token"
                                }
                                logger.info(f"рџ“ќ Р—Р°РїРёСЃР°РЅР° РїРѕРїС‹С‚РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ РґР»СЏ device_id={payload_device_id[:8]}...")
                            await ws.close(code=4003, message=b"Token required")
                            return ws
                        
                        # РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ С‡РµСЂРµР· AuthService (Р‘Р”)
                        auth_service = AuthService(state)
                        token_info = await auth_service.verify_agent_token(token)
                        
                        if not token_info:
                            logger.warning(f"рџ”ґ РќРµРІР°Р»РёРґРЅС‹Р№ С‚РѕРєРµРЅ Р°РіРµРЅС‚Р°: {token[:8]}...")
                            # РЎРѕС…СЂР°РЅСЏРµРј РїРѕРїС‹С‚РєСѓ РїРѕРґРєР»СЋС‡РµРЅРёСЏ СЃ РЅРµРІР°Р»РёРґРЅС‹Рј С‚РѕРєРµРЅРѕРј
                            if payload_device_id:
                                state.pending_connections[payload_device_id] = {
                                    "device_id": payload_device_id,
                                    "attempted_at": time.time(),
                                    "ip_address": request.remote,
                                    "user_agent": request.headers.get("User-Agent", ""),
                                    "reason": "invalid_token"
                                }
                                logger.info(f"рџ“ќ Р—Р°РїРёСЃР°РЅР° РїРѕРїС‹С‚РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ СЃ РЅРµРІР°Р»РёРґРЅС‹Рј С‚РѕРєРµРЅРѕРј РґР»СЏ device_id={payload_device_id[:8]}...")
                            await ws.close(code=4003, message=b"Invalid token")
                            return ws
                        
                        # РљР РРўРР§РќРћ: device_id Р±РµСЂРµС‚СЃСЏ РёР· С‚РѕРєРµРЅР°, РЅРµ РёР· payload
                        device_id = token_info["device_id"]
                        agent_id = device_id
                        
                        # РЎРѕР·РґР°РµРј AuthContext РґР»СЏ СЌС‚РѕРіРѕ СЃРѕРµРґРёРЅРµРЅРёСЏ
                        auth_context = AuthContext(
                            actor_id=device_id,
                            actor_role="agent",
                            auth_type=AuthType.AGENT_TOKEN,
                            token=token
                        )
                        
                        # РўРѕРєРµРЅ РІР°Р»РёРґРµРЅ - СЂР°Р·СЂРµС€Р°РµРј СЂР°Р±РѕС‚Сѓ
                        authenticated = True
                        
                        # РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ device_id РёР· payload СЃРѕРІРїР°РґР°РµС‚ СЃ С‚РѕРєРµРЅРѕРј (РµСЃР»Рё СѓРєР°Р·Р°РЅ)
                        payload_device_id = data.get("device_id")
                        if payload_device_id and payload_device_id != device_id:
                            logger.warning(
                                f"рџ”ґ Device ID mismatch: token={device_id}, payload={payload_device_id}. "
                                f"Using device_id from token."
                            )
                        
                        # Р РµРіРёСЃС‚СЂРёСЂСѓРµРј Р°РіРµРЅС‚Р°
                        metadata = {
                            "device_id": device_id,
                            "agent_version": data.get("agent_version", "unknown"),
                            "modules": data.get("modules", []),
                            "protocol_version": protocol_version,  # Phase E: СЃРѕС…СЂР°РЅСЏРµРј
                            "capabilities": capabilities,  # Phase E: СЃРѕС…СЂР°РЅСЏРµРј
                            "connected_at": time.time(),
                            "last_seen": time.time(),
                            "status": "online",
                            "pending_futures": {},  # Dict[str, asyncio.Future] РґР»СЏ РїР°СЂР°Р»Р»РµР»СЊРЅС‹С… Р·Р°РїСЂРѕСЃРѕРІ
                            "auth_context": auth_context,  # Phase 3: СЃРѕС…СЂР°РЅСЏРµРј AuthContext
                            "token": token,  # Р”Р»СЏ РѕР±СЂР°С‚РЅРѕР№ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё (deprecated)
                            "ws": ws
                        }
                        payload_pre = data.get("payload", {}) or data.get("meta", {})
                        metadata["os_type"] = payload_pre.get("os_type") or payload_pre.get("os")
                        if payload_pre.get("applied_update_version") is not None:
                            metadata["applied_update_version"] = payload_pre["applied_update_version"]
                        if payload_pre.get("last_update_operation_id") is not None:
                            metadata["last_update_operation_id"] = payload_pre["last_update_operation_id"]
                        state.register_agent(agent_id, ws, metadata)
                        
                        logger.success(f"вњ… РђРіРµРЅС‚ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅ: {device_id}")
                        logger.info(f"   Protocol: {protocol_version}")
                        logger.info(f"   Capabilities: {capabilities}")
                        logger.info(f"   РњРѕРґСѓР»Рё: {data.get('modules', [])}")
                        
                        # Device Registry: upsert device and check toolset_hash
                        desired_revision = 0
                        should_request_toolset = False
                        
                        if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                            try:
                                async with get_session() as session:
                                    from app.repos import DevicesRepo, DeviceConfigRepo
                                    
                                    devices_repo = DevicesRepo(session)
                                    config_repo = DeviceConfigRepo(session)
                                    
                                    # Р§РёС‚Р°РµРј os, toolset_hash, tools_count РёР· payload (Р°РіРµРЅС‚ С€Р»С‘С‚ РІ payload)
                                    payload = data.get("payload", {})
                                    agent_toolset_hash = payload.get("toolset_hash") or meta.get("toolset_hash")
                                    agent_version = payload.get("agent_version") or data.get("agent_version", "unknown")
                                    hostname = payload.get("hostname") or meta.get("hostname")
                                    os_info = payload.get("os") or meta.get("os")
                                    tools_version = payload.get("tools_version") or meta.get("tools_version")
                                    modules = payload.get("modules") or data.get("modules", [])
                                    metadata_db = {"modules": modules}
                                    if payload.get("applied_update_version") is not None:
                                        metadata_db["applied_update_version"] = payload["applied_update_version"]
                                    if payload.get("last_update_operation_id") is not None:
                                        metadata_db["last_update_operation_id"] = payload["last_update_operation_id"]
                                    if payload.get("os_type") is not None:
                                        metadata_db["os_type"] = payload["os_type"]
                                    if not metadata_db.get("os_type") and os_info:
                                        metadata_db["os_type"] = os_info
                                    # Upsert device
                                    device = await devices_repo.upsert_on_handshake(
                                        device_id=device_id,
                                        protocol_version=protocol_version,
                                        agent_version=agent_version,
                                        hostname=hostname,
                                        os=os_info,
                                        capabilities=capabilities,
                                        tools_version=tools_version,
                                        toolset_hash=agent_toolset_hash,
                                        metadata=metadata_db
                                    )
                                    
                                    # Get or create config
                                    device_config = await config_repo.get_or_create_default(device_id)
                                    desired_revision = device_config.desired_revision
                                    
                                    # Check if we should request toolset
                                    if agent_toolset_hash is None:
                                        # No toolset hash provided - check rate-limit
                                        should_request_toolset = await devices_repo.should_refresh_toolset(
                                            device_id=device_id,
                                            rate_limit_minutes=10
                                        )
                                        
                                        if should_request_toolset:
                                            logger.info(
                                                f"[handshake] No toolset_hash provided, "
                                                f"will request list_tools (rate-limit passed)"
                                            )
                                        else:
                                            logger.debug(
                                                f"[handshake] No toolset_hash provided, "
                                                f"but rate-limited - skipping list_tools"
                                            )
                                    
                                    elif agent_toolset_hash != device.current_toolset_hash:
                                        # Toolset hash changed - always refresh (no rate-limit)
                                        should_request_toolset = True
                                        logger.info(
                                            f"[handshake] Toolset hash changed: "
                                            f"old={device.current_toolset_hash} "
                                            f"new={agent_toolset_hash}, will request list_tools"
                                        )
                                    else:
                                        # Toolset hash unchanged - no need to refresh
                                        logger.debug(
                                            f"[handshake] Toolset hash unchanged: {agent_toolset_hash}"
                                        )
                                    
                                    # Process modules_inventory if present (payload СѓР¶Рµ РїРѕР»СѓС‡РµРЅ РІС‹С€Рµ)
                                    modules_inventory = payload.get("modules_inventory")
                                    if isinstance(modules_inventory, list):
                                        from websocket.modules_sync import sync_modules_inventory
                                        await sync_modules_inventory(
                                            session=session,
                                            device_id=device_id,
                                            inventory=modules_inventory
                                        )
                                    else:
                                        # Fallback: если modules_inventory отсутствует или имеет неверный формат, запросить через команду
                                        logger.info(
                                            f"[handshake] modules_inventory not provided/invalid, "
                                            f"will request list_installed_modules"
                                        )
                                        # Enqueue list_installed_modules command (async, fire-and-forget)
                                        from websocket.protocol import enqueue_command_async
                                        await enqueue_command_async(
                                            state=state,
                                            device_id=device_id,
                                            command="list_installed_modules",
                                            params={},
                                            actor_role="server",
                                            trace_id=None
                                        )
                                    
                                    await session.commit()
                                    
                            except Exception as e:
                                logger.opt(exception=True).error(
                                    "[handshake] Failed to upsert device: {}",
                                    e,
                                )
                        
                        # Phase D: Get open tickets for handshake sync
                        open_tickets = []
                        if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                            try:
                                async with get_session() as session:
                                    # РљР РРўРР§РќРћ: Р»РѕРєР°Р»СЊРЅС‹Р№ РёРјРїРѕСЂС‚ вЂ” РІ СЌС‚РѕР№ Р¶Рµ С„СѓРЅРєС†РёРё РµСЃС‚СЊ РґСЂСѓРіРёРµ РёРјРїРѕСЂС‚С‹ TicketEventsRepo,
                                    # РёР·-Р·Р° С‡РµРіРѕ РёРјСЏ СЃС‡РёС‚Р°РµС‚СЃСЏ Р»РѕРєР°Р»СЊРЅС‹Рј Рё РІ РґР°РЅРЅРѕР№ РІРµС‚РєРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РЅРµ РѕРїСЂРµРґРµР»РµРЅРѕ
                                    from app.repos import TicketEventsRepo as _TicketEventsRepo
                                    if not DB_AVAILABLE:
                                        logger.warning(
                                            f"[handshake] DB not available, skipping open tickets fetch"
                                        )
                                    else:
                                        ticket_repo = _TicketEventsRepo(session)
                                        open_tickets = await ticket_repo.get_open_tickets_for_device(device_id)
                                        logger.info(
                                            f"[handshake] Found {len(open_tickets)} open tickets "
                                            f"for device_id={device_id}"
                                        )
                            except Exception as e:
                                logger.warning(
                                    f"[handshake] Failed to fetch open tickets: {e}"
                                )
                        
                        # Phase E: РћС‚РїСЂР°РІР»СЏРµРј handshake_ack СЃ server_capabilities Рё desired_revision
                        from config import SERVER_CAPABILITIES
                        
                        handshake_ack = {
                            "type": "handshake_ack",
                            "request_id": data.get("request_id"),
                            "device_id": device_id,
                            "protocol_version": "ws_ticket_v3",  # Phase E: РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ
                            "trace_id": data.get("trace_id") or str(uuid.uuid4()),
                            "payload": {
                                "status": "success",
                                "message": "Handshake accepted",
                                "server_version": "3.0.0",  # Phase E: РІРµСЂСЃРёСЏ СЃРµСЂРІРµСЂР°
                                "open_tickets": open_tickets,  # Phase D: Send open tickets
                                "desired_revision": desired_revision,  # Device config revision
                                "server_capabilities": SERVER_CAPABILITIES  # РР· config.py
                            },
                            "meta": {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "actor_role": "server"
                            }
                        }
                        await ws.send_json(handshake_ack)
                        logger.debug(f"рџ“¤ РћС‚РїСЂР°РІР»РµРЅ handshake_ack Р°РіРµРЅС‚Сѓ {device_id}")
                        if open_tickets:
                            logger.debug(
                                f"рџ“¤ РћС‚РїСЂР°РІР»РµРЅРѕ {len(open_tickets)} РѕС‚РєСЂС‹С‚С‹С… С‚РёРєРµС‚РѕРІ "
                                f"РІ handshake_ack"
                            )
                        
                        # Enqueue list_tools if needed (СЃ debounce: РЅРµ СЃС‚Р°РІРёРј, РµСЃР»Рё СѓР¶Рµ РµСЃС‚СЊ pending list_tools)
                        if should_request_toolset and DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                            try:
                                from websocket.protocol import enqueue_command_async
                                from app.repos import DevicesRepo, OperationsRepo
                                
                                # Р—Р°С‰РёС‚Р° РѕС‚ С€С‚РѕСЂРјР°: РЅРµ enqueue list_tools, РµСЃР»Рё СѓР¶Рµ РµСЃС‚СЊ РѕР¶РёРґР°СЋС‰Р°СЏ РѕРїРµСЂР°С†РёСЏ
                                async with get_session() as session:
                                    op_repo = OperationsRepo(session)
                                    if await op_repo.has_pending_list_tools(device_id):
                                        logger.debug(
                                            f"[handshake] Skipping list_tools: device_id={device_id} "
                                            f"already has pending list_tools"
                                        )
                                        should_request_toolset = False
                                if not should_request_toolset:
                                    pass  # skip enqueue below
                                else:
                                    # Enqueue list_tools command (СЃРѕР·РґР°РµС‚ РѕРїРµСЂР°С†РёСЋ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё)
                                    command_id = await enqueue_command_async(
                                    state=state,
                                    device_id=device_id,
                                    command="list_tools",
                                    params={},
                                    actor_role="server",
                                    trace_id=None
                                )
                                
                                logger.info(
                                    f"[handshake] Enqueued list_tools: "
                                    f"device_id={device_id} command_id={command_id}"
                                )
                                
                                # Update last_toolset_refresh_at immediately to prevent duplicates
                                async with get_session() as session:
                                    devices_repo = DevicesRepo(session)
                                    await devices_repo.update_toolset_refresh_time(device_id)
                                    await session.commit()
                                    
                            except Exception as e:
                                logger.error(
                                    f"[handshake] Failed to enqueue list_tools: {e}",
                                    exc_info=True
                                )
                    
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # b) type == "pong"
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    elif msg_type == "pong":
                        # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ Р°РіРµРЅС‚Р° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё pong
                        if agent_id:
                            agent_info = state.get_agent(agent_id)
                            if agent_info:
                                agent_info["metadata"]["last_seen"] = time.time()
                                agent_info["metadata"]["status"] = "online"
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # b.5) type == "command_ack" - Operations System integration
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    elif msg_type == "command_ack":
                        # Agent acknowledges command receipt
                        if agent_id:
                            agent_info = state.get_agent(agent_id)
                            if agent_info:
                                agent_info["metadata"]["last_seen"] = time.time()
                                
                                payload = data.get("payload", {})
                                # РљР РРўРР§РќРћ: operation_id = request_id (РµРґРёРЅС‹Р№ UUID)
                                operation_id = data.get("request_id")
                                ack_status = payload.get("status")  # "accepted" РёР»Рё "rejected"
                                
                                if not operation_id:
                                    logger.warning(
                                        f"[command_ack] Missing operation_id (request_id) "
                                        f"from agent {agent_id}"
                                    )
                                    continue
                                
                                logger.info(
                                    f"[command_ack] RX from agent {agent_id}: "
                                    f"operation_id={operation_id} status={ack_status}"
                                )
                                
                                # Update operation status based on ack_status
                                if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                    try:
                                        async with get_session() as session:
                                            from app.services import OperationService
                                            # РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·СѓРµРј UiPublisher РёР· state РґР»СЏ push РѕР±РЅРѕРІР»РµРЅРёР№
                                            ui_publisher = state.ui_publisher if hasattr(state, 'ui_publisher') else None
                                            op_service = OperationService(session, publisher=ui_publisher)
                                            
                                            if ack_status == "accepted":
                                                # Agent accepted the command
                                                success = await op_service.mark_accepted(
                                                    operation_id=operation_id,
                                                    expected_statuses=["sent", "queued"]
                                                )
                                                
                                                if success:
                                                    logger.info(
                                                        f"[command_ack] Operation marked as accepted: "
                                                        f"operation_id={operation_id}"
                                                    )
                                                else:
                                                    logger.warning(
                                                        f"[command_ack] Failed to mark operation as accepted: "
                                                        f"operation_id={operation_id} (status mismatch)"
                                                    )
                                                
                                            elif ack_status == "rejected":
                                                # Agent rejected the command (protocol-level error)
                                                error_code = payload.get("error_code", "REJECTED")
                                                error_message = payload.get("error_message", "Command rejected by agent")
                                                
                                                success = await op_service.mark_failed(
                                                    operation_id=operation_id,
                                                    error_code=error_code,
                                                    error_message=error_message,
                                                    expected_statuses=["sent", "queued"]
                                                )
                                                
                                                if success:
                                                    logger.warning(
                                                        f"[command_ack] Operation marked as failed (rejected): "
                                                        f"operation_id={operation_id} error_code={error_code}"
                                                    )
                                                else:
                                                    logger.warning(
                                                        f"[command_ack] Failed to mark operation as failed: "
                                                        f"operation_id={operation_id} (status mismatch)"
                                                    )
                                            else:
                                                logger.warning(
                                                    f"[command_ack] Unknown ack_status: {ack_status} "
                                                    f"for operation_id={operation_id}"
                                                )
                                            
                                            await session.commit()
                                            
                                    except Exception as e:
                                        logger.error(
                                            f"[command_ack] Failed to update operation status: {e}",
                                            exc_info=True
                                        )
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # c) type == "command_result"
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    elif msg_type == "command_result":
                        # Phase C: Result of a command (lifecycle tracking)
                        if agent_id:
                            agent_info = state.get_agent(agent_id)
                            if agent_info:
                                agent_info["metadata"]["last_seen"] = time.time()
                                agent_info["metadata"]["last_response"] = data
                                
                                # PR1: РќРѕСЂРјР°Р»РёР·СѓРµРј payload С‡РµСЂРµР· normalize_command_result_payload
                                raw_payload = data.get("payload")
                                normalized = normalize_command_result_payload(raw_payload)
                                
                                # Р“Р°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅС‹Рµ РїРѕР»СЏ РїРѕСЃР»Рµ РЅРѕСЂРјР°Р»РёР·Р°С†РёРё
                                status = normalized["status"]  # "success" | "error" | "consent_required"
                                error_info = normalized["error"]  # Р’СЃРµРіРґР° dict
                                data_payload = normalized["data"]  # Р’СЃРµРіРґР° dict
                                meta_info = normalized["meta"]  # Р’СЃРµРіРґР° dict
                                is_malformed = normalized["is_malformed"]  # bool
                                
                                # Р”Р»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё СЃ legacy РєРѕРґРѕРј
                                payload = {"status": status, "error": error_info, "data": data_payload, "meta": meta_info}
                                payload_is_broken = is_malformed
                                meta = meta_info
                                
                                # РљР РРўРР§РќРћ: РџСЂРёРѕСЂРёС‚РµС‚РЅРѕ РёСЃРїРѕР»СЊР·СѓРµРј request_id РєР°Рє command_id
                                command_id = data.get("request_id") or meta.get("command_id")
                                
                                logger.debug(
                                    f"[command_result] Processing: command_id={command_id} "
                                    f"status={status} is_malformed={is_malformed}"
                                )
                                
                                if command_id:
                                    # Phase C: Update device_outbox status
                                    # PR#6: Integrate OperationService to mark operations succeeded/failed
                                    if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                        try:
                                            async with get_session() as session:
                                                from app.repos import DeviceOutboxRepo, TicketEventsRepo
                                                from app.services import OperationService
                                                
                                                repo = DeviceOutboxRepo(session)
                                                # РљР РРўРР§РќРћ: РСЃРїРѕР»СЊР·СѓРµРј UiPublisher РёР· state РґР»СЏ push РѕР±РЅРѕРІР»РµРЅРёР№
                                                ui_publisher = state.ui_publisher if hasattr(state, 'ui_publisher') else None
                                                op_service = OperationService(session, publisher=ui_publisher)
                                                
                                                # РљР РРўРР§РќРћ: operation_id = command_id (РµРґРёРЅС‹Р№ UUID end-to-end)
                                                operation_id = command_id
                                                
                                                # РџСЂРѕРІРµСЂРёС‚СЊ, СЏРІР»СЏРµС‚СЃСЏ Р»Рё СЌС‚Рѕ cancel-op РѕРїРµСЂР°С†РёРµР№
                                                from app.repos import OperationsRepo
                                                ops_repo = OperationsRepo(session)
                                                cancel_op = await ops_repo.get_by_operation_id(operation_id)
                                                
                                                # РљР РРўРР§РќРћ: Р›РѕРіРёСЂСѓРµРј РёРЅС„РѕСЂРјР°С†РёСЋ РѕР± РѕРїРµСЂР°С†РёРё РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё
                                                if cancel_op:
                                                    logger.debug(
                                                        f"[command_result] Found operation: "
                                                        f"operation_id={operation_id} kind={cancel_op.kind} "
                                                        f"status={cancel_op.status}"
                                                    )
                                                else:
                                                    logger.warning(
                                                        f"[command_result] CRITICAL: Operation not found in DB: "
                                                        f"operation_id={operation_id} command_id={command_id}"
                                                    )
                                                
                                                if cancel_op and cancel_op.kind == "cancel_operation":
                                                    # Р­С‚Рѕ СЂРµР·СѓР»СЊС‚Р°С‚ cancel-РєРѕРјР°РЅРґС‹
                                                    target_operation_id = cancel_op.cancel_target_operation_id
                                                    
                                                    if not target_operation_id:
                                                        logger.error(
                                                            f"[command_result] Cancel-op {operation_id} has no cancel_target_operation_id"
                                                        )
                                                    else:
                                                        target_op = await ops_repo.get_by_operation_id(target_operation_id)
                                                        
                                                        if status == "success":
                                                            # Cancel СѓСЃРїРµС€РµРЅ: РѕР±РЅРѕРІРёС‚СЊ target-op РґРѕ canceled
                                                            if target_op and target_op.status == "cancel_requested":
                                                                # Guarded update: С‚РѕР»СЊРєРѕ РµСЃР»Рё РµС‰Рµ РІ cancel_requested
                                                                success = await op_service.mark_canceled(
                                                                    operation_id=target_operation_id,
                                                                    expected_statuses=["cancel_requested"]
                                                                )
                                                                
                                                                if success:
                                                                    logger.info(
                                                                        f"[command_result] Target operation marked as canceled: "
                                                                        f"target_operation_id={target_operation_id}"
                                                                    )
                                                                    
                                                                    # Р—Р°РїРёСЃР°С‚СЊ op_canceled event (РµСЃР»Рё РµСЃС‚СЊ ticket_id)
                                                                    if target_op.ticket_id:
                                                                        from app.repos import TicketEventsRepo
                                                                        events_repo = TicketEventsRepo(session)
                                                                        # Р“РµРЅРµСЂРёСЂСѓРµРј event_id РґР»СЏ server-originated СЃРѕР±С‹С‚РёСЏ
                                                                        event_id = str(uuid.uuid4())
                                                                        result = await events_repo.add_event(
                                                                            ticket_id=target_op.ticket_id,
                                                                            device_id=target_op.device_id,
                                                                            agent_seq=None,  # Server-originated
                                                                            event_type="op_canceled",
                                                                            payload={
                                                                                "operation_id": target_operation_id,
                                                                                "cancel_operation_id": operation_id
                                                                            },
                                                                            trace_id=cancel_op.trace_id,
                                                                            event_id=event_id,
                                                                            operation_id=target_operation_id
                                                                        )
                                                                        if result:
                                                                            inserted_id, created_at = result
                                                                            await session.commit()
                                                                            # Push event to UI
                                                                            if state.subscription_registry:
                                                                                from websocket.ui_handler import push_ticket_event_committed
                                                                                await push_ticket_event_committed(
                                                                                    state,
                                                                                    ticket_id=target_op.ticket_id,
                                                                                    event_id=inserted_id,
                                                                                    event_type="op_canceled",
                                                                                    operation_id=target_operation_id,
                                                                                    agent_seq=None,
                                                                                    created_at=created_at,
                                                                                    payload={
                                                                                        "operation_id": target_operation_id,
                                                                                        "cancel_operation_id": operation_id
                                                                                    }
                                                                                )
                                                                        else:
                                                                            await session.commit()
                                                                else:
                                                                    logger.warning(
                                                                        f"[command_result] Failed to mark target operation as canceled: "
                                                                        f"target_operation_id={target_operation_id} "
                                                                        f"(status={target_op.status if target_op else 'not found'})"
                                                                    )
                                                            
                                                            # Mark cancel-op РєР°Рє succeeded
                                                            await op_service.mark_succeeded(
                                                                operation_id=operation_id,
                                                                result_summary="Cancel operation completed successfully",
                                                                expected_statuses=["queued", "sent", "accepted", "running"]
                                                            )
                                                        
                                                        elif status == "error":
                                                            # Cancel failed: rollback target-op Рє status_before_cancel
                                                            error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                            error_message = error_info.get("message", "Unknown error")
                                                            
                                                            if target_op and target_op.status == "cancel_requested" and target_op.status_before_cancel:
                                                                # Guarded rollback: С‚РѕР»СЊРєРѕ РµСЃР»Рё РµС‰Рµ РІ cancel_requested
                                                                rollback_success = await op_service.rollback_cancel_request(
                                                                    operation_id=target_operation_id,
                                                                    expected_statuses=["cancel_requested"]
                                                                )
                                                                
                                                                if rollback_success:
                                                                    logger.info(
                                                                        f"[command_result] Rolled back cancel request: "
                                                                        f"target_operation_id={target_operation_id} "
                                                                        f"restored_status={target_op.status_before_cancel}"
                                                                    )
                                                                    
                                                                    # Р—Р°РїРёСЃР°С‚СЊ op_cancel_failed event (РµСЃР»Рё РµСЃС‚СЊ ticket_id)
                                                                    if target_op.ticket_id:
                                                                        from app.repos import TicketEventsRepo
                                                                        events_repo = TicketEventsRepo(session)
                                                                        # Р“РµРЅРµСЂРёСЂСѓРµРј event_id РґР»СЏ server-originated СЃРѕР±С‹С‚РёСЏ
                                                                        event_id = str(uuid.uuid4())
                                                                        result = await events_repo.add_event(
                                                                            ticket_id=target_op.ticket_id,
                                                                            device_id=target_op.device_id,
                                                                            agent_seq=None,  # Server-originated
                                                                            event_type="op_cancel_failed",
                                                                            payload={
                                                                                "operation_id": target_operation_id,
                                                                                "cancel_operation_id": operation_id,
                                                                                "error_code": error_code,
                                                                                "error_message": error_message
                                                                            },
                                                                            trace_id=cancel_op.trace_id,
                                                                            event_id=event_id,
                                                                            operation_id=target_operation_id
                                                                        )
                                                                else:
                                                                    logger.warning(
                                                                        f"[command_result] Failed to rollback cancel request: "
                                                                        f"target_operation_id={target_operation_id} "
                                                                        f"(status={target_op.status if target_op else 'not found'})"
                                                                    )
                                                            
                                                            # Mark cancel-op РєР°Рє failed
                                                            await op_service.mark_failed(
                                                                operation_id=operation_id,
                                                                error_code=error_code,
                                                                error_message=error_message,
                                                                expected_statuses=["queued", "sent", "accepted", "running"]
                                                            )
                                                        
                                                        # Mark outbox as delivered
                                                        await repo.mark_as_delivered(command_id)
                                                
                                                # Legacy: Check if this is a canceled operation confirmation (old format)
                                                elif status == "success":
                                                    data_payload = payload.get("data", {})
                                                    is_canceled = data_payload.get("canceled") == True
                                                    
                                                    if is_canceled:
                                                        # Mark operation as canceled (agent confirmed cancellation)
                                                        success = await op_service.mark_canceled(
                                                            operation_id=operation_id,
                                                            expected_statuses=["cancel_requested", "running", "accepted", "waiting_consent"]
                                                        )
                                                        
                                                        if success:
                                                            logger.info(
                                                                f"[command_result] Operation marked as canceled (legacy format): "
                                                                f"operation_id={operation_id}"
                                                            )
                                                        
                                                        # Mark outbox as delivered
                                                        await repo.mark_as_delivered(command_id)
                                                    else:
                                                        # РљР РРўРР§РќРћ: Р­С‚Рѕ РѕР±С‹С‡РЅР°СЏ СѓСЃРїРµС€РЅР°СЏ РѕРїРµСЂР°С†РёСЏ (РЅРµ cancel)
                                                        # РџСЂРѕРґРѕР»Р¶Р°РµРј РѕР±СЂР°Р±РѕС‚РєСѓ РІ СЃР»РµРґСѓСЋС‰РµРј Р±Р»РѕРєРµ
                                                        pass
                                                
                                                # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° РѕР±С‹С‡РЅС‹С… СѓСЃРїРµС€РЅС‹С… РѕРїРµСЂР°С†РёР№
                                                # Р­С‚РѕС‚ Р±Р»РѕРє РІС‹РїРѕР»РЅСЏРµС‚СЃСЏ РµСЃР»Рё:
                                                # 1. РћРїРµСЂР°С†РёСЏ РЅРµ СЏРІР»СЏРµС‚СЃСЏ cancel_operation
                                                # 2. status == "success"
                                                # 3. is_canceled != True (РґР»СЏ legacy С„РѕСЂРјР°С‚Р°)
                                                if status == "success" and (not cancel_op or cancel_op.kind != "cancel_operation"):
                                                    # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ РѕР±СЂР°Р±РѕС‚Р°Р»Рё Р»Рё СѓР¶Рµ РІ legacy Р±Р»РѕРєРµ
                                                    data_payload_check = payload.get("data", {})
                                                    is_canceled_check = data_payload_check.get("canceled") == True
                                                    
                                                    if not is_canceled_check:
                                                        # Mark outbox as delivered
                                                        await repo.mark_as_delivered(command_id)
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° list_tools Р”Рћ mark_succeeded
                                                    # Р­С‚Рѕ РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ snapshot СЃРѕС…СЂР°РЅСЏРµС‚СЃСЏ РІ Р‘Р” РґР°Р¶Рµ РµСЃР»Рё mark_succeeded СѓРїР°РґРµС‚
                                                    cmd_record = await repo.get_command_by_id(command_id)
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° list_tools РЅРµР·Р°РІРёСЃРёРјРѕ РѕС‚ СЂРµР·СѓР»СЊС‚Р°С‚Р° mark_succeeded
                                                    # РРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚СЊ РѕР±РµСЃРїРµС‡РёРІР°РµС‚СЃСЏ UNIQUE constraint РІ insert_snapshot_if_not_exists
                                                    # РџРѕСЌС‚РѕРјСѓ РІСЃРµРіРґР° РѕР±СЂР°Р±Р°С‚С‹РІР°РµРј, РµСЃР»Рё РµСЃС‚СЊ tools_list РІ payload
                                                    if cmd_record and cmd_record.command == "list_tools":
                                                        # РР·РІР»РµРєР°РµРј tools_list
                                                        data_payload = payload.get("data", {})
                                                        observations = data_payload.get("observations", {})
                                                        tools_list = observations.get("tools", [])
                                                        
                                                        if tools_list:
                                                            from app.repos import DevicesRepo, ToolsetSnapshotsRepo
                                                            from utils.toolset_hash import sort_tools, compute_toolset_hash
                                                            from utils.tool_metadata_validation import filter_tools_production_catalog

                                                            # Production catalog: С‚РѕР»СЊРєРѕ РёРЅСЃС‚СЂСѓРјРµРЅС‚С‹ СЃ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹РјРё metadata
                                                            production_tools = filter_tools_production_catalog(tools_list)
                                                            use_tools = production_tools if production_tools else tools_list

                                                            devices_repo = DevicesRepo(session)
                                                            device = await devices_repo.get_by_device_id(agent_id)

                                                            if device:
                                                                sorted_tools = sort_tools(use_tools)
                                                                
                                                                # Р’С‹С‡РёСЃР»СЏРµРј toolset_hash (server-computed as source of truth)
                                                                toolset_hash_server = compute_toolset_hash(sorted_tools)
                                                                
                                                                # РРґРµРјРїРѕС‚РµРЅС‚РЅР°СЏ РІСЃС‚Р°РІРєР° snapshot (UNIQUE constraint РїСЂРµРґРѕС‚РІСЂР°С‰Р°РµС‚ РґСѓР±Р»РёРєР°С‚С‹)
                                                                snapshots_repo = ToolsetSnapshotsRepo(session)
                                                                snapshot_id = await snapshots_repo.insert_snapshot_if_not_exists(
                                                                    device_id=agent_id,
                                                                    toolset_hash=toolset_hash_server,
                                                                    toolset_json={"tools": sorted_tools},
                                                                    agent_version=device.agent_version,
                                                                    tool_count=len(sorted_tools)
                                                                )
                                                                
                                                                if snapshot_id:
                                                                    # РћР±РЅРѕРІР»СЏРµРј devices
                                                                    await devices_repo.update_toolset_snapshot_ref(
                                                                        device_id=agent_id,
                                                                        toolset_hash=toolset_hash_server,
                                                                        snapshot_id=snapshot_id
                                                                    )
                                                                    
                                                                    logger.info(
                                                                        f"[command_result] Processed list_tools (before mark_succeeded): "
                                                                        f"device_id={agent_id} "
                                                                        f"toolset_hash={toolset_hash_server} "
                                                                        f"snapshot_id={snapshot_id} "
                                                                        f"tool_count={len(sorted_tools)}"
                                                                    )
                                                            else:
                                                                logger.error(
                                                                    f"[command_result] Device not found for "
                                                                    f"list_tools result: device_id={agent_id}"
                                                                )
                                                        else:
                                                            logger.warning(
                                                                f"[command_result] list_tools returned empty tools list: "
                                                                f"device_id={agent_id}"
                                                            )
                                                    
                                                    # РљР РРўРР§РќРћ: РџСЂРѕРІРµСЂСЏРµРј С‚РµРєСѓС‰РёР№ СЃС‚Р°С‚СѓСЃ РѕРїРµСЂР°С†РёРё РїРµСЂРµРґ РѕР±РЅРѕРІР»РµРЅРёРµРј
                                                    from app.repos import OperationsRepo
                                                    ops_repo_check = OperationsRepo(session)
                                                    current_op = await ops_repo_check.get_by_operation_id(operation_id)
                                                    
                                                    if not current_op:
                                                        logger.error(
                                                            f"[command_result] CRITICAL: Operation not found: "
                                                            f"operation_id={operation_id} command_id={command_id}"
                                                        )
                                                    else:
                                                        logger.debug(
                                                            f"[command_result] Current operation status before mark_succeeded: "
                                                            f"operation_id={operation_id} current_status={current_op.status}"
                                                        )
                                                    
                                                    # PR#6: Mark operation as succeeded
                                                    # Extract result summary from payload
                                                    data_payload = payload.get("data", {})
                                                    observations = data_payload.get("observations", {})
                                                    result_summary = None
                                                    
                                                    # Try to create a brief summary from observations
                                                    if observations:
                                                        # Limit summary to 500 chars
                                                        summary_str = str(observations)[:500]
                                                        result_summary = summary_str
                                                    
                                                    # Mark operation as succeeded with optimistic locking
                                                    # РљР РРўРР§РќРћ: Р Р°Р·СЂРµС€Р°РµРј РѕР±РЅРѕРІР»РµРЅРёРµ РёР· queued/sent, С‚Р°Рє РєР°Рє РѕРїРµСЂР°С†РёСЏ РјРѕР¶РµС‚ Р±С‹С‚СЊ Р±С‹СЃС‚СЂРѕ Р·Р°РІРµСЂС€РµРЅР°
                                                    try:
                                                        success = await op_service.mark_succeeded(
                                                            operation_id=operation_id,
                                                            result_summary=result_summary,
                                                            result_event_id=None,  # Can be populated if we create ticket_event
                                                            expected_statuses=["running", "accepted", "waiting_consent", "queued", "sent"]
                                                        )
                                                        
                                                        if success:
                                                            logger.info(
                                                                f"[command_result] Operation marked as succeeded: "
                                                                f"operation_id={operation_id}"
                                                            )
                                                            # Playbook Engine: РїСЂРѕРґРІРёР¶РµРЅРёРµ РїСЂРё СѓСЃРїРµС…Рµ РѕРїРµСЂР°С†РёРё (Р­С‚Р°Рї 4)
                                                            try:
                                                                from app.services.playbook_engine import advance_after_terminal
                                                                await advance_after_terminal(
                                                                    session, state, operation_id, "succeeded", payload
                                                                )
                                                            except Exception as pe:
                                                                logger.debug(
                                                                    f"[command_result] Playbook advance_after_terminal: {pe}"
                                                                )
                                                            # РљР РРўРР§РќРћ: РЎРѕР·РґР°С‘Рј ticket_event tool_call_result вЂ” С‡С‚РѕР±С‹ РЅР° СЃС‚СЂР°РЅРёС†Рµ С‚РёРєРµС‚Р° РѕС‚РѕР±СЂР°Р¶Р°Р»СЃСЏ РѕС‚РІРµС‚ (РїРѕ РѕРїРµСЂР°С†РёРё, РЅРµ С‚РѕР»СЊРєРѕ РїРѕ cmd_record)
                                                            is_tool_call = (current_op and current_op.ticket_id and (
                                                                current_op.kind == "tool_call" or
                                                                (cmd_record and cmd_record.command == "run_tool")
                                                            ))
                                                            if is_tool_call:
                                                                ticket_events_repo = TicketEventsRepo(session)
                                                                tool_name = (current_op.tool_name or
                                                                    (cmd_record.params if cmd_record else {}).get("tool") or "run_tool")
                                                                # Р­С‚Р°Рї 6: РІРєР»СЋС‡Р°РµРј artifacts РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ РІ Web UI С‚РёРєРµС‚Р° (СЃРєСЂРёРЅС€РѕС‚С‹, РІРёРґРµРѕ)
                                                                artifacts_list = data_payload.get("artifacts") if isinstance(data_payload.get("artifacts"), list) else []
                                                                result_payload = {
                                                                    "event": "tool_call_result",
                                                                    "call_id": command_id,
                                                                    "tool_name": tool_name,
                                                                    "status": "success",
                                                                    "summary": (result_summary[:500] if result_summary else "OK"),
                                                                    "result": observations if isinstance(observations, dict) else (data_payload if isinstance(data_payload, dict) else {}),
                                                                    "artifacts": artifacts_list,
                                                                    "ts": time.time()
                                                                }
                                                                te_result = await ticket_events_repo.add_event(
                                                                    ticket_id=current_op.ticket_id,
                                                                    device_id=agent_id,
                                                                    agent_seq=None,
                                                                    event_type="tool_call_result",
                                                                    payload=result_payload,
                                                                    trace_id=current_op.trace_id,
                                                                    event_id=None,
                                                                    operation_id=operation_id
                                                                )
                                                                if te_result:
                                                                    inserted_id, created_at = te_result
                                                                    if state.subscription_registry:
                                                                        from websocket.ui_handler import push_ticket_event_committed
                                                                        await push_ticket_event_committed(
                                                                            state,
                                                                            ticket_id=current_op.ticket_id,
                                                                            event_id=inserted_id,
                                                                            event_type="tool_call_result",
                                                                            operation_id=operation_id,
                                                                            agent_seq=None,
                                                                            created_at=created_at,
                                                                            payload=result_payload
                                                                        )
                                                        else:
                                                            # РљР РРўРР§РќРћ: РџСЂРѕРІРµСЂСЏРµРј, РїРѕС‡РµРјСѓ РЅРµ СѓРґР°Р»РѕСЃСЊ РѕР±РЅРѕРІРёС‚СЊ
                                                            if current_op:
                                                                logger.warning(
                                                                    f"[command_result] Failed to mark operation as succeeded: "
                                                                    f"operation_id={operation_id} current_status={current_op.status} "
                                                                    f"expected_statuses=['running', 'accepted', 'waiting_consent', 'queued', 'sent']"
                                                                )
                                                            else:
                                                                logger.error(
                                                                    f"[command_result] Failed to mark operation as succeeded: "
                                                                    f"operation_id={operation_id} (operation not found)"
                                                                )
                                                    except Exception as mark_error:
                                                        logger.error(
                                                            f"[command_result] CRITICAL: Exception in mark_succeeded: "
                                                            f"operation_id={operation_id} error={mark_error}",
                                                            exc_info=True
                                                        )
                                                        # РљР РРўРР§РќРћ: РќР• РґРµР»Р°РµРј rollback Р·РґРµСЃСЊ, С‡С‚РѕР±С‹ РЅРµ РїРѕС‚РµСЂСЏС‚СЊ РёР·РјРµРЅРµРЅРёСЏ РѕС‚ list_tools
                                                        # Rollback Р±СѓРґРµС‚ СЃРґРµР»Р°РЅ РІ РѕР±С‰РµРј Р±Р»РѕРєРµ РѕР±СЂР°Р±РѕС‚РєРё РѕС€РёР±РѕРє commit
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° list_tools СѓР¶Рµ РІС‹РїРѕР»РЅРµРЅР° РІС‹С€Рµ, РїСЂРѕРїСѓСЃРєР°РµРј РґСѓР±Р»РёСЂРѕРІР°РЅРёРµ
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° list_installed_modules Р”Рћ commit (РІ С‚РѕР№ Р¶Рµ С‚СЂР°РЅР·Р°РєС†РёРё)
                                                    if cmd_record and cmd_record.command == "list_installed_modules":
                                                        # РљР РРўРР§РќРћ: РїСѓС‚СЊ Рє РґР°РЅРЅС‹Рј - payload.data.observations.modules
                                                        observations = payload.get("data", {}).get("observations", {})
                                                        modules_list = observations.get("modules", [])
                                                        
                                                        if not isinstance(modules_list, list):
                                                            logger.warning(
                                                                f"[command_result] list_installed_modules has invalid modules payload type: "
                                                                f"{type(modules_list).__name__}"
                                                            )
                                                        else:
                                                            # Sync inventory через единый helper (включая пустой список).
                                                            from websocket.modules_sync import flatten_modules_list, sync_modules_inventory

                                                            flattened_inventory = flatten_modules_list(modules_list)
                                                            await sync_modules_inventory(
                                                                session=session,
                                                                device_id=agent_id,
                                                                inventory=flattened_inventory
                                                            )
                                                            logger.info(
                                                                f"[command_result] Synced {len(flattened_inventory)} module versions "
                                                                f"from list_installed_modules for device_id={agent_id} (before commit)"
                                                            )
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° install_module_package Р”Рћ commit (РІ С‚РѕР№ Р¶Рµ С‚СЂР°РЅР·Р°РєС†РёРё)
                                                    if cmd_record and cmd_record.command == "install_module_package":
                                                        # РРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚СЊ: РµСЃР»Рё СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅ (delivered), РїСЂРѕРїСѓСЃРєР°РµРј
                                                        # РќРµ РїСЂРѕРїСѓСЃРєР°С‚СЊ РїРѕ delivered: mark_as_delivered РІС‹Р·РІР°РЅ РІС‹С€Рµ, РѕР±РЅРѕРІР»СЏРµРј device_modules РїРѕ СѓСЃРїРµС‡РЅРѕРјСѓ СЂРµР·СѓР»СЊС‚Р°С‚Сѓ (idempotent)
                                                        params = cmd_record.params
                                                        module_name = params.get("module_name") or params.get("name")
                                                        version = params.get("module_version") or params.get("version")
                                                        
                                                        if module_name and version:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РЈСЃРїРµС€РЅР°СЏ СѓСЃС‚Р°РЅРѕРІРєР°
                                                                    # РљР РРўРР§РќРћ: install_module_package Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё Р°РєС‚РёРІРёСЂСѓРµС‚ РјРѕРґСѓР»СЊ РїРѕСЃР»Рµ СѓСЃС‚Р°РЅРѕРІРєРё
                                                                    await device_modules_repo.upsert_device_module(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        installed=True,
                                                                        active=True,  # install_module_package Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё Р°РєС‚РёРІРёСЂСѓРµС‚
                                                                        state="active",  # РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј state (СѓСЃС‚Р°РЅРѕРІРєР° + Р°РєС‚РёРІР°С†РёСЏ Р·Р°РІРµСЂС€РµРЅС‹)
                                                                        last_error_code=None,
                                                                        last_error_message=None,
                                                                        source="command_result",
                                                                        update_last_seen=True,
                                                                    )
                                                                    
                                                                    logger.info(
                                                                        f"[command_result] Processed install_module_package success (before commit): "
                                                                        f"device_id={agent_id} module_name={module_name} version={version}"
                                                                    )
                                                                    # РђРІС‚РѕСЃРёРЅС…СЂРѕРЅРёР·Р°С†РёСЏ: РѕР±РЅРѕРІРёС‚СЊ inventory Рё toolset Р±РµР· СЂСѓС‡РЅРѕРіРѕ sync
                                                                    try:
                                                                        from websocket.protocol import enqueue_command_async
                                                                        await enqueue_command_async(
                                                                            state=state,
                                                                            device_id=agent_id,
                                                                            command="list_installed_modules",
                                                                            params={},
                                                                            actor_role="admin",
                                                                        )
                                                                        await enqueue_command_async(
                                                                            state=state,
                                                                            device_id=agent_id,
                                                                            command="list_tools",
                                                                            params={},
                                                                            actor_role="admin",
                                                                        )
                                                                        logger.debug(
                                                                            f"[command_result] Enqueued auto-sync (list_installed_modules + list_tools) for device_id={agent_id}"
                                                                        )
                                                                    except Exception as sync_err:
                                                                        logger.warning(
                                                                            f"[command_result] Auto-sync after install failed: {sync_err}"
                                                                        )
                                                                elif status == "error":
                                                                    # РћС€РёР±РєР° СѓСЃС‚Р°РЅРѕРІРєРё: Р·Р°РїРёСЃСЊ РІ device_modules СЃ state=failed (СЃРѕР·РґР°С‘Рј/РѕР±РЅРѕРІР»СЏРµРј)
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    await device_modules_repo.upsert_device_module(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        installed=False,
                                                                        active=False,
                                                                        state="failed",
                                                                        last_error_code=error_code,
                                                                        last_error_message=error_message,
                                                                    )
                                                                    
                                                                    logger.warning(
                                                                        f"[command_result] Processed install_module_package error (before commit): "
                                                                        f"device_id={agent_id} module_name={module_name} version={version} "
                                                                        f"error_code={error_code}"
                                                                    )
                                                        else:
                                                            logger.warning(
                                                                f"[command_result] install_module_package missing module_name or version: "
                                                                f"command_id={command_id} params={params}"
                                                            )
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° activate_module Р”Рћ commit (РІ С‚РѕР№ Р¶Рµ С‚СЂР°РЅР·Р°РєС†РёРё)
                                                    if cmd_record and cmd_record.command == "activate_module":
                                                        # РРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚СЊ: РµСЃР»Рё СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅ (delivered), РїСЂРѕРїСѓСЃРєР°РµРј
                                                        if cmd_record.status == "delivered":
                                                            logger.debug(
                                                                f"[command_result] activate_module already processed: "
                                                                f"command_id={command_id}"
                                                            )
                                                        else:
                                                            params = cmd_record.params
                                                            module_name = params.get("name")
                                                            version = params.get("version")
                                                            
                                                            if module_name and version:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РћР±РЅРѕРІР»СЏРµРј active Рё state
                                                                    await device_modules_repo.upsert_device_module(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        installed=True,
                                                                        active=True,
                                                                        state="active"
                                                                    )
                                                                    
                                                                    logger.info(
                                                                        f"[command_result] Processed activate_module success (before commit): "
                                                                        f"device_id={agent_id} module_name={module_name} version={version}"
                                                                    )
                                                                elif status == "error":
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    await device_modules_repo.mark_error(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        error_code=error_code,
                                                                        error_message=error_message
                                                                    )
                                                    
                                                    # РљР РРўРР§РќРћ: РћР±СЂР°Р±РѕС‚РєР° deactivate_module Р”Рћ commit (РІ С‚РѕР№ Р¶Рµ С‚СЂР°РЅР·Р°РєС†РёРё)
                                                    if cmd_record and cmd_record.command == "deactivate_module":
                                                        # РРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚СЊ: РµСЃР»Рё СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅ (delivered), РїСЂРѕРїСѓСЃРєР°РµРј
                                                        if cmd_record.status == "delivered":
                                                            logger.debug(
                                                                f"[command_result] deactivate_module already processed: "
                                                                f"command_id={command_id}"
                                                            )
                                                        else:
                                                            params = cmd_record.params
                                                            module_name = params.get("name")
                                                            
                                                            if module_name:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РјРѕРґСѓР»СЏ Рё РґРµР°РєС‚РёРІРёСЂСѓРµРј РµС‘
                                                                    # РљР РРўРР§РќРћ: deactivate_module РЅРµ С‚СЂРµР±СѓРµС‚ version, РґРµР°РєС‚РёРІРёСЂСѓРµС‚ С‚РµРєСѓС‰СѓСЋ Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    
                                                                    # РќР°С…РѕРґРёРј РјРѕРґСѓР»СЊ СЃ РЅСѓР¶РЅС‹Рј РёРјРµРЅРµРј
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        # Р”РµР°РєС‚РёРІРёСЂСѓРµРј РЅР°Р№РґРµРЅРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                        await device_modules_repo.upsert_device_module(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            installed=True,
                                                                            active=False,
                                                                            state="installed"  # Р”РµР°РєС‚РёРІРёСЂРѕРІР°РЅ, РЅРѕ СѓСЃС‚Р°РЅРѕРІР»РµРЅ
                                                                        )
                                                                        
                                                                        logger.info(
                                                                            f"[command_result] Processed deactivate_module success (before commit): "
                                                                            f"device_id={agent_id} module_name={module_name} version={target_module.version}"
                                                                        )
                                                                    else:
                                                                        logger.warning(
                                                                            f"[command_result] deactivate_module: no active version found for {module_name}"
                                                                        )
                                                                elif status == "error":
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РґР»СЏ Р·Р°РїРёСЃРё РѕС€РёР±РєРё
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        await device_modules_repo.mark_error(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            error_code=error_code,
                                                                            error_message=error_message
                                                                        )
                                                
                                                elif status == "error":
                                                    logger.debug(
                                                        f"[command_result] Processing error status: "
                                                        f"operation_id={operation_id} payload={payload}"
                                                    )
                                                    # PR2: РРЎРџР РђР’Р›Р•РќРР• - Mark outbox as delivered (РЅРµ failed)
                                                    # Execution error в‰  delivery error
                                                    # Error result РѕР·РЅР°С‡Р°РµС‚, С‡С‚Рѕ РєРѕРјР°РЅРґР° РґРѕСЃС‚Р°РІР»РµРЅР° Рё РѕР±СЂР°Р±РѕС‚Р°РЅР° Р°РіРµРЅС‚РѕРј,
                                                    # РЅРѕ Р·Р°РІРµСЂС€РёР»Р°СЃСЊ СЃ РѕС€РёР±РєРѕР№. Р­С‚Рѕ РќР• РѕС€РёР±РєР° РґРѕСЃС‚Р°РІРєРё.
                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                    error_message = error_info.get("message", "Unknown error")
                                                    
                                                    logger.debug(
                                                        f"[command_result] Extracted error info: "
                                                        f"error_code={error_code} error_message={error_message}"
                                                    )
                                                    
                                                    # PR2: Outbox в†’ delivered (РєРѕРјР°РЅРґР° РґРѕСЃС‚Р°РІР»РµРЅР° Рё РѕР±СЂР°Р±РѕС‚Р°РЅР°)
                                                    await repo.mark_as_delivered(command_id)
                                                    logger.info(
                                                        f"[command_result] Outbox marked as delivered (error result): "
                                                        f"command_id={command_id} error_code={error_code}"
                                                    )
                                                    
                                                    # РљР РРўРР§РќРћ: Р“Р°СЂР°РЅС‚РёСЂСѓРµРј, С‡С‚Рѕ РѕРїРµСЂР°С†РёСЏ РґРѕСЃС‚РёРіР°РµС‚ terminal СЃРѕСЃС‚РѕСЏРЅРёСЏ
                                                    # РџСЂРёРЅС†РёРї: error status = РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ terminal path
                                                    from app.repos import OperationsRepo
                                                    ops_repo = OperationsRepo(session)
                                                    
                                                    # РЎРЅР°С‡Р°Р»Р° РїСЂРѕР±СѓРµРј С‡РµСЂРµР· OperationService СЃ optimistic locking
                                                    success = await op_service.mark_failed(
                                                        operation_id=operation_id,
                                                        error_code=error_code,
                                                        error_message=error_message,
                                                        result_event_id=None,
                                                        expected_statuses=["running", "accepted", "waiting_consent", "sent", "queued"]
                                                    )
                                                    
                                                    if success:
                                                        logger.warning(
                                                            f"[command_result] Operation marked as failed: "
                                                            f"operation_id={operation_id} error_code={error_code}"
                                                        )
                                                        # Playbook Engine: РїСЂРѕРґРІРёР¶РµРЅРёРµ РїСЂРё РѕС€РёР±РєРµ РѕРїРµСЂР°С†РёРё (Р­С‚Р°Рї 4)
                                                        try:
                                                            from app.services.playbook_engine import advance_after_terminal
                                                            await advance_after_terminal(
                                                                session, state, operation_id, "failed", payload
                                                            )
                                                        except Exception as pe:
                                                            logger.debug(
                                                                f"[command_result] Playbook advance_after_terminal: {pe}"
                                                            )
                                                        # РљР РРўРР§РќРћ: РЎРѕР·РґР°С‘Рј ticket_event tool_call_result (РѕС€РёР±РєР°) вЂ” С‡С‚РѕР±С‹ РЅР° СЃС‚СЂР°РЅРёС†Рµ С‚РёРєРµС‚Р° РѕС‚РѕР±СЂР°Р¶Р°Р»СЃСЏ РѕС‚РІРµС‚
                                                        current_op_err = await ops_repo.get_by_operation_id(operation_id)
                                                        cmd_record_err = await repo.get_command_by_id(command_id)
                                                        is_tool_call_err = (current_op_err and current_op_err.ticket_id and (
                                                            current_op_err.kind == "tool_call" or
                                                            (cmd_record_err and cmd_record_err.command == "run_tool")
                                                        ))
                                                        if is_tool_call_err:
                                                            ticket_events_repo_err = TicketEventsRepo(session)
                                                            tool_name_err = (current_op_err.tool_name or
                                                                (cmd_record_err.params if cmd_record_err else {}).get("tool") or "run_tool")
                                                            result_payload_err = {
                                                                "event": "tool_call_result",
                                                                "call_id": command_id,
                                                                "tool_name": tool_name_err,
                                                                "status": "error",
                                                                "summary": (error_message[:500] if error_message else str(error_code)),
                                                                "error": error_message,
                                                                "result": {},
                                                                "ts": time.time()
                                                            }
                                                            te_result_err = await ticket_events_repo_err.add_event(
                                                                ticket_id=current_op_err.ticket_id,
                                                                device_id=agent_id,
                                                                agent_seq=None,
                                                                event_type="tool_call_result",
                                                                payload=result_payload_err,
                                                                trace_id=current_op_err.trace_id,
                                                                event_id=None,
                                                                operation_id=operation_id
                                                            )
                                                            if te_result_err:
                                                                inserted_id_err, created_at_err = te_result_err
                                                                if state.subscription_registry:
                                                                    from websocket.ui_handler import push_ticket_event_committed
                                                                    await push_ticket_event_committed(
                                                                        state,
                                                                        ticket_id=current_op_err.ticket_id,
                                                                        event_id=inserted_id_err,
                                                                        event_type="tool_call_result",
                                                                        operation_id=operation_id,
                                                                        agent_seq=None,
                                                                        created_at=created_at_err,
                                                                        payload=result_payload_err
                                                                    )
                                                    else:
                                                        # Fallback: РїСЂРѕРІРµСЂСЏРµРј С‚РµРєСѓС‰РёР№ СЃС‚Р°С‚СѓСЃ РѕРїРµСЂР°С†РёРё
                                                        # Р•СЃР»Рё СѓР¶Рµ terminal - OK, РёРЅР°С‡Рµ РїСЂРѕРІРµСЂСЏРµРј, РјРѕР¶РЅРѕ Р»Рё РґРµР»Р°С‚СЊ forced update
                                                        current_op = await ops_repo.get_by_operation_id(operation_id)
                                                        
                                                        if current_op:
                                                            terminal_statuses = ["succeeded", "failed", "timed_out", "canceled"]
                                                            if current_op.status in terminal_statuses:
                                                                logger.info(
                                                                    f"[command_result] Operation already in terminal state: "
                                                                    f"operation_id={operation_id} status={current_op.status}"
                                                                )
                                                            else:
                                                                # РљР РРўРР§РќРћ: Forced update СЂР°Р·СЂРµС€РµРЅ С‚РѕР»СЊРєРѕ РґР»СЏ РѕРїСЂРµРґРµР»РµРЅРЅС‹С… РєР»Р°СЃСЃРѕРІ РѕС€РёР±РѕРє
                                                                # РёР»Рё РєРѕРіРґР° payload СЂРµР°Р»СЊРЅРѕ Р±РёС‚С‹Р№ (None/РЅРµ dict)
                                                                # Р­С‚Рѕ Р·Р°С‰РёС‚Р° РѕС‚ РЅР°СЂСѓС€РµРЅРёСЏ РјР°С€РёРЅС‹ СЃРѕСЃС‚РѕСЏРЅРёР№ РїСЂРё РЅРѕСЂРјР°Р»СЊРЅС‹С… РѕС€РёР±РєР°С…
                                                                allowed_forced_error_codes = {
                                                                    "SERVER_PROCESSING_ERROR",
                                                                    "MALFORMED_RESULT",
                                                                    "EXCEPTION_RECOVERY"
                                                                }
                                                                # payload_is_broken СѓР¶Рµ РѕРїСЂРµРґРµР»РµРЅ РІС‹С€Рµ РїСЂРё РёР·РІР»РµС‡РµРЅРёРё payload
                                                                error_code_allows_force = error_code in allowed_forced_error_codes
                                                                
                                                                if payload_is_broken or error_code_allows_force:
                                                                    # РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ Р±РµР· expected_statuses (edge case recovery)
                                                                    reason = "broken_payload" if payload_is_broken else f"error_code_{error_code}"
                                                                    logger.warning(
                                                                        f"[command_result] FORCED_TRANSITION: "
                                                                        f"operation_id={operation_id} "
                                                                        f"request_id={command_id} "
                                                                        f"current_status={current_op.status} "
                                                                        f"incoming_status=failed "
                                                                        f"reason={reason} "
                                                                        f"error_code={error_code}"
                                                                    )
                                                                    force_success = await ops_repo.update_status(
                                                                        operation_id=operation_id,
                                                                        new_status="failed",
                                                                        expected_statuses=None,  # Force update
                                                                        timestamp_field="finished_at",
                                                                        error_code=error_code,
                                                                        error_message=error_message,
                                                                        deadline_at=None
                                                                    )
                                                                    if not force_success:
                                                                        logger.error(
                                                                            f"[command_result] CRITICAL: Failed to force-update operation to failed: "
                                                                            f"operation_id={operation_id}"
                                                                        )
                                                                else:
                                                                    # РќРѕСЂРјР°Р»СЊРЅР°СЏ РѕС€РёР±РєР°, РЅРѕ СЃС‚Р°С‚СѓСЃ РЅРµ СЃРѕРІРїР°РґР°РµС‚ - СЌС‚Рѕ РїСЂРѕР±Р»РµРјР° РјР°С€РёРЅС‹ СЃРѕСЃС‚РѕСЏРЅРёР№
                                                                    logger.error(
                                                                        f"[command_result] State machine violation: "
                                                                        f"operation_id={operation_id} "
                                                                        f"current_status={current_op.status} "
                                                                        f"error_code={error_code} "
                                                                        f"mark_failed failed (expected_statuses mismatch). "
                                                                        f"Forced update NOT allowed for this error code."
                                                                    )
                                                        else:
                                                                logger.error(
                                                                    f"[command_result] CRITICAL: Operation not found: "
                                                                    f"operation_id={operation_id}"
                                                                )
                                                
                                                elif status == "consent_required":
                                                    # PR5: РћР±СЂР°Р±РѕС‚РєР° consent_required РєР°Рє РѕС‚РґРµР»СЊРЅРѕРіРѕ СЃС‚Р°С‚СѓСЃР°
                                                    logger.debug(
                                                        f"[command_result] Processing consent_required status: "
                                                        f"operation_id={operation_id}"
                                                    )
                                                    
                                                    # Mark outbox as delivered (РєРѕРјР°РЅРґР° РґРѕСЃС‚Р°РІР»РµРЅР°)
                                                    await repo.mark_as_delivered(command_id)
                                                    logger.info(
                                                        f"[command_result] Outbox marked as delivered (consent_required result): "
                                                        f"command_id={command_id}"
                                                    )
                                                    
                                                    # Mark operation as waiting_consent
                                                    success = await op_service.mark_waiting_consent(
                                                        operation_id=operation_id,
                                                        expected_statuses=["running", "accepted", "sent", "queued"]
                                                    )
                                                    
                                                    if success:
                                                        logger.info(
                                                            f"[command_result] Operation marked as waiting_consent: "
                                                            f"operation_id={operation_id}"
                                                        )
                                                    else:
                                                        logger.warning(
                                                            f"[command_result] Failed to mark operation as waiting_consent: "
                                                            f"operation_id={operation_id} (status mismatch or not found)"
                                                        )
                                                
                                                # РљР РРўРР§РќРћ: Commit С‚СЂР°РЅР·Р°РєС†РёРё РїРѕСЃР»Рµ РІСЃРµС… РѕР±РЅРѕРІР»РµРЅРёР№
                                                # Р­С‚Рѕ РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РІСЃРµ РёР·РјРµРЅРµРЅРёСЏ (outbox + operations) СЃРѕС…СЂР°РЅСЏСЋС‚СЃСЏ
                                                # Обновлять PostgreSQL (device_modules) только при успехе remove_*:
                                                # success = агент реально удалил файлы (shutil.rmtree). REMOVE_FAILED не считаем подтверждением.
                                                cmd_record = await repo.get_command_by_id(command_id)
                                                _remove_ok = (
                                                    cmd_record
                                                    and cmd_record.command in ["remove_module_version", "remove_module"]
                                                    and status == "success"
                                                )
                                                if _remove_ok:
                                                    params = cmd_record.params or {}
                                                    _mod_name = params.get("name") or params.get("module_name")
                                                    _mod_ver = params.get("version")
                                                    if _mod_name:
                                                        from app.repos import DeviceModulesRepo
                                                        _dm_repo = DeviceModulesRepo(session)
                                                        if _mod_ver:
                                                            await _dm_repo.mark_removed(
                                                                device_id=agent_id,
                                                                module_name=_mod_name,
                                                                version=_mod_ver
                                                            )
                                                        else:
                                                            await _dm_repo.mark_module_removed(
                                                                device_id=agent_id,
                                                                module_name=_mod_name
                                                            )
                                                        logger.info(
                                                            f"[command_result] device_modules updated for {cmd_record.command} (confirmed removal): "
                                                            f"device_id={agent_id} module_name={_mod_name} version={_mod_ver or 'all'}"
                                                        )
                                                        # Обновить снимок toolset в PostgreSQL: запросить list_tools и list_installed_modules
                                                        try:
                                                            from websocket.protocol import enqueue_command_async
                                                            await enqueue_command_async(
                                                                state=state,
                                                                device_id=agent_id,
                                                                command="list_installed_modules",
                                                                params={},
                                                                actor_role="admin",
                                                            )
                                                            await enqueue_command_async(
                                                                state=state,
                                                                device_id=agent_id,
                                                                command="list_tools",
                                                                params={},
                                                                actor_role="admin",
                                                            )
                                                            logger.debug(
                                                                f"[command_result] Enqueued list_installed_modules + list_tools after remove: device_id={agent_id}"
                                                            )
                                                        except Exception as sync_err:
                                                            logger.warning(
                                                                f"[command_result] Enqueue list_tools after remove failed: {sync_err}"
                                                            )
                                                try:
                                                    await session.commit()
                                                    logger.info(
                                                        f"[command_result] Transaction committed: "
                                                        f"command_id={command_id} status={status}"
                                                    )
                                                except Exception as commit_error:
                                                    logger.error(
                                                        f"[command_result] CRITICAL: Failed to commit transaction: "
                                                        f"command_id={command_id} error={commit_error}",
                                                        exc_info=True
                                                    )
                                                    await session.rollback()
                                                    # Fallback: после rollback обновить device_modules для remove_*
                                                    if _remove_ok:
                                                        _params = cmd_record.params or {}
                                                        _mod_name = _params.get("name") or _params.get("module_name")
                                                        _mod_ver = _params.get("version")
                                                        if _mod_name:
                                                            from app.repos import DeviceModulesRepo
                                                            _dm_repo = DeviceModulesRepo(session)
                                                            if _mod_ver:
                                                                await _dm_repo.mark_removed(
                                                                    device_id=agent_id,
                                                                    module_name=_mod_name,
                                                                    version=_mod_ver
                                                                )
                                                            else:
                                                                await _dm_repo.mark_module_removed(
                                                                    device_id=agent_id,
                                                                    module_name=_mod_name
                                                                )
                                                            await session.commit()
                                                            logger.info(
                                                                f"[command_result] Processed {cmd_record.command} success (after rollback): "
                                                                f"device_id={agent_id} module_name={_mod_name}"
                                                            )
                                                    
                                                    # РћР±СЂР°Р±РѕС‚РєР° activate_module
                                                    if cmd_record and cmd_record.command == "activate_module":
                                                        if cmd_record.status == "delivered":
                                                            logger.debug(
                                                                f"[command_result] activate_module already processed: "
                                                                f"command_id={command_id}"
                                                            )
                                                        else:
                                                            params = cmd_record.params
                                                            module_name = params.get("name")
                                                            version = params.get("version")
                                                            
                                                            if module_name and version:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РћР±РЅРѕРІР»СЏРµРј active Рё state
                                                                    await device_modules_repo.upsert_device_module(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        installed=True,
                                                                        active=True,
                                                                        state="active"
                                                                    )
                                                                    await session.commit()
                                                                    
                                                                    logger.info(
                                                                        f"[command_result] Processed activate_module success: "
                                                                        f"device_id={agent_id} module_name={module_name} version={version}"
                                                                    )
                                                                elif status == "error":
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    await device_modules_repo.mark_error(
                                                                        device_id=agent_id,
                                                                        module_name=module_name,
                                                                        version=version,
                                                                        error_code=error_code,
                                                                        error_message=error_message
                                                                    )
                                                                    await session.commit()
                                                    
                                                    # РћР±СЂР°Р±РѕС‚РєР° deactivate_module
                                                    if cmd_record and cmd_record.command == "deactivate_module":
                                                        if cmd_record.status == "delivered":
                                                            logger.debug(
                                                                f"[command_result] deactivate_module already processed: "
                                                                f"command_id={command_id}"
                                                            )
                                                        else:
                                                            params = cmd_record.params
                                                            module_name = params.get("name")
                                                            
                                                            if module_name:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РјРѕРґСѓР»СЏ Рё РґРµР°РєС‚РёРІРёСЂСѓРµРј РµС‘
                                                                    # РљР РРўРР§РќРћ: deactivate_module РЅРµ С‚СЂРµР±СѓРµС‚ version, РґРµР°РєС‚РёРІРёСЂСѓРµС‚ С‚РµРєСѓС‰СѓСЋ Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                    # РќСѓР¶РЅРѕ РЅР°Р№С‚Рё Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ С‡РµСЂРµР· get_device_modules
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    
                                                                    # РќР°С…РѕРґРёРј РјРѕРґСѓР»СЊ СЃ РЅСѓР¶РЅС‹Рј РёРјРµРЅРµРј
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        # Р”РµР°РєС‚РёРІРёСЂСѓРµРј РЅР°Р№РґРµРЅРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                        await device_modules_repo.upsert_device_module(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            installed=True,
                                                                            active=False,
                                                                            state="installed"  # Р”РµР°РєС‚РёРІРёСЂРѕРІР°РЅ, РЅРѕ СѓСЃС‚Р°РЅРѕРІР»РµРЅ
                                                                        )
                                                                        await session.commit()
                                                                        
                                                                        logger.info(
                                                                            f"[command_result] Processed deactivate_module success: "
                                                                            f"device_id={agent_id} module_name={module_name} version={target_module.version}"
                                                                        )
                                                                    else:
                                                                        logger.warning(
                                                                            f"[command_result] deactivate_module: no active version found for {module_name}"
                                                                        )
                                                                elif status == "error":
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РґР»СЏ Р·Р°РїРёСЃРё РѕС€РёР±РєРё
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        await device_modules_repo.mark_error(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            error_code=error_code,
                                                                            error_message=error_message
                                                                        )
                                                                        await session.commit()
                                                    
                                                    # РћР±СЂР°Р±РѕС‚РєР° deactivate_module
                                                    if cmd_record and cmd_record.command == "deactivate_module":
                                                        if cmd_record.status == "delivered":
                                                            logger.debug(
                                                                f"[command_result] deactivate_module already processed: "
                                                                f"command_id={command_id}"
                                                            )
                                                        else:
                                                            params = cmd_record.params
                                                            module_name = params.get("name")
                                                            
                                                            if module_name:
                                                                from app.repos import DeviceModulesRepo
                                                                
                                                                device_modules_repo = DeviceModulesRepo(session)
                                                                
                                                                if status == "success":
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РјРѕРґСѓР»СЏ Рё РґРµР°РєС‚РёРІРёСЂСѓРµРј РµС‘
                                                                    # РљР РРўРР§РќРћ: deactivate_module РЅРµ С‚СЂРµР±СѓРµС‚ version, РґРµР°РєС‚РёРІРёСЂСѓРµС‚ С‚РµРєСѓС‰СѓСЋ Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    
                                                                    # РќР°С…РѕРґРёРј РјРѕРґСѓР»СЊ СЃ РЅСѓР¶РЅС‹Рј РёРјРµРЅРµРј
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        # Р”РµР°РєС‚РёРІРёСЂСѓРµРј РЅР°Р№РґРµРЅРЅСѓСЋ РІРµСЂСЃРёСЋ
                                                                        await device_modules_repo.upsert_device_module(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            installed=True,
                                                                            active=False,
                                                                            state="installed"  # Р”РµР°РєС‚РёРІРёСЂРѕРІР°РЅ, РЅРѕ СѓСЃС‚Р°РЅРѕРІР»РµРЅ
                                                                        )
                                                                        await session.commit()
                                                                        
                                                                        logger.info(
                                                                            f"[command_result] Processed deactivate_module success: "
                                                                            f"device_id={agent_id} module_name={module_name} version={target_module.version}"
                                                                        )
                                                                    else:
                                                                        logger.warning(
                                                                            f"[command_result] deactivate_module: no active version found for {module_name}"
                                                                        )
                                                                elif status == "error":
                                                                    error_code = error_info.get("code", "UNKNOWN_ERROR")
                                                                    error_message = error_info.get("message", "Unknown error")
                                                                    
                                                                    # РќР°С…РѕРґРёРј Р°РєС‚РёРІРЅСѓСЋ РІРµСЂСЃРёСЋ РґР»СЏ Р·Р°РїРёСЃРё РѕС€РёР±РєРё
                                                                    device_modules = await device_modules_repo.get_device_modules(
                                                                        device_id=agent_id,
                                                                        active_only=True
                                                                    )
                                                                    target_module = None
                                                                    for dm in device_modules:
                                                                        if dm.module_name == module_name and dm.active:
                                                                            target_module = dm
                                                                            break
                                                                    
                                                                    if target_module:
                                                                        await device_modules_repo.mark_error(
                                                                            device_id=agent_id,
                                                                            module_name=module_name,
                                                                            version=target_module.version,
                                                                            error_code=error_code,
                                                                            error_message=error_message
                                                                        )
                                                                        await session.commit()
                                                    
                                                    # Р‘РµР·РѕРїР°СЃРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ device_outbox (no-op РµСЃР»Рё СѓР¶Рµ delivered)
                                                    if cmd_record and cmd_record.status == "sent":
                                                        await repo.mark_as_delivered(command_id)
                                                        
                                        except Exception as e:
                                            logger.error(
                                                f"[command_result] Failed to update outbox: {e}",
                                                exc_info=True
                                            )
                                            
                                            # РљР РРўРР§РќРћ: РџСЂРё exception РІСЃРµ СЂР°РІРЅРѕ РїС‹С‚Р°РµРјСЃСЏ РіР°СЂР°РЅС‚РёСЂРѕРІР°С‚СЊ terminal СЃРѕСЃС‚РѕСЏРЅРёРµ
                                            # Р­С‚Рѕ РєСЂРёС‚РёС‡РЅРѕ РґР»СЏ error-path, С‡С‚РѕР±С‹ РѕРїРµСЂР°С†РёСЏ РЅРµ "Р·Р°РІРёСЃР»Р°"
                                            # Exception recovery РІСЃРµРіРґР° СЂР°Р·СЂРµС€РµРЅ РґР»СЏ forced update (СЌС‚Рѕ EXCEPTION_RECOVERY)
                                            if status == "error" and command_id:
                                                try:
                                                    # Р‘РµР·РѕРїР°СЃРЅРѕРµ РёР·РІР»РµС‡РµРЅРёРµ payload РґР»СЏ exception recovery
                                                    # payload РјРѕР¶РµС‚ Р±С‹С‚СЊ None РµСЃР»Рё exception РїСЂРѕРёР·РѕС€РµР» РґРѕ РµРіРѕ РѕР±СЂР°Р±РѕС‚РєРё
                                                    safe_payload = payload if isinstance(payload, dict) else {}
                                                    
                                                    async with get_session() as session:
                                                        from app.repos import OperationsRepo
                                                        ops_repo = OperationsRepo(session)
                                                        current_op = await ops_repo.get_by_operation_id(operation_id)
                                                        
                                                        if current_op:
                                                            terminal_statuses = ["succeeded", "failed", "timed_out", "canceled"]
                                                            if current_op.status not in terminal_statuses:
                                                                # РџСЂРёРЅСѓРґРёС‚РµР»СЊРЅРѕРµ РѕР±РЅРѕРІР»РµРЅРёРµ РїСЂРё exception (EXCEPTION_RECOVERY)
                                                                error_info = safe_payload.get("error", {}) if isinstance(safe_payload, dict) else {}
                                                                error_code = error_info.get("code", "EXCEPTION_RECOVERY") if isinstance(error_info, dict) else "EXCEPTION_RECOVERY"
                                                                error_message = error_info.get("message", "Exception during command_result processing") if isinstance(error_info, dict) else "Exception during command_result processing"
                                                                
                                                                await ops_repo.update_status(
                                                                    operation_id=operation_id,
                                                                    new_status="failed",
                                                                    expected_statuses=None,
                                                                    timestamp_field="finished_at",
                                                                    error_code=error_code,
                                                                    error_message=error_message,
                                                                    deadline_at=None
                                                                )
                                                                await session.commit()
                                                                logger.warning(
                                                                    f"[command_result] FORCED_TRANSITION: "
                                                                    f"operation_id={operation_id} "
                                                                    f"request_id={command_id} "
                                                                    f"current_status={current_op.status} "
                                                                    f"incoming_status=failed "
                                                                    f"reason=exception_recovery "
                                                                    f"error_code={error_code} "
                                                                    f"original_exception={str(e)[:100]}"
                                                                )
                                                except Exception as recovery_error:
                                                    logger.error(
                                                        f"[command_result] CRITICAL: Failed exception recovery: {recovery_error}",
                                                        exc_info=True
                                                    )
                                    
                                    # РљР РРўРР§РќРћ: Р Р°Р·СЂРµС€Р°РµРј future РїРѕСЃР»Рµ РѕР±СЂР°Р±РѕС‚РєРё command_result
                                    # РџСЂРёРјРµС‡Р°РЅРёРµ: РґР»СЏ error status РѕРїРµСЂР°С†РёСЏ РґРѕР»Р¶РЅР° Р±С‹С‚СЊ СѓР¶Рµ РїРµСЂРµРІРµРґРµРЅР° РІ terminal
                                    # С‡РµСЂРµР· mark_failed РІС‹С€Рµ. Р•СЃР»Рё СЌС‚РѕРіРѕ РЅРµ РїСЂРѕРёР·РѕС€Р»Рѕ - СЌС‚Рѕ СѓР¶Рµ Р·Р°Р»РѕРіРёСЂРѕРІР°РЅРѕ.
                                    pending_futures = agent_info["metadata"].get("pending_command_futures", {})
                                    future = pending_futures.get(command_id)
                                    
                                    if future and not future.done():
                                        future.set_result(data)
                                        del pending_futures[command_id]
                                        
                                        logger.info(
                                            f"[command_result] Future resolved: "
                                            f"command_id={command_id} status={status}"
                                        )
                                    else:
                                        logger.debug(
                                            f"[command_result] No pending future for "
                                            f"command_id={command_id} (likely timeout or async)"
                                        )
                                else:
                                    logger.warning(
                                        f"[command_result] Missing command_id from agent {agent_id}"
                                    )
                    
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # d) type == "command" - РєРѕРјР°РЅРґС‹ РѕС‚ Р°РіРµРЅС‚Р° Рє СЃРµСЂРІРµСЂСѓ
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    elif msg_type == "command":
                        # Р­С‚Рѕ РєРѕРјР°РЅРґР° РѕС‚ Р°РіРµРЅС‚Р° Рє СЃРµСЂРІРµСЂСѓ
                        if agent_id:
                            agent_info = state.get_agent(agent_id)
                            if agent_info:
                                agent_info["metadata"]["last_seen"] = time.time()
                                
                                req_id = data.get("request_id")
                                payload = data.get("payload", {})
                                command = payload.get("command")
                                params = payload.get("params", {})
                                
                                logger.info(f"[SERVER] RX command from agent {agent_id}: command={command} request_id={req_id}")
                                
                                # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                # РћР±СЂР°Р±РѕС‚РєР° РєРѕРјР°РЅРґС‹ chat_raise РѕС‚ Р°РіРµРЅС‚Р°
                                # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                if command == "chat_raise":
                                    title = params.get("title", "Agent Support Request")
                                    reason = params.get("reason", "agent_initiated")
                                    severity = params.get("severity", "warning")
                                    context = params.get("context", {})
                                    
                                    # Р“РµРЅРµСЂРёСЂСѓРµРј IDs
                                    chat_job_id = str(uuid.uuid4())
                                    ticket_id = str(uuid.uuid4())  # Phase V3: create ticket_id
                                    
                                    # РЎРѕР·РґР°РµРј ChatSession
                                    session_data = {
                                        "chat_job_id": chat_job_id,
                                        "ticket_id": ticket_id,  # Phase V3: link ticket
                                        "device_id": agent_id,  # Р°РіРµРЅС‚, РєРѕС‚РѕСЂС‹Р№ РёРЅРёС†РёРёСЂРѕРІР°Р»
                                        "owner_uuid": agent_info["metadata"].get("user", "unknown"),
                                        "created_by": "agent",
                                        "status": "active",
                                        "created_at": time.time(),
                                        "subscribers": set(),
                                        "events": []
                                    }
                                    state.create_chat_session(chat_job_id, session_data)
                                    
                                    # Phase V3: Persist ticket to Postgres for validation
                                    if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                        try:
                                            async with get_session() as db_session:
                                                # РљР РРўРР§РќРћ: РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ TicketEventsRepo РґРѕСЃС‚СѓРїРµРЅ
                                                if not DB_AVAILABLE:
                                                    logger.warning(
                                                        f"[chat_raise] DB not available, skipping ticket creation"
                                                    )
                                                else:
                                                    ticket_repo = TicketEventsRepo(db_session)
                                                    created = await ticket_repo.create_ticket(
                                                        ticket_id=ticket_id,
                                                        device_id=agent_id,
                                                        title=title,
                                                        description=f"Agent-initiated: {reason} (severity: {severity})",
                                                        status="new",
                                                        requester_id=agent_id,
                                                    )
                                                    # РРјСЏ Р·Р°СЏРІРєРё: РЅРѕРјРµСЂ (T-000002) + С‚РµРєСЃС‚ РёР· Р·Р°СЏРІРєРё
                                                    code = getattr(created, "ticket_code", None) or ""
                                                    if code:
                                                        snippet = (title or getattr(created, "description", "") or "")[:80].strip()
                                                        new_title = f"{code} {snippet}".strip() if snippet else code
                                                        if new_title:
                                                            await ticket_repo.update_ticket(ticket_id, title=new_title)
                                                    await db_session.commit()
                                                    logger.info(f"вњ… [V3] Ticket created for chat_raise: ticket_id={ticket_id}")
                                        except Exception as e:
                                            logger.opt(exception=True).error(
                                                "вќЊ [V3] Failed to create ticket for chat_raise: {}",
                                                e,
                                            )
                                    
                                    # Р’РђР–РќРћ: РќРµРјРµРґР»РµРЅРЅРѕ РѕС‚РїСЂР°РІР»СЏРµРј РѕС‚РІРµС‚ Р°РіРµРЅС‚Сѓ РџР•Р Р•Р” Р·Р°РїСѓСЃРєРѕРј РґР»РёС‚РµР»СЊРЅС‹С… РѕРїРµСЂР°С†РёР№
                                    # Р­С‚Рѕ РїСЂРµРґРѕС‚РІСЂР°С‰Р°РµС‚ С‚Р°Р№РјР°СѓС‚ РЅР° СЃС‚РѕСЂРѕРЅРµ Р°РіРµРЅС‚Р°
                                    response_envelope = {
                                        "type": "command_result",
                                        "request_id": req_id,
                                        "device_id": agent_id,
                                        "payload": {
                                            "status": "success",
                                            "data": {
                                                "observations": {
                                                    "job_id": chat_job_id,
                                                    "ticket_id": ticket_id,  # Phase V3: return ticket_id
                                                    "message": "Chat session created"
                                                }
                                            }
                                        }
                                    }
                                    
                                    await ws.send_json(response_envelope)
                                    logger.success(f"[chat_raise] agent_id={agent_id} job_id={chat_job_id} в†’ success response sent IMMEDIATELY")
                                    
                                    # PUSH invite РІ РІРµР±-UI (РїРѕРґРґРµСЂР¶РєР°) - РќР• Р±Р»РѕРєРёСЂСѓРµС‚
                                    invite_event = {
                                        "event": "chat_invite",
                                        "job_id": chat_job_id,
                                        "ticket_id": ticket_id,  # Phase V3: include ticket_id
                                        "device_id": agent_id,
                                        "from": "agent",
                                        "title": title,
                                        "reason": reason,
                                        "severity": severity,
                                        "context": context,
                                        "ts": time.time()
                                    }
                                    await push_chat_event_to_ui(state, chat_job_id, invite_event)
                                    logger.info(f"[chat_raise] invite pushed to UI for job_id={chat_job_id}")
                                    
                                    # Р—Р°РїСѓСЃРєР°РµРј start_job Рё ui_notify Р°СЃРёРЅС…СЂРѕРЅРЅРѕ РІ background (РЅРµ Р¶РґРµРј РѕС‚РІРµС‚Р°)
                                    async def _background_notify():
                                        """Р¤РѕРЅРѕРІР°СЏ Р·Р°РґР°С‡Р° РґР»СЏ РѕС‚РїСЂР°РІРєРё start_job Рё ui_notify"""
                                        try:
                                            # РЎС‚Р°СЂС‚СѓРµРј support_chat РЅР° Р°РіРµРЅС‚Рµ
                                            try:
                                                await send_ws_command(
                                                    state=state,
                                                    device_id=agent_id,
                                                    command="start_job",
                                                    params={
                                                        "job_type": "support_chat",
                                                        "params": {
                                                            "job_id": chat_job_id,
                                                            "ticket_id": ticket_id  # Phase V3: send ticket_id
                                                        }
                                                    },
                                                    actor_role="agent"
                                                )
                                                logger.info(f"[chat_raise] start_job sent to agent {agent_id}")
                                            except Exception as e:
                                                logger.opt(exception=True).error(
                                                    "[chat_raise] Failed to send start_job to agent: {}",
                                                    e,
                                                )
                                            
                                            # PUSH invite РІ Р»РѕРєР°Р»СЊРЅС‹Р№ GUI Р°РіРµРЅС‚Р° С‡РµСЂРµР· ui_notify
                                            try:
                                                await send_ws_command(
                                                    state=state,
                                                    device_id=agent_id,
                                                    command="ui_notify",
                                                    params={"event": invite_event},
                                                    actor_role="agent"
                                                )
                                                logger.info(f"[chat_raise] ui_notify sent to agent {agent_id}")
                                            except Exception as e:
                                                logger.opt(exception=True).error(
                                                    "[chat_raise] Failed to send ui_notify to agent: {}",
                                                    e,
                                                )
                                        except Exception as e:
                                            logger.opt(exception=True).error(
                                                "[chat_raise] Background notify failed: {}",
                                                e,
                                            )
                                    
                                    # Р—Р°РїСѓСЃРєР°РµРј РІ background, РЅРµ Р¶РґРµРј Р·Р°РІРµСЂС€РµРЅРёСЏ
                                    asyncio.create_task(_background_notify())
                                
                                # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                # РќРµРёР·РІРµСЃС‚РЅР°СЏ РєРѕРјР°РЅРґР° РѕС‚ Р°РіРµРЅС‚Р°
                                # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                else:
                                    logger.warning(f"[SERVER] Unknown command from agent {agent_id}: {command}")
                                    
                                    # РћС‚РїСЂР°РІР»СЏРµРј РѕС€РёР±РєСѓ Р°РіРµРЅС‚Сѓ
                                    error_envelope = {
                                        "type": "command_result",
                                        "request_id": req_id,
                                        "device_id": agent_id,
                                        "payload": {
                                            "status": "error",
                                            "error": {
                                                "code": "UNKNOWN_COMMAND",
                                                "message": f"Unknown command: {command}"
                                            }
                                        }
                                    }
                                    
                                    await ws.send_json(error_envelope)
                    
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # e) type == "outbox_item" - V3 Protocol with Postgres Ingest
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    elif msg_type == "outbox_item":
                        # Р­С‚Рѕ РґРѕСЃС‚Р°РІРєР° РґР°РЅРЅС‹С… РёР· outbox Р°РіРµРЅС‚Р° (Protocol V3)
                        # РљР РРўРР§РќРћ: РР·РІР»РµРєР°РµРј outbox_id Рё trace_id Р”Рћ РѕР±СЂР°Р±РѕС‚РєРё РґР»СЏ РіР°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅРѕР№ РѕС‚РїСЂР°РІРєРё NACK РїСЂРё РѕС€РёР±РєРµ
                        outbox_id = None
                        trace_id = None
                        agent_device_id = None
                        
                        if agent_id:
                            agent_info = state.get_agent(agent_id)
                            if agent_info:
                                try:
                                    agent_info["metadata"]["last_seen"] = time.time()
                                    
                                    # Update devices.last_seen_at in database
                                    if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                        try:
                                            async with get_session() as session:
                                                from app.repos import DevicesRepo
                                                devices_repo = DevicesRepo(session)
                                                await devices_repo.update_last_seen(agent_id)
                                                await session.commit()
                                        except Exception as e:
                                            logger.debug(f"[outbox_item] Failed to update last_seen: {e}")

                                    
                                    # РР·РІР»РµРєР°РµРј trace_id РёР· envelope (РѕР±СЏР·Р°С‚РµР»РµРЅ РґР»СЏ ACK/NACK)
                                    trace_id = data.get("trace_id")
                                    if not trace_id:
                                        logger.warning(f"[V3] outbox_item without trace_id from agent {agent_id}")
                                        trace_id = str(uuid.uuid4())  # Fallback
                                    
                                    payload = data.get("payload", {})
                                    # РџСЂРѕРІРµСЂРєР° С‚РёРїР° payload
                                    if not isinstance(payload, dict):
                                        logger.error(
                                            f"[V3] outbox_item payload is not a dict: "
                                            f"type={type(payload).__name__} value={payload}"
                                        )
                                        # РћС‚РїСЂР°РІР»СЏРµРј NACK РґР»СЏ РЅРµРєРѕСЂСЂРµРєС‚РЅРѕРіРѕ payload
                                        outbox_id = payload.get("outbox_id") if isinstance(payload, dict) else None
                                        if outbox_id:
                                            agent_device_id = agent_info["metadata"].get("device_id", agent_id)
                                            batch_ack_manager.add_nack(
                                                device_id=agent_id,
                                                outbox_id=str(outbox_id),
                                                trace_id=trace_id,
                                                nack_info=NackInfo(
                                                    retryable=False,
                                                    error_code="VALIDATION_ERROR",
                                                    error_message="Payload is not a dict",
                                                    retry_after_sec=None
                                                )
                                            )
                                        continue
                                    
                                    outbox_id = payload.get("outbox_id")
                                    item_type = payload.get("item_type", "unknown")
                                    agent_device_id = agent_info["metadata"].get("device_id", agent_id)
                                    
                                    if not outbox_id:
                                        logger.error(f"[V3] outbox_item without outbox_id from agent {agent_id}")
                                        # РћС‚РїСЂР°РІР»СЏРµРј NACK РґР»СЏ РѕС‚СЃСѓС‚СЃС‚РІСѓСЋС‰РµРіРѕ outbox_id
                                        batch_ack_manager.add_nack(
                                            device_id=agent_id,
                                            outbox_id="unknown",
                                            trace_id=trace_id,
                                            nack_info=NackInfo(
                                                retryable=False,
                                                error_code="VALIDATION_ERROR",
                                                error_message="Missing outbox_id in payload",
                                                retry_after_sec=None
                                            )
                                        )
                                        continue
                                
                                    logger.info(
                                        f"[V3] RX outbox_item: agent_id={agent_id} "
                                        f"outbox_id={outbox_id} item_type={item_type} trace_id={trace_id}"
                                    )
                                    
                                    # РљР РРўРР§РќРћ: Р›РѕРіРёСЂСѓРµРј payload РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё РїСЂРѕР±Р»РµРј СЃ РїР°СЂСЃРёРЅРіРѕРј
                                    if item_type == "job_event":
                                        logger.debug(
                                            f"[V3] job_event payload structure: "
                                            f"outbox_id={outbox_id} payload_keys={list(payload.keys())} "
                                            f"has_event={'event' in payload} "
                                            f"event_type={type(payload.get('event')).__name__ if 'event' in payload else 'missing'}"
                                        )
                                    
                                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                    # РћР±СЂР°Р±РѕС‚РєР° job_event (РјРѕР¶РµС‚ Р±С‹С‚СЊ ticket event РёР»Рё device event)
                                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                    if item_type == "job_event":
                                        # РќРѕСЂРјР°Р»РёР·Р°С†РёСЏ payload: РєР»СЋС‡ С‚РѕР»СЊРєРѕ "event", РЅРµ '"event"' (РµРґРёРЅС‹Р№ РІРёРґ РґР»СЏ РІСЃРµРіРѕ РєРѕРґР°)
                                        _pk = '"event"'
                                        if _pk in payload and "event" not in payload:
                                            payload["event"] = payload[_pk]
                                            del payload[_pk]
                                        elif _pk in payload:
                                            del payload[_pk]
                                        # РљР РРўРР§РќРћ: event РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ СЃР»РѕРІР°СЂРµРј, РЅРѕ РјРѕР¶РµС‚ Р±С‹С‚СЊ СЃС‚СЂРѕРєРѕР№ РІ legacy С„РѕСЂРјР°С‚Рµ
                                        try:
                                            event_raw = payload.get("event", {})
                                            if event_raw is None:
                                                event_raw = {}
                                            # Р•СЃР»Рё event РїСЂРёС€С‘Р» РєР°Рє JSON-СЃС‚СЂРѕРєР° (РґРІРѕР№РЅРѕРµ РєРѕРґРёСЂРѕРІР°РЅРёРµ), РїР°СЂСЃРёРј
                                            if isinstance(event_raw, str) and event_raw.strip().startswith("{"):
                                                try:
                                                    event_raw = json.loads(event_raw)
                                                except json.JSONDecodeError:
                                                    pass
                                            
                                            # РљР РРўРР§РќРћ: РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ event_raw РЅРµ СЏРІР»СЏРµС‚СЃСЏ СЃС‚СЂРѕРєРѕР№ "event" (РѕС€РёР±РєР° РїР°СЂСЃРёРЅРіР°)
                                            if isinstance(event_raw, str) and event_raw == "event":
                                                logger.error(
                                                    f"[V3] CRITICAL: payload.event is string 'event' instead of dict. "
                                                    f"payload={payload} outbox_id={outbox_id}"
                                                )
                                                raise ValueError(
                                                    f"Invalid event format: payload.event is string '{event_raw}' "
                                                    f"instead of dict. Full payload: {payload}"
                                                )
                                            
                                            if isinstance(event_raw, dict):
                                                event = dict(event_raw)
                                            else:
                                                # Legacy С„РѕСЂРјР°С‚: event - СЌС‚Рѕ СЃС‚СЂРѕРєР° (С‚РёРї СЃРѕР±С‹С‚РёСЏ)
                                                # РЎРѕР·РґР°РµРј СЃР»РѕРІР°СЂСЊ СЃ РїРѕР»РµРј event Рё РѕСЃС‚Р°Р»СЊРЅС‹РјРё РїРѕР»СЏРјРё РёР· payload (РёРіРЅРѕСЂРёСЂСѓРµРј РѕР±Р° РІР°СЂРёР°РЅС‚Р° РєР»СЋС‡Р°)
                                                event = {
                                                    "event": event_raw if isinstance(event_raw, str) else "unknown",
                                                    **{k: v for k, v in payload.items() if k not in ("event", '"event"')}
                                                }
                                            
                                            # РљР РРўРР§РќРћ: РќРѕСЂРјР°Р»РёР·Р°С†РёСЏ РєР»СЋС‡Р° "event" вЂ” РІРµР·РґРµ С‚РѕР»СЊРєРѕ "event", Р±РµР· '"event"'
                                            # РЈСЃС‚СЂР°РЅСЏРµС‚ KeyError РїСЂРё РїРµСЂРµРґР°С‡Рµ РІ СЂРµРїРѕР·РёС‚РѕСЂРёРё Рё РґР°Р»СЊС€Рµ РїРѕ РєРѕРґСѓ
                                            _wrong_key = '"event"'
                                            if _wrong_key in event:
                                                if "event" not in event:
                                                    event["event"] = event[_wrong_key]
                                                del event[_wrong_key]
                                            
                                            # РљР РРўРР§РќРћ: Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅР°СЏ РїСЂРѕРІРµСЂРєР°, С‡С‚Рѕ event - СЌС‚Рѕ СЃР»РѕРІР°СЂСЊ
                                            if not isinstance(event, dict):
                                                logger.error(
                                                    f"[V3] CRITICAL: event is not a dict after processing: "
                                                    f"type={type(event)} value={event} outbox_id={outbox_id}"
                                                )
                                                raise ValueError(
                                                    f"Invalid event format: event is {type(event).__name__}, "
                                                    f"expected dict. Value: {event}"
                                                )
                                            
                                            ticket_id = event.get("ticket_id")
                                            agent_seq = payload.get("agent_seq")
                                            event_id = payload.get("event_id")
                                        except (KeyError, ValueError, TypeError) as parse_error:
                                            # РљР РРўРР§РќРћ: РћС€РёР±РєР° РїР°СЂСЃРёРЅРіР° event - РѕС‚РїСЂР°РІР»СЏРµРј NACK СЃ РґРµС‚Р°Р»СЊРЅРѕР№ РёРЅС„РѕСЂРјР°С†РёРµР№
                                            logger.error(
                                                f"[V3] Failed to parse event from payload: {parse_error} "
                                                f"outbox_id={outbox_id} payload={payload}",
                                                exc_info=True
                                            )
                                            batch_ack_manager.add_nack(
                                                device_id=agent_id,
                                                outbox_id=outbox_id,
                                                trace_id=trace_id,
                                                nack_info=NackInfo(
                                                    retryable=False,  # РќРµ СЂРµС‚СЂР°РёС‚СЃСЏ, С‚Р°Рє РєР°Рє СЌС‚Рѕ РѕС€РёР±РєР° С„РѕСЂРјР°С‚Р°
                                                    error_code="VALIDATION_ERROR",
                                                    error_message=f"Failed to parse event: {str(parse_error)}",
                                                    retry_after_sec=None
                                                )
                                            )
                                            continue
                                        
                                        # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                        # РЎР»СѓС‡Р°Р№ 1: Device Event (Р±РµР· ticket_id)
                                        # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                        if not ticket_id:
                                            device_seq = payload.get("device_seq", 0)
                                            event_type = event.get("event", "unknown")
                                            
                                            if not device_seq:
                                                logger.warning(
                                                    f"[V3] Device event without device_seq: "
                                                    f"event_type={event_type}, using 0 as fallback"
                                                )
                                            
                                            # Persist to Postgres (device_events)
                                            if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                                try:
                                                    async with get_session() as session:
                                                        device_events_repo = DeviceEventsRepo(session)
                                                        inserted_id = await device_events_repo.add_event(
                                                            device_id=agent_id,
                                                            device_seq=device_seq,
                                                            event_type=event_type,
                                                            payload=event,
                                                            trace_id=trace_id,
                                                            event_id=event_id
                                                        )
                                                        await session.commit()
                                                        
                                                        if inserted_id:
                                                            logger.info(
                                                                f"[V3] Device event persisted: "
                                                                f"id={inserted_id} device_id={agent_id} "
                                                                f"device_seq={device_seq} event_type={event_type}"
                                                            )
                                                        else:
                                                            logger.debug(
                                                                f"[V3] Duplicate device event: "
                                                                f"device_id={agent_id} device_seq={device_seq}"
                                                            )
                                                except Exception as e:
                                                    logger.opt(exception=True).error(
                                                        "[V3] Failed to persist device event: {}",
                                                        e,
                                                    )
                                            
                                            # Check if this is tools_changed event
                                            if event_type == "tools_changed":
                                                # Extract toolset_hash and tools_count
                                                toolset_hash = event.get("toolset_hash")
                                                tools_count = event.get("tools_count")
                                                
                                                # Update devices.last_toolset_hash and last_tools_changed_at
                                                if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                                    try:
                                                        async with get_session() as session:
                                                            from app.repos import DevicesRepo
                                                            from websocket.modules_sync import check_module_tools_drift
                                                            
                                                            devices_repo = DevicesRepo(session)
                                                            await devices_repo.update_toolset_info(
                                                                device_id=agent_id,
                                                                toolset_hash=toolset_hash,
                                                                tools_count=tools_count
                                                            )
                                                            
                                                            # Drift check: verify active modules have tools in snapshot
                                                            drift_warnings = await check_module_tools_drift(
                                                                session=session,
                                                                device_id=agent_id
                                                            )
                                                            
                                                            if drift_warnings:
                                                                logger.warning(
                                                                    f"[tools_changed] Device {agent_id} has drift: {drift_warnings}"
                                                                )
                                                            
                                                            await session.commit()
                                                            logger.info(
                                                                f"[tools_changed] Updated toolset info: "
                                                                f"device_id={agent_id} toolset_hash={toolset_hash} "
                                                                f"tools_count={tools_count}"
                                                            )
                                                    except Exception as e:
                                                        logger.opt(exception=True).error(
                                                            "[V3] Failed to update toolset info: {}",
                                                            e,
                                                        )
                                            
                                            # module_state_changed: агент сообщает о реальном состоянии модуля
                                            if event_type == "module_state_changed":
                                                if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                                    try:
                                                        async with get_session() as session:
                                                            from websocket.modules_sync import sync_modules_inventory, flatten_modules_list
                                                            from modules.reconcile import reconcile_device

                                                            modules_snapshot = event.get("modules_snapshot") or []
                                                            if modules_snapshot:
                                                                flat = flatten_modules_list(modules_snapshot)
                                                                await sync_modules_inventory(
                                                                    session=session,
                                                                    device_id=agent_id,
                                                                    inventory=flat,
                                                                )
                                                                await session.commit()
                                                                logger.info(
                                                                    f"[module_state_changed] Synced inventory: "
                                                                    f"device={agent_id} modules={len(flat)}"
                                                                )

                                                            # Immediate reconcile после обновления actual state
                                                            reconcile_stats = await reconcile_device(
                                                                device_id=agent_id,
                                                                state=state,
                                                                reason="module_state_changed",
                                                            )
                                                            if reconcile_stats["installs"] or reconcile_stats["removes"]:
                                                                logger.info(
                                                                    f"[module_state_changed] Reconcile: "
                                                                    f"device={agent_id} {reconcile_stats}"
                                                                )
                                                    except Exception as e:
                                                        logger.opt(exception=True).error(
                                                            "[module_state_changed] Error: {}",
                                                            e,
                                                        )

                                            # Legacy: С‚Р°РєР¶Рµ СЃРѕС…СЂР°РЅСЏРµРј РІ job_events (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
                                            job_id = payload.get("job_id")
                                            if job_id:
                                                state.append_job_event(job_id, event)
                                                await persist_job_event(job_id, event)
                                                await push_chat_event_to_ui(state, job_id, event)
                                            
                                            # Phase B: РќР°РєР°РїР»РёРІР°РµРј ACK РІ batch manager
                                            batch_ack_manager.add_ack(
                                                device_id=agent_id,
                                                outbox_id=outbox_id,
                                                trace_id=trace_id
                                            )
                                            continue
                                        
                                        # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                        # РЎР»СѓС‡Р°Р№ 2: Ticket Event (СЃ ticket_id) - С‚СЂРµР±СѓРµС‚ РІР°Р»РёРґР°С†РёРё
                                        # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                        
                                        # Phase B: Р’Р°Р»РёРґР°С†РёСЏ СЃ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёРµРј EventValidator
                                        event_type = event.get("event", "unknown")
                                        
                                        # РџРµСЂРІРёС‡РЅР°СЏ РІР°Р»РёРґР°С†РёСЏ Рё РІСЃС‚Р°РІРєР° РІ DB
                                        if DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                                            try:
                                                async with get_session() as session:
                                                    # Р’Р°Р»РёРґРёСЂСѓРµРј СЃРѕР±С‹С‚РёРµ
                                                    validation_result = await event_validator.validate_ticket_event(
                                                        session=session,
                                                        ticket_id=ticket_id,
                                                        device_id=agent_id,
                                                        agent_seq=agent_seq,
                                                        event_type=event_type,
                                                        payload=event
                                                    )
                                                    
                                                    if not validation_result.valid:
                                                        # Р’Р°Р»РёРґР°С†РёСЏ РЅРµ РїСЂРѕС€Р»Р° - РЅР°РєР°РїР»РёРІР°РµРј NACK
                                                        logger.warning(
                                                            f"[V3] Validation failed: ticket_id={ticket_id} "
                                                            f"error_code={validation_result.error_code}"
                                                        )
                                                        
                                                        batch_ack_manager.add_nack(
                                                            device_id=agent_id,
                                                            outbox_id=outbox_id,
                                                            trace_id=trace_id,
                                                            nack_info=NackInfo(
                                                                retryable=validation_result.retryable,
                                                                error_code=validation_result.error_code,
                                                                error_message=validation_result.error_message,
                                                                retry_after_sec=30 if validation_result.retryable else None
                                                            )
                                                        )
                                                        continue
                                                    
                                                    # Р’Р°Р»РёРґР°С†РёСЏ РїСЂРѕР№РґРµРЅР° - РІСЃС‚Р°РІР»СЏРµРј СЃРѕР±С‹С‚РёРµ РІ Postgres
                                                    # РљР РРўРР§РќРћ: РџСЂРѕРІРµСЂСЏРµРј, С‡С‚Рѕ TicketEventsRepo РґРѕСЃС‚СѓРїРµРЅ
                                                    if not DB_AVAILABLE:
                                                        logger.error(
                                                            f"[V3] DB not available but reached ticket event insertion: "
                                                            f"ticket_id={ticket_id}"
                                                        )
                                                        raise RuntimeError("DB not available")
                                                    
                                                    # Р›РѕРєР°Р»СЊРЅС‹Р№ РёРјРїРѕСЂС‚ РґР»СЏ РіР°СЂР°РЅС‚РёРё РґРѕСЃС‚СѓРїРЅРѕСЃС‚Рё
                                                    from app.repos import TicketEventsRepo as TicketEventsRepoLocal
                                                    ticket_events_repo = TicketEventsRepoLocal(session)
                                                    
                                                    # РљР РРўРР§РќРћ: РќР°С…РѕРґРёРј operation_id РґР»СЏ СЃРѕР±С‹С‚РёР№ tool_call_started Рё tool_call_result
                                                    # С‡РµСЂРµР· call_id РёР· СЃРѕР±С‹С‚РёСЏ
                                                    operation_id = None
                                                    if event_type in ["tool_call_started", "tool_call_result"]:
                                                        call_id = event.get("call_id")
                                                        if call_id:
                                                            # РС‰РµРј server-originated СЃРѕР±С‹С‚РёРµ tool_call_started СЃ СЌС‚РёРј call_id
                                                            # С‡С‚РѕР±С‹ РїРѕР»СѓС‡РёС‚СЊ operation_id
                                                            from sqlalchemy import select
                                                            from app.db.models import TicketEvent
                                                            stmt = select(TicketEvent).where(
                                                                TicketEvent.ticket_id == ticket_id,
                                                                TicketEvent.event_type == "tool_call_started",
                                                                TicketEvent.payload['call_id'].astext == call_id,
                                                                TicketEvent.operation_id.isnot(None)
                                                            ).limit(1)
                                                            result = await session.execute(stmt)
                                                            server_event = result.scalar_one_or_none()
                                                            if server_event and server_event.operation_id:
                                                                operation_id = server_event.operation_id
                                                                logger.debug(
                                                                    f"[V3] Found operation_id={operation_id} "
                                                                    f"for call_id={call_id} event_type={event_type}"
                                                                )
                                                    
                                                    result = await ticket_events_repo.add_event(
                                                        ticket_id=ticket_id,
                                                        device_id=agent_id,
                                                        agent_seq=agent_seq,
                                                        event_type=event_type,
                                                        payload=event,
                                                        trace_id=trace_id,
                                                        event_id=event_id,
                                                        operation_id=operation_id  # РљР РРўРР§РќРћ: СЃРІСЏР·С‹РІР°РµРј СЃ РѕРїРµСЂР°С†РёРµР№
                                                    )
                                                    
                                                    if result:
                                                        await session.commit()
                                                        inserted_id, created_at = result
                                                        logger.info(
                                                            f"[V3] Ticket event persisted: "
                                                            f"id={inserted_id} ticket_id={ticket_id} "
                                                            f"agent_seq={agent_seq} event_type={event_type}"
                                                        )
                                                        
                                                        # РљР РРўРР§РќРћ: Push РёСЃРїРѕР»СЊР·СѓРµС‚ РґР°РЅРЅС‹Рµ РёР· INSERT RETURNING
                                                        if state.subscription_registry:
                                                            from websocket.ui_handler import push_ticket_event_committed
                                                            await push_ticket_event_committed(
                                                                state,
                                                                ticket_id=ticket_id,
                                                                event_id=inserted_id,
                                                                event_type=event_type,
                                                                operation_id=operation_id,
                                                                agent_seq=agent_seq,
                                                                created_at=created_at,
                                                                payload=event
                                                            )
                                                    else:
                                                        # Stage 7: rollback РїСЂРё РёРґРµРјРїРѕС‚РµРЅС‚РЅРѕРј РґСѓР±Р»РёРєР°С‚Рµ
                                                        await session.rollback()
                                                        logger.debug(
                                                            f"[V3] Duplicate ticket event: "
                                                            f"ticket_id={ticket_id} agent_seq={agent_seq}"
                                                        )
                                                    
                                                    # Legacy: С‚Р°РєР¶Рµ РѕР±РЅРѕРІР»СЏРµРј in-memory state (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
                                                    job_id = payload.get("job_id")
                                                    if job_id:
                                                        state.append_job_event(job_id, event)
                                                        await persist_job_event(job_id, event)
                                                        await push_chat_event_to_ui(state, job_id, event)
                                                    
                                                    # Р”РѕРї. Р»РѕРіРёРєР° РґР»СЏ С‚РёРєРµС‚РѕРІ: РѕР±РЅРѕРІР»РµРЅРёРµ СЃС‚Р°С‚СѓСЃР° Рё runtime-СЃРµСЃСЃРёР№
                                                    # РЎРѕР±С‹С‚РёСЏ СѓР¶Рµ РІ Р‘Р” (add_event РІС‹С€Рµ). StateManager РЅРµ СЃРѕРґРµСЂР¶РёС‚
                                                    # append_ticket_event/append_ticket_message (V3 SoT вЂ” PostgreSQL).
                                                    ticket_obj = await ticket_events_repo.get_ticket(ticket_id)
                                                    if ticket_obj:
                                                        # chat_message: СѓР¶Рµ Р·Р°РїРёСЃР°РЅ РІ ticket_events С‡РµСЂРµР· add_event
                                                        # Р”РµРґСѓРїР»РёРєР°С†РёСЏ вЂ” С‡РµСЂРµР· state.is_duplicate_message (runtime cache)
                                                        if event_type == "chat_message":
                                                            message_id = event.get("message_id")
                                                            if message_id:
                                                                state.is_duplicate_message(ticket_id, message_id)
                                                        
                                                        # chat_ended: РѕР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ С‚РёРєРµС‚Р° РІ Р‘Р” Рё runtime-СЃРµСЃСЃРёСЋ
                                                        elif event_type == "chat_ended":
                                                            if ticket_obj.status != "closed":
                                                                await ticket_events_repo.update_ticket_status(
                                                                    ticket_id, "closed"
                                                                )
                                                                try:
                                                                    from app.repos.auth_tokens_repo import AuthTokensRepo
                                                                    auth_repo = AuthTokensRepo(session)
                                                                    await auth_repo.revoke_ticket_public_sessions(
                                                                        ticket_id,
                                                                        commit=False,
                                                                    )
                                                                except Exception as revoke_err:
                                                                    logger.warning(
                                                                        f"[V3] Failed to revoke public ticket sessions on chat_ended: "
                                                                        f"ticket_id={ticket_id} err={revoke_err}"
                                                                    )
                                                                session_obj = state.get_session_by_ticket(ticket_id)
                                                                if session_obj:
                                                                    session_obj.status = "closed"
                                                                    session_obj.updated_at = now_iso()
                                                                    session_obj.last_activity_at = now_iso()
                                                    
                                                    # Phase B: РќР°РєР°РїР»РёРІР°РµРј ACK РІ batch manager
                                                    batch_ack_manager.add_ack(
                                                        device_id=agent_id,
                                                        outbox_id=outbox_id,
                                                        trace_id=trace_id
                                                    )
                                                    
                                            except Exception as e:
                                                try:
                                                    await session.rollback()
                                                except Exception:
                                                    logger.opt(exception=True).error(
                                                        "[V3] Failed to rollback session after ticket event error"
                                                    )
                                                logger.opt(exception=True).error(
                                                    f"[V3] Failed to process ticket event: "
                                                    f"ticket_id={ticket_id} outbox_id={outbox_id} trace_id={trace_id}"
                                                )
                                                # Р’ СЃР»СѓС‡Р°Рµ РѕС€РёР±РєРё РЅР°РєР°РїР»РёРІР°РµРј retryable NACK
                                                batch_ack_manager.add_nack(
                                                    device_id=agent_id,
                                                    outbox_id=outbox_id,
                                                    trace_id=trace_id,
                                                    nack_info=NackInfo(
                                                        retryable=True,
                                                        error_code="SERVER_ERROR",
                                                        error_message=f"Internal server error: {str(e)}",
                                                        retry_after_sec=30
                                                    )
                                                )
                                        else:
                                            # DB РЅРµ РґРѕСЃС‚СѓРїРЅР° - РЅР°РєР°РїР»РёРІР°РµРј ACK
                                            logger.warning(
                                                f"[V3] DB not available, accumulating ACK for "
                                                f"ticket_id={ticket_id}"
                                            )
                                            
                                            # Legacy РѕР±СЂР°Р±РѕС‚РєР°
                                            job_id = payload.get("job_id")
                                            if job_id:
                                                state.append_job_event(job_id, event)
                                                await persist_job_event(job_id, event)
                                                await push_chat_event_to_ui(state, job_id, event)
                                            
                                            batch_ack_manager.add_ack(
                                                device_id=agent_id,
                                                outbox_id=outbox_id,
                                                trace_id=trace_id
                                            )
                                    
                                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                    # Р”СЂСѓРіРёРµ С‚РёРїС‹ item_type (РїРѕРєР° РЅРµ РїРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ)
                                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                                    else:
                                        logger.warning(
                                            f"[V3] Unknown item_type: {item_type}, accumulating ACK anyway"
                                        )
                                        batch_ack_manager.add_ack(
                                            device_id=agent_id,
                                            outbox_id=outbox_id,
                                            trace_id=trace_id
                                        )
                                
                                except Exception as e:
                                    # РљР РРўРР§РќРћ: Р“Р°СЂР°РЅС‚РёСЂРѕРІР°РЅРЅР°СЏ РѕС‚РїСЂР°РІРєР° NACK РїСЂРё Р»СЋР±РѕР№ РѕС€РёР±РєРµ РѕР±СЂР°Р±РѕС‚РєРё outbox_item
                                    error_type = type(e).__name__
                                    error_msg = str(e)
                                    
                                    # РљР РРўРР§РќРћ: Р›РѕРіРёСЂСѓРµРј РїРѕР»РЅСѓСЋ РёРЅС„РѕСЂРјР°С†РёСЋ РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё (Р±РµР· format РґР»СЏ error_msg вЂ” РјРѕР¶РµС‚ СЃРѕРґРµСЂР¶Р°С‚СЊ {})
                                    logger.opt(exception=True).error(
                                        f"[V3] Failed to process outbox_item: error_type={error_type} "
                                        f"outbox_id={outbox_id} item_type={item_type} agent_id={agent_id} trace_id={trace_id} error={error_msg!r}"
                                    )
                                    
                                    # РљР РРўРР§РќРћ: Р›РѕРіРёСЂСѓРµРј payload РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё (РµСЃР»Рё РґРѕСЃС‚СѓРїРµРЅ)
                                    try:
                                        payload_str = str(payload)[:500]  # РћРіСЂР°РЅРёС‡РёРІР°РµРј РґР»РёРЅСѓ
                                        logger.debug(
                                            f"[V3] Error context - payload preview: {payload_str}"
                                        )
                                    except:
                                        pass
                                    
                                    if outbox_id and trace_id:
                                        # РћРїСЂРµРґРµР»СЏРµРј, СЂРµС‚СЂР°РёС‚СЃСЏ Р»Рё РѕС€РёР±РєР°
                                        # KeyError, ValueError, TypeError - РѕР±С‹С‡РЅРѕ РЅРµ СЂРµС‚СЂР°РёС‚СЃСЏ (РѕС€РёР±РєР° С„РѕСЂРјР°С‚Р°)
                                        # Р”СЂСѓРіРёРµ РѕС€РёР±РєРё - РјРѕРіСѓС‚ Р±С‹С‚СЊ РІСЂРµРјРµРЅРЅС‹РјРё
                                        is_retryable = error_type not in ("KeyError", "ValueError", "TypeError", "AttributeError")
                                        
                                        batch_ack_manager.add_nack(
                                            device_id=agent_id,
                                            outbox_id=str(outbox_id),
                                            trace_id=trace_id,
                                            nack_info=NackInfo(
                                                retryable=is_retryable,
                                                error_code="VALIDATION_ERROR" if not is_retryable else "SERVER_ERROR",
                                                error_message=f"Internal server error during processing: {error_type}: {error_msg}",
                                                retry_after_sec=30 if is_retryable else None
                                            )
                                        )
                    
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    # f) Р›СЋР±РѕР№ РґСЂСѓРіРѕР№ type / РЅРµРёР·РІРµСЃС‚РЅС‹Р№ С„РѕСЂРјР°С‚
                    # в”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓв”Ѓ
                    else:
                        # РЎС‚Р°СЂС‹Р№ С„РѕСЂРјР°С‚ Р±РµР· type - Р»РѕРіРёСЂСѓРµРј Рё РёРіРЅРѕСЂРёСЂСѓРµРј
                        if msg_type is None:
                            logger.warning(f"[SERVER] Received message without type from agent {agent_id}, ignoring")
                        else:
                            logger.warning(f"[SERVER] Unknown message type '{msg_type}' from agent {agent_id}, ignoring")
                    
                    # Phase B: Flush batch ACK/NACK РїРѕСЃР»Рµ РѕР±СЂР°Р±РѕС‚РєРё РєР°Р¶РґРѕРіРѕ СЃРѕРѕР±С‰РµРЅРёСЏ
                    if agent_id and batch_ack_manager.has_pending(agent_id):
                        await batch_ack_manager.flush(ws, agent_id)
                
                except json.JSONDecodeError:
                    logger.warning(f"вљ пёЏ  РџРѕР»СѓС‡РµРЅРѕ РЅРµ-JSON СЃРѕРѕР±С‰РµРЅРёРµ: {msg.data}")
                except Exception as e:
                    logger.opt(exception=True).error(
                        f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё СЃРѕРѕР±С‰РµРЅРёСЏ: {e!r}"
                    )
                    # РљР РРўРР§РќРћ: Р•СЃР»Рё СЌС‚Рѕ outbox_item Рё РјС‹ Р·РЅР°РµРј outbox_id, РѕС‚РїСЂР°РІР»СЏРµРј NACK
                    # Р­С‚Рѕ РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ Р°РіРµРЅС‚ РЅРµ Р±СѓРґРµС‚ Р¶РґР°С‚СЊ ACK Р±РµСЃРєРѕРЅРµС‡РЅРѕ
                    if msg_type == "outbox_item" and agent_id:
                        try:
                            # РџС‹С‚Р°РµРјСЃСЏ РёР·РІР»РµС‡СЊ outbox_id Рё trace_id РёР· РґР°РЅРЅС‹С…
                            payload = data.get("payload", {}) if isinstance(data, dict) else {}
                            outbox_id = payload.get("outbox_id") if isinstance(payload, dict) else None
                            trace_id = data.get("trace_id") if isinstance(data, dict) else None
                            
                            if outbox_id and trace_id:
                                agent_info = state.get_agent(agent_id)
                                if agent_info:
                                    agent_device_id = agent_info["metadata"].get("device_id", agent_id)
                                    batch_ack_manager.add_nack(
                                        device_id=agent_id,
                                        outbox_id=str(outbox_id),
                                        trace_id=trace_id,
                                        nack_info=NackInfo(
                                            retryable=True,  # Retryable, С‚Р°Рє РєР°Рє СЌС‚Рѕ РјРѕР¶РµС‚ Р±С‹С‚СЊ РІСЂРµРјРµРЅРЅР°СЏ РѕС€РёР±РєР°
                                            error_code="SERVER_ERROR",
                                            error_message=f"Internal server error during processing: {str(e)}",
                                            retry_after_sec=30
                                        )
                                    )
                                    # Flush NACK РЅРµРјРµРґР»РµРЅРЅРѕ
                                    if batch_ack_manager.has_pending(agent_id):
                                        await batch_ack_manager.flush(ws, agent_id)
                        except Exception as nack_error:
                            logger.opt(exception=True).error(
                                f"вќЊ РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ NACK РґР»СЏ outbox_item: {nack_error!r}"
                            )
                    # РќРµ РІР°Р»РёРј СЃРѕРµРґРёРЅРµРЅРёРµ РїСЂРё РѕС€РёР±РєРµ РѕР±СЂР°Р±РѕС‚РєРё
            
            elif msg.type == web.WSMsgType.ERROR:
                logger.error(
                    f"вќЊ РћС€РёР±РєР° WebSocket: {ws.exception()!r}"
                )
                break
    
    finally:
        # РћС‚РєР»СЋС‡РµРЅРёРµ Р°РіРµРЅС‚Р° - РїСЂРѕСЃС‚Рѕ СѓРґР°Р»СЏРµРј РёР· СЃРїРёСЃРєР° (РІС‹С…РѕРґ РёР· handler = СЃРѕРµРґРёРЅРµРЅРёРµ Р·Р°РєСЂС‹С‚Рѕ)
        if agent_id:
            agent_info = state.get_agent(agent_id)
            if agent_info:
                agent_info["metadata"]["status"] = "offline"
            state.unregister_agent(agent_id)
            logger.info(
                f"[WS handler] Exiting handler for agent_id={agent_id}, unregistering (connection closed)"
            )
            logger.warning(f"рџ”ґ РђРіРµРЅС‚ РѕС‚РєР»СЋС‡РµРЅ: {agent_id}")
    
    return ws
