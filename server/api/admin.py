"""
Admin API endpoints.
"""

import asyncio
import json
import uuid
from aiohttp import web
from loguru import logger
from utils import now_iso, new_ticket_id, new_session_id
from config import ENABLE_DB_PERSISTENCE
from models import Session
from tools.service import ToolExecutionService
from websocket.protocol import WsCommandQueueFullError

try:
    from app.db import get_session
    from app.repos import TicketEventsRepo
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


async def handle_admin_run_tool(request):
    """
    HTTP API для выполнения tool: POST /api/admin/run_tool
    
    Выполняет tool (raw JSON / structured), логирует в system ticket.
    
    Request JSON:
    {
        "device_id": "...",
        "tool_name": "module.tool",
        "params": { ... },
        "mode": "in_ticket" | "system_ticket",  // default: "system_ticket"
        "ticket_id": "optional if in_ticket",
        "raw_command": { ... }   // optional, если админ шлёт полностью
    }
    
    Response:
    {
        "status": "ok",
        "ticket_id": "...",
        "call_id": "...",
        "result": { ... }
    }
    """
    try:
        state = request.app['state']
        if not _DB_AVAILABLE or not ENABLE_DB_PERSISTENCE:
            return web.json_response({
                "status": "error",
                "error": "db_required",
                "message": "Admin run_tool requires database persistence"
            }, status=503)
        
        data = await request.json()
        
        # Валидация обязательных полей
        device_id = data.get("device_id", "").strip()
        tool_name = data.get("tool_name", "").strip()
        params = data.get("params", {})
        mode = data.get("mode", "system_ticket")
        ticket_id = data.get("ticket_id")
        raw_command = data.get("raw_command")
        
        validation_errors = {}
        
        if not device_id:
            validation_errors["device_id"] = "Device ID is required"
        
        if not tool_name:
            validation_errors["tool_name"] = "Tool name is required"
        
        if mode not in ["in_ticket", "system_ticket"]:
            validation_errors["mode"] = "Mode must be 'in_ticket' or 'system_ticket'"
        
        if mode == "in_ticket" and not ticket_id:
            validation_errors["ticket_id"] = "Ticket ID is required for mode 'in_ticket'"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Проверяем, подключен ли агент
        if not state.is_agent_online(device_id):
            return web.json_response({
                "status": "error",
                "error": "agent_offline"
            }, status=503)
        
        async with get_session() as db_session:
            repo = TicketEventsRepo(db_session)
            
            # Определяем ticket context (тикеты после V3 только в БД)
            if mode == "system_ticket":
                ticket_id = new_ticket_id()
                session_id = new_session_id()
                title = f"Admin action: {tool_name}"
                params_str = json.dumps(params, ensure_ascii=False, indent=2)
                if len(params_str) > 500:
                    params_str = params_str[:500] + "..."
                description = f"Run tool {tool_name} with params:\n{params_str}"
                await repo.create_ticket(
                    ticket_id=ticket_id,
                    device_id=device_id,
                    title=title,
                    description=description,
                    status="In Progress",
                )
                state.create_session(Session(
                    session_id=session_id,
                    ticket_id=ticket_id,
                    device_id=device_id,
                    job_id=None,
                    status="open",
                    created_at=now_iso(),
                    updated_at=now_iso(),
                    last_activity_at=now_iso(),
                ))
                for ev in (
                    {"type": "ticket_created", "ticket_id": ticket_id, "session_id": session_id, "device_id": device_id, "ts": now_iso()},
                    {"type": "session_opened", "ticket_id": ticket_id, "session_id": session_id, "device_id": device_id, "ts": now_iso()},
                    {"type": "initial_message_created", "ticket_id": ticket_id, "message_id": str(uuid.uuid4()), "ts": now_iso()},
                ):
                    await repo.add_event(ticket_id, device_id, None, ev["type"], ev, trace_id=str(uuid.uuid4()))
                await db_session.commit()
                logger.info(f"[ADMIN_RUN_TOOL] Создан системный тикет: ticket_id={ticket_id}")
            else:
                ticket = await repo.get_ticket(ticket_id)
                if not ticket:
                    return web.json_response({
                        "status": "error",
                        "error": "ticket_not_found"
                    }, status=404)
                device_id = ticket.device_id  # для add_event используем device_id тикета
                logger.info(f"[ADMIN_RUN_TOOL] Используется существующий тикет: ticket_id={ticket_id}")
            
            call_id = str(uuid.uuid4())
            
            # Аудит: записываем в тикет только факт запроса (tool_call_started создаётся в ToolService.run_tool)
            await repo.add_event(
                ticket_id, device_id, None, "tool_call",
                {"kind": "agent_action", "type": "tool_call", "title": "Admin requested tool call", "tool_name": tool_name, "call_id": call_id, "ts": now_iso()},
                trace_id=str(uuid.uuid4())
            )
            await db_session.commit()
            
            auth_context = request.get("auth_context")
            tool_service = ToolExecutionService(state)
            logger.info(f"[ADMIN_RUN_TOOL] Вызов ToolService.run_tool для device_id={device_id} (tool_call_started создаётся в ToolService)")
            
            try:
                command_result = await tool_service.run_tool(
                    device_id=device_id,
                    ticket_id=ticket_id,
                    tool_name=tool_name,
                    params=params if not raw_command else raw_command,
                    call_id=call_id,
                    timeout=60,
                    auth_context=auth_context,
                )
                
                # ToolService.run_tool при успехе возвращает ответ send_ws_command (есть payload), при ошибке — dict с status/error
                payload = command_result.get("payload") or {}
                if not payload and command_result.get("status") == "error":
                    payload = {"status": "error", "error": command_result.get("error"), "data": {}}
                
                if command_result.get("error") == "timeout":
                    logger.error(f"❌ Таймаут при выполнении tool {tool_name}")
                    await repo.add_event(
                        ticket_id, device_id, None, "tool_call_result",
                        {"type": "tool_call_result", "call_id": call_id, "tool_name": tool_name, "status": "error", "summary": f"Tool {tool_name} execution timeout", "error": "timeout", "ts": now_iso()},
                        trace_id=str(uuid.uuid4())
                    )
                    await db_session.commit()
                    return web.json_response({
                        "status": "error",
                        "error": "timeout",
                        "ticket_id": ticket_id,
                        "call_id": call_id
                    }, status=504)
                
                status = payload.get("status")
                tool_result = payload.get("data", {})
                tool_status = "success" if status == "success" else "error"
                
                result_str = json.dumps(tool_result, ensure_ascii=False)
                max_result_size = 10 * 1024
                if len(result_str) > max_result_size:
                    tool_result = {
                        "truncated": True,
                        "original_size": len(result_str),
                        "preview": result_str[:max_result_size] + "..."
                    }
                    logger.warning(f"[ADMIN_RUN_TOOL] Результат tool усечён: {len(result_str)} -> {max_result_size} bytes")
                
                if status == "success":
                    summary = f"Tool {tool_name} executed successfully"
                else:
                    error_info = payload.get("error")
                    if error_info and isinstance(error_info, dict):
                        summary = f"Tool {tool_name} failed: {error_info.get('message', 'unknown error')}"
                    else:
                        summary = f"Tool {tool_name} failed: unknown error"
                
                await repo.add_event(
                    ticket_id, device_id, None, "tool_call_result",
                    {"type": "tool_call_result", "call_id": call_id, "tool_name": tool_name, "status": tool_status, "summary": summary, "result": tool_result, "ts": now_iso()},
                    trace_id=str(uuid.uuid4())
                )
                await db_session.commit()
                logger.success(f"✅ Tool {tool_name} выполнен: status={tool_status}")
                return web.json_response({
                    "status": "ok",
                    "ticket_id": ticket_id,
                    "call_id": call_id,
                    "result": tool_result,
                    "tool_status": tool_status
                })
            
            except WsCommandQueueFullError as e:
                return web.json_response({
                    "status": "error",
                    "error": "WS command queue full",
                    "error_code": getattr(e, "error_code", "WS_COMMAND_QUEUE_FULL"),
                }, status=429)
            
            except asyncio.TimeoutError:
                logger.error(f"❌ Таймаут при выполнении tool {tool_name}")
                await repo.add_event(
                    ticket_id, device_id, None, "tool_call_result",
                    {"type": "tool_call_result", "call_id": call_id, "tool_name": tool_name, "status": "error", "summary": f"Tool {tool_name} execution timeout", "error": "timeout", "ts": now_iso()},
                    trace_id=str(uuid.uuid4())
                )
                await db_session.commit()
                return web.json_response({
                    "status": "error",
                    "error": "timeout",
                    "ticket_id": ticket_id,
                    "call_id": call_id
                }, status=504)
            
            except Exception as e:
                logger.error(f"❌ Исключение при выполнении tool {tool_name}: {e}")
                logger.exception(e)
                await repo.add_event(
                    ticket_id, device_id, None, "tool_call_result",
                    {"type": "tool_call_result", "call_id": call_id, "tool_name": tool_name, "status": "error", "summary": f"Tool {tool_name} execution error", "error": str(e), "ts": now_iso()},
                    trace_id=str(uuid.uuid4())
                )
                await db_session.commit()
                return web.json_response({
                    "status": "error",
                    "error": str(e),
                    "ticket_id": ticket_id,
                    "call_id": call_id
                }, status=500)
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка обработки запроса POST /api/admin/run_tool: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

