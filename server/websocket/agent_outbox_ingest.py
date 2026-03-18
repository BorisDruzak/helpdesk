"""Outbox ingest handler extracted from agent websocket legacy module."""

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
from websocket.job_event_persistence import persist_job_event

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

async def handle_outbox_item(
    ws: web.WebSocketResponse,
    data: dict,
    state: Any,
    agent_id: Optional[str],
    batch_ack_manager: BatchAckManager,
    event_validator: EventValidator,
) -> bool:
    """РћР±СЂР°Р±РѕС‚РєР° outbox_item (device/ticket events, batch ACK/NACK). Р›РѕРіРёРєР° РІ Р±Р»РѕРєРµ elif msg_type == "outbox_item"."""
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
                    return True
                
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
                    return True
            
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
                        return True
                    
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
                        return True
                    
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
                                    return True
                                
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

    return False
