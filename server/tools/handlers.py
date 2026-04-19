"""
HTTP обработчики для работы с инструментами.
"""

import json
import asyncio
from aiohttp import web
from loguru import logger
from .service import ToolExecutionService
from utils import new_call_id, now_iso
from auth.context import AuthContext
from websocket.protocol import WsCommandQueueFullError
from core.policy_engine import PolicyEngine
from core.tool_metadata import ToolMetadata


def _tool_error_status_code(result: dict) -> int:
    error_code = str(result.get("error_code") or "").strip().upper()
    if error_code == "WS_COMMAND_QUEUE_FULL":
        return 429
    if error_code == "AUTH_REQUIRED":
        return 401
    if error_code == "AGENT_NOT_CONNECTED":
        return 503
    if error_code in {"TIMEOUT", "MODULE_INSTALL_TIMEOUT"}:
        return 504
    if error_code == "DEVICE_NOT_FOUND":
        return 404
    if error_code in {
        "MODULE_NOT_ON_SERVER",
        "MODULE_TOOL_OWNER_CONFLICT",
        "MODULE_PLATFORM_MISMATCH",
        "AGENT_VERSION_TOO_OLD",
        "AGENT_VERSION_UNKNOWN",
        "DEVICE_OS_UNKNOWN",
    }:
        return 409
    return 500


def _tool_error_response(
    result: dict,
    *,
    operation_id: str,
    poll_url: str,
    ticket_id: str,
    device_id: str,
) -> web.Response:
    resolved_operation_id = result.get("operation_id") or operation_id
    payload = {
        "status": "error",
        "error": result.get("error") or "Tool dispatch failed",
        "error_code": result.get("error_code") or "TOOL_DISPATCH_FAILED",
        "operation_id": resolved_operation_id,
        "ticket_id": ticket_id,
        "device_id": device_id,
    }
    trace_id = result.get("trace_id")
    if trace_id:
        payload["trace_id"] = trace_id
    if resolved_operation_id:
        payload["poll_url"] = poll_url
    return web.json_response(payload, status=_tool_error_status_code(result))


async def handle_get_tools(request):
    """
    HTTP API для получения списка tools: GET /api/tools
    
    Query параметры:
        device_id: ID устройства
    """
    try:
        device_id = request.query.get("device_id")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "device_id is required"
            }, status=400)
        
        state = request.app['state']
        tool_service = ToolExecutionService(state)
        
        tools = await tool_service.get_tools_list(device_id)
        # При офлайн-агенте или отсутствии snapshot возвращаем пустой список,
        # а не 500 — панель откроется с инструментами «с установкой» с сервера
        if tools is None:
            tools = []
        
        tools_from_server = await tool_service.get_tools_from_server(device_id)
        
        return web.json_response({
            "status": "ok",
            "tools": tools,
            "tools_from_server": tools_from_server,
            "count": len(tools),
            "count_from_server": len(tools_from_server),
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения tools: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_tools_run(request):
    """
    HTTP API для запуска tool из интерфейса тикета: POST /api/tools/run
    
    Request JSON:
    {
        "device_id": "string",
        "ticket_id": "string",
        "tool_name": "string",
        "preset_id": "string" (optional),
        "params": {} (optional)
    }
    
    Query параметры:
        wait: "1" для синхронного режима (dev mode, по умолчанию async)
    """
    try:
        # КРИТИЧНО: Получаем actor_role из AuthContext, не из JSON body
        auth_context: AuthContext = request.get('auth_context')
        if not auth_context:
            return web.json_response({
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED"
            }, status=401)
        
        data = await request.json()
        
        # КРИТИЧНО: Игнорируем actor_role из JSON body с warning
        if "actor_role" in data:
            logger.warning(
                f"[handle_tools_run] actor_role in JSON body ignored: "
                f"using actor_role={auth_context.actor_role} from AuthContext"
            )
            data.pop("actor_role", None)
        
        device_id = data.get("device_id", "").strip()
        ticket_id = data.get("ticket_id", "").strip()
        tool_name = data.get("tool_name", "").strip()
        preset_id = data.get("preset_id")
        params = data.get("params", {})
        
        # Валидация
        validation_errors = {}
        
        if not device_id:
            validation_errors["device_id"] = "Device ID is required"
        
        if not ticket_id:
            validation_errors["ticket_id"] = "Ticket ID is required"
        
        if not tool_name:
            validation_errors["tool_name"] = "Tool name is required"
        
        if validation_errors:
            return web.json_response({
                "status": "error",
                "error": "validation_error",
                "details": validation_errors
            }, status=400)
        
        # Check ?wait=1 parameter
        wait_mode = request.query.get("wait", "0") == "1"
        
        state = request.app['state']
        tool_service = ToolExecutionService(state)
        
        # Phase 4: Policy check ПЕРЕД созданием operation
        # Получаем tools list для получения metadata
        tools_list = await tool_service.get_tools_list(device_id)
        
        # Создаем PolicyEngine
        from config import ALLOW_REMOTE_CODE
        policy_engine = PolicyEngine(config={"allow_remote_code": ALLOW_REMOTE_CODE})
        
        # Получаем metadata для tool
        tool_metadata = policy_engine.get_tool_metadata(tool_name, tools_list)
        if not tool_metadata:
            tools_from_server = await tool_service.get_tools_from_server(device_id)
            tool_metadata = policy_engine.get_tool_metadata(tool_name, tools_from_server)
            if tool_metadata:
                logger.info(
                    f"[handle_tools_run] Using server registry metadata for {tool_name} "
                    f"(device snapshot missing/stale)"
                )
        
        # Если metadata не найдена: для screen.collect/screen.record — разрешаем user/agent
        # (запрос из GUI агента часто идёт с токеном устройства → actor_role=agent, snapshot может быть пуст)
        if not tool_metadata:
            if tool_name in ("screen.collect", "screen.record"):
                tool_metadata = ToolMetadata(
                    risk_level="sensitive_read",
                    allow_roles=["user", "agent", "llm", "support", "admin"],
                    requires_consent=False,
                )
                logger.debug(
                    f"[handle_tools_run] Tool {tool_name} not in list, using screen fallback (allow user/agent)"
                )
            else:
                logger.warning(
                    f"[handle_tools_run] Tool metadata not found for {tool_name}, "
                    f"using default (safe_read)"
                )
                tool_metadata = ToolMetadata(risk_level="safe_read")
        
        # Проверяем policy
        policy_decision = policy_engine.check_policy(
            actor_role=auth_context.actor_role,
            tool_name=tool_name,
            metadata=tool_metadata,
            params=params
        )
        
        # Если policy запрещает → 403, операция не создается
        if not policy_decision.allow:
            logger.warning(
                f"[handle_tools_run] Policy violation: tool={tool_name} "
                f"actor_role={auth_context.actor_role!r} reason={policy_decision.reason} "
                f"required_role={policy_decision.required_role!r}"
            )
            return web.json_response({
                "status": "error",
                "error": "Policy violation",
                "error_code": policy_decision.reason,
                "required_role": policy_decision.required_role,
                "actor_role": auth_context.actor_role,
            }, status=403)
        
        # Генерируем call_id и operation_id
        call_id = new_call_id()
        import uuid
        operation_id = str(uuid.uuid4())
        poll_url = f"/api/operations/{operation_id}"
        
        # Если указан preset_id, то params должны быть пустыми
        # (агент сам определит параметры пресета)
        if preset_id:
            params = {"preset_id": preset_id}
        
        # Phase 4: Если policy требует consent → создание operation со статусом waiting_consent
        # КРИТИЧНО: Операция создается, но не enqueued до approve
        if policy_decision.requires_consent:
            logger.info(
                f"[handle_tools_run] Tool requires consent: tool={tool_name} "
                f"actor_role={auth_context.actor_role} operation_id={operation_id}"
            )
            
            # Создаем operation со статусом waiting_consent
            from app.db import get_session
            from app.services.operation_service import OperationService
            
            async with get_session() as session:
                ui_publisher = state.ui_publisher if hasattr(state, 'ui_publisher') else None
                op_service = OperationService(session, publisher=ui_publisher)
                
                operation = await op_service.enqueue_operation(
                    operation_id=operation_id,
                    device_id=device_id,
                    kind="tool_call",
                    tool_name=tool_name,
                    ticket_id=ticket_id,
                    job_id=None,
                    actor_role=auth_context.actor_role,
                    trace_id=str(uuid.uuid4()),
                    initial_status="waiting_consent"  # КРИТИЧНО: статус waiting_consent
                )
                
                await session.commit()
            
            # Возвращаем operation_id, но не запускаем tool
            return web.json_response({
                "status": "waiting_consent",
                "operation_id": operation_id,
                "poll_url": poll_url,
                "ticket_id": ticket_id,
                "device_id": device_id,
                "message": "Operation requires consent approval"
            }, status=202)
        
        # Запускаем tool (передаем operation_id через params для использования в send_ws_command)
        params_with_operation = params.copy()
        params_with_operation["_operation_id"] = operation_id  # Внутренний параметр
        
        if wait_mode:
            # Dev-only: synchronous wait
            result = await tool_service.run_tool(
                device_id=device_id,
                ticket_id=ticket_id,
                tool_name=tool_name,
                params=params_with_operation,
                call_id=call_id,
                auth_context=auth_context  # Передаем AuthContext
            )
            
            if result.get("status") == "error":
                return _tool_error_response(
                    result,
                    operation_id=operation_id,
                    poll_url=poll_url,
                    ticket_id=ticket_id,
                    device_id=device_id,
                )

            payload = result.get("payload", {})
            tool_status = payload.get("status", "error")
            tool_result = payload.get("data", {})
            
            return web.json_response({
                "status": "ok",
                "operation_id": operation_id,
                "ticket_id": ticket_id,
                "result": tool_result,
                "tool_status": tool_status
            })
        else:
            # Production: async mode - только enqueue, без ожидания command_result.
            # Это снижает количество долгоживущих корутин под высокой нагрузкой.
            result = await tool_service.run_tool(
                device_id=device_id,
                ticket_id=ticket_id,
                tool_name=tool_name,
                params=params_with_operation,
                call_id=call_id,
                auth_context=auth_context,  # Передаем AuthContext
                wait_for_result=False,
            )
            if result.get("status") != "accepted":
                return _tool_error_response(
                    result,
                    operation_id=operation_id,
                    poll_url=poll_url,
                    ticket_id=ticket_id,
                    device_id=device_id,
                )

            return web.json_response({
                "status": "accepted",
                "operation_id": result.get("operation_id") or operation_id,
                "poll_url": poll_url,
                "ticket_id": ticket_id,
                "device_id": device_id,
                "trace_id": result.get("trace_id"),
            }, status=202)
    
    except asyncio.TimeoutError:
        logger.error(f"❌ Таймаут выполнения tool")
        return web.json_response({
            "status": "error",
            "error": "timeout"
        }, status=504)
    
    except WsCommandQueueFullError as e:
        return web.json_response({
            "status": "error",
            "error": "WS command queue full",
            "error_code": getattr(e, "error_code", "WS_COMMAND_QUEUE_FULL"),
        }, status=429)
    
    except json.JSONDecodeError:
        return web.json_response({
            "status": "error",
            "error": "Invalid JSON"
        }, status=400)
    
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения tool: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)
