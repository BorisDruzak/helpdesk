"""
HTTP handlers for agents/devices read API.
"""

from datetime import datetime, timezone
from aiohttp import web
from loguru import logger
import time
from .service import AgentService
from app.db import get_session
from app.repos.connection_requests_repo import ConnectionRequestsRepo


def _serialize_provisioning_state(
    *,
    token_info: dict,
    latest_request_status: str | None,
    latest_request_at: datetime | None,
) -> dict:
    active = token_info.get("active_count", 0) > 0
    revoked = token_info.get("total_count", 0) > 0 and not active
    has_request = latest_request_status in {"pending", "approved", "rejected"}

    if active:
        provisioning_state = "active"
    elif has_request and latest_request_status == "pending":
        provisioning_state = "unprovisioned"
    elif revoked:
        provisioning_state = "token_revoked"
    else:
        provisioning_state = "reprovision_required"

    return {
        "provisioning_state": provisioning_state,
        "token_status": "active" if active else ("revoked" if revoked else "missing"),
        "reprovision_required": not active,
        "last_connection_request_status": latest_request_status,
        "last_connection_request_at": latest_request_at.isoformat() if latest_request_at else None,
        "token_issued_at": token_info.get("token_issued_at"),
        "token_last_used_at": token_info.get("token_last_used_at"),
        "token_revoked_at": token_info.get("token_revoked_at"),
    }


def _serialize_update_summary(
    *,
    device_metadata: dict,
    recent_update_operation: dict | None,
) -> dict:
    op = recent_update_operation or {}
    return {
        "applied_update_version": device_metadata.get("applied_update_version"),
        "last_update_operation_id": device_metadata.get("last_update_operation_id"),
        "rollout_health": op.get("status"),
        "last_update_operation_status": op.get("status"),
        "last_update_error_code": op.get("error_code"),
        "last_update_error_message": op.get("error_message"),
        "last_update_result_summary": op.get("result_summary"),
        "last_update_finished_at": op.get("finished_at"),
    }


async def handle_get_agents(request):
    """
    API эндпоинт для получения списка подключённых агентов: GET /api/agents
    
    Возвращает информацию обо всех активных агентах, включая:
    - device_id, версию агента, список модулей
    - статус, uptime, время последней активности
    """
    try:
        state = request.app['state']
        agent_service = AgentService(state)
        
        agents_list = agent_service.get_agents_list()
        
        return web.json_response({
            "status": "ok",
            "agents": agents_list,
            "count": len(agents_list)
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка агентов: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_pending_connections(request):
    """
    API эндпоинт для получения списка попыток подключения: GET /api/pending_connections
    
    Возвращает список агентов, которые пытались подключиться без токена или с невалидным токеном.
    """
    try:
        async with get_session() as session:
            repo = ConnectionRequestsRepo(session)
            pending_rows = await repo.list_pending(only_active=True)

        pending_list = []
        now_ts = time.time()
        for row in pending_rows:
            metadata = row.request_metadata if isinstance(row.request_metadata, dict) else {}
            attempted_ts = row.last_request_at.timestamp() if row.last_request_at else row.created_at.timestamp()
            pending_list.append(
                {
                    "device_id": row.device_id,
                    "attempted_at": attempted_ts,
                    "ip_address": row.ip_address or "",
                    "user_agent": metadata.get("user_agent", ""),
                    "reason": metadata.get("reason", "pending"),
                    "age_seconds": round(now_ts - attempted_ts, 2),
                }
            )
        
        return web.json_response({
            "status": "ok",
            "pending_connections": pending_list,
            "count": len(pending_list)
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка попыток подключения: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_devices(request):
    """
    GET /api/devices
    
    Returns summary of all devices with modules info and online status.
    """
    try:
        from app.db import get_session
        from app.repos import DevicesRepo, DeviceModulesRepo, ToolsetSnapshotsRepo
        from app.repos.auth_tokens_repo import AuthTokensRepo
        from app.repos.operations_repo import OperationsRepo
        
        # Get state manager for checking online status
        state = request.app['state']
        
        async with get_session() as session:
            devices_repo = DevicesRepo(session)
            device_modules_repo = DeviceModulesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)
            auth_tokens_repo = AuthTokensRepo(session)
            connection_requests_repo = ConnectionRequestsRepo(session)
            operations_repo = OperationsRepo(session)
            
            # Get all devices from DB
            all_devices = await devices_repo.list_all()
            
            devices_summary = []
            for device in all_devices:
                # Get active modules count
                active_modules = await device_modules_repo.get_active_modules(device.device_id)
                
                # Get latest snapshot
                latest_snapshot = await snapshots_repo.get_latest_snapshot(device.device_id)
                
                # КРИТИЧНО: tool_count берется из snapshot.tool_count (поле в модели)
                # Если snapshot отсутствует, вычисляем из toolset_json["tools"]
                tools_count = 0
                if latest_snapshot:
                    tools_count = latest_snapshot.tool_count
                    # Fallback: вычисляем из JSON если поле отсутствует или равно 0
                    if tools_count == 0 and latest_snapshot.toolset_json:
                        tools_list = latest_snapshot.toolset_json.get("tools", [])
                        tools_count = len(tools_list)
                
                # КРИТИЧНО: Проверяем статус подключения через WebSocket
                # Метод is_agent_online теперь выполняет полную проверку:
                # 1. Наличие в connected_agents
                # 2. Состояние WebSocket соединения
                # 3. Статус в метаданных
                is_online = state.is_agent_online(device.device_id)
                
                # Модули из device_metadata (handshake)
                modules_list = []
                if device.device_metadata and isinstance(device.device_metadata, dict):
                    modules_list = device.device_metadata.get("modules") or []

                device_meta = device.device_metadata if isinstance(device.device_metadata, dict) else {}

                tokens = await auth_tokens_repo.get_agent_tokens_by_device(device.device_id)
                now = datetime.now(timezone.utc)
                token_rows = list(tokens or [])
                active_tokens = [
                    t for t in token_rows
                    if t.revoked_at is None and (t.expires_at is None or t.expires_at > now)
                ]
                latest_token = max(token_rows, key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc), default=None)
                token_info = {
                    "total_count": len(token_rows),
                    "active_count": len(active_tokens),
                    "token_issued_at": latest_token.created_at.isoformat() if latest_token and latest_token.created_at else None,
                    "token_last_used_at": latest_token.last_used_at.isoformat() if latest_token and latest_token.last_used_at else None,
                    "token_revoked_at": latest_token.revoked_at.isoformat() if latest_token and latest_token.revoked_at else None,
                }

                latest_request = await connection_requests_repo.get_latest_by_device_id(device.device_id)
                latest_request_status = latest_request.status if latest_request else None
                latest_request_at = (latest_request.last_request_at if latest_request else None) or (latest_request.created_at if latest_request else None)

                recent_updates = await operations_repo.get_recent_operations(
                    device_id=device.device_id,
                    kinds=["agent_update"],
                    limit=1,
                )
                update_op = recent_updates[0] if recent_updates else None
                update_summary = _serialize_update_summary(
                    device_metadata=device_meta,
                    recent_update_operation={
                        "status": getattr(update_op, "status", None),
                        "error_code": getattr(update_op, "error_code", None),
                        "error_message": getattr(update_op, "error_message", None),
                        "result_summary": getattr(update_op, "result_summary", None),
                        "finished_at": update_op.finished_at.isoformat() if update_op and update_op.finished_at else None,
                    } if update_op else None,
                )
                provisioning_summary = _serialize_provisioning_state(
                    token_info=token_info,
                    latest_request_status=latest_request_status,
                    latest_request_at=latest_request_at,
                )

                devices_summary.append({
                    "device_id": device.device_id,
                    "hostname": device.hostname,
                    "agent_version": device.agent_version,
                    "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
                    "first_seen_at": device.first_seen_at.isoformat() if device.first_seen_at else None,
                    "last_handshake_at": device.last_handshake_at.isoformat() if device.last_handshake_at else None,
                    "protocol_version": device.protocol_version,
                    "os": device.os,
                    "tools_version": device.tools_version,
                    "toolset_hash": device.current_toolset_hash,
                    "tools_count": tools_count,
                    "active_modules_count": len(active_modules),
                    "last_tools_changed_at": device.last_tools_changed_at.isoformat() if device.last_tools_changed_at else None,
                    "online": is_online,
                    "capabilities": device.capabilities if isinstance(device.capabilities, (list, dict)) else [],
                    "modules": modules_list,
                    "provisioning_summary": provisioning_summary,
                    "update_summary": update_summary,
                })
            
            return web.json_response({
                "status": "ok",
                "devices": devices_summary,
                "count": len(devices_summary)
            })
    
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка устройств: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_get_device(request):
    """
    GET /api/devices/{device_id}

    Возвращает полную информацию об устройстве из БД (для страницы агента).
    """
    try:
        from app.db import get_session
        from app.repos import DevicesRepo, DeviceModulesRepo, ToolsetSnapshotsRepo
        from app.repos.auth_tokens_repo import AuthTokensRepo
        from app.repos.operations_repo import OperationsRepo

        device_id = request.match_info["device_id"]
        state = request.app["state"]

        async with get_session() as session:
            devices_repo = DevicesRepo(session)
            device_modules_repo = DeviceModulesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)
            auth_tokens_repo = AuthTokensRepo(session)
            connection_requests_repo = ConnectionRequestsRepo(session)
            operations_repo = OperationsRepo(session)

            device = await devices_repo.get_by_device_id(device_id)
            if not device:
                return web.json_response({
                    "status": "error",
                    "error": "Устройство не найдено"
                }, status=404)

            active_modules = await device_modules_repo.get_active_modules(device_id)
            latest_snapshot = await snapshots_repo.get_latest_snapshot(device_id)
            tools_count = 0
            if latest_snapshot:
                tools_count = latest_snapshot.tool_count or 0
                if tools_count == 0 and latest_snapshot.toolset_json:
                    tools_count = len(latest_snapshot.toolset_json.get("tools", []))

            modules_list = []
            if device.device_metadata and isinstance(device.device_metadata, dict):
                modules_list = device.device_metadata.get("modules") or []

            is_online = state.is_agent_online(device_id)

            device_meta = device.device_metadata if isinstance(device.device_metadata, dict) else {}
            tokens = await auth_tokens_repo.get_agent_tokens_by_device(device_id)
            now = datetime.now(timezone.utc)
            token_rows = list(tokens or [])
            active_tokens = [
                t for t in token_rows
                if t.revoked_at is None and (t.expires_at is None or t.expires_at > now)
            ]
            latest_token = max(token_rows, key=lambda t: t.created_at or datetime.min.replace(tzinfo=timezone.utc), default=None)
            token_info = {
                "total_count": len(token_rows),
                "active_count": len(active_tokens),
                "token_issued_at": latest_token.created_at.isoformat() if latest_token and latest_token.created_at else None,
                "token_last_used_at": latest_token.last_used_at.isoformat() if latest_token and latest_token.last_used_at else None,
                "token_revoked_at": latest_token.revoked_at.isoformat() if latest_token and latest_token.revoked_at else None,
            }
            latest_request = await connection_requests_repo.get_latest_by_device_id(device_id)
            latest_request_status = latest_request.status if latest_request else None
            latest_request_at = (latest_request.last_request_at if latest_request else None) or (latest_request.created_at if latest_request else None)

            recent_updates = await operations_repo.get_recent_operations(
                device_id=device_id,
                kinds=["agent_update"],
                limit=1,
            )
            update_op = recent_updates[0] if recent_updates else None
            provisioning_summary = _serialize_provisioning_state(
                token_info=token_info,
                latest_request_status=latest_request_status,
                latest_request_at=latest_request_at,
            )
            update_summary = _serialize_update_summary(
                device_metadata=device_meta,
                recent_update_operation={
                    "status": getattr(update_op, "status", None),
                    "error_code": getattr(update_op, "error_code", None),
                    "error_message": getattr(update_op, "error_message", None),
                    "result_summary": getattr(update_op, "result_summary", None),
                    "finished_at": update_op.finished_at.isoformat() if update_op and update_op.finished_at else None,
                } if update_op else None,
            )
            return web.json_response({
                "status": "ok",
                "device": {
                    "device_id": device.device_id,
                    "hostname": device.hostname,
                    "agent_version": device.agent_version,
                    "protocol_version": device.protocol_version,
                    "os": device.os,
                    "tools_version": device.tools_version,
                    "capabilities": device.capabilities if isinstance(device.capabilities, (list, dict)) else [],
                    "modules": modules_list,
                    "first_seen_at": device.first_seen_at.isoformat() if device.first_seen_at else None,
                    "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
                    "last_handshake_at": device.last_handshake_at.isoformat() if device.last_handshake_at else None,
                    "last_toolset_refresh_at": device.last_toolset_refresh_at.isoformat() if device.last_toolset_refresh_at else None,
                    "last_tools_changed_at": device.last_tools_changed_at.isoformat() if device.last_tools_changed_at else None,
                    "toolset_hash": device.current_toolset_hash,
                    "tools_count": tools_count,
                    "active_modules_count": len(active_modules),
                    "online": is_online,
                    "applied_update_version": device_meta.get("applied_update_version"),
                    "last_update_operation_id": device_meta.get("last_update_operation_id"),
                    "provisioning_summary": provisioning_summary,
                    "update_summary": update_summary,
                }
            })
    except Exception as e:
        logger.error(f"❌ Ошибка получения устройства: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_device_check(request):
    """
    POST /api/devices/{device_id}/check

    Принудительная проверка устройства по протоколу: ставит в очередь команду list_tools,
    агент выполняет и сервер обновляет снапшот и данные устройства.
    Агент должен быть онлайн.
    """
    try:
        from websocket.protocol import enqueue_command_async

        device_id = request.match_info["device_id"]
        state = request.app["state"]

        if not state.is_agent_online(device_id):
            return web.json_response({
                "status": "error",
                "error": "Устройство не в сети. Подключите агент для проверки."
            }, status=404)

        command_id = await enqueue_command_async(
            state=state,
            device_id=device_id,
            command="list_tools",
            params={},
            actor_role="admin",
            require_online=True,
        )

        return web.json_response({
            "status": "ok",
            "message": "Запрос проверки отправлен. Данные обновятся после ответа агента.",
            "operation_id": command_id,
        })
    except ValueError as e:
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=404)
    except Exception as e:
        logger.error(f"❌ Ошибка проверки устройства: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_delete_device(request):
    """
    DELETE /api/devices/{device_id}

    Удаляет устройство из БД и все связанные данные (токены, outbox, операции,
    модули, конфиг, снапшоты). Тикеты не удаляются (device_id может остаться в них).
    """
    try:
        from app.db import get_session
        from app.repos import DevicesRepo

        device_id = request.match_info["device_id"]

        async with get_session() as session:
            devices_repo = DevicesRepo(session)
            deleted = await devices_repo.delete_device(device_id)
            await session.commit()

        if not deleted:
            return web.json_response({
                "status": "error",
                "error": "Устройство не найдено"
            }, status=404)

        return web.json_response({
            "status": "ok",
            "message": "Устройство удалено из БД"
        })
    except Exception as e:
        logger.error(f"❌ Ошибка удаления устройства: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

