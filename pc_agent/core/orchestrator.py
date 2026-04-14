"""
Универсальный контроллер агента (orchestrator).

Этот модуль реализует единую точку входа для обработки всех команд,
поступающих к агенту. Управляет модулями сбора данных, обрабатывает
команды, и возвращает унифицированные ответы.
"""

import time
import asyncio
import json
import uuid
import pathlib
import base64
import tempfile
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Awaitable, Callable, Dict, Any, List, Optional
from time import perf_counter
import hashlib
try:
    import aiohttp
except ImportError:
    aiohttp = None
from modules import ModuleFactory, BaseCollector
from core.database import DatabaseManager
from core.validator import CodeValidator
from core.loader import DynamicModuleLoader
from core.process_provider import ProcessProvider
from core.registry import ModuleRegistry
from core.tool_response import ToolResponse, ToolMeta, ToolData, ErrorInfo, ok, fail, partial
from core.artifacts import ArtifactIntent, ArtifactManager
from core.tools import ToolSpec, check_policy, ToolMetadata
from core.policy_engine import PolicyEngine
from core.consent_service import ConsentService, ConsentState
from network.uploader import get_uploader
from core.identity import IdentityManager
from core.module_manager import ModuleManager
from core.job_manager import JobManager
from core.recording_controller import get_recording_controller
from pc_agent.config.config_loader import CORE_ENABLED_MODULES, get_config
from pc_agent.version import AGENT_VERSION, EXIT_UPDATE_PENDING
from pc_agent.core.orchestrator_collect_helpers import handle_collect as helper_handle_collect
from pc_agent.core.orchestrator_job_helpers import (
    format_uptime as helper_format_uptime,
    handle_get_job_status as helper_handle_get_job_status,
    handle_job_send_event as helper_handle_job_send_event,
    handle_list_jobs as helper_handle_list_jobs,
    handle_start_job as helper_handle_start_job,
    handle_stop_job as helper_handle_stop_job,
)
from pc_agent.core.orchestrator_shared import logger
from utils.toolset_hash import compute_toolset_hash
import inspect

# Импорт ValidationError из pydantic (опционально)
try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = None


BUILTIN_PACKAGE_INSTALL_MODULES = {name.lower() for name in CORE_ENABLED_MODULES}


class AgentOrchestrator:
    """
    Универсальный контроллер агента для обработки команд.
    
    Основная задача - принимать команды в виде словарей, обрабатывать их
    и возвращать унифицированные ответы. Управляет модулями сбора данных
    и обеспечивает отказоустойчивость системы.
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        enabled_modules: Optional[List[str]] = None,
        agent_uuid: Optional[str] = None,
        identity_manager: Optional[IdentityManager] = None,
        data_root: Optional[Path] = None,
        schedule_update_exit: Optional[Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = None,
    ):
        """
        Инициализация оркестратора.

        Args:
            db_manager: Менеджер базы данных (опционально)
            enabled_modules: Список имен активных модулей (опционально)
            agent_uuid: Идентификатор агента (опционально)
            identity_manager: Менеджер идентификации для загрузки артефактов (опционально)
            data_root: Корень данных (runtime_paths); если задан, modules_store и temp в нём
        """
        self.db_manager = db_manager
        self.enabled_modules = enabled_modules or []
        self._module_load_context = self._build_module_load_context()
        self.loaded_modules: List[BaseCollector] = []
        self.start_time = time.time()
        self.agent_uuid = agent_uuid
        self.identity_manager = identity_manager
        self.job_manager: Optional[JobManager] = None
        self._data_root = data_root
        self.schedule_update_exit = schedule_update_exit

        # Для tools_changed event (Этап B, C)
        self.device_id = agent_uuid  # device_id совпадает с agent_uuid
        self._last_toolset_hash: Optional[str] = None

        # Загрузчик пакетных модулей (только load_module_from_path для modules_store)
        self.loader = DynamicModuleLoader(data_root=data_root)

        # Инициализируем реестр модулей
        self.registry = ModuleRegistry()

        # Инициализируем PolicyEngine для контроля доступа
        self.policy = PolicyEngine()

        # UI Bridge для публикации событий (устанавливается извне)
        self.ui_bus = None
        self.consent_service = ConsentService(
            db_manager=self.db_manager,
            device_id_getter=lambda: self.device_id or self.agent_uuid or "unknown",
        )

        # Tech debt (BOTTLENECKS): Закомментированный consent-путь; при включении согласовать
        # с текущей моделью consent в БД и server waiting_consent. См. docs/BOTTLENECKS_AND_RISKS.md
        # self.pending_tool_calls: Dict[str, Dict[str, Any]] = {}  # consent_token -> dict
        # self.consent_cache: Dict[str, Dict[str, bool]] = {}  # session_key -> {consent_token: bool}

        # Менеджер модулей: data_root/modules_store и data_root/temp при наличии data_root
        cfg = get_config()
        if data_root is not None:
            data_dir = str(data_root)
            temp_dir = str(data_root / "temp")
        else:
            data_dir = cfg.paths.data_dir
            try:
                temp_dir = cfg.paths.temp_dir
            except AttributeError:
                temp_dir = str(pathlib.Path(data_dir) / "temp")
        self.module_manager = ModuleManager(data_dir=data_dir, temp_dir=temp_dir)
        
        # КРИТИЧНО: Registry для отслеживания выполняющихся операций (для cancel)
        # Ключ: operation_id (из meta.request_id), значение: asyncio.Task
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info("AgentOrchestrator инициализирован")
        logger.debug(f"Активные модули: {self.enabled_modules}")

    def _build_module_load_context(self) -> Dict[str, Any]:
        """
        Сохраняет контекст загрузки built-in/extra-path модулей на lifetime orchestrator.
        """
        extra_paths: List[str] = []
        try:
            cfg = get_config()
            if hasattr(cfg, "modules") and hasattr(cfg.modules, "extra_paths"):
                extra_paths = list(cfg.modules.extra_paths or [])
        except Exception as exc:
            logger.warning(f"Не удалось получить extra_paths из config: {exc}")
        return {
            "enabled_modules": list(self.enabled_modules),
            "extra_paths": extra_paths,
            "source": "builtin_or_extra_path",
        }

    def _load_builtin_modules(self) -> List[BaseCollector]:
        """
        Загружает built-in/extra-path модули из сохранённого контекста.
        """
        context = self._module_load_context or {}
        enabled_modules = context.get("enabled_modules") or []
        extra_paths = context.get("extra_paths") or []
        if not enabled_modules:
            return []
        return ModuleFactory.create_modules(enabled_modules, extra_paths=extra_paths)
    
    async def initialize(self) -> None:
        """
        Асинхронная инициализация оркестратора.
        
        Загружает модули и инициализирует базу данных.
        """
        try:
            # Загружаем модули
            if self.enabled_modules:
                logger.info(f"Загружаю модули: {self.enabled_modules}")
                self.loaded_modules = self._load_builtin_modules()
                logger.success(f"Загружено модулей: {len(self.loaded_modules)}")
                
                # Регистрируем модули в реестре
                for module in self.loaded_modules:
                    self.registry.register(module)
                    logger.debug(f"Модуль '{module.name}' зарегистрирован в реестре")
            # Tech debt: блок миграции pending_tool_calls (атрибут закомментирован выше)
            if hasattr(self, 'pending_tool_calls') and self.pending_tool_calls and self.db_manager:
                logger.info("Migrating in-memory pending_tool_calls to database...")
                for consent_token, pending_data in self.pending_tool_calls.items():
                    try:
                        await self.db_manager.add_pending_consent(
                            operation_id=consent_token,
                            tool_name=pending_data["tool_name"],
                            params=pending_data["params"],
                            payload_hash=self._hash_payload(pending_data["params"]),
                            actor_role=pending_data["actor_role"],
                            ticket_id=None,  # Может отсутствовать в старых данных
                            expires_at=int(time.time()) + 1800
                        )
                    except Exception as e:
                        logger.error(f"Failed to migrate consent {consent_token}: {e}")
                self.pending_tool_calls.clear()

            # КРИТИЧНО: Автозагрузка активных модулей из modules_store
            # Это гарантирует, что модули, установленные до перезапуска, будут доступны
            # Список сломанных модулей, удалённых при старте, для последующего уведомления сервера
            broken_modules_deleted: list = []
            if self.module_manager:
                logger.info("Автозагрузка активных модулей из modules_store...")
                try:
                    installed = self.module_manager.list_installed()
                    active_modules_loaded = 0
                    
                    for m in installed.get("modules", []):
                        if not m.get("active"):
                            continue
                        
                        module_name = m.get("name")
                        if not module_name:
                            continue
                        
                        # Получаем путь к активной версии модуля
                        m_path = self.module_manager.get_active_path(module_name)
                        if not m_path:
                            logger.warning(
                                f"Активный модуль '{module_name}' найден, но путь не доступен"
                            )
                            continue
                        
                        try:
                            # Читаем manifest для получения entrypoint
                            manifest = self._read_json(m_path / "manifest.json")
                            entrypoint = manifest.get("entrypoint", "module:register")
                            
                            # Загружаем модуль
                            inst = self.loader.load_module_from_path(
                                module_name, 
                                m_path, 
                                entrypoint=entrypoint
                            )
                            
                            # Добавляем в loaded_modules и регистрируем
                            self.loaded_modules.append(inst)
                            self.registry.register(inst)
                            active_modules_loaded += 1
                            
                            logger.success(
                                f"OK Автозагружен активный модуль '{module_name}' "
                                f"версии {m.get('active', 'unknown')} из modules_store"
                            )
                        except Exception as e:
                            logger.error(
                                f"ERROR Ошибка автозагрузки активного модуля '{module_name}': {e}"
                            )
                            logger.exception(e)
                            # Модуль не загружается — удаляем с диска, чтобы не оставался «установленным»
                            module_version = m_path.name
                            try:
                                self.module_manager.remove_version_force(module_name, module_version)
                                logger.warning(
                                    f"Модуль {module_name}@{module_version} удалён с диска (не загружается)"
                                )
                            except Exception as rm_e:
                                logger.warning(f"Не удалось удалить сломанный модуль {module_name}@{module_version}: {rm_e}")
                            else:
                                broken_modules_deleted.append(f"{module_name}@{module_version}")
                            continue
                    
                    if active_modules_loaded > 0:
                        logger.success(
                            f"Автозагружено активных модулей из modules_store: {active_modules_loaded}"
                        )
                    else:
                        logger.info("В modules_store не найдено активных модулей для автозагрузки")
                except Exception as e:
                    logger.error(f"Ошибка при автозагрузке активных модулей из modules_store: {e}")
                    logger.exception(e)
            else:
                logger.debug("ModuleManager не инициализирован, пропускаем автозагрузку из modules_store")
            
            # ==================================
            
            # Инициализируем базу данных
            if self.db_manager:
                await self.db_manager.init_db()
                logger.success("База данных инициализирована")
                # Уведомляем сервер об удалённых сломанных модулях (после готовности БД)
                if broken_modules_deleted:
                    await self._emit_module_state_changed(
                        reason=f"broken_removed_at_startup:{','.join(broken_modules_deleted)}"
                    )
            
        except Exception as e:
            logger.error(f"Ошибка инициализации оркестратора: {e}")
            raise
    
    def attach_job_manager(self, job_manager: JobManager) -> None:
        """
        Подключает JobManager к оркестратору.
        
        Args:
            job_manager: Экземпляр JobManager
        """
        self.job_manager = job_manager
        logger.info("OK JobManager подключен к оркестратору")
    
    async def handle_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Единая точка входа для обработки команд.
        
        Args:
            command: Словарь с командой, например:
                    {'cmd': 'ping'} или
                    {'cmd': 'collect', 'modules': ['system']}
        
        Returns:
            Dict[str, Any]: Унифицированный ответ в формате ToolResponse.model_dump()
        """
        cmd = command.get('cmd', '').lower()
        start_time = perf_counter()
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        
        # Извлекаем request_id из payload или генерируем новый (fallback)
        payload_request_id = command.get('request_id')
        if payload_request_id:
            request_id = payload_request_id
        else:
            request_id = str(uuid.uuid4())
            logger.debug(f"request_id не указан в payload, сгенерирован новый: {request_id}")
        
        device_id = command.get('device_id')
        ticket_id = command.get('ticket_id') or (command.get('params', {}) or {}).get('ticket_id')
        actor_role = command.get('actor_role')
        agent_id = self.agent_uuid if hasattr(self, 'agent_uuid') and self.agent_uuid else None
        
        # Создаём job для выполнения команды (command_job_id)
        command_job_id = str(uuid.uuid4())
        job_id = command_job_id  # Для обратной совместимости в начале
        job_created = False
        
        meta = ToolMeta(
            timestamp_iso=timestamp_iso,
            command=cmd,
            request_id=request_id,
            agent_id=agent_id,
            duration_ms=None
        )
        
        # Проверка согласованности request_id: если payload содержит request_id,
        # то meta.request_id должен быть равен ему
        if payload_request_id and meta.request_id != payload_request_id:
            logger.error(
                f"ERROR РАСХОЖДЕНИЕ request_id: payload.request_id={payload_request_id}, "
                f"meta.request_id={meta.request_id}. Привожу meta.request_id Рє payload.request_id"
            )
            meta.request_id = payload_request_id
            request_id = payload_request_id  # Обновляем для использования в дальнейшем
        
        logger.info(f"Получена команда: {cmd}, request_id={request_id}")
        logger.debug(f"Полный запрос: {command}")
        
        if self.db_manager:
            try:
                meta_json = json.dumps(meta.model_dump(), ensure_ascii=False)
                await self.db_manager.create_job(
                    job_id=command_job_id,
                    request_id=request_id,
                    device_id=device_id,
                    command=cmd,
                    actor_role=actor_role,
                    meta_json=meta_json
                )
                job_created = True
                logger.info(f"Создан job: {command_job_id}, command={cmd}")
            except Exception as db_error:
                logger.warning(f"Не удалось создать job в БД: {db_error}")
        
        try:
            match cmd:
                case 'ping':
                    result = await self._handle_ping(meta)
                    
                case 'collect':
                    modules = command.get('modules')
                    result = await self._handle_collect(modules, meta)
                    
                case 'list_modules':
                    result = await self._handle_list_modules(meta)
                    
                case 'list_installed_modules':
                    result = await self._handle_list_installed_modules(meta)
                    
                case 'activate_module':
                    name = command.get('name')
                    version = command.get('version')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_activate_module(name, version, actor_role, meta)
                    
                case 'rollback_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_rollback_module(name, actor_role, meta)
                    
                case 'deactivate_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_deactivate_module(name, actor_role, meta)
                    
                case 'remove_module_version':
                    name = command.get('name')
                    version = command.get('version')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_remove_module_version(name, version, actor_role, meta)
                    
                case 'remove_module':
                    name = command.get('name')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_remove_module(name, actor_role, meta)
                    
                case 'update':
                    result = await self._handle_update(command, meta)
                    
                case 'install_module_package':
                    name = command.get('name') or command.get('module_name')
                    version = command.get('version') or command.get('module_version')
                    package_b64 = command.get('package_b64')
                    download_url = command.get('download_url')
                    sha256 = command.get('sha256')
                    size = command.get('size')
                    actor_role = command.get('actor_role', 'user')
                    replace_if_different_sha = command.get('replace_if_different_sha') or (command.get('params') or {}).get('replace_if_different_sha', False)
                    result = await self._handle_install_module_package(
                        name, version, package_b64, download_url, sha256, size, actor_role, meta,
                        replace_if_different_sha=replace_if_different_sha
                    )
                    
                case 'exec_script':
                    code = command.get('code')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_exec_script(code, actor_role, meta)
                    
                case 'get_manifest':
                    result = await self._handle_get_manifest(meta)
                    
                case 'list_tools':
                    result = await self._handle_list_tools(meta)
                    
                case 'describe_tool':
                    tool = command.get("tool")
                    result = await self._handle_describe_tool(tool, meta)
                    
                case 'cancel_operation':
                    # Обработка команды cancel_operation
                    params = command.get("params", {})
                    target_operation_id = params.get("target_operation_id") or params.get("operation_id")
                    result = await self._handle_cancel_operation(
                        target_operation_id,
                        meta,
                        ticket_id=ticket_id,
                        device_id=device_id,
                    )
                    
                case 'run_tool' | 'call_tool':
                    # Поддержка обоих форматов: tool в корне или в params
                    # call_tool - алиас для run_tool
                    tool = command.get("tool") or command.get("params", {}).get("tool")
                    tool_params = command.get("params", {}) or {}
                    chat_job_id = command.get("chat_job_id")
                    actor_role = command.get("actor_role", "user")
                    
                    # Создаём обёртку command_params с tool, params, chat_job_id
                    command_params = {
                        "tool": tool,
                        "params": tool_params,
                        "chat_job_id": chat_job_id,
                        "ticket_id": ticket_id,
                        "job_id": command.get("job_id"),
                    }
                    result = await self._handle_run_tool(tool, command_params, actor_role, meta)
                    
                case 'start_job':
                    job_type = command.get('job_type')
                    params = command.get('params', {})
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_start_job(job_type, params, actor_role, device_id, meta)
                    
                case 'stop_job':
                    job_id = command.get('job_id')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_stop_job(job_id, actor_role, meta)
                    
                case 'get_job_status':
                    job_id = command.get('job_id')
                    result = await self._handle_get_job_status(job_id, meta)
                    
                case 'list_jobs':
                    limit = command.get('limit', 50)
                    result = await self._handle_list_jobs(limit, meta)
                    
                case 'job_send_event':
                    # Извлекаем chat_job_id из params (это job_id чата, НЕ command_job_id)
                    chat_job_id = command.get('job_id') or command.get('params', {}).get('job_id')
                    event = command.get('event') or command.get('params', {}).get('event')
                    actor_role = command.get('actor_role', 'user')
                    result = await self._handle_job_send_event(chat_job_id, event, actor_role, meta)
                    
                case 'consent_decision':
                    consent_token = command.get('consent_token')
                    approved = command.get('approved', False)
                    session_key = command.get('session_key')
                    result = await self._handle_consent_decision(consent_token, approved, session_key, meta)
                    
                case 'ui_notify':
                    # ожидаем event dict: {"event":"chat_invite", "job_id":..., "ts":...}
                    ev = command.get("event") or command.get("params", {}).get("event")
                    if not isinstance(ev, dict):
                        result = fail(
                            code="BAD_REQUEST",
                            message="ui_notify требует поле event (dict)",
                            meta=meta
                        )
                    else:
                        if self.ui_bus:
                            await self.ui_bus.publish(ev)
                            logger.info(f"UI notify published: {ev.get('event')} job_id={ev.get('job_id')}")
                        else:
                            logger.warning("ui_notify получен, но ui_bus не инициализирован")
                        result = ok(
                            data=ToolData(observations={"published": True}),
                            meta=meta
                        )
                    
                case '':
                    result = fail(
                        code="UNKNOWN_COMMAND",
                        message='Не указана команда (поле "cmd" отсутствует или пустое)',
                        meta=meta
                    )
                    
                case _:
                    result = fail(
                        code="UNKNOWN_COMMAND",
                        message=f'Неизвестная команда: {cmd}',
                        meta=meta
                    )
            
            duration_ms = int((perf_counter() - start_time) * 1000)
            result.meta.duration_ms = duration_ms
            
            # Проверка согласованности request_id в результате
            if result.meta.request_id != request_id:
                logger.error(
                    f"ERROR РАСХОЖДЕНИЕ request_id в результате: "
                    f"ожидался request_id={request_id}, получен result.meta.request_id={result.meta.request_id}. "
                    f"Исправляю result.meta.request_id"
                )
                result.meta.request_id = request_id
            
            if self.db_manager and job_created:
                try:
                    error_json = None
                    if result.error:
                        error_json = json.dumps(result.error.model_dump(), ensure_ascii=False)
                    
                    # Завершаем command_job_id (job выполнения команды), а не chat_job_id
                    await self.db_manager.finish_job(
                        job_id=command_job_id,
                        status=result.status,
                        error_json=error_json
                    )
                    
                    result_dict = result.model_dump()
                    if ticket_id:
                        outbox_id = await self.db_manager.enqueue_tool_response(
                            job_id=command_job_id,
                            request_id=request_id,
                            device_id=device_id,
                            ticket_id=ticket_id,
                            tool_response=result_dict
                        )
                        logger.info(
                            f"Enqueued tool_response to outbox: job_id={command_job_id}, "
                            f"request_id={request_id}, ticket_id={ticket_id}, outbox_id={outbox_id}"
                        )
                    else:
                        logger.debug(
                            f"Skip enqueue_tool_response for command_job_id={command_job_id}: missing ticket_id"
                        )
                    if cmd == 'collect':
                        logger.info(f"Collect command completed: outbox_written=1 (single canonical ToolResponse)")
                    logger.info(f"Завершен job: {command_job_id}, status={result.status}")
                except Exception as db_error:
                    logger.warning(f"Не удалось сохранить результат в БД: {db_error}")
            
            logger.success(f"OK Команда '{cmd}' выполнена успешно (duration: {duration_ms}ms)")
            return result.model_dump()
            
        except Exception as e:
            duration_ms = int((perf_counter() - start_time) * 1000)
            meta.duration_ms = duration_ms
            
            # Убеждаемся, что meta.request_id совпадает с request_id
            if meta.request_id != request_id:
                logger.error(
                    f"ERROR РАСХОЖДЕНИЕ request_id в meta при ошибке: "
                    f"ожидался request_id={request_id}, получен meta.request_id={meta.request_id}. "
                    f"Исправляю meta.request_id"
                )
                meta.request_id = request_id
            
            error_msg = f"Ошибка выполнения команды '{cmd}': {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            result = fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
            
            # Проверка согласованности request_id в результате ошибки
            if result.meta.request_id != request_id:
                logger.error(
                    f"ERROR РАСХОЖДЕНИЕ request_id в результате ошибки: "
                    f"ожидался request_id={request_id}, получен result.meta.request_id={result.meta.request_id}. "
                    f"Исправляю result.meta.request_id"
                )
                result.meta.request_id = request_id
            
            if self.db_manager and job_created:
                try:
                    error_json = json.dumps(result.error.model_dump(), ensure_ascii=False) if result.error else None
                    await self.db_manager.finish_job(
                        job_id=command_job_id,
                        status=result.status,
                        error_json=error_json
                    )
                    
                    result_dict = result.model_dump()
                    if ticket_id:
                        outbox_id = await self.db_manager.enqueue_tool_response(
                            job_id=command_job_id,
                            request_id=request_id,
                            device_id=device_id,
                            ticket_id=ticket_id,
                            tool_response=result_dict
                        )
                        logger.info(
                            f"Enqueued tool_response to outbox: job_id={command_job_id}, "
                            f"request_id={request_id}, ticket_id={ticket_id}, outbox_id={outbox_id}"
                        )
                    else:
                        logger.debug(
                            f"Skip enqueue_tool_response for command_job_id={command_job_id}: missing ticket_id"
                        )
                    logger.info(f"Завершен job: {command_job_id}, status={result.status}")
                except Exception as db_error:
                    logger.warning(f"Не удалось сохранить ошибку в БД: {db_error}")
            
            return result.model_dump()
    
    async def _handle_ping(self, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'ping' - возвращает быстрый статус агента.
        
        Args:
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с информацией о статусе агента
        """
        try:
            uptime = time.time() - self.start_time
            
            # Список имен загруженных модулей
            module_names = [module.name for module in self.loaded_modules]
            
            agent_uuid = self.agent_uuid if hasattr(self, 'agent_uuid') and self.agent_uuid else None
            
            observations = {
                'message': 'Agent is alive',
                'agent': agent_uuid,
                'uptime': round(uptime, 2),
                'uptime_human': self._format_uptime(uptime),
                'modules_loaded': module_names,
                'modules_count': len(module_names)
            }
            
            logger.debug(f"Ping ответ: {observations}")
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            logger.error(f"Ошибка в _handle_ping: {e}")
            raise
    
    async def _handle_collect(self, modules: Optional[List[str]], meta: ToolMeta) -> ToolResponse:
        """Delegate collect handling to the extracted helper."""
        return await helper_handle_collect(self, modules, meta)

    async def _handle_list_modules(self, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'list_modules' - возвращает список доступных модулей.
        
        Args:
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse со списком модулей и их описанием
        """
        try:
            modules_info = []
            
            for module in self.loaded_modules:
                module_info = {
                    'name': module.name,
                    'class': module.__class__.__name__,
                    'description': module.__class__.__doc__.strip() if module.__class__.__doc__ else 'Нет описания'
                }
                modules_info.append(module_info)
            
            logger.debug(f"Список модулей: {[m['name'] for m in modules_info]}")
            
            observations = {
                'modules': modules_info,
                'total_count': len(modules_info),
                'enabled_modules': self.enabled_modules
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            logger.error(f"Ошибка в _handle_list_modules: {e}")
            raise
    
    async def _handle_list_installed_modules(self, meta: ToolMeta) -> ToolResponse:
        try:
            data = self.module_manager.list_installed()
            observations = {
                "modules": data.get("modules", [])
            }
            return ok(data=ToolData(observations=observations), meta=meta)
        except Exception as e:
            return fail(code="LIST_INSTALLED_FAILED", message=str(e), meta=meta, retriable=True)
    
    def _read_json(self, path: pathlib.Path) -> Dict[str, Any]:
        """
        Helper функция для чтения JSON файла.
        
        Args:
            path: Путь к JSON файлу
            
        Returns:
            Dict с содержимым JSON файла
            
        Raises:
            FileNotFoundError: если файл не существует
            json.JSONDecodeError: если файл содержит невалидный JSON
        """
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    async def _handle_activate_module(self, name: Optional[str], version: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'activate_module' - активация версии модуля.
        
        Args:
            name: Имя модуля
            version: Версия модуля для активации
            actor_role: Роль актора для проверки прав доступа
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом активации модуля
        """
        try:
            # 1) gate
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)

            if not name or not version:
                return fail(code="ACTIVATE_FAILED", message="name and version required", meta=meta)

            # 2) activate in ModuleManager
            active_path = self.module_manager.activate(name, version)
            self._purge_module_runtime(name)

            # 3) rebuild registry from all active modules
            await self._rebuild_registry_from_active_modules()
            # emit module_state_changed
            await self._emit_module_state_changed(reason=f"activate:{name}@{version}")

            observations = {
                "activated": name,
                "version": version,
                "active_path": str(active_path)
            }
            return ok(data=ToolData(observations=observations), meta=meta)

        except Exception as e:
            return fail(code="ACTIVATE_FAILED", message=str(e), meta=meta, retriable=True)
    
    async def _rebuild_registry_from_active_modules(self) -> None:
        """
        Пересобирает реестр модулей из активных модулей.

        Очищает registry и loaded_modules, затем загружает:
        1. Built-in модули из enabled_modules (если есть)
        2. Все активные package модули из module_manager (modules_store)

        После успешной пересборки отправляет tools_changed device_event при изменении toolset_hash.
        """
        self.registry.reset()
        self.loaded_modules = []
        if self.loader:
            self.loader.reset_runtime_cache()

        # Зарегистрировать built-in модули, если они есть в enabled_modules
        if self.enabled_modules:
            logger.info(f"Перезагрузка встроенных модулей: {self.enabled_modules}")
            builtin_modules = self._load_builtin_modules()
            self.loaded_modules.extend(builtin_modules)
            for module in builtin_modules:
                self.registry.register(module)
                logger.debug(f"Встроенный модуль '{module.name}' зарегистрирован в реестре")

        # Зарегистрировать ВСЕ активные package modules:
        if self.module_manager:
            installed = self.module_manager.list_installed()
            for m in installed.get("modules", []):
                if not m.get("active"):
                    continue
                m_path = self.module_manager.get_active_path(m["name"])
                if not m_path:
                    continue
                module_name = m["name"]
                module_version = m_path.name
                try:
                    manifest = self._read_json(m_path / "manifest.json")
                    entrypoint = manifest.get("entrypoint", "module:register")
                    inst = self.loader.load_module_from_path(module_name, m_path, entrypoint=entrypoint)
                    self.loaded_modules.append(inst)
                    self.registry.register(inst)
                    logger.debug(f"Package модуль '{module_name}' зарегистрирован в реестре")
                except Exception as load_err:
                    # Модуль на диске не загружается — удаляем, чтобы не оставался «установленным, но сломанным»
                    logger.warning(f"Модуль {module_name}@{module_version} не загружается: {load_err}, удаляю с диска")
                    try:
                        self.module_manager.remove_version_force(module_name, module_version)
                    except Exception as rm_e:
                        logger.warning(f"Не удалось удалить сломанный модуль {module_name}@{module_version}: {rm_e}")
                    continue

        # После успешной пересборки отправляем tools_changed event
        # EDGE GUARD: проверяем, изменился ли hash (избегаем лишних events)
        try:
            # Получаем tools_list и вычисляем hash
            tools_list = self._build_tools_list()
            tools_count = len(tools_list)
            
            new_toolset_hash = compute_toolset_hash(tools_list) if tools_list else None
            
            # Edge guard: проверяем, изменился ли hash
            if hasattr(self, '_last_toolset_hash') and self._last_toolset_hash == new_toolset_hash:
                logger.debug(f"toolset_hash не изменился ({new_toolset_hash}), пропускаем tools_changed")
                return  # Hash не изменился, не отправляем event
            
            # Сохраняем новый hash
            self._last_toolset_hash = new_toolset_hash
            
            # Отправляем device_event tools_changed
            if self.db_manager and self.device_id:
                await self.db_manager.enqueue_event(
                    device_id=self.device_id,
                    kind="tools_changed",
                    payload={
                        "event": "tools_changed",
                        "toolset_hash": new_toolset_hash,
                        "tools_count": tools_count,
                        "tools_version": "tools_v1",
                        "agent_version": AGENT_VERSION,
                        "reason": "registry_rebuilt"
                    },
                    actor_role="system",
                    ticket_id=None,  # Device event без ticket_id
                    trace_id=None,
                    span_id=None,
                    batch_seq=0
                )
                logger.info(f"tools_changed event enqueued: toolset_hash={new_toolset_hash}, tools_count={tools_count}")
        except Exception as e:
            logger.error(f"Failed to enqueue tools_changed event: {e}", exc_info=True)
            # Не падаем, если event не отправился

    def _purge_module_runtime(self, module_name: Optional[str]) -> None:
        """
        Remove stale runtime bindings for a module before lifecycle transitions.

        This protects the agent from continuing to execute a removed or
        deactivated package module from in-memory objects that survived the last
        operation.
        """
        if not module_name:
            return

        self.loaded_modules = [
            module
            for module in self.loaded_modules
            if getattr(module, "name", None) != module_name
        ]
        try:
            self.registry.unregister(module_name)
        except Exception:
            logger.debug(f"Failed to unregister module '{module_name}' from registry", exc_info=True)
        if self.loader:
            try:
                self.loader.unload_module(module_name)
            except Exception:
                logger.debug(f"Failed to unload runtime cache for module '{module_name}'", exc_info=True)

    def _get_loaded_module_instance(self, module_name: str):
        for module in self.loaded_modules:
            if getattr(module, "name", None) == module_name:
                return module
        return None

    def _get_module_source_path(self, module_instance: Any) -> Optional[Path]:
        if module_instance is None:
            return None
        try:
            source_path = inspect.getsourcefile(module_instance.__class__) or inspect.getfile(module_instance.__class__)
        except Exception:
            return None
        if not source_path:
            return None
        try:
            return Path(source_path).resolve()
        except Exception:
            return None

    def _is_dynamic_module_instance(self, module_instance: Any) -> bool:
        source_path = self._get_module_source_path(module_instance)
        if source_path is None:
            return False
        return any(part.lower() == "modules_store" for part in source_path.parts)

    def _get_expected_tool_method_from_active_manifest(
        self,
        module_name: str,
        full_tool_name: str,
    ) -> tuple[Optional[Path], Optional[str]]:
        if not self.module_manager:
            return None, None
        active_path = self.module_manager.get_active_path(module_name)
        if not active_path:
            return None, None
        try:
            manifest = self._read_json(active_path / "manifest.json")
        except Exception:
            return active_path, None

        short_tool_name = full_tool_name.split(".", 1)[1] if "." in full_tool_name else full_tool_name
        for tool_info in manifest.get("tools", []) or []:
            declared_tool = tool_info.get("tool")
            if declared_tool in (full_tool_name, short_tool_name, f"{module_name}.{short_tool_name}"):
                return active_path, tool_info.get("method")

        return active_path, None

    async def _ensure_module_runtime_matches_inventory(
        self,
        module_name: str,
        *,
        full_tool_name: Optional[str] = None,
    ) -> None:
        """
        Self-heals stale package runtime when inventory/current.json and in-memory
        registry diverge.

        This protects run_tool/list_tools from executing a removed or outdated
        package implementation after rollback/remove/restart edge cases.
        """
        if not module_name or not self.module_manager:
            return

        active_path, expected_method = self._get_expected_tool_method_from_active_manifest(
            module_name,
            full_tool_name or module_name,
        )
        loaded_instance = self._get_loaded_module_instance(module_name)
        registry_tool = self.registry.get_tool(full_tool_name) if full_tool_name else None
        registry_module = self.registry.get_module(module_name)
        source_path = self._get_module_source_path(loaded_instance)

        should_rebuild = False
        reasons: List[str] = []

        if active_path:
            active_path_resolved = active_path.resolve()
            if loaded_instance is None:
                should_rebuild = True
                reasons.append("loaded_instance_missing")
            elif source_path is not None and active_path_resolved not in source_path.parents:
                should_rebuild = True
                reasons.append(f"source_path_mismatch:{source_path}")

            if registry_module is None:
                should_rebuild = True
                reasons.append("registry_module_missing")

            if full_tool_name and expected_method:
                current_method = registry_tool.get("method_name") if registry_tool else None
                if current_method != expected_method:
                    should_rebuild = True
                    reasons.append(
                        f"tool_method_mismatch:{current_method or '<missing>'}!={expected_method}"
                    )
        else:
            if loaded_instance is not None and self._is_dynamic_module_instance(loaded_instance):
                should_rebuild = True
                reasons.append("stale_dynamic_runtime_without_active_version")
            elif registry_module is not None and loaded_instance is None and module_name not in self.enabled_modules:
                should_rebuild = True
                reasons.append("stale_registry_without_loaded_instance")

        if not should_rebuild:
            return

        logger.warning(
            f"[runtime_self_heal] Rebuilding registry for module '{module_name}' due to: {', '.join(reasons)}"
        )
        self._purge_module_runtime(module_name)
        await self._rebuild_registry_from_active_modules()

    async def _ensure_all_package_runtime_matches_inventory(self) -> None:
        if not self.module_manager:
            return

        module_names = {
            module_info.get("name")
            for module_info in self.module_manager.list_installed().get("modules", [])
            if module_info.get("name")
        }
        module_names.update(
            getattr(module, "name", None)
            for module in self.loaded_modules
            if self._is_dynamic_module_instance(module)
        )
        module_names.discard(None)

        for module_name in sorted(module_names):
            await self._ensure_module_runtime_matches_inventory(module_name)

    async def _emit_module_state_changed(self, reason: str = "unknown") -> None:
        """
        Publishes device_event module_state_changed with current modules snapshot.
        Server uses this to update actual state and trigger reconcile.
        """
        try:
            if not self.db_manager or not self.device_id or not self.module_manager:
                return
            snapshot = self.module_manager.list_installed().get("modules", [])
            await self.db_manager.enqueue_event(
                device_id=self.device_id,
                kind="module_state_changed",
                payload={
                    "event": "module_state_changed",
                    "reason": reason,
                    "modules_snapshot": snapshot,
                },
                actor_role="system",
                ticket_id=None,
                trace_id=None,
                span_id=None,
                batch_seq=0,
            )
            logger.info(f"[module_state_changed] Event enqueued: reason={reason} modules={len(snapshot)}")
        except Exception as e:
            logger.warning(f"[module_state_changed] Failed to enqueue event: {e}")

    async def _handle_rollback_module(self, name: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'rollback_module' - откат модуля на предыдущую версию.
        
        Args:
            name: Имя модуля
            actor_role: Роль актора для проверки прав доступа
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом отката модуля
        """
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="ROLLBACK_FAILED", message="name required", meta=meta)

        prev_path = self.module_manager.rollback(name)
        if not prev_path:
            return fail(code="ROLLBACK_FAILED", message="No previous version to rollback", meta=meta, retriable=False)

        # После rollback ОБЯЗАТЕЛЬНО вызвать ту же логику rebuild registry, что и в activate_module
        self._purge_module_runtime(name)
        await self._rebuild_registry_from_active_modules()
        await self._emit_module_state_changed(reason=f"rollback:{name}")

        return ok(
            data=ToolData(
                observations={
                    "rolled_back": name,
                    "active_path": str(prev_path),
                    "active_version": prev_path.name,
                }
            ),
            meta=meta,
        )
    
    async def _handle_deactivate_module(self, name: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'deactivate_module' - деактивация модуля.
        
        Args:
            name: Имя модуля
            actor_role: Роль актора для проверки прав доступа
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом деактивации модуля
        """
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="DEACTIVATE_FAILED", message="name required", meta=meta)

        self.module_manager.deactivate(name)
        self._purge_module_runtime(name)

        # rebuild
        await self._rebuild_registry_from_active_modules()
        # emit module_state_changed
        await self._emit_module_state_changed(reason=f"deactivate:{name}")

        return ok(data=ToolData(observations={"deactivated": name}), meta=meta)
    
    async def _handle_remove_module_version(
        self,
        name: Optional[str],
        version: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Remove specific version of module."""
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name or not version:
            return fail(code="REMOVE_FAILED", message="name and version required", meta=meta)
        
        try:
            # Check if version is active before removal
            installed_info = self.module_manager.list_installed()
            for module_info in installed_info.get("modules", []):
                if module_info["name"] == name:
                    active_version = module_info.get("active")
                    if active_version == version:
                        return fail(
                            code="REMOVE_FAILED",
                            message=f"Cannot remove active version {version} of {name}. Deactivate first.",
                            meta=meta,
                            retriable=False
                        )
                    break
            
            removed = self.module_manager.remove_version(name, version)
            if removed:
                remaining_modules = {
                    module_info["name"]
                    for module_info in self.module_manager.list_installed().get("modules", [])
                }
                if name not in remaining_modules:
                    self._purge_module_runtime(name)
                    await self._rebuild_registry_from_active_modules()
                    await self._emit_module_state_changed(reason=f"remove_version:{name}@{version}")
                return ok(data=ToolData(observations={"removed": f"{name}@{version}"}), meta=meta)
            else:
                return fail(code="REMOVE_FAILED", message="Version not found", meta=meta, retriable=False)
        except ValueError as e:
            return fail(code="REMOVE_FAILED", message=str(e), meta=meta, retriable=False)

    async def _handle_remove_module(
        self,
        name: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Remove all versions of module."""
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
        if not name:
            return fail(code="REMOVE_FAILED", message="name required", meta=meta)
        
        try:
            # Check if module has active version
            installed_info = self.module_manager.list_installed()
            for module_info in installed_info.get("modules", []):
                if module_info["name"] == name:
                    active_version = module_info.get("active")
                    if active_version is not None:
                        return fail(
                            code="REMOVE_FAILED",
                            message=f"Cannot remove module {name}: has active version {active_version}. Deactivate first.",
                            meta=meta,
                            retriable=False
                        )
                    break
            
            removed = self.module_manager.remove_module(name)
            if removed:
                self._purge_module_runtime(name)
                await self._rebuild_registry_from_active_modules()
                await self._emit_module_state_changed(reason=f"remove:{name}")
                return ok(data=ToolData(observations={"removed": name}), meta=meta)
            else:
                return fail(code="REMOVE_FAILED", message="Module not found", meta=meta, retriable=False)
        except ValueError as e:
            return fail(code="REMOVE_FAILED", message=str(e), meta=meta, retriable=False)
    
    async def _handle_cancel_operation(
        self,
        target_operation_id: Optional[str],
        meta: ToolMeta,
        *,
        ticket_id: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> ToolResponse:
        """
        Отменяет выполняющуюся операцию.
        
        КРИТИЧНО: Использует timeout для предотвращения зависания cancel-команды.
        
        Args:
            target_operation_id: ID операции для отмены (должен совпадать с ключом в running_tasks)
            meta: Метаданные команды
        
        Returns:
            ToolResponse с результатом отмены
        """
        if not target_operation_id:
            return fail(
                code="INVALID_REQUEST",
                message="target_operation_id is required",
                meta=meta,
                retriable=False
            )
        
        if target_operation_id in self.running_tasks:
            task = self.running_tasks[target_operation_id]
            task.cancel()
            
            # КРИТИЧНО: timeout для предотвращения зависания cancel-команды
            # Если task выполняет блокирующую операцию или плохо обрабатывает cancellation,
            # await task может зависнуть, и cancel-команда сама станет "вечной"
            CANCEL_TIMEOUT = 2.0  # 2 секунды максимум на graceful cancellation
            
            try:
                await asyncio.wait_for(task, timeout=CANCEL_TIMEOUT)
                cancel_status = "canceled"
            except asyncio.CancelledError:
                cancel_status = "canceled"
            except asyncio.TimeoutError:
                # Task не отменился за timeout - но cancel-команда должна завершиться
                cancel_status = "cancel_requested"  # или "cannot_cancel_gracefully"
                logger.warning(
                    f"[cancel_operation] Task {target_operation_id} did not cancel gracefully within {CANCEL_TIMEOUT}s"
                )
            
            # КРИТИЧНО: Обязательно опубликовать событие canceled для target операции
            # Это критично для UI и redundancy на сервере
            # Если cancel-команда success, а обновление target-op на сервере не прошло (transient DB error),
            # событие от агента позволит довести operation до canceled ("вторая линия")
            
            # Извлекаем ticket_id из meta если доступен
            event_ticket_id = ticket_id
            event_device_id = device_id or self.device_id

            if event_ticket_id and self.db_manager:
                try:
                    await self.db_manager.enqueue_job_event(
                        job_id=None,  # Может быть None для операций без job
                        request_id=target_operation_id,
                        device_id=event_device_id,
                        event_payload={
                            "event": "tool_call_result",  # или "agent_action"
                            "ticket_id": event_ticket_id,
                            "operation_id": target_operation_id,
                            "status": "canceled",
                            "cancel_status": cancel_status
                        }
                    )
                except Exception as e:
                    logger.error(f"[cancel_operation] Failed to publish canceled event: {e}")
            
            return ok(
                data=ToolData(
                    observations={
                        "cancel_status": cancel_status,
                        "target_operation_id": target_operation_id,
                    }
                ),
                meta=meta
            )
        else:
            # Операция не найдена или уже завершена
            return fail(
                code="UNKNOWN_OPERATION",
                message=f"Operation {target_operation_id} not found or already finished",
                meta=meta,
                retriable=False
            )
    
    async def _handle_update(self, command: Dict[str, Any], meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'update' - обновление агента (self-update).
        
        Args:
            command: Полный payload команды (params из WS), включая download_url/sha256/size/version.
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом операции обновления
        """
        try:
            actor_role = (command.get("actor_role") or "user").lower()
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)

            version = command.get("version")
            target = command.get("target")
            channel = command.get("channel") or "stable"
            download_url = command.get("download_url")
            expected_sha256 = command.get("sha256")
            expected_size = command.get("size")
            restart_delay_sec = command.get("restart_delay_sec")
            archive_type = command.get("archive_type") or "zip"
            operation_id = (meta.request_id or "") if hasattr(meta, "request_id") else ""
            requested_by = (command.get("actor_role") or "admin").lower()

            if not version:
                return fail(code="UPDATE_FAILED", message="Missing version", meta=meta, retriable=False)
            if not download_url:
                return fail(code="UPDATE_FAILED", message="Missing download_url", meta=meta, retriable=False)
            if not expected_sha256:
                return fail(code="UPDATE_FAILED", message="Missing sha256", meta=meta, retriable=False)
            if archive_type not in ("zip", "tar.gz", "tgz"):
                return fail(code="UPDATE_FAILED", message="Unsupported archive_type", meta=meta, retriable=False)
            # tgz — алиас для tar.gz (launcher/installer поддерживает оба)

            # data_root/updates/downloads
            if self._data_root is not None:
                data_dir = self._data_root
            else:
                agent_dir = pathlib.Path(__file__).resolve().parent.parent
                data_dir = agent_dir / get_config().paths.data_dir
            updates_dir = data_dir / "updates"
            downloads_dir = updates_dir / "downloads"
            downloads_dir.mkdir(parents=True, exist_ok=True)
            ext = "zip" if archive_type == "zip" else "tar.gz"
            artifact_path = downloads_dir / f"build.{ext}"

            dl_sha256, dl_size = await self._download_file_to_path(
                url=download_url,
                dest_path=artifact_path,
                expected_sha256=expected_sha256,
                expected_size=expected_size,
            )

            received_at = datetime.now(timezone.utc).isoformat()
            # Launcher ожидает archive_type "zip" или "tar.gz"/"tgz"; сохраняем нормализованный для распаковки
            pending_archive_type = "tar.gz" if archive_type == "tgz" else archive_type
            pending_payload = {
                "version": version,
                "target": target,
                "channel": channel,
                "archive_type": pending_archive_type,
                "artifact_path": str(artifact_path.resolve()),
                "received_at": received_at,
                "operation_id": operation_id,
                "requested_by": requested_by,
                "requested_reason": command.get("reason"),
                "sha256": dl_sha256,
                "size": dl_size,
            }
            pending_path = updates_dir / "pending_update.json"
            pending_path.write_text(json.dumps(pending_payload, ensure_ascii=False, indent=2), encoding="utf-8")

            restart_delay = 2
            if isinstance(restart_delay_sec, int) and 0 <= restart_delay_sec <= 60:
                restart_delay = restart_delay_sec
            try:
                if self.schedule_update_exit is not None:
                    await self.schedule_update_exit(
                        {
                            "delay_sec": restart_delay,
                            "reason": "self_update",
                            "version": version,
                            "operation_id": operation_id,
                        }
                    )
                else:
                    loop = asyncio.get_running_loop()
                    loop.call_later(restart_delay, lambda: os._exit(EXIT_UPDATE_PENDING))
            except Exception as e:
                logger.warning(f"[update] Failed to schedule exit: {e}")

            observations = {
                "message": "scheduled",
                "requested_version": version,
                "current_version": AGENT_VERSION,
                "target": target,
                "channel": channel,
                "archive_type": archive_type,
                "downloaded_sha256": dl_sha256,
                "downloaded_size": dl_size,
                "exit_code_pending": EXIT_UPDATE_PENDING,
            }
            return ok(data=ToolData(observations=observations), meta=meta)
            
        except Exception as e:
            logger.error(f"Ошибка в _handle_update: {e}")
            raise

    async def _download_file_to_path(
        self,
        *,
        url: str,
        dest_path: pathlib.Path,
        expected_sha256: Optional[str],
        expected_size: Optional[int],
        chunk_size: int = 8192,
    ) -> tuple[str, int]:
        """
        Download a file to disk with streaming sha256 verification.

        Uses agent token for Authorization (Bearer) when available.
        """
        if aiohttp is None:
            raise ImportError("aiohttp is required for update downloads")

        headers: dict[str, str] = {}
        if self.identity_manager and self.identity_manager.has_token:
            token = self.identity_manager.token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.debug(f"[UpdateDownload] Using token for download: {token[:8]}...")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".tmp")

        sha256_hash = hashlib.sha256()
        total_size = 0

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        raise RuntimeError("Download failed: HTTP 401 (AUTH_REQUIRED)")
                    if resp.status != 200:
                        raise RuntimeError(f"Download failed: HTTP {resp.status}")

                    content_length = resp.headers.get("Content-Length")
                    if expected_size and content_length and int(content_length) != int(expected_size):
                        raise ValueError(f"Size mismatch: expected {expected_size}, got {content_length}")

                    with open(tmp_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(chunk_size):
                            if not chunk:
                                break
                            total_size += len(chunk)
                            sha256_hash.update(chunk)
                            f.write(chunk)

            actual_sha256 = sha256_hash.hexdigest()
            if expected_sha256 and actual_sha256 != expected_sha256:
                raise ValueError(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")

            if expected_size and total_size != int(expected_size):
                raise ValueError(f"Size mismatch: expected {expected_size}, got {total_size}")

            tmp_path.replace(dest_path)
            return actual_sha256, total_size
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
            raise
    
    async def _handle_install_module_package(
        self,
        name: Optional[str],
        version: Optional[str],
        package_b64: Optional[str],
        download_url: Optional[str],
        sha256: Optional[str],
        size: Optional[int],
        actor_role: str,
        meta: ToolMeta,
        *,
        replace_if_different_sha: bool = False
    ) -> ToolResponse:
        """
        Обработка команды 'install_module_package' - установка динамического модуля из пакета.
        
        Поддерживает два режима:
        1. download_url (новый): скачивает ZIP по HTTP, проверяет sha256, устанавливает
        2. package_b64 (fallback): работает как раньше (для совместимости)
        
        Args:
            name: Имя модуля
            version: Версия модуля
            package_b64: ZIP-архив модуля в формате base64 (fallback)
            download_url: URL для скачивания ZIP (новый способ)
            sha256: SHA256 хеш архива (обязателен для download_url)
            size: Размер файла в байтах (опционально, для проверки)
            actor_role: Роль актора для проверки прав доступа
            meta: Метаданные выполнения команды
            replace_if_different_sha: При конфликте SHA (та же версия, другой хеш) удалить старый каталог и установить заново.
        
        Returns:
            ToolResponse с результатом установки модуля
        """
        try:
            # 1) Gate: проверка прав доступа (admin — с админки, system — серверная установка, например reconcile)
            if actor_role not in ("admin", "system"):
                return fail(
                    code="FORBIDDEN",
                    message="admin only",
                    meta=meta,
                    retriable=False
                )
            
            # 2) Validate input: проверка обязательных параметров
            if not name:
                return fail(
                    code="INSTALL_FAILED",
                    message='Не указано имя модуля (поле "name" или "module_name")',
                    meta=meta
                )
            
            if not version:
                return fail(
                    code="INSTALL_FAILED",
                    message='Не указана версия модуля (поле "version" или "module_version")',
                    meta=meta
                )
            
            if name.lower() in BUILTIN_PACKAGE_INSTALL_MODULES:
                logger.info(
                    f"Builtin module package install skipped: {name}/{version} "
                    f"(already bundled with agent)"
                )
                return ok(
                    data=ToolData(observations={
                        "module_name": name,
                        "module_version": version,
                        "skipped": True,
                        "reason": "builtin_module",
                        "message": (
                            f"Module {name}/{version} is bundled with the agent and "
                            "does not require package installation."
                        ),
                    }),
                    meta=meta,
                )

            zip_bytes = None
            
            # 3) Download or decode: получение ZIP файла
            if download_url:
                # Режим 1: HTTP download
                if not sha256:
                    return fail(
                        code="INSTALL_FAILED",
                        message="sha256 is required when using download_url",
                        meta=meta
                    )
                
                if aiohttp is None:
                    return fail(
                        code="INSTALL_FAILED",
                        message="aiohttp is required for download_url mode",
                        meta=meta
                    )
                
                try:
                    zip_bytes = await self._download_module_zip(download_url, sha256, size)
                    logger.info(f"📦 Модуль '{name}' версии '{version}' скачан по HTTP")
                except Exception as e:
                    error_msg = f"Ошибка скачивания модуля: {str(e)}"
                    error_msg = f"Module download failed: {str(e)}"
                    logger.error(error_msg)
                    return fail(
                        code="MODULE_DOWNLOAD_FAILED",
                        message=error_msg,
                        meta=meta,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)}
                    )
            elif package_b64:
                # Режим 2: Fallback (старый способ)
                try:
                    zip_bytes = base64.b64decode(package_b64)
                    logger.info(f"📦 Модуль '{name}' версии '{version}' получен через base64")
                except Exception as e:
                    error_msg = f"Ошибка декодирования base64: {str(e)}"
                    error_msg = f"Base64 decode failed: {str(e)}"
                    logger.error(error_msg)
                    return fail(
                        code="INSTALL_FAILED",
                        message="invalid base64",
                        meta=meta,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)}
                    )
            else:
                return fail(
                    code="INSTALL_FAILED",
                    message='Не указан пакет модуля (поле "package_b64" или "download_url")',
                    meta=meta
                )
            
            logger.info(f"📦 Установка модуля '{name}' версии '{version}' из пакета")
            
            # 4) Install: установка модуля (идемпотентно по SHA: same name+version+same sha -> no-op)
            result = None
            already_installed = False
            try:
                result = self.module_manager.install_zip_bytes(
                    zip_bytes, expected_sha256=sha256, replace_if_different_sha=replace_if_different_sha
                )
            except ValueError as e:
                err_str = str(e)
                if "INSTALL_CONFLICT_SHA" in err_str:
                    return fail(
                        code="INSTALL_CONFLICT_SHA",
                        message="Та же имя+версия уже установлена с другим SHA. Удалите версию или установите пакет с тем же SHA.",
                        meta=meta,
                        details={"module_name": name, "module_version": version},
                        retriable=False,
                    )
                if "already installed" in err_str.lower():
                    already_installed = True
                    # Модуль уже установлен — активируем и загружаем, возвращаем успех
                    target_path = self.module_manager.store_root / name / version
                    if not target_path.exists():
                        return fail(
                            code="INSTALL_FAILED",
                            message=str(e),
                            meta=meta,
                            details={"module_name": name, "module_version": version}
                        )
                    try:
                        import json
                        manifest_path = target_path / "manifest.json"
                        with open(manifest_path, "r", encoding="utf-8") as f:
                            manifest = json.load(f)
                        result = {
                            "module_name": name,
                            "module_version": version,
                            "path": str(target_path),
                            "manifest": manifest
                        }
                        logger.info(f"Модуль '{name}' версии '{version}' уже установлен, активируем и загружаем")
                    except Exception as read_e:
                        return fail(
                            code="INSTALL_FAILED",
                            message=f"Модуль уже установлен, но не удалось прочитать manifest: {read_e}",
                            meta=meta,
                            details={"module_name": name, "module_version": version}
                        )
                else:
                    raise
            except Exception as e:
                error_msg = f"Ошибка установки модуля: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
                )
            
            # Проверка соответствия имени и версии
            if result["module_name"] != name:
                return fail(
                    code="INSTALL_FAILED",
                    message=f'Несоответствие имени модуля: ожидалось "{name}", получено "{result["module_name"]}"',
                    meta=meta,
                    details={"expected_name": name, "actual_name": result["module_name"]}
                )
            
            if result["module_version"] != version:
                return fail(
                    code="INSTALL_FAILED",
                    message=f'Несоответствие версии модуля: ожидалось "{version}", получено "{result["module_version"]}"',
                    meta=meta,
                    details={"expected_version": version, "actual_version": result["module_version"]}
                )
            
            if already_installed:
                logger.success(f"Модуль '{name}' версии '{version}' уже установлен, активация и загрузка выполнены")
            else:
                logger.success(f"Модуль '{name}' версии '{version}' успешно установлен")
            
            # 5) Activate: активация модуля
            try:
                active_path = self.module_manager.activate(name, version)
                logger.info(f"Модуль '{name}' версии '{version}' активирован: {active_path}")
            except Exception as e:
                error_msg = f"Ошибка активации модуля: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                # Откат: модуль не должен оставаться на диске, если не работает
                try:
                    self.module_manager.remove_version_force(name, version)
                    logger.info(f"Откат: версия {name}@{version} удалена с диска после сбоя активации")
                except Exception as rollback_e:
                    logger.warning(f"Не удалось удалить каталог при откате: {rollback_e}")
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
                )
            
            # 6) Validate load: проверяем, что новая версия импортируется без runtime cache от предыдущей.
            try:
                entrypoint = result["manifest"].get("entrypoint", "module:register")
                self.loader.load_module_from_path(name, active_path, entrypoint=entrypoint)
                self.loader.unload_module(name)
                logger.success(f"Модуль '{name}' успешно прошел validate load")
            except Exception as e:
                self.loader.unload_module(name)
                error_msg = f"Ошибка загрузки модуля: {str(e)}"
                logger.error(error_msg)
                logger.exception(e)
                # Откат: нерабочий модуль не оставляем на диске (решает зависшие модули и конфликт SHA)
                try:
                    self.module_manager.remove_version_force(name, version)
                    logger.info(f"Откат: версия {name}@{version} удалена с диска после сбоя загрузки")
                except Exception as rollback_e:
                    logger.warning(f"Не удалось удалить каталог при откате: {rollback_e}")
                return fail(
                    code="INSTALL_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={"module_name": name, "module_version": version, "entrypoint": entrypoint, "exception_type": type(e).__name__}
                )
            
            # 7) Rebuild registry: используем rebuild вместо прямого register
            # Это обеспечит единообразную обработку и автоматическую отправку tools_changed
            self._purge_module_runtime(name)
            await self._rebuild_registry_from_active_modules()
            logger.debug(f"Реестр модулей пересобран после установки '{name}'")

            # 7b) GC: оставляем только current+prev версии
            if self.module_manager:
                try:
                    removed_versions = self.module_manager.garbage_collect(name, keep=2)
                    if removed_versions:
                        logger.info(
                            f"[GC] Удалены старые версии {name}: {removed_versions} (оставлены current+prev)"
                        )
                except Exception as gc_e:
                    logger.warning(f"[GC] Ошибка GC для '{name}': {gc_e}")

            # 7c) Публикуем module_state_changed device_event
            await self._emit_module_state_changed(reason=f"install:{name}@{version}")

            # 8) Return ok
            observations = {
                "installed": name,
                "version": version,
                "path": str(active_path),
                "mode": "package"
            }
            if already_installed:
                observations["already_installed"] = True
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"Ошибка установки модуля '{name}': {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="INSTALL_FAILED",
                message=error_msg,
                meta=meta,
                details={"module_name": name, "module_version": version, "exception_type": type(e).__name__}
            )
    
    async def _download_module_zip(
        self,
        download_url: str,
        expected_sha256: Optional[str],
        expected_size: Optional[int]
    ) -> bytes:
        """
        Скачивает ZIP модуля по HTTP с проверкой sha256.
        
        Phase 6: Отправляет токен в Authorization header (Bearer token).
        
        Args:
            download_url: URL для скачивания
            expected_sha256: Ожидаемый SHA256 хеш (обязателен)
            expected_size: Ожидаемый размер файла (опционально)
        
        Returns:
            bytes: Байты ZIP файла
        
        Raises:
            ValueError: Если sha256 не совпадает
            aiohttp.ClientError: Если download failed
        """
        if aiohttp is None:
            raise ImportError("aiohttp is required for download_url mode")
        
        # Phase 6: Получаем токен из identity_manager для аутентификации
        headers = {}
        if self.identity_manager and self.identity_manager.has_token:
            token = self.identity_manager.token
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logger.debug(f"[DownloadModule] Using token for download: {token[:8]}...")
            else:
                logger.warning("[DownloadModule] Identity manager has token flag but token is None")
        else:
            logger.warning("[DownloadModule] No token available for download authentication")
        
        # Скачиваем во временный файл (streaming)
        temp_file = None
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url, headers=headers) as response:
                    error_details = ""
                    if response.status != 200:
                        try:
                            error_payload = await response.json(content_type=None)
                        except Exception:
                            error_payload = None
                        if isinstance(error_payload, dict):
                            parts = []
                            if error_payload.get("error_code"):
                                parts.append(str(error_payload["error_code"]))
                            if error_payload.get("error"):
                                parts.append(str(error_payload["error"]))
                            if error_payload.get("hint"):
                                parts.append(str(error_payload["hint"]))
                            if parts:
                                error_details = " [" + " | ".join(parts) + "]"
                    if response.status == 401:
                        raise aiohttp.ClientError(
                            f"Download failed: Authentication required (HTTP 401). "
                            f"Token may be missing or invalid.{error_details}"
                        )
                    if response.status != 200:
                        raise aiohttp.ClientError(
                            f"Download failed: HTTP {response.status}{error_details}"
                        )
                    
                    # Проверка размера (если указан)
                    if expected_size:
                        content_length = response.headers.get('Content-Length')
                        if content_length and int(content_length) != expected_size:
                            raise ValueError(f"Size mismatch: expected {expected_size}, got {content_length}")
                    
                    # Создаем временный файл
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                    
                    # Потоковое скачивание с вычислением sha256
                    sha256_hash = hashlib.sha256()
                    async for chunk in response.content.iter_chunked(8192):
                        temp_file.write(chunk)
                        sha256_hash.update(chunk)
                    
                    temp_file.close()
                    
                    # Проверка sha256
                    actual_sha256 = sha256_hash.hexdigest()
                    if expected_sha256 and actual_sha256 != expected_sha256:
                        os.unlink(temp_file.name)
                        raise ValueError(f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}")
                    
                    # ТЕХНИЧЕСКИЙ ДОЛГ: Сейчас читаем файл в память, т.к. install_zip_bytes ожидает bytes.
                    # В перспективе: изменить install_zip_bytes чтобы принимать path/file-like объект,
                    # чтобы большие архивы (>100MB) не держались в RAM.
                    with open(temp_file.name, 'rb') as f:
                        zip_bytes = f.read()
                    
                    # Удаляем временный файл
                    os.unlink(temp_file.name)
                    
                    return zip_bytes
        
        except Exception as e:
            # Очистка при ошибке
            if temp_file and os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise
    
    async def _handle_exec_script(
        self, 
        code: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        Обработка команды 'exec_script' - выполнение скрипта в памяти.
        
        Args:
            code: Исходный код скрипта (должен содержать async функцию run)
            actor_role: Роль актора для проверки прав доступа
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом выполнения скрипта
        """
        try:
            # Проверка прав доступа: только admin
            if actor_role != "admin":
                return fail(code="FORBIDDEN", message="admin only", meta=meta, retriable=False)
            
            # Проверка настройки безопасности: allow_remote_code должен быть True
            if get_config().security.allow_remote_code != True:
                return fail(code="REMOTE_CODE_DISABLED", message="Remote code execution disabled", meta=meta, retriable=False)
            
            # Проверка наличия кода
            if not code:
                return fail(
                    code="EXEC_DISABLED",
                    message='Не указан код скрипта (поле "code")',
                    meta=meta
                )
            
            logger.info("Выполнение скрипта в памяти")
            
            # Валидация кода
            validation_result = CodeValidator.validate(code)
            
            if validation_result != 'function':
                error_msg = f"Код должен содержать асинхронную функцию 'run'. Получен тип: {validation_result}"
                logger.error(error_msg)
                return fail(
                    code="EXEC_DISABLED",
                    message=error_msg,
                    meta=meta,
                    details={"validation_result": validation_result}
                )
            
            logger.success("Код скрипта валиден")
            
            # ========== СОЗДАНИЕ КОНТЕКСТА ВЫПОЛНЕНИЯ ==========
            # Базовый namespace с встроенными функциями
            script_globals = {
                '__builtins__': __builtins__,
                # Базовые библиотеки
                'json': json,
                'datetime': datetime,
                'timedelta': timedelta,
                # Логгер
                'logger': logger,
                # ProcessProvider (синглтон)
                'ProcessProvider': ProcessProvider,
                'registry': self.registry,
            }
            
            # ========== АВТОМАТИЧЕСКИЙ ПРОБРОС МОДУЛЕЙ ==========
            # Итерация по всем загруженным модулям
            modules_added = []
            for module in self.loaded_modules:
                module_name = module.name
                
                # Проверка конфликта имен
                if module_name in script_globals:
                    # Конфликт с системной переменной
                    prefixed_name = f"mod_{module_name}"
                    logger.warning(
                        f"вљ пёЏ Конфликт имен: модуль '{module_name}' переименован в '{prefixed_name}'"
                    )
                    script_globals[prefixed_name] = module
                    modules_added.append(prefixed_name)
                else:
                    # Нормальное добавление модуля
                    script_globals[module_name] = module
                    modules_added.append(module_name)
            
            logger.info(f"📦 Модули доступны в скрипте: {modules_added}")
            
            # ========== ВЫПОЛНЕНИЕ КОДА ==========
            exec(code, script_globals)
            
            # Проверяем, что функция run существует
            if 'run' not in script_globals:
                return fail(
                    code="EXEC_FAILED",
                    message='Функция run не найдена в коде',
                    meta=meta
                )
            
            # Вызываем асинхронную функцию run
            result = await script_globals['run']()
            
            logger.success(f"OK Скрипт выполнен успешно. Результат: {result}")
            
            # Возвращаем результат через observations
            observations = {
                'result': result,
                'modules_available': modules_added
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"Ошибка выполнения скрипта: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="EXEC_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_get_manifest(self, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'get_manifest' - получение манифеста всех модулей.
        
        Возвращает манифест в формате:
        {
            'module_name': {
                'description': '...',
                'methods': {
                    'tool_name': {
                        'tool_name': '...',
                        'module_name': '...',
                        'description': '...',
                        'parameters': [...],
                        'async': True/False
                    }
                }
            }
        }
        
        Args:
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с полным манифестом системы (модули + core команды)
        """
        try:
            logger.info("Получение манифеста модулей")
            
            # Получаем манифест от всех зарегистрированных модулей
            manifest = self.registry.get_all()
            
            # Добавляем секцию "core" с системными командами
            manifest['core'] = {
                'description': 'Системные команды ядра оркестратора',
                'methods': {
                    'exec_script': {
                        'tool_name': 'exec_script',
                        'module_name': 'core',
                        'description': 'Выполнение скрипта в памяти. Скрипт должен содержать асинхронную функцию run(). В контексте доступны все загруженные модули, logger, ProcessProvider и стандартные библиотеки (json, datetime, timedelta).',
                        'parameters': [
                            {
                                'name': 'code',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            }
                        ],
                        'async': True,
                        'risk_level': 'break_glass',
                        'metadata': {
                            'risk_level': 'code_exec',
                            'scopes': [],
                            'requires_consent': False,
                            'allow_roles': ['admin']
                        }
                    },
                    'install_module_package': {
                        'tool_name': 'install_module_package',
                        'module_name': 'core',
                        'description': 'Установка динамического модуля из пакета (ZIP в base64). Требует роль admin.',
                        'parameters': [
                            {
                                'name': 'name',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'version',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'package_b64',
                                'type': 'str',
                                'kind': 'positional_or_keyword'
                            },
                            {
                                'name': 'sha256',
                                'type': 'Optional[str]',
                                'kind': 'positional_or_keyword',
                                'default': None
                            }
                        ],
                        'async': True,
                        'risk_level': 'write_action',
                        'metadata': {
                            'risk_level': 'system_write',
                            'scopes': ['pkg'],
                            'requires_consent': False,
                            'allow_roles': ['admin']
                        }
                    },
                    'update_agent': {
                        'tool_name': 'update_agent',
                        'module_name': 'core',
                        'description': 'Обновление агента до указанной версии (или до последней доступной версии, если версия не указана). Скачивает, проверяет и применяет обновление.',
                        'parameters': [
                            {
                                'name': 'version',
                                'type': 'Optional[str]',
                                'kind': 'positional_or_keyword',
                                'default': None
                            }
                        ],
                        'async': True
                    }
                }
            }
            
            logger.success(f"Манифест получен: {len(manifest)} разделов")
            logger.debug(f"Разделы манифеста: {list(manifest.keys())}")
            
            observations = {
                'manifest': manifest
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"Ошибка получения манифеста: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    def _build_tools_list(self) -> List[Dict[str, Any]]:
        """
        Строит список tools в формате list_tools (для handshake hash и list_tools ответа).
        
        КРИТИЧНО: Этот метод должен возвращать ТОЧНО тот же формат, что и _handle_list_tools().
        Hash считается от полного tool_info (не упрощённого), чтобы изменения spec 
        (params_schema, metadata) правильно отражались в hash.
        
        Returns:
            Список tool dictionaries с полями tool, module, spec (полный формат)
        """
        # Получаем плоский список всех tools из registry
        tools_flat = self.registry.get_tools_flat()
        
        # Формируем список инструментов (полный формат как в _handle_list_tools)
        tools_list = []
        for tool_data in tools_flat:
            tool_name = tool_data.get('tool')
            module_name = tool_data.get('module')
            spec = tool_data.get('spec', {})
            
            # Извлекаем metadata из spec
            metadata = spec.get('metadata', {})
            if not metadata:
                # Если metadata отсутствует, проставляем default
                metadata = {
                    'risk_level': 'safe_read',
                    'scopes': [],
                    'requires_consent': False,
                    'allow_roles': None
                }
            
            # Получаем presets из spec
            presets = spec.get('presets', [])
            
            # Если presets пусто и модуль не требует параметров (или имеет только опциональные),
            # добавляем дефолтный пресет "Запустить"
            params_schema = spec.get('params_schema', {})
            properties = params_schema.get('properties', {})
            
            # Проверяем, есть ли обязательные параметры
            has_required_params = False
            if properties:
                for prop_name, prop_schema in properties.items():
                    # Если параметр не имеет default значения, считаем его обязательным
                    if 'default' not in prop_schema:
                        has_required_params = True
                        break
            
            # Если нет presets и нет обязательных параметров, добавляем дефолтный пресет
            if not presets and not has_required_params:
                presets = [{
                    'id': 'default',
                    'name': '▶️ Запустить',
                    'description': 'Запустить с параметрами по умолчанию',
                    'params': {}
                }]
            
            # Формируем структуру tool с вложенным spec (полный формат)
            tool_info = {
                'tool': tool_name,
                'module': module_name,
                'spec': {
                    'description': spec.get('description', 'Описание отсутствует'),
                    'risk_level': spec.get('risk_level', 'safe_readonly'),
                    'capabilities': spec.get('capabilities'),
                    'params_schema': params_schema,
                    'presets': presets,
                    'metadata': {
                        'risk_level': metadata.get('risk_level', 'safe_read'),
                        'scopes': metadata.get('scopes', []),
                        'requires_consent': metadata.get('requires_consent', False),
                        'allow_roles': metadata.get('allow_roles')
                    }
                }
            }
            tools_list.append(tool_info)
        
        # НЕ сортируем здесь - сортировка выполняется в compute_toolset_hash()
        return tools_list
    
    async def _handle_list_tools(self, meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'list_tools' - возвращает список всех доступных инструментов.
        
        Возвращает список инструментов без полной информации о параметрах
        (только name, module, description, risk_level, capabilities).
        
        Args:
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse со списком инструментов в observations.tools
        """
        try:
            logger.info("Получение списка инструментов")

            await self._ensure_all_package_runtime_matches_inventory()
            
            # Используем _build_tools_list() для единообразия
            tools_list = self._build_tools_list()
            
            logger.success(f"Найдено инструментов: {len(tools_list)}")
            
            observations = {
                'tools': tools_list
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"Ошибка получения списка инструментов: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_describe_tool(self, tool_name: Optional[str], meta: ToolMeta) -> ToolResponse:
        """
        Обработка команды 'describe_tool' - возвращает полную информацию об инструменте.
        
        Возвращает полную информацию об инструменте, включая parameters, params_schema,
        risk_level, capabilities, async статус.
        
        Args:
            tool_name: Имя инструмента для описания
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с полной информацией об инструменте в observations.tool
            или fail с кодом TOOL_NOT_FOUND, если инструмент не найден
        """
        try:
            if not tool_name:
                return fail(
                    code="TOOL_NOT_FOUND",
                    message='Не указано имя инструмента (поле "tool" отсутствует или пустое)',
                    meta=meta,
                    retriable=False
                )
            
            logger.info(f"Получение описания инструмента: {tool_name}")
            
            # Получаем плоский список всех tools из registry
            tools_flat = self.registry.get_tools_flat()
            
            # Ищем tool по имени
            tool_found = None
            for tool_data in tools_flat:
                if tool_data.get('tool') == tool_name:
                    tool_found = tool_data
                    break
            
            if not tool_found:
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'Инструмент "{tool_name}" не найден в реестре',
                    meta=meta,
                    retriable=False
                )
            
            # Формируем полную информацию об инструменте
            spec = tool_found.get('spec', {})
            tool_info = {
                'name': tool_found.get('tool'),
                'module': tool_found.get('module'),
                'description': spec.get('description', 'Описание отсутствует'),
                'parameters': spec.get('parameters', []),
                'params_schema': spec.get('params_schema', {}),
                'risk_level': spec.get('risk_level', 'safe_readonly'),
                'capabilities': spec.get('capabilities'),
                'async': spec.get('async', False)
            }
            
            logger.success(f"Инструмент найден: {tool_name}")
            
            observations = {
                'tool': tool_info
            }
            
            data = ToolData(observations=observations)
            return ok(data=data, meta=meta)
            
        except Exception as e:
            error_msg = f"Ошибка получения описания инструмента: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    def _session_key_from_command(self, meta: ToolMeta, params: Dict[str, Any]) -> str:
        """
        Извлекает session_key из параметров команды.
        
        MVP: возвращает params.get("chat_job_id") or meta.request_id
        
        Args:
            meta: Метаданные команды
            params: Параметры команды
        
        Returns:
            session_key: строка-ключ сессии
        """
        return (
            params.get("chat_job_id")
            or params.get("session_key")
            or meta.request_id
            or str(uuid.uuid4())
        )
    
    def _redact_params(self, tool: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        def _hash_payload(self, params: Dict[str, Any]) -> str:
            """Вычисляет SHA256 хеш параметров для идемпотентности."""
            canonical = json.dumps(params, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        """
        Скрывает чувствительные ключи в параметрах для безопасного отображения.
        
        Скрывает ключи по маске: password, token, secret, api_key, key, auth
        
        Args:
            tool: Имя инструмента (опционально, для будущего использования)
            params: Словарь параметров
        
        Returns:
            Словарь с скрытыми чувствительными значениями
        """
        if not isinstance(params, dict):
            return params
        
        redacted = {}
        sensitive_patterns = ["password", "token", "secret", "api_key", "key", "auth"]
        
        for key, value in params.items():
            key_lower = key.lower()
            # Проверяем, содержит ли ключ чувствительный паттерн
            is_sensitive = any(pattern in key_lower for pattern in sensitive_patterns)
            
            if is_sensitive:
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_params(tool, value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_params(tool, item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    async def _publish_chat_event(self, job_id: str, meta: ToolMeta, payload: dict, ticket_id: Optional[str] = None):
        if not job_id or not self.db_manager:
            return
        try:
            ev = dict(payload)
            ev.setdefault("job_id", job_id)
            ev.setdefault("ts", time.time())
            # КРИТИЧНО: ticket_id в приоритете из аргумента, затем из payload.
            event_ticket_id = ticket_id or ev.get("ticket_id")
            if event_ticket_id:
                ev["ticket_id"] = event_ticket_id
            event_device_id = getattr(meta, "device_id", None) or self.device_id
            if not event_device_id:
                logger.error(f"[chat_event] missing device_id for job_id={job_id}, event={ev.get('event')}")
                return
            await self.db_manager.enqueue_job_event(
                job_id=job_id,
                request_id=getattr(meta, "request_id", None),
                device_id=event_device_id,
                event_payload=ev
            )
            logger.debug(f"[chat_event] enqueued job_id={job_id} ticket_id={event_ticket_id} event={ev.get('event')}")
        except Exception as e:
            logger.exception(f"Failed to enqueue chat_event job_id={job_id}: {e}")
    
    async def _publish_screen_ui_done(self, tool: str, operation_id: str) -> None:
        """Публикует screen_capture_done или screen_recording_done и снимает регистрацию записи (этап 4)."""
        if tool == "screen.record":
            get_recording_controller().unregister(operation_id)
        event_type = "screen_capture_done" if tool == "screen.collect" else "screen_recording_done"
        if tool not in ("screen.collect", "screen.record"):
            return
        if self.ui_bus:
            event = {
                "event_type": event_type,
                "data": {"operation_id": operation_id},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await self.ui_bus.publish(event)
    
    async def _handle_run_tool(
        self,
        tool: Optional[str],
        params: Optional[Dict[str, Any]],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """
        Универсальный handler для запуска любого зарегистрированного tool.
        
        Поддерживает:
        - Встроенные tools и tools из пакетных модулей
        - Policy проверку через check_policy
        - Artifacts intent (_artifacts, _cleanup_paths)
        - Валидацию параметров через params_model (pydantic)
        - Единый формат ToolResponse
        
        Args:
            tool: Имя инструмента
            params: Параметры для передачи в tool (dict или None)
            actor_role: Роль актора для проверки политики доступа
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом выполнения инструмента
        """
        start_ts = time.time()
        
        # Разделяем command_params и tool_params для устранения бага "params перезатёрли"
        command_params = params  # теперь это обёртка
        if command_params is None:
            command_params = {}
        
        # Извлекаем tool из command_params
        tool = command_params.get("tool")
        
        tool_params = command_params.get("params", {}) or {}
        chat_job_id = command_params.get("chat_job_id")
        # КРИТИЧНО: Извлекаем ticket_id из command_params (передается из envelope команды)
        ticket_id = command_params.get("ticket_id") or tool_params.get("ticket_id")
        
        # 4.1 До PolicyEngine / до выполнения tool
        # Сразу после вычисления tool/tool_params/chat_job_id публикуем tool_requested
        if chat_job_id:
            await self._publish_chat_event(chat_job_id, meta, {
                "event": "tool_requested",
                "tool": tool or "<empty>",
                "actor_role": actor_role,
                "params_redacted": self._redact_params(tool, tool_params),
            }, ticket_id=ticket_id)
        
        # 3.1 Валидация входа
        if not tool:
            logger.error(f"[AGENT] run_tool fail tool=<empty> code=INVALID_REQUEST")
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool or "<empty>",
                    "ok": False,
                    "error": "INVALID_REQUEST: tool is required",
                }, ticket_id=ticket_id)
            return fail(
                code="INVALID_REQUEST",
                message="tool is required",
                meta=meta,
                retriable=False
            )
        
        # Диагностика
        logger.info(f"[AGENT] run_tool tool={tool} chat_job_id={chat_job_id} tool_params_keys={list(tool_params.keys())}")
        
        logger.info(f"[AGENT] run_tool start tool={tool} actor_role={actor_role} request_id={meta.request_id}")
        
        try:
            
            # Контракт (Этап 3 Playbook): только формат "module.tool"; короткое имя не допускается
            if "." not in tool:
                error_msg = 'Используйте формат "module.tool" (например ping_check.ping_host). Короткое имя не поддерживается.'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"INVALID_TOOL_FORMAT: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="INVALID_TOOL_FORMAT",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            parts = tool.split(".", 1)
            module_name = parts[0]
            tool_name = parts[1]
            module_info = None  # будет заполнен через get_tool
            await self._ensure_module_runtime_matches_inventory(module_name, full_tool_name=tool)
            tool_data_from_registry = self.registry.get_tool(tool)
            if not tool_data_from_registry:
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f'TOOL_NOT_FOUND: Инструмент "{tool}" не найден. Используйте формат module.tool.',
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'Инструмент "{tool}" не найден. Используйте формат module.tool.',
                    meta=meta,
                    retriable=False
                )
            module_info = self.registry.get_module(module_name)
            if not module_info:
                error_msg = f'Модуль "{module_name}" не найден в реестре'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"MODULE_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="MODULE_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            methods_info = module_info.get('methods', {})
            method_name = tool_data_from_registry.get("method_name")
            if not method_name:
                for method_name_key, method_info_item in methods_info.items():
                    method_tool_name = method_info_item.get('tool_name', method_name_key)
                    if method_tool_name == tool_name or f"{module_name}.{method_tool_name}" == tool:
                        method_name = method_info_item.get('real_method_name', method_name_key)
                        break
            if not method_name:
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result", "tool": tool, "ok": False,
                        "error": f"TOOL_NOT_FOUND: метод для {tool} не найден в реестре",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=f'Метод для инструмента "{tool}" не найден',
                    meta=meta,
                    retriable=False
                )
            
            # Находим instance модуля
            module_instance = None
            for module in self.loaded_modules:
                if module.name == module_name:
                    module_instance = module
                    break
            
            if not module_instance:
                error_msg = f'Экземпляр модуля "{module_name}" не найден в loaded_modules'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"MODULE_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="MODULE_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # Получаем метод из instance (method_name — имя метода в модуле)
            if not hasattr(module_instance, method_name):
                error_msg = f'Метод "{method_name}" не найден в модуле "{module_name}"'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            method = getattr(module_instance, method_name)
            if not callable(method):
                error_msg = f'Атрибут "{method_name}" в модуле "{module_name}" не является вызываемым'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_CALLABLE: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_CALLABLE",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # Получаем method_info из registry для policy check
            # (module_info уже получен выше, если tool не содержал точку)
            if module_info is None:
                module_info = self.registry.get_module(module_name)
                if not module_info:
                    error_msg = f'Модуль "{module_name}" не найден в реестре'
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_result",
                            "tool": tool,
                            "ok": False,
                            "error": f"MODULE_NOT_FOUND: {error_msg}",
                        }, ticket_id=ticket_id)
                    return fail(
                        code="MODULE_NOT_FOUND",
                        message=error_msg,
                        meta=meta,
                        retriable=False
                    )
            
            methods_info = module_info.get('methods', {})
            method_info = methods_info.get(method_name)
            
            if not method_info:
                # Fallback: если метод не найден в registry, но есть в instance
                method_info = {
                    'description': f'Метод {method_name} модуля {module_name}',
                    'risk_level': 'safe_readonly',
                    'capabilities': None,
                    'params_schema': {}
                }
            
            # 2) Валидация параметров через params_model (если задан)
            validated_dict = None
            params_model = getattr(method, '__tool_params_model__', None)
            
            if params_model is not None:
                # params_model задан - валидируем входной params
                if ValidationError is None:
                    logger.warning(
                        f"params_model задан для инструмента {tool}, но pydantic не установлен. "
                        "Пропускаю валидацию."
                    )
                else:
                    try:
                        # Валидируем tool_params через params_model
                        validated = params_model(**tool_params)
                        # Преобразуем в dict
                        validated_dict = validated.model_dump()
                        logger.debug(f"Параметры инструмента {tool} успешно валидированы через {params_model.__name__}")
                    except ValidationError as e:
                        # Ошибка валидации - возвращаем fail
                        error_msg = "Parameters validation failed"
                        if chat_job_id:
                            await self._publish_chat_event(chat_job_id, meta, {
                                "event": "tool_result",
                                "tool": tool,
                                "ok": False,
                                "error": f"INVALID_PARAMS: {error_msg}",
                            }, ticket_id=ticket_id)
                        return fail(
                            code="INVALID_PARAMS",
                            message=error_msg,
                            meta=meta,
                            details={
                                "errors": e.errors(),
                                "tool": tool
                            },
                            retriable=False
                        )
            
            # 3) Policy gate через PolicyEngine
            # Получаем spec через registry.get_tool для единой точки контроля доступа
            tool_spec = self.registry.get_tool(tool)
            if not tool_spec:
                error_msg = f'Инструмент "{tool}" не найден в реестре'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"TOOL_NOT_FOUND: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code="TOOL_NOT_FOUND",
                    message=error_msg,
                    meta=meta,
                    retriable=False
                )
            
            # Извлекаем metadata из spec
            spec_dict = tool_spec.get('spec', {})
            metadata_dict = spec_dict.get('metadata', {})
            
            # Если metadata отсутствует, проставляем default значения
            if not metadata_dict:
                metadata_dict = {
                    'risk_level': 'safe_read',
                    'scopes': [],
                    'requires_consent': False,
                    'allow_roles': None
                }
            
            # Преобразуем metadata в ToolMetadata
            try:
                metadata = ToolMetadata(**metadata_dict)
            except Exception as e:
                logger.warning(f"Ошибка создания ToolMetadata для {tool}: {e}, используем default")
                metadata = ToolMetadata()
            
            # Вызываем PolicyEngine для принятия решения
            decision = self.policy.decide(
                actor_role=actor_role,
                tool_name=tool,
                metadata=metadata,
                params=tool_params,
                context={
                    "request_id": meta.request_id,
                    "command": meta.command or "run_tool"
                }
            )
            
            # Проверяем решение политики
            # PolicyDecision - TypedDict (словарь), доступ через словарь
            decision_allow = decision.get("allow", False)
            decision_requires_consent = decision.get("requires_consent", False)
            decision_reason = decision.get("reason")
            decision_required_role = decision.get("required_role")
            
            if not decision_allow:
                # Если требуется согласие, создаем pending tool call и публикуем событие
                if decision_requires_consent:
                    session_key = self._session_key_from_command(meta, command_params)
                    consent_record = await self.consent_service.create_pending(
                        tool_name=tool,
                        params=tool_params,
                        payload_hash=self._hash_payload(tool_params),
                        request_id=meta.request_id,
                        session_key=session_key,
                        actor_role=actor_role,
                        ticket_id=command_params.get("ticket_id"),
                        job_id=command_params.get("job_id") or chat_job_id,
                        expires_in_sec=1800,
                    )
                    consent_token = consent_record.consent_token
                    
                    # Формируем событие consent_required
                    event = {
                        "event_type": "consent_required",
                        "data": {
                            "consent_token": consent_token,
                            "session_key": session_key,
                            "request_id": meta.request_id,
                            "device_id": getattr(meta, "device_id", None),
                            "actor_role": actor_role,
                            "tool_name": tool,
                            "reason": decision_reason,
                            "params_preview": self._redact_params(tool, tool_params),
                            "expires_in_sec": 3600
                        },
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Публикуем событие через EventBus
                    if self.ui_bus:
                        await self.ui_bus.publish(event)
                        logger.info(f"Событие consent_required опубликовано: consent_token={consent_token}, tool={tool}")
                    
                    # 7.2 Публикуем событие tool_waiting_consent в chat job
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_waiting_consent",
                            "tool": tool,
                            "consent_token": consent_token,
                            "risk_level": metadata.risk_level,
                            "reason": decision_reason,
                        }, ticket_id=ticket_id)
                    
                    # Возвращаем command_result с requires_consent
                    return fail(
                        code="CONSENT_REQUIRED",
                        message=decision_reason or f'Требуется согласие для выполнения инструмента "{tool}"',
                        meta=meta,
                        details={
                            "requires_consent": True,
                            "consent_token": consent_token,
                            "session_key": session_key,
                            "consent_state": ConsentState.WAITING_USER.value,
                            "tool": tool,
                            "risk_level": metadata.risk_level,
                            "reason": decision_reason,
                        },
                        retriable=False
                    )
                
                # Для других случаев (не requires_consent) возвращаем обычную ошибку
                # Определяем код ошибки на основе reason
                if decision_reason in ("ROLE_NOT_ALLOWED", "NOT_PERMITTED", "REMOTE_CODE_DISABLED"):
                    error_code = "FORBIDDEN"
                else:
                    # Для всех остальных случаев используем FORBIDDEN
                    error_code = "FORBIDDEN"
                
                # Формируем details
                details = {
                    "tool": tool,
                    "risk_level": metadata.risk_level,
                    "requires_consent": False,
                    "required_role": decision_required_role
                }
                
                error_msg = decision_reason or f'Доступ к инструменту "{tool}" запрещен для роли "{actor_role}"'
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": f"{error_code}: {error_msg}",
                    }, ticket_id=ticket_id)
                return fail(
                    code=error_code,
                    message=error_msg,
                    meta=meta,
                    details=details,
                    retriable=False
                )
            
            # 4) Валидация tool_params (если params_model не задан)
            if validated_dict is None:
                # params_model не задан - проверяем, что tool_params это dict
                if not isinstance(tool_params, dict):
                    error_msg = f'Параметры должны быть словарем (dict), получен тип: {type(tool_params).__name__}'
                    if chat_job_id:
                        await self._publish_chat_event(chat_job_id, meta, {
                            "event": "tool_result",
                            "tool": tool,
                            "ok": False,
                            "error": f"INVALID_PARAMS: {error_msg}",
                        }, ticket_id=ticket_id)
                    return fail(
                        code="INVALID_PARAMS",
                        message=error_msg,
                        meta=meta,
                        retriable=False
                    )
                # Используем оригинальные tool_params
                params_to_use = tool_params
            else:
                # Используем валидированные params
                params_to_use = validated_dict
            
            # Фильтруем params_to_use: передаём в метод только объявленные параметры (сервер может присылать preset_id и др.)
            try:
                sig = inspect.signature(method)
                has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                if not has_kwargs:
                    allowed = {k for k in sig.parameters if k != 'self'}
                    params_to_use = {k: v for k, v in params_to_use.items() if k in allowed}
            except Exception:
                pass
            
            # 5) Исполнение
            # 7.3 Публикуем событие tool_running перед вызовом инструмента (после разрешения policy)
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_running",
                    "tool": tool
                }, ticket_id=ticket_id)
            
            # КРИТИЧНО: operation_id берется из meta.request_id (это же command_id в Protocol V3)
            operation_id = meta.request_id
            
            # Этап 4: события UI для скриншота/записи — минимизация окна и STOP-кнопка
            if tool == "screen.collect" and self.ui_bus:
                await self.ui_bus.publish({
                    "event_type": "prepare_screen_capture",
                    "data": {"operation_id": operation_id},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                # Даём GUI время свернуть окно до захвата, иначе в кадр попадёт само приложение
                await asyncio.sleep(1.2)
            elif tool == "screen.record":
                get_recording_controller().register(operation_id)
                if self.ui_bus:
                    await self.ui_bus.publish({
                        "event_type": "prepare_screen_recording",
                        "data": {"operation_id": operation_id},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    await asyncio.sleep(1.2)
                # Этап 5: передаём operation_id в модуль для доступа к stop_event (RecordingController)
                params_to_use = dict(params_to_use)
                params_to_use["operation_id"] = operation_id
            
            # Создаем task для выполнения tool и регистрируем в running_tasks
            async def _execute_tool():
                """Внутренняя функция для выполнения tool в task."""
                try:
                    is_async = inspect.iscoroutinefunction(method)
                    
                    if is_async:
                        return await method(**params_to_use)
                    else:
                        # Выполняем sync метод в threadpool
                        return await asyncio.to_thread(method, **params_to_use)
                finally:
                    # Удаляем из running_tasks после завершения
                    self.running_tasks.pop(operation_id, None)
            
            # Регистрируем task в running_tasks
            task = asyncio.create_task(_execute_tool())
            self.running_tasks[operation_id] = task
            
            try:
                observations = await task
                
                # Убеждаемся, что результат - dict
                if not isinstance(observations, dict):
                    # Если метод вернул не dict, оборачиваем в dict
                    observations = {"result": observations}
                
            except Exception as e:
                error_msg = f'Ошибка выполнения инструмента "{tool}": {str(e)}'
                logger.error(error_msg)
                logger.exception(e)
                
                # 7.5 Публикуем событие tool_result при ошибке tool
                if chat_job_id:
                    await self._publish_chat_event(chat_job_id, meta, {
                        "event": "tool_result",
                        "tool": tool,
                        "ok": False,
                        "error": str(e),
                    }, ticket_id=ticket_id)
                
                # Этап 4: уведомление GUI о завершении захвата/записи (окно восстановить, STOP скрыть)
                await self._publish_screen_ui_done(tool, operation_id)
                
                return fail(
                    code="TOOL_EXEC_FAILED",
                    message=error_msg,
                    meta=meta,
                    details={
                        "tool": tool,
                        "exc_type": type(e).__name__,
                        "exc_message": str(e)
                    },
                    retriable=True
                )
            
            # Этап 4: уведомление GUI о завершении захвата/записи (успешный путь)
            await self._publish_screen_ui_done(tool, operation_id)
            
            # 3.6 Нормализация результата
            # Ожидание: observations это dict с данными и опционально _artifacts/_cleanup_paths
            if not isinstance(observations, dict):
                observations = {"result": observations}
            
            # Извлекаем artifacts intents
            artifact_intents_data = observations.get("_artifacts", [])
            cleanup_paths_data = observations.get("_cleanup_paths", [])
            
            # Извлекаем наблюдения (без ключей начинающихся с "_")
            observations_clean = {k: v for k, v in observations.items() if not k.startswith("_")}
            
            # 3.7 Обработка artifacts intents
            artifact_intents: list[ArtifactIntent] = []
            cleanup_paths: list[pathlib.Path] = []
            
            # Формируем ArtifactIntent из данных; добавляем ticket_id и operation_id в meta для сервера (доступ UI к артефакту по тикету)
            operation_id_for_upload = getattr(meta, "request_id", None)
            if artifact_intents_data and not ticket_id:
                logger.warning(
                    "[AGENT] Upload артефактов без ticket_id — в БД artifact.ticket_id будет null; "
                    "доступ из UI только по ticket_id в query (fallback по ticket_events)"
                )
            for item in artifact_intents_data:
                if isinstance(item, dict) and "local_path" in item:
                    try:
                        intent_meta = dict(item.get("meta") or {})
                        if ticket_id:
                            intent_meta["ticket_id"] = ticket_id
                        if operation_id_for_upload:
                            intent_meta["operation_id"] = operation_id_for_upload
                        artifact_intent = ArtifactIntent(
                            local_path=pathlib.Path(item["local_path"]),
                            name=item.get("name"),
                            mime=item.get("mime"),
                            kind=item.get("kind"),
                            ttl_seconds=item.get("ttl_seconds"),
                            meta=intent_meta
                        )
                        artifact_intents.append(artifact_intent)
                        logger.debug(f"Добавлен артефакт для загрузки: {item['local_path']}")
                    except Exception as e:
                        logger.warning(f"Ошибка создания ArtifactIntent для {item.get('local_path')}: {e}")
            
            # Формируем cleanup_paths
            for path_str in cleanup_paths_data:
                try:
                    cleanup_path = pathlib.Path(path_str)
                    cleanup_paths.append(cleanup_path)
                    logger.debug(f"Добавлен путь для очистки: {path_str}")
                except Exception as e:
                    logger.warning(f"Ошибка создания Path для cleanup: {path_str}: {e}")
            
            # Загружаем артефакты, если они есть
            uploaded_artifacts = []
            upload_errors = []
            
            if artifact_intents:
                try:
                    # Создаем uploader и ArtifactManager
                    if self.identity_manager:
                        uploader = get_uploader(identity_manager=self.identity_manager)
                    else:
                        uploader = get_uploader()
                    
                    artifact_manager = ArtifactManager(uploader)
                    
                    logger.info(f"📤 Начинаю загрузку {len(artifact_intents)} артефактов...")
                    uploaded_artifacts, upload_errors = await artifact_manager.upload_many(artifact_intents)
                    
                    logger.success(f"OK Загружено артефактов: {len(uploaded_artifacts)}/{len(artifact_intents)}")
                    
                    if upload_errors:
                        logger.warning(f"вљ пёЏ  Ошибок загрузки: {len(upload_errors)}")
                
                except Exception as e:
                    error_msg = f"Ошибка при загрузке артефактов: {e}"
                    logger.error(f"ERROR {error_msg}")
                    upload_error_info = ErrorInfo(
                        code="ARTIFACT_UPLOAD_SYSTEM_ERROR",
                        message=error_msg,
                        details={"exception_type": type(e).__name__, "exception_message": str(e)},
                        retriable=True
                    )
                    upload_errors.append(upload_error_info)
            
            # Очистка временных файлов (best-effort)
            if cleanup_paths:
                logger.info(f"Очистка {len(cleanup_paths)} временных файлов...")
                for cleanup_path in cleanup_paths:
                    try:
                        if cleanup_path.exists():
                            cleanup_path.unlink()
                            logger.debug(f"OK Удален временный файл: {cleanup_path}")
                    except Exception as e:
                        logger.warning(f"вљ пёЏ  Не удалось удалить временный файл {cleanup_path}: {e}")
            
            # 3.8 Формирование ToolResponse
            duration_ms = int((time.time() - start_ts) * 1000)
            meta.duration_ms = duration_ms
            meta.command = "run_tool"
            
            warnings = []
            if upload_errors:
                warnings.extend([f"Ошибка загрузки артефакта: {e.message}" for e in upload_errors])
            
            data = ToolData(
                observations=observations_clean,
                artifacts=uploaded_artifacts,
                warnings=warnings if warnings else []
            )
            
            # 7.4 Публикуем событие tool_result после успешного результата
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool,
                    "ok": True,
                }, ticket_id=ticket_id)
            
            # Если есть ошибки загрузки, но основной результат успешен - partial
            if upload_errors:
                logger.warning(f"[AGENT] run_tool partial tool={tool} duration_ms={duration_ms} artifacts={len(uploaded_artifacts)} upload_errors={len(upload_errors)}")
                return partial(data=data, meta=meta, warnings=warnings, errors=upload_errors)
            else:
                logger.success(f"[AGENT] run_tool ok tool={tool} duration_ms={duration_ms} artifacts={len(uploaded_artifacts)}")
                return ok(data=data, meta=meta)
            
        except Exception as e:
            duration_ms = int((time.time() - start_ts) * 1000)
            error_msg = f"Ошибка в _handle_run_tool: {str(e)}"
            logger.error(f"[AGENT] run_tool fail tool={tool} code=COMMAND_FAILED exc={type(e).__name__}")
            logger.exception(e)
            
            # 7.5 Публикуем событие tool_result при ошибке tool (внешний exception handler)
            if chat_job_id:
                await self._publish_chat_event(chat_job_id, meta, {
                    "event": "tool_result",
                    "tool": tool,
                    "ok": False,
                    "error": str(e),
                }, ticket_id=ticket_id)
            
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_consent_decision(
        self,
        consent_token: Optional[str],
        approved: bool,
        session_key: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """
        Обработка команды 'consent_decision' - решение о согласии на выполнение инструмента.
        
        Args:
            consent_token: Токен согласия
            approved: Одобрено ли действие
            session_key: Ключ сессии (если не указан, вычисляется из meta)
            meta: Метаданные выполнения команды
        
        Returns:
            ToolResponse с результатом обработки решения
        """
        try:
            # Валидация параметров
            if not consent_token:
                return fail(
                    code="INVALID_REQUEST",
                    message="consent_token is required",
                    meta=meta,
                    retriable=False
                )
            
            # Если session_key не указан, используем request_id как fallback
            if not session_key:
                session_key = meta.request_id or str(uuid.uuid4())

            consent_record = await self.consent_service.apply_decision(
                consent_token=consent_token,
                approved=approved,
            )
            if consent_record.state == ConsentState.EXPIRED:
                return fail(
                    code="CONSENT_EXPIRED",
                    message=f"Consent token expired: {consent_token}",
                    meta=meta,
                    retriable=False
                )
            if not consent_record.pending:
                return fail(
                    code="UNKNOWN_CONSENT_TOKEN",
                    message=f"Unknown consent_token: {consent_token}",
                    meta=meta,
                    retriable=False
                )
            pending = consent_record.pending
            
            # Извлекаем данные из pending
            tool_name = pending["tool_name"]
            tool_params = pending["params"]  # это tool_params, не command_params
            actor_role = pending["actor_role"]
            pending_request_id = pending["request_id"]
            pending_device_id = pending.get("device_id")
            pending_session_key = pending.get("session_key")
            pending_ticket_id = pending.get("ticket_id")
            pending_job_id = pending.get("job_id")
            
            if consent_record.state == ConsentState.APPROVED:
                # Выполняем инструмент
                logger.info(f"OK Согласие получено, выполняю tool: {tool_name}, consent_token={consent_token}")
                
                # Добавляем consent_token в tool_params, чтобы PolicyEngine разрешил выполнение
                tool_params_with_consent = tool_params.copy()
                tool_params_with_consent["consent_token"] = consent_token
                
                # Восстанавливаем command_params структуру с полным контекстом.
                command_params = {
                    "tool": tool_name,
                    "params": tool_params_with_consent,
                    "chat_job_id": pending_job_id,
                    "job_id": pending_job_id,
                    "ticket_id": pending_ticket_id,
                }
                if pending_session_key:
                    command_params["session_key"] = pending_session_key
                
                # Вызываем _handle_run_tool с восстановленной command_params структурой
                result = await self._handle_run_tool(
                    tool=tool_name,
                    params=command_params,
                    actor_role=actor_role,
                    meta=meta
                )
                
                # Формируем событие tool_executed
                result_preview = None
                if result.status == "success" and result.data:
                    observations = result.data.observations if result.data.observations else {}
                    # Берем первые 200 символов результата как preview
                    result_str = str(observations)[:200]
                    result_preview = result_str + ("..." if len(str(observations)) > 200 else "")
                elif result.error:
                    result_preview = f"Error: {result.error.code} - {result.error.message}"
                
                event = {
                    "event_type": "tool_executed",
                    "data": {
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool_name": tool_name,
                        "ok": result.status == "success",
                        "result_preview": result_preview,
                        "request_id": pending_request_id,
                        "consent_state": ConsentState.RESOLVED.value,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Публикуем событие
                if self.ui_bus:
                    await self.ui_bus.publish(event)
                    logger.info(f"Событие tool_executed опубликовано: consent_token={consent_token}, tool={tool_name}")
                
                return result
            else:
                # Отклонено - публикуем событие tool_denied
                logger.info(f"ERROR Согласие отклонено: consent_token={consent_token}, tool={tool_name}")
                
                event = {
                    "event_type": "tool_denied",
                    "data": {
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool_name": tool_name,
                        "request_id": pending_request_id,
                        "consent_state": ConsentState.REJECTED.value,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Публикуем событие
                if self.ui_bus:
                    await self.ui_bus.publish(event)
                    logger.info(f"Событие tool_denied опубликовано: consent_token={consent_token}, tool={tool_name}")
                
                return fail(
                    code="CONSENT_DENIED",
                    message=f"Согласие на выполнение инструмента '{tool_name}' отклонено",
                    meta=meta,
                    details={
                        "consent_token": consent_token,
                        "session_key": session_key,
                        "tool": tool_name,
                    },
                    retriable=False
                )
        
        except Exception as e:
            error_msg = f"Ошибка обработки consent_decision: {str(e)}"
            logger.error(error_msg)
            logger.exception(e)
            return fail(
                code="COMMAND_FAILED",
                message=error_msg,
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
    
    async def _handle_start_job(
        self,
        job_type: Optional[str],
        params: Dict[str, Any],
        actor_role: str,
        device_id: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """Delegate job start handling to the extracted helper."""
        return await helper_handle_start_job(self, job_type, params, actor_role, device_id, meta)

    async def _handle_stop_job(
        self,
        job_id: Optional[str],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Delegate job stop handling to the extracted helper."""
        return await helper_handle_stop_job(self, job_id, actor_role, meta)

    async def _handle_get_job_status(
        self,
        job_id: Optional[str],
        meta: ToolMeta
    ) -> ToolResponse:
        """Delegate job status handling to the extracted helper."""
        return await helper_handle_get_job_status(self, job_id, meta)

    async def _handle_list_jobs(
        self,
        limit: int,
        meta: ToolMeta
    ) -> ToolResponse:
        """Delegate list-jobs handling to the extracted helper."""
        return await helper_handle_list_jobs(self, limit, meta)

    async def _handle_job_send_event(
        self,
        job_id: Optional[str],
        event: Optional[dict],
        actor_role: str,
        meta: ToolMeta
    ) -> ToolResponse:
        """Delegate job event delivery to the extracted helper."""
        return await helper_handle_job_send_event(self, job_id, event, actor_role, meta)

    def _format_uptime(self, seconds: float) -> str:
        """Delegate uptime formatting to the extracted helper."""
        return helper_format_uptime(seconds)

    async def shutdown(self) -> None:
        """
        Корректное завершение работы оркестратора.
        """
        logger.info("Завершение работы AgentOrchestrator")
        
        # Здесь можно добавить логику очистки ресурсов
        # - Закрытие соединений
        # - Сохранение состояния
        # - Завершение фоновых задач
        
        logger.success("AgentOrchestrator остановлен")


# ==================== ТЕСТИРОВАНИЕ ====================

async def test_tool_response_format():
    """
    Unit-тесты для проверки формата ToolResponse.
    """
    from core.database import db_manager
    
    logger.info("=" * 70)
    logger.info("Unit-тесты формата ToolResponse")
    logger.info("=" * 70)
    
    try:
        # Создаем оркестратор с тестовыми модулями
        orchestrator = AgentOrchestrator(
            db_manager=db_manager,
            enabled_modules=["system"],
            agent_uuid="test-agent-123"
        )
        
        # Инициализация
        await orchestrator.initialize()
        
        # Тест 1: ping возвращает ToolResponse
        logger.info("\n1пёЏвѓЈ Тест ping - формат ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'ping', 'request_id': 'test-request-1'})
        assert result['status'] in ['success', 'error', 'partial'], f"Неверный статус: {result.get('status')}"
        assert 'meta' in result, "Отсутствует поле meta"
        assert 'timestamp_iso' in result['meta'], "Отсутствует timestamp_iso в meta"
        assert 'command' in result['meta'], "Отсутствует command в meta"
        assert result['meta']['command'] == 'ping', f"Неверная команда: {result['meta']['command']}"
        assert result['meta']['request_id'] == 'test-request-1', "Неверный request_id"
        assert result['meta']['agent_id'] == 'test-agent-123', "Неверный agent_id"
        assert 'duration_ms' in result['meta'], "Отсутствует duration_ms в meta"
        if result['status'] == 'success':
            assert 'data' in result, "Отсутствует поле data"
            assert 'observations' in result['data'], "Отсутствует observations в data"
            assert 'message' in result['data']['observations'], "Отсутствует message в observations"
            assert 'agent' in result['data']['observations'], "Отсутствует agent в observations"
        logger.success("OK ping возвращает корректный ToolResponse")
        
        # Тест 2: list_modules возвращает ToolResponse
        logger.info("\n2пёЏвѓЈ Тест list_modules - формат ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'list_modules'})
        assert result['status'] == 'success', f"Неверный статус: {result.get('status')}"
        assert 'data' in result, "Отсутствует поле data"
        assert 'observations' in result['data'], "Отсутствует observations в data"
        assert 'modules' in result['data']['observations'], "Отсутствует modules в observations"
        assert isinstance(result['data']['observations']['modules'], list), "modules должен быть списком"
        logger.success("OK list_modules возвращает корректный ToolResponse")
        
        # Тест 3: collect возвращает ToolResponse с observations.results
        logger.info("\n3пёЏвѓЈ Тест collect - формат ToolResponse...")
        result = await orchestrator.handle_command({'cmd': 'collect', 'modules': ['system']})
        assert result['status'] in ['success', 'partial'], f"Неверный статус: {result.get('status')}"
        assert 'data' in result, "Отсутствует поле data"
        assert 'observations' in result['data'], "Отсутствует observations в data"
        assert 'results' in result['data']['observations'], "Отсутствует results в observations"
        assert isinstance(result['data']['observations']['results'], dict), "results должен быть словарем"
        logger.success("OK collect возвращает корректный ToolResponse")
        
        # Тест 4: неизвестная команда возвращает fail с кодом UNKNOWN_COMMAND
        logger.info("\n4пёЏвѓЈ Тест неизвестной команды - код ошибки UNKNOWN_COMMAND...")
        result = await orchestrator.handle_command({'cmd': 'unknown_command'})
        assert result['status'] == 'error', f"Неверный статус: {result.get('status')}"
        assert 'error' in result, "Отсутствует поле error"
        assert result['error']['code'] == 'UNKNOWN_COMMAND', f"Неверный код ошибки: {result['error']['code']}"
        logger.success("OK неизвестная команда возвращает fail с кодом UNKNOWN_COMMAND")
        
        # Тест 5: пустая команда возвращает fail с кодом UNKNOWN_COMMAND
        logger.info("\n5пёЏвѓЈ Тест пустой команды - код ошибки UNKNOWN_COMMAND...")
        result = await orchestrator.handle_command({})
        assert result['status'] == 'error', f"Неверный статус: {result.get('status')}"
        assert result['error']['code'] == 'UNKNOWN_COMMAND', f"Неверный код ошибки: {result['error']['code']}"
        logger.success("OK пустая команда возвращает fail с кодом UNKNOWN_COMMAND")
        
        # Тест 6: collect с несуществующим модулем возвращает partial с warnings
        logger.info("\n6пёЏвѓЈ Тест collect с несуществующим модулем - partial с warnings...")
        result = await orchestrator.handle_command({'cmd': 'collect', 'modules': ['nonexistent_module']})
        assert result['status'] in ['partial', 'error'], f"Неверный статус: {result.get('status')}"
        if result['status'] == 'partial':
            assert 'data' in result, "Отсутствует поле data"
            assert 'warnings' in result['data'], "Отсутствует warnings в data"
            assert len(result['data']['warnings']) > 0, "Должны быть warnings"
        logger.success("OK collect с несуществующим модулем возвращает partial с warnings")
        
        # Тест 7: exec_script возвращает результат через observations
        logger.info("\n7пёЏвѓЈ Тест exec_script - результат через observations...")
        test_code = """
async def run():
    return {"test": "result"}
"""
        result = await orchestrator.handle_command({'cmd': 'exec_script', 'code': test_code})
        assert result['status'] == 'success', f"Неверный статус: {result.get('status')}"
        assert 'data' in result, "Отсутствует поле data"
        assert 'observations' in result['data'], "Отсутствует observations в data"
        assert 'result' in result['data']['observations'], "Отсутствует result в observations"
        logger.success("OK exec_script возвращает результат через observations")
        
        # Тест 8: проверка отсутствия топ-левел timestamp
        logger.info("\n8пёЏвѓЈ Тест отсутствия топ-левел timestamp...")
        result = await orchestrator.handle_command({'cmd': 'ping'})
        assert 'timestamp' not in result, "Не должно быть топ-левел timestamp"
        assert 'timestamp_iso' in result['meta'], "timestamp_iso должен быть в meta"
        logger.success("OK топ-левел timestamp отсутствует, timestamp_iso в meta")
        
        # Завершение
        await orchestrator.shutdown()
        
        logger.info("=" * 70)
        logger.success("OK Все unit-тесты пройдены успешно!")
        logger.info("=" * 70)
        
    except AssertionError as e:
        logger.error(f"ERROR Ошибка в unit-тесте: {e}")
        raise
    except Exception as e:
        logger.error(f"ERROR Ошибка во время тестирования: {e}")
        logger.exception(e)
        raise


async def test_orchestrator():
    """
    Тестовая функция для проверки работы AgentOrchestrator.
    """
    from core.database import db_manager
    
    logger.info("=" * 70)
    logger.info("Начало тестирования AgentOrchestrator")
    logger.info("=" * 70)
    
    try:
        # Создаем оркестратор с тестовыми модулями
        orchestrator = AgentOrchestrator(
            db_manager=db_manager,
            enabled_modules=["system"]
        )
        
        # Инициализация
        logger.info("\n1пёЏвѓЈ Инициализация оркестратора...")
        await orchestrator.initialize()
        
        # Тест команды ping
        logger.info("\n2пёЏвѓЈ Тест команды 'ping'...")
        result = await orchestrator.handle_command({'cmd': 'ping'})
        logger.info(f"Результат ping: {result}")
        
        # Тест команды list_modules
        logger.info("\n3пёЏвѓЈ Тест команды 'list_modules'...")
        result = await orchestrator.handle_command({'cmd': 'list_modules'})
        logger.info(f"Результат list_modules: {result}")
        
        # Тест команды collect (все модули)
        logger.info("\n4пёЏвѓЈ Тест команды 'collect' (все модули)...")
        result = await orchestrator.handle_command({'cmd': 'collect'})
        logger.info(f"Результат collect: {result}")
        
        # Тест команды collect (конкретный модуль)
        logger.info("\n5пёЏвѓЈ Тест команды 'collect' (модуль system)...")
        result = await orchestrator.handle_command({
            'cmd': 'collect',
            'modules': ['system']
        })
        logger.info(f"Результат collect (system): {result}")
        
        # Тест команды update
        logger.info("\n6пёЏвѓЈ Тест команды 'update'...")
        result = await orchestrator.handle_command({
            'cmd': 'update',
            'version': '2.0.0'
        })
        logger.info(f"Результат update: {result}")
        
        # Тест команды exec_script
        logger.info("\n7пёЏвѓЈ Тест команды 'exec_script'...")
        test_code = """
async def run():
    return {"test": "result"}
"""
        result = await orchestrator.handle_command({
            'cmd': 'exec_script',
            'code': test_code
        })
        logger.info(f"Результат exec_script: {result}")
        
        # Тест неизвестной команды
        logger.info("\n8пёЏвѓЈ Тест неизвестной команды...")
        result = await orchestrator.handle_command({'cmd': 'unknown_command'})
        logger.info(f"Результат unknown_command: {result}")
        
        # Тест пустой команды
        logger.info("\n9пёЏвѓЈ Тест пустой команды...")
        result = await orchestrator.handle_command({})
        logger.info(f"Результат пустой команды: {result}")
        
        # Завершение
        await orchestrator.shutdown()
        
        logger.info("=" * 70)
        logger.success("OK Тестирование завершено успешно!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"ERROR Ошибка во время тестирования: {e}")
        logger.exception(e)
        raise


if __name__ == "__main__":
    import asyncio
    
    # Запускаем тестирование
    asyncio.run(test_orchestrator())
