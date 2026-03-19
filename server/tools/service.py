"""
Сервис управления инструментами.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from loguru import logger
from .cache import ToolsCache
from utils.module_manifest import get_module_manifest
from config import (
    TOOL_EXECUTION_TIMEOUT,
    ENABLE_DB_PERSISTENCE,
    SERVER_PUBLIC_BASE_URL,
    AGENT_BUILTIN_MODULES,
)

# Lazy import для избежания circular dependency
DB_AVAILABLE = False
try:
    from app.db.engine import get_session
    from app.repos.ticket_events_repo import TicketEventsRepo
    DB_AVAILABLE = True
except ImportError:
    pass

# Таймаут ожидания установки модуля при auto-install перед run_tool (секунды)
MODULE_INSTALL_TIMEOUT = 90


class ToolService:
    """Сервис для работы с инструментами."""
    
    def __init__(self, state_manager):
        self.state = state_manager
        self.cache = ToolsCache(state_manager)
    
    async def get_tools_list(self, device_id: str) -> Optional[List[Dict]]:
        """
        Получает список инструментов от агента.
        
        КРИТИЧНО: Использует device_toolset_snapshots как источник истины.
        Это работает даже после перезагрузки сервера, когда кеш пуст.
        
        Args:
            device_id: ID устройства
        
        Returns:
            Список инструментов или None
        """
        # КРИТИЧНО: Сначала пытаемся получить из toolset snapshot (БД)
        # Это работает даже после перезагрузки сервера
        if DB_AVAILABLE:
            try:
                from app.repos import ToolsetSnapshotsRepo
                
                async with get_session() as session:
                    repo = ToolsetSnapshotsRepo(session)
                    snapshot = await repo.get_latest_snapshot(device_id)
                    
                    if snapshot and snapshot.toolset_json:
                        tools = snapshot.toolset_json.get("tools", [])
                        if tools:
                            logger.debug(
                                f"📦 Получены tools из snapshot для {device_id}: "
                                f"{len(tools)} tools (snapshot_id={snapshot.snapshot_id})"
                            )
                            # Кешируем результат для последующих запросов
                            self.cache.set({
                                "device_id": device_id,
                                "tools": tools
                            })
                            return tools
            except Exception as e:
                logger.debug(f"Не удалось получить tools из snapshot: {e}")
        
        # Если snapshot нет, проверяем кеш
        cached = self.cache.get()
        if cached and cached.get("device_id") == device_id:
            logger.debug(f"📦 Возвращаем tools из кеша для {device_id}")
            return cached.get("tools")
        
        # Проверяем, что агент online
        if not self.state.is_agent_online(device_id):
            logger.warning(f"⚠️  Агент {device_id} не подключен")
            return None
        
        # Запрашиваем tools у агента через WebSocket
        try:
            from websocket.protocol import send_ws_command
            
            result = await send_ws_command(
                state=self.state,
                device_id=device_id,
                command="list_tools",
                params={},
                actor_role="support",  # System-initiated, no auth_context
                timeout=45  # Согласовано с OPERATION_SLA для kind=command (снижение доли timeout в метриках)
            )
            
            payload = result.get("payload", {})
            if payload.get("status") == "success":
                # Инструменты находятся в data.observations.tools
                data = payload.get("data", {})
                observations = data.get("observations", {})
                tools = observations.get("tools", [])
                
                # Сохраняем в кеш
                self.cache.set({
                    "device_id": device_id,
                    "tools": tools
                })
                
                return tools
            else:
                logger.error(f"❌ Ошибка получения tools: {payload.get('error')}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Ошибка запроса tools: {e}")
            return None
    
    async def get_tools_from_server(
        self,
        device_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Возвращает список инструментов из реестра модулей сервера (таблица modules).
        Каждый инструмент помечен как доступный «с установкой» (сервер установит при run_tool).
        По одному инструменту на (module_name, tool_name) — берётся последняя версия модуля.
        """
        if not DB_AVAILABLE:
            return []
        try:
            from app.repos import ModulesRepo
        except ImportError:
            return []
        result: List[Dict] = []
        seen_tool_names: set = set()
        async with get_session() as session:
            repo = ModulesRepo(session)
            modules = await repo.list_modules(limit=500)
            by_module: Dict[str, object] = {}
            for m in modules:
                if m.module_name not in by_module:
                    by_module[m.module_name] = m
            for m in by_module.values():
                manifest = get_module_manifest(m)
                tools = manifest.get("tools") or []
                # Если в manifest нет списка tools (например, модуль залит через upload без tools в manifest),
                # показываем один инструмент на модуль: module_name.run
                if not tools:
                    tools = [{
                        "tool": f"{m.module_name}.run",
                        "description": manifest.get("description") or f"Инструмент модуля {m.module_name}",
                        "params_schema": {},
                        "presets": [],
                        "metadata": {"origin": "managed"},
                    }]
                for t in tools:
                    name = t.get("tool") or t.get("name") or f"{m.module_name}.run"
                    if name in seen_tool_names:
                        continue
                    seen_tool_names.add(name)
                    metadata = t.get("metadata") or {}
                    entry = {
                        "tool": name,
                        "name": name,
                        "module": m.module_name,
                        "description": t.get("description") or "",
                        "spec": {
                            "params_schema": t.get("params_schema") or {},
                            "presets": t.get("presets") or [],
                            "risk_level": (metadata.get("risk_level") or "safe_readonly"),
                        },
                        "metadata": metadata,
                        "install_required": True,
                    }
                    result.append(entry)
        return result
    
    async def _ensure_module_installed(
        self,
        device_id: str,
        tool_name: str,
        auth_context: Optional[object] = None,
    ) -> Optional[Dict]:
        """
        Если tool_name — модульный инструмент (формат module.tool), ищет модуль на сервере (modules)
        и всегда запускает установку на агент (install_module_package), затем возвращает None.
        Агент идемпотентно обрабатывает «уже установлен»; так избегаем TOOL_NOT_FOUND из-за
        устаревшего device_modules (например после перезапуска агента).
        При ошибке (модуль не на сервере, ошибка установки) возвращает dict с status/error.
        Для встроенных инструментов (без точки в имени) сразу возвращает None.
        """
        if "." not in tool_name:
            return None
        module_name = tool_name.split(".", 1)[0]
        if module_name.lower() in AGENT_BUILTIN_MODULES:
            logger.debug(
                f"[ensure_module] {tool_name!r} belongs to builtin module {module_name!r}, "
                f"skip auto-install"
            )
            return None
        if not DB_AVAILABLE:
            return None
        # Если инструмент уже зарегистрирован в toolset snapshot агента — не переустанавливать.
        # Переустановка триггерит _rebuild_registry_from_active_modules, что может сломать registry.
        try:
            from app.repos import ToolsetSnapshotsRepo
            async with get_session() as session_snap:
                snap_repo = ToolsetSnapshotsRepo(session_snap)
                snapshot = await snap_repo.get_latest_snapshot(device_id)
                if snapshot and snapshot.toolset_json:
                    known_tools = [t.get("tool") or t.get("name") for t in snapshot.toolset_json.get("tools", [])]
                    if tool_name in known_tools:
                        logger.debug(f"[ensure_module] {tool_name!r} уже в toolset snapshot, пропускаем установку")
                        return None
        except Exception as snap_e:
            logger.debug(f"[ensure_module] Не удалось проверить snapshot: {snap_e}")
        try:
            from app.repos import ModulesRepo
            from app.repos.devices_repo import DevicesRepo
        except ImportError:
            return None
        async with get_session() as session:
            modules_repo = ModulesRepo(session)
            server_modules = await modules_repo.list_modules(module_name=module_name, limit=1)
            if not server_modules:
                logger.warning(f"[ensure_module] Модуль {module_name!r} не найден на сервере")
                return {
                    "status": "error",
                    "error": f"Модуль {module_name!r} не установлен на агенте и не найден на сервере. Загрузите модуль на сервер или установите его вручную.",
                    "error_code": "MODULE_NOT_ON_SERVER",
                }
            module = server_modules[0]
            version = module.version
            manifest = get_module_manifest(module)
            mod_platforms = manifest.get("platforms") or ["any"]
            if isinstance(mod_platforms, list) and len(mod_platforms) > 0 and "any" not in [str(p).lower() for p in mod_platforms]:
                devices_repo = DevicesRepo(session)
                device = await devices_repo.get_by_device_id(device_id)
                if not device:
                    return {"status": "error", "error": f"Устройство {device_id} не найдено", "error_code": "DEVICE_NOT_FOUND"}
                device_os = (device.os or "").strip()
                if not device_os:
                    return {
                        "status": "error",
                        "error": "ОС устройства неизвестна, нельзя проверить совместимость модуля. Подключите агент для обновления сведений.",
                        "error_code": "DEVICE_OS_UNKNOWN",
                    }
                os_norm = device_os.lower()
                if os_norm == "windows":
                    os_norm = "win32"
                elif os_norm not in ("linux", "darwin"):
                    os_norm = os_norm.replace(" ", "")
                allowed = [str(p).lower() for p in mod_platforms]
                if os_norm not in allowed:
                    return {
                        "status": "error",
                        "error": f"Модуль не поддерживается на ОС устройства: device os={device_os!r}, модуль: {allowed}",
                        "error_code": "MODULE_PLATFORM_MISMATCH",
                    }
            download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{module_name}/{version}/download"
            params_install = {
                "module_name": module_name,
                "module_version": version,
                "download_url": download_url,
                "sha256": module.sha256,
                "size": module.size,
                "package_b64": None,
            }
        # Автоустановка выполняется от имени admin, чтобы политика install_module_package не блокировала
        logger.info(f"[ensure_module] Устанавливаем модуль {module_name}@{version} на {device_id} перед run_tool")
        actor_role = "admin"
        try:
            from websocket.protocol import send_ws_command
            result = await send_ws_command(
                state=self.state,
                device_id=device_id,
                command="install_module_package",
                params=params_install,
                actor_role=actor_role,
                auth_context=None,
                timeout=MODULE_INSTALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.error(f"[ensure_module] Таймаут установки модуля {module_name} на {device_id}")
            return {
                "status": "error",
                "error": f"Таймаут установки модуля {module_name!r} на агент",
                "error_code": "MODULE_INSTALL_TIMEOUT",
            }
        except Exception as e:
            logger.exception(e)
            return {
                "status": "error",
                "error": str(e),
                "error_code": "MODULE_INSTALL_FAILED",
            }
        payload = result.get("payload", {})
        if payload.get("status") != "success":
            err = payload.get("error") or payload.get("error_code") or "unknown"
            return {
                "status": "error",
                "error": f"Ошибка установки модуля {module_name!r}: {err}",
                "error_code": payload.get("error_code") or "MODULE_INSTALL_FAILED",
            }
        logger.info(f"✅ Модуль {module_name}@{version} установлен на {device_id}, продолжаем run_tool")
        return None
    
    async def run_tool(
        self,
        device_id: str,
        ticket_id: str,
        tool_name: str,
        params: Dict,
        call_id: str,
        timeout: float = None,
        auth_context: Optional[object] = None,  # AuthContext type hint
        wait_for_result: bool = True,
    ) -> Dict:
        """
        Запускает инструмент на агенте.
        
        Args:
            device_id: ID устройства
            ticket_id: ID тикета
            tool_name: Имя инструмента
            params: Параметры инструмента
            call_id: ID вызова
            timeout: Таймаут выполнения
        
        Returns:
            Результат выполнения
        """
        if timeout is None:
            timeout = TOOL_EXECUTION_TIMEOUT
        
        logger.info(f"🔧 Запуск tool {tool_name} на {device_id}")
        
        # Проверка и при необходимости установка модуля (только для module.tool)
        ensure_err = await self._ensure_module_installed(device_id, tool_name, auth_context)
        if ensure_err:
            return ensure_err
        
        try:
            from websocket.protocol import send_ws_command
            
            # Получаем job_id из сессии тикета (опционально, для обратной совместимости)
            # КРИТИЧНО: В Protocol V3 события сохраняются в ticket_events, а не в job_events
            # job_id не обязателен для сохранения событий - они сохраняются через TicketEventsRepo
            session = self.state.get_session_by_ticket(ticket_id)
            chat_job_id = session.job_id if session else None
            
            # КРИТИЧНО: Извлекаем operation_id из params (если есть)
            # operation_id должен быть передан из handlers.py для корреляции
            operation_id = params.pop("_operation_id", None)  # Извлекаем и удаляем из params
            
            # Формируем параметры команды
            command_params = {
                "ticket_id": ticket_id,
                "call_id": call_id,  # Legacy поле, не используется для корреляции
                "tool_name": tool_name,
                "params": params
            }
            
            # КРИТИЧНО: Если operation_id был передан, используем его
            if operation_id:
                command_params["_operation_id"] = operation_id
                logger.debug(f"📋 Передача _operation_id в send_ws_command: {operation_id}")
            
            # Генерируем trace_id для корреляции (будет использован в send_ws_command и для события)
            trace_id = str(uuid.uuid4())
            
            # КРИТИЧНО: Создаём событие tool_call_started ПЕРЕД отправкой команды
            # 
            # ИНВАРИАНТ: tool_call_started всегда создаётся сервером до отправки run_tool команды.
            # Корреляция по operation_id (call_id - legacy поле, не используется для поиска/обновления).
            # Идемпотентность гарантируется UNIQUE индексом: (ticket_id, operation_id, event_type) 
            # WHERE operation_id IS NOT NULL.
            if operation_id and DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                try:
                    async with get_session() as session:
                        ticket_events_repo = TicketEventsRepo(session)
                        
                        # Санитизация params для payload (убираем внутренние поля)
                        sanitized_params = {
                            k: v for k, v in params.items() 
                            if not k.startswith("_")  # Убираем внутренние поля типа _operation_id
                        }
                        
                        # Создаём событие tool_call_started с operation_id сразу
                        result = await ticket_events_repo.add_event(
                            ticket_id=ticket_id,
                            device_id=device_id,
                            agent_seq=None,  # Server-originated
                            event_type="tool_call_started",
                            payload={
                                "event": "tool_call_started",
                                "ticket_id": ticket_id,
                                "tool_name": tool_name,
                                "params": sanitized_params,
                                "actor_role": "support",  # По умолчанию support для run_tool
                                "call_id": call_id,  # Legacy поле, optional
                                "ts": datetime.now(timezone.utc).isoformat()
                            },
                            trace_id=trace_id,
                            event_id=None,
                            operation_id=operation_id  # КРИТИЧНО: operation_id сразу
                        )
                        
                        if result:
                            event_id, created_at = result
                            await session.commit()
                            logger.debug(
                                f"[ToolService] Created tool_call_started event: "
                                f"ticket_id={ticket_id} operation_id={operation_id} "
                                f"event_id={event_id} tool_name={tool_name}"
                            )
                        else:
                            # Дубликат (идемпотентность) — Stage 7: rollback на уровне handler
                            await session.rollback()
                            logger.debug(
                                f"[ToolService] tool_call_started event already exists "
                                f"(idempotent): ticket_id={ticket_id} operation_id={operation_id}"
                            )
                except Exception as e:
                    logger.error(
                        f"[ToolService] Failed to create tool_call_started event: {e}",
                        exc_info=True
                    )
                    # Не прерываем выполнение - событие может быть создано агентом (fallback)
            
            # КРИТИЧНО: Передаём tool_name в params — для операции (protocol) и для агента (orchestrator)
            command_params["tool_name"] = tool_name
            # Добавляем chat_job_id если он есть (для обратной совместимости с legacy кодом)
            if chat_job_id:
                command_params["chat_job_id"] = chat_job_id
                logger.debug(f"📋 Отправка run_tool с chat_job_id={chat_job_id}")
            # Убрано предупреждение: job_id не обязателен в Protocol V3
            # События сохраняются в ticket_events через TicketEventsRepo независимо от job_id
            
            # Передаём trace_id и auth_context в send_ws_command для корреляции
            result = await send_ws_command(
                state=self.state,
                device_id=device_id,
                command="run_tool",
                params=command_params,
                auth_context=auth_context,  # КРИТИЧНО: используем auth_context вместо actor_role
                timeout=timeout,
                trace_id=trace_id,  # КРИТИЧНО: передаём trace_id для корреляции
                wait_for_result=wait_for_result,
            )
            
            return result
        
        except asyncio.TimeoutError:
            logger.error(f"⏱️  Таймаут выполнения tool {tool_name}")
            return {
                "status": "error",
                "error": "timeout"
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения tool {tool_name}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


class ToolExecutionService(ToolService):
    """
    Канонический фасад выполнения run_tool.

    ToolService сохранен для обратной совместимости, а все новые вызовы
    должны использовать ToolExecutionService.
    """
