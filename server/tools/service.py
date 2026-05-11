"""
Сервис управления инструментами.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from loguru import logger
from .cache import ToolsCache
from utils.module_manifest import get_module_manifest
from utils.versioning import compare_versions, version_key
from config import (
    TOOL_EXECUTION_TIMEOUT,
    ENABLE_DB_PERSISTENCE,
    SERVER_PUBLIC_BASE_URL,
    AGENT_BUILTIN_MODULES,
)

# Lazy import для избежания circular dependency
DB_AVAILABLE = False
try:
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

    @staticmethod
    def _session_context():
        from app.db import get_session as runtime_get_session

        return runtime_get_session()

    @staticmethod
    def _tool_matches_manifest_entry(tool_entry: Dict, tool_name: str) -> bool:
        canonical_name = tool_entry.get("tool") or tool_entry.get("name")
        if canonical_name == tool_name:
            return True
        aliases = tool_entry.get("aliases") or []
        return tool_name in aliases

    @staticmethod
    def _tool_identifiers(tool_entry: Dict[str, Any]) -> List[str]:
        identifiers: List[str] = []
        canonical_name = tool_entry.get("tool") or tool_entry.get("name")
        if isinstance(canonical_name, str) and canonical_name.strip():
            identifiers.append(canonical_name.strip())
        for alias in tool_entry.get("aliases") or []:
            alias_name = str(alias or "").strip()
            if alias_name:
                identifiers.append(alias_name)
        return list(dict.fromkeys(identifiers))

    async def _enqueue_module_refresh_after_install(
        self,
        *,
        device_id: str,
        actor_role: str,
    ) -> None:
        try:
            from websocket.protocol import enqueue_command_async

            for command in ("list_installed_modules", "list_tools"):
                await enqueue_command_async(
                    state=self.state,
                    device_id=device_id,
                    command=command,
                    params={},
                    actor_role=actor_role,
                    trace_id=None,
                    require_online=False,
                )
            logger.info(
                "[ensure_module] queued post-install inventory/toolset refresh: "
                f"device_id={device_id}"
            )
        except Exception as exc:
            logger.warning(
                "[ensure_module] post-install inventory/toolset refresh enqueue failed: "
                f"device_id={device_id} error={exc}"
            )

    @staticmethod
    def _pick_preferred_module(modules: List[object]):
        if not modules:
            return None
        return max(
            modules,
            key=lambda module: (
                version_key(getattr(module, "version", "")).key,
                getattr(module, "created_at", None) or 0,
            ),
        )

    async def _get_preferred_server_modules(self, session) -> Dict[str, object]:
        try:
            from app.repos import ModulesRepo, ModuleRolloutRepo
        except ImportError:
            return {}
        modules_repo = ModulesRepo(session)
        rollout_repo = ModuleRolloutRepo(session)
        modules = await modules_repo.list_modules(limit=1000)
        assignments = {
            item["module_name"]: item["version"]
            for item in await rollout_repo.list_assignments()
        }
        grouped: Dict[str, List[object]] = {}
        for module in modules:
            grouped.setdefault(module.module_name, []).append(module)
        selected: Dict[str, object] = {}
        for module_name, items in grouped.items():
            preferred_version = assignments.get(module_name)
            preferred = None
            if preferred_version:
                preferred = next((item for item in items if getattr(item, "version", None) == preferred_version), None)
            if preferred is None:
                preferred = self._pick_preferred_module(items)
            if preferred is not None:
                selected[module_name] = preferred
        return selected

    async def _resolve_preferred_server_module_for_tool(self, session, tool_name: str) -> Dict[str, Any]:
        preferred_modules = await self._get_preferred_server_modules(session)
        matches: List[Dict[str, Any]] = []
        for module in preferred_modules.values():
            manifest = get_module_manifest(module)
            for tool_entry in manifest.get("tools") or []:
                if self._tool_matches_manifest_entry(tool_entry, tool_name):
                    matches.append(
                        {
                            "module": module,
                            "manifest": manifest,
                            "tool_entry": tool_entry,
                        }
                    )
        if not matches:
            return {"status": "missing"}
        owner_names = {match["module"].module_name for match in matches}
        if len(owner_names) > 1:
            owners = sorted(owner_names)
            return {
                "status": "conflict",
                "error": (
                    f"Tool {tool_name!r} is declared by multiple preferred module packs: "
                    + ", ".join(owners)
                ),
                "owners": owners,
            }
        match = matches[0]
        match["status"] = "ok"
        return match
    
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
                
                async with self._session_context() as session:
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
        result: List[Dict] = []
        seen_tool_names: set = set()
        async with self._session_context() as session:
            for m in (await self._get_preferred_server_modules(session)).values():
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
                        "aliases": t.get("aliases") or [],
                        "description": t.get("description") or "",
                        "spec": {
                            "params_schema": t.get("params_schema") or {},
                            "output_schema": t.get("output_schema") or {},
                            "output_contract": t.get("output_contract") or {},
                            "presets": t.get("presets") or [],
                            "risk_level": (metadata.get("risk_level") or "safe_readonly"),
                            "metadata": metadata,
                            "execution": t.get("execution") or {},
                            "deployment": t.get("deployment") or {},
                            "safety": t.get("safety") or {},
                            "readiness": t.get("readiness") or {},
                            "evidence": t.get("evidence") or {},
                            "artifacts": t.get("artifacts") or {},
                        },
                        "metadata": metadata,
                        "execution": t.get("execution") or {},
                        "deployment": t.get("deployment") or {},
                        "safety": t.get("safety") or {},
                        "readiness": t.get("readiness") or {},
                        "evidence": t.get("evidence") or {},
                        "artifacts": t.get("artifacts") or {},
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
        builtin_prefix = tool_name.split(".", 1)[0].lower() if "." in tool_name else ""
        if builtin_prefix in AGENT_BUILTIN_MODULES:
            logger.debug(
                f"[ensure_module] {tool_name!r} belongs to builtin module {builtin_prefix!r}, "
                f"skip auto-install"
            )
            return None
        if not DB_AVAILABLE:
            return None
        try:
            from app.repos import DeviceModulesRepo, ToolsetSnapshotsRepo
            from app.repos.devices_repo import DevicesRepo
            from modules.reconcile import set_desired_installed
        except ImportError:
            return None

        actor_role = "admin"
        async with self._session_context() as session:
            resolution = await self._resolve_preferred_server_module_for_tool(session, tool_name)
            if resolution.get("status") == "conflict":
                logger.error(f"[ensure_module] {resolution.get('error')}")
                return {
                    "status": "error",
                    "error": resolution.get("error"),
                    "error_code": "MODULE_TOOL_OWNER_CONFLICT",
                }
            if resolution.get("status") != "ok":
                guessed_module_name = tool_name.split(".", 1)[0] if "." in tool_name else tool_name
                logger.warning(f"[ensure_module] Tool {tool_name!r} не найден в server module registry")
                return {
                    "status": "error",
                    "error": f"Инструмент {tool_name!r} не установлен на агенте и не найден на сервере. Загрузите модуль {guessed_module_name!r} на сервер или установите его вручную.",
                    "error_code": "MODULE_NOT_ON_SERVER",
                }

            module = resolution["module"]
            manifest = resolution["manifest"]
            tool_entry = resolution["tool_entry"]
            module_name = module.module_name
            version = module.version
            tool_metadata = tool_entry.get("metadata") or {}
            tool_dependencies = tool_entry.get("dependencies") or {}
            mod_platforms = tool_metadata.get("platforms") or manifest.get("platforms") or ["any"]
            devices_repo = DevicesRepo(session)
            device = None
            if isinstance(mod_platforms, list) and len(mod_platforms) > 0 and "any" not in [str(p).lower() for p in mod_platforms]:
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
            min_agent_version = str(
                tool_dependencies.get("min_agent_version")
                or manifest.get("min_agent_version")
                or ""
            ).strip()
            if min_agent_version:
                if device is None:
                    device = await devices_repo.get_by_device_id(device_id)
                if not device:
                    return {"status": "error", "error": f"Устройство {device_id} не найдено", "error_code": "DEVICE_NOT_FOUND"}
                device_agent_version = str(device.agent_version or "").strip()
                if not device_agent_version:
                    return {
                        "status": "error",
                        "error": f"Неизвестна версия агента для {device_id}, требуется минимум {min_agent_version}",
                        "error_code": "AGENT_VERSION_UNKNOWN",
                    }
                if compare_versions(device_agent_version, min_agent_version) < 0:
                    return {
                        "status": "error",
                        "error": (
                            f"Инструмент {tool_name!r} требует agent >= {min_agent_version}, "
                            f"но устройство сообщает {device_agent_version}"
                        ),
                        "error_code": "AGENT_VERSION_TOO_OLD",
                    }

            snapshot_has_tool = False
            try:
                snap_repo = ToolsetSnapshotsRepo(session)
                snapshot = await snap_repo.get_latest_snapshot(device_id)
                if snapshot and snapshot.toolset_json:
                    known_tools = {
                        t.get("tool") or t.get("name")
                        for t in snapshot.toolset_json.get("tools", [])
                        if (t.get("tool") or t.get("name"))
                    }
                    snapshot_has_tool = bool(known_tools.intersection(self._tool_identifiers(tool_entry)))
            except Exception as snap_e:
                logger.debug(f"[ensure_module] Не удалось проверить snapshot: {snap_e}")

            device_modules_repo = DeviceModulesRepo(session)
            installed_modules = await device_modules_repo.get_device_modules(device_id, active_only=False)
            preferred_active = any(
                item.module_name == module_name and item.version == version and item.installed and item.active
                for item in installed_modules
            )

            try:
                await set_desired_installed(
                    device_id=device_id,
                    module_name=module_name,
                    desired_version=version,
                    desired_sha256=module.sha256,
                    reason="run_tool",
                    updated_by=actor_role,
                    session=session,
                )
                await session.commit()
            except Exception as desired_e:
                logger.error(
                    f"[ensure_module] Failed to persist desired state for "
                    f"{device_id}:{module_name}@{version}: {desired_e}"
                )
                return {
                    "status": "error",
                    "error": f"Не удалось зафиксировать desired state для {module_name!r}",
                    "error_code": "MODULE_DESIRED_STATE_FAILED",
                }

            if preferred_active and snapshot_has_tool:
                logger.debug(
                    f"[ensure_module] {tool_name!r} already resolved to preferred "
                    f"{module_name}@{version} on {device_id}"
                )
                return None

            download_url = f"{SERVER_PUBLIC_BASE_URL}/api/modules/{module_name}/{version}/download"
            params_install = {
                "module_name": module_name,
                "module_version": version,
                "download_url": download_url,
                "sha256": module.sha256,
                "size": module.size,
                "package_b64": None,
            }

        logger.info(f"[ensure_module] Устанавливаем модуль {module_name}@{version} на {device_id} перед run_tool")
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
        await self._enqueue_module_refresh_after_install(
            device_id=device_id,
            actor_role=actor_role,
        )
        logger.info(f"✅ Модуль {module_name}@{version} установлен на {device_id}, продолжаем run_tool")
        return None

    @staticmethod
    def _derive_transport_error_code(error: object, fallback: str = "TOOL_DISPATCH_FAILED") -> str:
        explicit = getattr(error, "error_code", None)
        if explicit:
            return str(explicit)
        message = str(error or "").strip().lower()
        if "not connected" in message:
            return "AGENT_NOT_CONNECTED"
        if "timeout" in message:
            return "TIMEOUT"
        return fallback

    async def _record_terminal_tool_failure(
        self,
        *,
        operation_id: Optional[str],
        trace_id: str,
        ticket_id: str,
        device_id: str,
        tool_name: str,
        call_id: str,
        actor_role: str,
        error_code: str,
        error_message: str,
    ) -> None:
        if not (DB_AVAILABLE and ENABLE_DB_PERSISTENCE and operation_id and ticket_id):
            return

        summary = f"Tool {tool_name} failed: {error_message}"
        payload = {
            "type": "tool_call_result",
            "status": "error",
            "tool_name": tool_name,
            "call_id": call_id,
            "summary": summary,
            "error": error_message,
            "error_code": error_code,
            "result": {},
            "operation_id": operation_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        result_event = None

        try:
            from app.repos.operations_repo import OperationsRepo
            from app.services.operation_service import OperationService
            from websocket.ui_handler import push_ticket_event_committed

            async with self._session_context() as session:
                ui_publisher = self.state.ui_publisher if hasattr(self.state, "ui_publisher") else None
                op_service = OperationService(session, publisher=ui_publisher)
                op_repo = OperationsRepo(session)
                operation = await op_repo.get_by_operation_id(operation_id)
                if operation is None:
                    operation = await op_service.enqueue_operation(
                        operation_id=operation_id,
                        device_id=device_id,
                        kind="tool_call",
                        tool_name=tool_name,
                        ticket_id=ticket_id,
                        job_id=None,
                        actor_role=actor_role,
                        trace_id=trace_id,
                    )

                await op_service.mark_failed(
                    operation_id=operation_id,
                    error_code=error_code,
                    error_message=error_message,
                    expected_statuses=["queued", "sent", "accepted", "running", "waiting_consent", "cancel_requested"],
                )

                ticket_events_repo = TicketEventsRepo(session)
                result_event = await ticket_events_repo.add_event(
                    ticket_id=ticket_id,
                    device_id=device_id,
                    agent_seq=None,
                    event_type="tool_call_result",
                    payload=payload,
                    trace_id=trace_id,
                    event_id=None,
                    operation_id=operation_id,
                )
                if result_event is not None:
                    await op_repo.update_status(
                        operation_id=operation_id,
                        new_status="failed",
                        expected_statuses=["failed"],
                        error_code=error_code,
                        error_message=error_message,
                        result_summary=summary,
                        result_event_id=result_event[0],
                        deadline_at=None,
                    )

                await session.commit()

            if result_event is not None:
                await push_ticket_event_committed(
                    self.state,
                    ticket_id,
                    result_event[0],
                    "tool_call_result",
                    operation_id,
                    None,
                    result_event[1],
                    payload,
                )
        except Exception as exc:
            logger.warning(
                f"[ToolService] Failed to materialize terminal tool failure: "
                f"operation_id={operation_id} error={exc}"
            )

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
        params = dict(params or {})
        if timeout is None:
            timeout = TOOL_EXECUTION_TIMEOUT
        
        logger.info(f"🔧 Запуск tool {tool_name} на {device_id}")
        requested_operation_id_raw = params.get("_operation_id")
        requested_operation_id = str(requested_operation_id_raw).strip() if requested_operation_id_raw else None
        actor_role = getattr(auth_context, "actor_role", None) or "support"
        trace_id = None

        if ticket_id and DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
            try:
                async with self._session_context() as session:
                    ticket_repo = TicketEventsRepo(session)
                    trace_id = await ticket_repo.ensure_ticket_observer_root_trace_id(ticket_id)
                    await session.commit()
            except Exception as exc:
                logger.warning(f"[ToolService] failed to resolve ticket root trace for ticket_id={ticket_id}: {exc}")
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # Проверка и при необходимости установка модуля по owner module из server registry.
        ensure_err = await self._ensure_module_installed(device_id, tool_name, auth_context)
        if ensure_err:
            error_message = str(ensure_err.get("error") or "Tool dispatch precheck failed")
            error_code = str(ensure_err.get("error_code") or "TOOL_PRECHECK_FAILED")
            await self._record_terminal_tool_failure(
                operation_id=requested_operation_id,
                trace_id=trace_id,
                ticket_id=ticket_id,
                device_id=device_id,
                tool_name=tool_name,
                call_id=call_id,
                actor_role=actor_role,
                error_code=error_code,
                error_message=error_message,
            )
            return {
                **ensure_err,
                "status": "error",
                "error": error_message,
                "error_code": error_code,
                "operation_id": requested_operation_id,
                "trace_id": trace_id,
            }
        
        operation_id = requested_operation_id
        
        try:
            from websocket.protocol import WsCommandQueueFullError, send_ws_command
            
            # Получаем job_id из сессии тикета (опционально, для обратной совместимости)
            # КРИТИЧНО: В Protocol V3 события сохраняются в ticket_events, а не в job_events
            # job_id не обязателен для сохранения событий - они сохраняются через TicketEventsRepo
            session = self.state.get_session_by_ticket(ticket_id)
            chat_job_id = session.job_id if session else None
            
            # КРИТИЧНО: Извлекаем operation_id из params (если есть)
            # operation_id должен быть передан из handlers.py для корреляции
            operation_id = params.pop("_operation_id", None)  # Извлекаем и удаляем из params
            if operation_id:
                operation_id = str(operation_id).strip()
            else:
                operation_id = requested_operation_id
            
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
            
            # КРИТИЧНО: Создаём событие tool_call_started ПЕРЕД отправкой команды
            # 
            # ИНВАРИАНТ: tool_call_started всегда создаётся сервером до отправки run_tool команды.
            # Корреляция по operation_id (call_id - legacy поле, не используется для поиска/обновления).
            # Идемпотентность гарантируется UNIQUE индексом: (ticket_id, operation_id, event_type) 
            # WHERE operation_id IS NOT NULL.
            if operation_id and DB_AVAILABLE and ENABLE_DB_PERSISTENCE:
                try:
                    async with self._session_context() as session:
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
                                "actor_role": actor_role,
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
        
        except WsCommandQueueFullError as e:
            error_code = self._derive_transport_error_code(e, fallback="WS_COMMAND_QUEUE_FULL")
            error_message = str(e)
            logger.error(
                f"❌ Очередь WS-команд переполнена для tool {tool_name}: "
                f"device_id={device_id} operation_id={operation_id}"
            )
            await self._record_terminal_tool_failure(
                operation_id=operation_id,
                trace_id=trace_id,
                ticket_id=ticket_id,
                device_id=device_id,
                tool_name=tool_name,
                call_id=call_id,
                actor_role=actor_role,
                error_code=error_code,
                error_message=error_message,
            )
            return {
                "status": "error",
                "error": error_message,
                "error_code": error_code,
                "operation_id": operation_id,
                "trace_id": trace_id,
            }
        
        except asyncio.TimeoutError:
            logger.error(f"⏱️  Таймаут выполнения tool {tool_name}")
            error_code = "TIMEOUT"
            error_message = "timeout"
            await self._record_terminal_tool_failure(
                operation_id=operation_id,
                trace_id=trace_id,
                ticket_id=ticket_id,
                device_id=device_id,
                tool_name=tool_name,
                call_id=call_id,
                actor_role=actor_role,
                error_code=error_code,
                error_message=error_message,
            )
            return {
                "status": "error",
                "error": error_message,
                "error_code": error_code,
                "operation_id": operation_id,
                "trace_id": trace_id,
            }
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения tool {tool_name}: {e}")
            error_code = self._derive_transport_error_code(e)
            error_message = str(e)
            await self._record_terminal_tool_failure(
                operation_id=operation_id,
                trace_id=trace_id,
                ticket_id=ticket_id,
                device_id=device_id,
                tool_name=tool_name,
                call_id=call_id,
                actor_role=actor_role,
                error_code=error_code,
                error_message=error_message,
            )
            return {
                "status": "error",
                "error": error_message,
                "error_code": error_code,
                "operation_id": operation_id,
                "trace_id": trace_id,
            }


class ToolExecutionService(ToolService):
    """
    Канонический фасад выполнения run_tool.

    ToolService сохранен для обратной совместимости, а все новые вызовы
    должны использовать ToolExecutionService.
    """
