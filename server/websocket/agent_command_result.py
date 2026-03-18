"""Command-result handler extracted from agent websocket legacy module."""

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

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

from websocket.job_event_persistence import persist_job_event

async def handle_command_result(
    ws: web.WebSocketResponse,
    data: dict,
    state: Any,
    agent_id: Optional[str],
) -> None:
    """РћР±СЂР°Р±РѕС‚РєР° command_result (lifecycle, operations, pending_command_futures). Р›РѕРіРёРєР° РІ Р±Р»РѕРєРµ elif msg_type == "command_result"."""
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



