"""Handshake handler extracted from agent websocket legacy module."""

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
from auth.agent_token_service import AgentTokenService
from auth.connection_request_service import ConnectionRequestService
from auth.context import AuthContext, AuthType
from websocket.contexts import AgentConnectionContext, EnvelopeContext
from websocket.agent_services import (
    AgentLoopSafetyService,
    AgentCommandService,
    AgentMessageRouter,
    CommandAckService,
    CommandResultService,
    HandshakeService,
    OutboxIngestService,
)

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

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
    agent_id = None
    device_id = None
    authenticated = False

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
        return (ws, agent_id, device_id, authenticated)
    
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
        return (ws, agent_id, device_id, authenticated)
    
    # Phase 3: РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ РґР»СЏ Р°СѓС‚РµРЅС‚РёС„РёРєР°С†РёРё С‡РµСЂРµР· Р‘Р”
    token = data.get("token")
    logger.debug(
        f"Handshake: token received=%s prefix=%s",
        bool(token),
        token[:12] + "..." if token and len(token) >= 12 else (token or "")
    )
    loop_safety_service = AgentLoopSafetyService()
    
    # РР·РІР»РµРєР°РµРј device_id РёР· payload РґР»СЏ РѕС‚СЃР»РµР¶РёРІР°РЅРёСЏ РїРѕРїС‹С‚РѕРє РїРѕРґРєР»СЋС‡РµРЅРёСЏ
    # РџСЂРѕРІРµСЂСЏРµРј РІ СЂР°Р·РЅС‹С… РјРµСЃС‚Р°С…: РєРѕСЂРµРЅСЊ СЃРѕРѕР±С‰РµРЅРёСЏ, payload, meta
    payload_device_id = (
        data.get("device_id") or 
        data.get("payload", {}).get("device_id") or
        data.get("payload", {}).get("uuid") or
        data.get("uuid")
    )
    
    connection_request_service = ConnectionRequestService()
    if not token:
        logger.warning("рџ”ґ РџРѕРїС‹С‚РєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Р±РµР· С‚РѕРєРµРЅР°")
        # Persist pending attempt in DB for admin visibility.
        if payload_device_id:
            await connection_request_service.record_unauthorized_attempt(
                device_id=payload_device_id,
                ip_address=request.remote,
                user_agent=request.headers.get("User-Agent", ""),
                reason="no_token",
            )
            logger.info(f"[handshake] Unauthorized attempt persisted: device_id={payload_device_id[:8]}... reason=no_token")
        await ws.close(code=4003, message=b"Token required")
        return (ws, agent_id, device_id, authenticated)
    
    # РџСЂРѕРІРµСЂСЏРµРј С‚РѕРєРµРЅ С‡РµСЂРµР· AuthService (Р‘Р”)
    token_service = AgentTokenService()
    token_info = await token_service.verify_agent_token(token)
    
    if not token_info:
        logger.warning(f"рџ”ґ РќРµРІР°Р»РёРґРЅС‹Р№ С‚РѕРєРµРЅ Р°РіРµРЅС‚Р°: {token[:8]}...")
        # Persist pending attempt with invalid token reason.
        if payload_device_id:
            await connection_request_service.record_unauthorized_attempt(
                device_id=payload_device_id,
                ip_address=request.remote,
                user_agent=request.headers.get("User-Agent", ""),
                reason="invalid_token",
            )
            logger.info(f"[handshake] Unauthorized attempt persisted: device_id={payload_device_id[:8]}... reason=invalid_token")
        await ws.close(code=4003, message=b"Invalid token")
        return (ws, agent_id, device_id, authenticated)
    
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

    return (None, agent_id, device_id, authenticated)
