"""
HTTP обработчики для работы с агентами.
"""

from aiohttp import web
from loguru import logger
import time
from .service import AgentService
from app.db import get_session
from app.repos.connection_requests_repo import ConnectionRequestsRepo


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
        
        # Get state manager for checking online status
        state = request.app['state']
        
        async with get_session() as session:
            devices_repo = DevicesRepo(session)
            device_modules_repo = DeviceModulesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)
            
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

        device_id = request.match_info["device_id"]
        state = request.app["state"]

        async with get_session() as session:
            devices_repo = DevicesRepo(session)
            device_modules_repo = DeviceModulesRepo(session)
            snapshots_repo = ToolsetSnapshotsRepo(session)

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

