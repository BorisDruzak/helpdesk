"""
WebSocket клиент для PC Agent с полной интеграцией модулей сбора данных.

Расширенная версия ws_agent.py с поддержкой:
- Реального сбора данных через модули PC Agent
- Универсального оркестратора для обработки команд
- Динамической загрузки модулей из конфигурации
- Сохранения данных в базу
- Расширенного протокола команд
"""

import asyncio
import json as jsonlib
import sys
import time
import socket
import platform
import uuid
import os
import argparse
import atexit
import queue
from urllib.parse import quote, urlparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import aiohttp
import aiohttp
from aiohttp import ClientSession, WSMsgType, ClientWebSocketResponse, ClientTimeout
from loguru import logger

# Добавляем путь к модулям PC Agent
# Добавляем родительскую директорию проекта для импорта from pc_agent.*
agent_dir = Path(__file__).resolve().parent
project_root = agent_dir.parent  # /var/chat_bot/pc_client
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
# Legacy managed modules still get their own import path from the module loader.
from pc_agent.core.database import DatabaseManager
from pc_agent.core.orchestrator import AgentOrchestrator
from pc_agent.core.identity import IdentityManager
from pc_agent.core.sender import WSOutboxFlusher
from pc_agent.core.job_manager import JobManager
from pc_agent.core.http_client import AioHttpClient
from pc_agent.config.config_loader import get_config, init_config
from pc_agent.core import runtime_paths
from pc_agent.core.runtime_logging import RuntimeLogBuffer, configure_runtime_logging, read_log_tail, format_log_tail
from pc_agent.core.action_trace import (
    configure_action_trace,
    get_action_trace_recorder,
    resolve_action_trace_text_filter,
    search_action_trace,
)
from pc_agent.network.uploader import get_uploader
from pc_agent.ui_bridge import EventBus, UiApiServer
from pc_agent.ui_bridge.models import ConsentDecision
from pc_agent.ui_gui.server_api import TicketApiClient
from pc_agent.ui_bridge.settings_service import AgentSettingsService
from pc_agent.core.database import PROTOCOL_VERSION, DB_SCHEMA_VERSION
from pc_agent.version import AGENT_VERSION, EXIT_UPDATE_PENDING
from pc_agent.core.single_instance import SingleInstanceLock
from pc_agent.auth.connection_request import run_connection_request_flow
from pc_agent.auth.gui_auth_state_machine import GuiAuthStateMachine
from pc_agent.auth.rejected_flag import connection_rejected_flag_path
from pc_agent.auth.token_source import load_auth_token, load_auth_token_from_db
from pc_agent.ws_agent_runtime_helpers import (
    authenticate as helper_authenticate,
    connection_rejected_flag_path_for,
    execute_scheduled_task as helper_execute_scheduled_task,
    format_uptime as helper_format_uptime,
    handle_scheduler_rpc as helper_handle_scheduler_rpc,
    request_connection_flow as helper_request_connection_flow,
    request_token_from_console as helper_request_token_from_console,
    restart_self as helper_restart_self,
    schedule_restart as helper_schedule_restart,
    schedule_update_shutdown as helper_schedule_update_shutdown,
    scheduler_error as helper_scheduler_error,
    scheduler_runtime_loop as helper_scheduler_runtime_loop,
    scheduler_success as helper_scheduler_success,
    shutdown_for_update as helper_shutdown_for_update,
)


def _configure_utf8_stdio() -> None:
    """Force UTF-8 for console streams to avoid mojibake on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 PROTOCOL V3 КОНСТАНТЫ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Разрешенные типы сообщений (Фаза 2.1)
ALLOWED_MESSAGE_TYPES = {
    "handshake_ack",
    "ping",
    "pong",
    "rpc_request",
    "rpc_response",
    "outbox_ack",
    "outbox_nack",
    "agent_observer_batch_ack",
    # Legacy support (будут удалены)
    "command",
    "command_result",
    "ack"
}

UPDATE_STATUS_CACHE_TTL_SEC = 300

# Методы требующие idempotency_key (Фаза 4.1, замечание 5)
IDEMPOTENT_METHODS = {
    "ticket_open",
    "ticket_closed",
    "start_job",
    "stop_job",
    "run_tool",
    "run_recipe",
    "schedule_task",
    "cancel_task",
    "task_run_now"
}

# Scheduler методы - заглушки (Фаза 7.1)
SCHEDULER_METHODS = {
    "schedule_task",
    "cancel_task",
    "list_tasks",
    "task_run_now"
}

# IDEMPOTENCY TTL (замечание 5)
IDEMPOTENCY_TTL_SECONDS = 3600  # 1 час

# In-progress: считаем запись «зависшей» после этого времени (сек), разрешаем повтор
IN_PROGRESS_STALE_SEC = 180  # 3 минуты

# Unknown message protection (замечание 6)
MAX_UNKNOWN_MESSAGES_PER_MINUTE = 10


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎯 КЛАСС АГЕНТА
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WSAgent:
    """
    WebSocket агент с интеграцией универсального оркестратора.
    
    Оркестратор предоставляет единую точку входа для обработки всех команд:
    - ping - проверка статуса
    - collect - сбор данных с модулей
    - list_modules - список доступных модулей
    - update - обновление агента (заглушка)
    - exec_script - выполнение скриптов (заглушка)
    
    Дополнительно ws_agent поддерживает:
    - get_status - статус агента с конфигурацией
    - get_info - системная информация
    - get_history - история событий из БД
    """
    
    def __init__(self, data_root: Optional[Path] = None, install_root: Optional[Path] = None):
        """Инициализация агента. data_root/install_root задаются из точки входа (runtime_paths)."""
        self._data_root: Optional[Path] = data_root
        self._install_root: Optional[Path] = install_root
        self.db_manager: Optional[DatabaseManager] = None
        self.orchestrator: Optional[AgentOrchestrator] = None
        self.identity_manager: Optional[IdentityManager] = None
        self.flusher: Optional[WSOutboxFlusher] = None
        self.flusher_task: Optional[asyncio.Task] = None
        self.server_capabilities: set[str] = set()
        self.device_id: Optional[str] = None  # Будет установлен из identity при initialize()
        self.start_time = time.time()
        self._http_session: Optional[ClientSession] = None
        self.http: Optional[AioHttpClient] = None
        self.auth_token: Optional[str] = None
        
        # UI Bridge компоненты
        self.event_bus: Optional[EventBus] = None
        self.ui_api_server: Optional[UiApiServer] = None
        self.ui_api_task: Optional[asyncio.Task] = None
        self.settings_service: Optional[AgentSettingsService] = None
        self._restart_task: Optional[asyncio.Task] = None
        self._runtime_log_buffer = RuntimeLogBuffer(limit=400)
        self._logging_runtime: Dict[str, Any] = {}
        self._last_connection_state: str = "initializing"
        self._last_connection_detail: str = ""
        self._last_connection_changed_at: Optional[str] = None
        self._cached_update_status: Dict[str, Any] = {}
        self._cached_update_checked_at: Optional[str] = None
        
        # Очередь и задача для публикации логов в EventBus
        # Используем обычную queue.Queue для синхронного sink
        self._log_queue: Optional[queue.Queue] = None
        self._log_publisher_task: Optional[asyncio.Task] = None
        self._housekeeping_task: Optional[asyncio.Task] = None
        self._consent_cleanup_task: Optional[asyncio.Task] = None
        self._scheduler_task: Optional[asyncio.Task] = None
        self._shutdown_task: Optional[asyncio.Task] = None
        self._run_task: Optional[asyncio.Task] = None
        self._requested_exit_code: int = 0
        
        # Process-local dedupe: command_id -> Future с результатом (для in_progress без дубля)
        self._running_commands: Dict[str, asyncio.Future] = {}
        self._background_command_tasks: set[asyncio.Task] = set()
        
        # WebSocket соединение с сервером (для chat_raise и других команд)
        self._agent_ws: Optional[ClientWebSocketResponse] = None
        self._ws_send_lock = asyncio.Lock()
        self._pending_chat_raise: Dict[str, asyncio.Future] = {}  # request_id -> Future
        
        # Protocol V3: Session ID для tracking unknown messages
        self._session_id: str = str(uuid.uuid4())
        
        # Protocol V3: Idempotency GC task
        self._idempotency_gc_task: Optional[asyncio.Task] = None
        
        # Protocol V3: Current trace_id для корреляции запросов
        self._current_trace_id: Optional[str] = None
        
        # Protocol V3: Current ticket_id и job_id контекст
        self._current_ticket_id: Optional[str] = None
        self._current_job_id: Optional[str] = None
        self._pending_agent_observer_upload: Optional[Dict[str, Any]] = None

    def _agent_observer_upload_state_path(self) -> Path:
        data_root = self._data_root or runtime_paths.resolve_data_root()
        logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))
        logs_dir.mkdir(parents=True, exist_ok=True)
        return logs_dir / "action_trace_upload_state.json"

    def _load_agent_observer_upload_cursor(self) -> int:
        path = self._agent_observer_upload_state_path()
        if not path.exists():
            return 0
        try:
            payload = jsonlib.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        if not isinstance(payload, dict):
            return 0
        try:
            return max(0, int(payload.get("last_uploaded_seq") or 0))
        except (TypeError, ValueError):
            return 0

    def _save_agent_observer_upload_cursor(self, seq: int) -> None:
        path = self._agent_observer_upload_state_path()
        payload = {
            "last_uploaded_seq": max(0, int(seq or 0)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(jsonlib.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _upload_agent_observer_events_once(self, ws: ClientWebSocketResponse) -> int:
        if self._pending_agent_observer_upload:
            return 0
        cursor = self._load_agent_observer_upload_cursor()
        events = get_action_trace_recorder().export_observer_events(after_seq=cursor, limit=100)
        if not events:
            return 0
        request_id = str(uuid.uuid4())
        max_seq = max(int((event.get("attrs_json") or {}).get("action_trace_seq") or event.get("agent_seq") or 0) for event in events)
        self._pending_agent_observer_upload = {
            "request_id": request_id,
            "max_seq": max_seq,
            "event_count": len(events),
        }
        await self.send_envelope(
            ws,
            "agent_observer_batch",
            request_id,
            {"events": events},
            trace_id=self._current_trace_id or str(uuid.uuid4()),
            actor_role="agent",
        )
        return len(events)

    async def _handle_agent_observer_batch_ack(self, payload: Dict[str, Any]) -> None:
        pending = self._pending_agent_observer_upload
        if not pending:
            return
        status = str(payload.get("status") or "").strip().lower()
        accepted_count = int(payload.get("accepted_count") or 0)
        if status == "ok" and accepted_count >= int(pending.get("event_count") or 0):
            self._save_agent_observer_upload_cursor(int(pending.get("max_seq") or 0))
        self._pending_agent_observer_upload = None

    def _get_latest_update_handshake_payload(self) -> Optional[Dict[str, str]]:
        """Returns the latest launcher-applied update result for handshake diagnostics."""
        try:
            data_root = self._data_root or runtime_paths.resolve_data_root()
            history_path = Path(data_root) / "updates" / "update_history.json"
            if not history_path.exists():
                return None
            history_raw = jsonlib.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history_raw, list):
                return None
            entries = [item for item in history_raw if isinstance(item, dict)]
            if not entries:
                return None
            entries.sort(key=lambda item: item.get("at") or "", reverse=True)
            latest = entries[0]
            version = latest.get("version")
            operation_id = latest.get("operation_id")
            if not version or not operation_id:
                return None
            if latest.get("success") is True:
                return {
                    "applied_update_version": str(version),
                    "last_update_operation_id": str(operation_id),
                }
            payload = {
                "failed_update_version": str(version),
                "failed_update_operation_id": str(operation_id),
                "failed_update_reason": str(latest.get("reason") or "update_failed"),
            }
            if latest.get("at"):
                payload["failed_update_at"] = str(latest["at"])
            if latest.get("message"):
                payload["failed_update_message"] = str(latest["message"])
            return payload
        except Exception as exc:
            logger.debug(f"[update] latest applied update confirmation unavailable: {exc}")
            return None

    @staticmethod
    def _release_channel_for_version(version: Optional[str]) -> str:
        lowered = str(version or "").strip().lower()
        if "beta" in lowered:
            return "beta"
        if "alpha" in lowered:
            return "alpha"
        if "rc" in lowered:
            return "rc"
        if "dev" in lowered:
            return "dev"
        if "-" in lowered:
            return "prerelease"
        return "stable"

    @classmethod
    def _is_release_version(cls, version: Optional[str]) -> bool:
        return cls._release_channel_for_version(version) == "stable"

    def _infer_build_target(self) -> Optional[str]:
        os_name = platform.system().strip().lower()
        if os_name.startswith("win"):
            return "windows_amd64"
        if os_name.startswith("linux"):
            return "linux_alt_x86_64"
        return None

    @staticmethod
    def _read_json_file(path: Path) -> Optional[Any]:
        try:
            if not path.exists():
                return None
            return jsonlib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.debug(f"[update] failed to read {path.name}: {exc}")
            return None

    def _read_local_update_state(self) -> Dict[str, Any]:
        data_root = Path(self._data_root or runtime_paths.resolve_data_root())
        updates_dir = data_root / "updates"
        pending_payload = self._read_json_file(updates_dir / "pending_update.json")
        history_payload = self._read_json_file(updates_dir / "update_history.json")
        failed_payload = self._read_json_file(updates_dir / "last_failed_pending_update.json")

        state = {
            "pending_update_version": None,
            "pending_update_operation_id": None,
            "pending_update_received_at": None,
            "pending_update_reason": None,
            "update_request_state": None,
            "update_request_version": None,
            "update_request_operation_id": None,
            "update_request_requested_at": None,
            "update_request_reason": None,
            "last_applied_update_version": None,
            "last_applied_update_at": None,
            "last_applied_update_operation_id": None,
            "last_failed_update_version": None,
            "last_failed_update_at": None,
            "last_failed_update_operation_id": None,
            "last_failed_update_reason": None,
            "last_failed_update_message": None,
        }

        if isinstance(pending_payload, dict):
            state["pending_update_version"] = pending_payload.get("version")
            state["pending_update_operation_id"] = pending_payload.get("operation_id")
            state["pending_update_received_at"] = pending_payload.get("received_at")
            state["pending_update_reason"] = pending_payload.get("requested_reason")
            state["update_request_state"] = "pending_restart"
            state["update_request_version"] = pending_payload.get("version")
            state["update_request_operation_id"] = pending_payload.get("operation_id")
            state["update_request_requested_at"] = pending_payload.get("received_at")
            state["update_request_reason"] = pending_payload.get("requested_reason")

        if isinstance(history_payload, list):
            entries = [item for item in history_payload if isinstance(item, dict)]
            if entries:
                entries.sort(key=lambda item: item.get("at") or "", reverse=True)
                latest_success = next((item for item in entries if item.get("success") is True), None)
                latest_failure = next((item for item in entries if item.get("success") is False), None)
                if latest_success:
                    state["last_applied_update_version"] = latest_success.get("version")
                    state["last_applied_update_at"] = latest_success.get("at")
                    state["last_applied_update_operation_id"] = latest_success.get("operation_id")
                if latest_failure:
                    state["last_failed_update_version"] = latest_failure.get("version")
                    state["last_failed_update_at"] = latest_failure.get("at")
                    state["last_failed_update_operation_id"] = latest_failure.get("operation_id")
                    state["last_failed_update_reason"] = latest_failure.get("reason")
                    state["last_failed_update_message"] = latest_failure.get("message")

        if isinstance(failed_payload, dict):
            pending_failed = failed_payload.get("pending_payload") if isinstance(failed_payload.get("pending_payload"), dict) else {}
            state["last_failed_update_version"] = state["last_failed_update_version"] or pending_failed.get("version")
            state["last_failed_update_operation_id"] = state["last_failed_update_operation_id"] or pending_failed.get("operation_id")
            state["last_failed_update_reason"] = state["last_failed_update_reason"] or failed_payload.get("error_message")
            state["last_failed_update_message"] = state["last_failed_update_message"] or failed_payload.get("error_message")

        return state

    def _base_update_status(self) -> Dict[str, Any]:
        return {
            "agent_version": AGENT_VERSION,
            "is_release": self._is_release_version(AGENT_VERSION),
            "release_channel": self._release_channel_for_version(AGENT_VERSION),
            "update_available": False,
            "recommended_version": None,
            "recommended_channel": None,
            "recommended_reason": None,
            "recommended_build": None,
            "comparison": "unknown",
            "recommendation_source": "none",
            "assigned_rollout": None,
            "update_status_error": None,
            "update_checked_at": self._cached_update_checked_at,
            "update_request_state": None,
            "update_request_version": None,
            "update_request_operation_id": None,
            "update_request_requested_at": None,
            "update_request_reason": None,
        }

    def _merge_update_status(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = self._base_update_status()
        if isinstance(payload, dict):
            for key in (
                "update_available",
                "recommended_version",
                "recommended_channel",
                "recommended_reason",
                "recommended_build",
                "comparison",
                "recommendation_source",
                "assigned_rollout",
                "update_status_error",
                "update_checked_at",
                "update_request_state",
                "update_request_version",
                "update_request_operation_id",
                "update_request_requested_at",
                "update_request_reason",
            ):
                if key in payload:
                    merged[key] = payload.get(key)
            if "is_release" in payload:
                merged["is_release"] = bool(payload.get("is_release"))
            if payload.get("release_channel"):
                merged["release_channel"] = str(payload.get("release_channel"))
        return merged

    @staticmethod
    def _finalize_update_status(status: Dict[str, Any]) -> Dict[str, Any]:
        pending_version = str(status.get("pending_update_version") or "").strip()
        pending_operation_id = str(status.get("pending_update_operation_id") or "").strip()
        pending_received_at = str(status.get("pending_update_received_at") or "").strip()
        pending_reason = str(status.get("pending_update_reason") or "").strip()
        if pending_version:
            status["update_request_state"] = "pending_restart"
            status["update_request_version"] = pending_version
            status["update_request_operation_id"] = pending_operation_id or status.get("update_request_operation_id")
            status["update_request_requested_at"] = pending_received_at or status.get("update_request_requested_at")
            status["update_request_reason"] = pending_reason or status.get("update_request_reason")

        request_state = str(status.get("update_request_state") or "").strip().lower()
        if request_state in {"requesting", "requested", "pending_restart"}:
            status["update_available"] = False
        return status

    @staticmethod
    def _decode_json_text(raw_text: str) -> Optional[Dict[str, Any]]:
        text = str(raw_text or "").strip()
        if not text:
            return None
        try:
            payload = jsonlib.loads(text)
        except Exception:
            return None
        if isinstance(payload, dict):
            return payload
        return None

    @staticmethod
    def _format_update_status_http_error(
        *,
        status: int,
        payload: Optional[Dict[str, Any]],
        raw_text: str,
    ) -> str:
        if isinstance(payload, dict):
            error_message = str(payload.get("error") or "").strip()
            if error_message:
                return error_message
        text = str(raw_text or "").strip()
        if status == 404:
            return "Update recommendation endpoint is unavailable on server (HTTP 404)"
        if text:
            return text[:200]
        return f"HTTP {status}"

    async def _fetch_update_status(self, *, force: bool = False) -> Dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        if (
            not force
            and self._cached_update_status
            and self._cached_update_checked_at
        ):
            try:
                cached_at = datetime.fromisoformat(self._cached_update_checked_at)
                if (datetime.now(timezone.utc) - cached_at).total_seconds() < UPDATE_STATUS_CACHE_TTL_SEC:
                    return self._merge_update_status(self._cached_update_status)
            except Exception:
                pass

        base = self._base_update_status()
        if not self.auth_token:
            base["update_status_error"] = "auth_token_missing"
            return base
        if not self.device_id:
            base["update_status_error"] = "device_id_missing"
            return base

        api_url = get_config().server.api_url.rstrip("/")
        target = self._infer_build_target()
        query = [f"current_version={quote(AGENT_VERSION)}"]
        if target:
            query.append(f"target={quote(target)}")
        recommendation_url = f"{api_url}/devices/{quote(self.device_id)}/agent/update_recommendation?{'&'.join(query)}"
        logger.info(
            "[update] fetching recommendation: "
            f"device_id={self.device_id} current_version={AGENT_VERSION} target={target or 'auto'}"
        )

        session = self._http_session
        created_session = False
        if session is None or session.closed:
            session = ClientSession(timeout=ClientTimeout(total=10))
            created_session = True

        try:
            async with session.get(
                recommendation_url,
                headers={"Authorization": f"Bearer {self.auth_token}"},
            ) as response:
                raw_text = await response.text()
                payload = self._decode_json_text(raw_text)
                if response.status != 200:
                    raise RuntimeError(
                        self._format_update_status_http_error(
                            status=response.status,
                            payload=payload,
                            raw_text=raw_text,
                        )
                    )
                if payload is None:
                    raise RuntimeError("Invalid recommendation payload")
                payload["update_checked_at"] = now_iso
                self._cached_update_checked_at = now_iso
                self._cached_update_status = dict(payload)
                logger.info(
                    "[update] recommendation received: "
                    f"device_id={self.device_id} current={AGENT_VERSION} "
                    f"recommended={payload.get('recommended_version') or 'none'} "
                    f"source={payload.get('recommendation_source') or 'none'} "
                    f"comparison={payload.get('comparison') or 'unknown'} "
                    f"available={bool(payload.get('update_available'))}"
                )
                return self._merge_update_status(payload)
        except Exception as exc:
            logger.warning(f"[update] recommendation fetch failed: {exc}")
            if self._cached_update_status:
                cached = dict(self._cached_update_status)
                cached["update_status_error"] = str(exc)
                cached["update_checked_at"] = now_iso
                return self._merge_update_status(cached)
            base["update_status_error"] = str(exc)
            base["update_checked_at"] = now_iso
            return base
        finally:
            if created_session:
                await session.close()

    @property
    def requested_exit_code(self) -> int:
        return self._requested_exit_code

    def _validate_server_config(self, ws_url: str, api_url: str) -> None:
        """Предупреждает о потенциальной misconfig target-host."""
        ws_host = urlparse(ws_url).hostname or ""
        api_host = urlparse(api_url).hostname or ""
        if ws_host in {"localhost", "127.0.0.1", "::1"} or api_host in {"localhost", "127.0.0.1", "::1"}:
            logger.warning(
                "[config] server.ws_url/api_url указывает на localhost. "
                "Если ожидается удалённый сервер — проверьте settings.yaml и env overrides."
            )

    async def _publish_connection_state(self, state: str, detail: str = "") -> None:
        self._last_connection_state = str(state or "").strip() or "unknown"
        self._last_connection_detail = str(detail or "").strip()
        self._last_connection_changed_at = datetime.now(timezone.utc).isoformat()
        if not self.event_bus:
            return
        try:
            await self.event_bus.publish(
                {
                    "event_type": "connection_state",
                    "data": {
                        "state": self._last_connection_state,
                        "detail": self._last_connection_detail,
                    },
                    "timestamp": self._last_connection_changed_at,
                }
            )
        except Exception as exc:
            logger.debug(f"[ui_bridge] connection_state publish skipped: {exc}")

    async def _check_server_reachability(self, api_url: str) -> None:
        """
        Быстрый preflight из агента:
        - /health (доступность сервера)
        - /modules/catalog (диагностика цепочки модулей и публичной раздачи)
        - /api/modules/ping (доступность module API префикса)
        """
        base = (api_url or "").rstrip("/")
        if not base:
            return
        timeout = aiohttp.ClientTimeout(total=4)
        modules_ping_endpoint = (
            f"{base}/modules/ping"
            if base.endswith("/api")
            else f"{base}/api/modules/ping"
        )
        endpoints = [
            ("health", f"{base}/health"),
            ("modules_catalog", f"{base}/modules/catalog"),
            ("modules_ping", modules_ping_endpoint),
        ]
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for endpoint_name, endpoint in endpoints:
                try:
                    async with session.get(endpoint) as response:
                        await response.read()
                        logger.info(f"[connectivity] {endpoint} -> HTTP {response.status}")
                except Exception as exc:
                    if endpoint_name == "modules_ping":
                        logger.warning(
                            "[connectivity] module API prefix unreachable "
                            f"({endpoint}): {exc}"
                        )
                    else:
                        logger.warning(f"[connectivity] {endpoint} unreachable: {exc}")

    def get_runtime_status(self) -> Dict[str, Any]:
        data_root = self._data_root or runtime_paths.resolve_data_root()
        logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))
        status = {
            "device_id": self.device_id,
            "agent_version": AGENT_VERSION,
            "started_at": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "uptime_seconds": max(0, int(time.time() - self.start_time)),
            "connection_state": self._last_connection_state,
            "connection_detail": self._last_connection_detail,
            "connection_changed_at": self._last_connection_changed_at,
            "has_auth_token": bool(self.auth_token),
            "ui_bridge_running": bool(self.ui_api_server and getattr(self.ui_api_server, "_listening", False)),
            "log_runtime": dict(self._logging_runtime),
            "logs_dir": str(logs_dir),
            "event_bus_subscribers": self.event_bus.get_subscriber_count() if self.event_bus else 0,
        }
        status.update(self._merge_update_status(self._cached_update_status))
        status.update(self._read_local_update_state())
        return self._finalize_update_status(self._overlay_active_cached_request_state(status))

    async def get_runtime_status_async(self) -> Dict[str, Any]:
        status = self.get_runtime_status()
        status.update(await self._fetch_update_status())
        status.update(self._read_local_update_state())
        return self._finalize_update_status(self._overlay_active_cached_request_state(status))

    def _overlay_active_cached_request_state(self, status: Dict[str, Any]) -> Dict[str, Any]:
        cached = self._cached_update_status if isinstance(self._cached_update_status, dict) else None
        if not cached:
            return status
        request_state = str(cached.get("update_request_state") or "").strip().lower()
        if request_state not in {"requesting", "requested", "pending_restart"}:
            return status
        for key in (
            "update_available",
            "recommended_reason",
            "update_request_state",
            "update_request_version",
            "update_request_operation_id",
            "update_request_requested_at",
            "update_request_reason",
        ):
            if key in cached:
                status[key] = cached.get(key)
        return status

    async def trigger_recommended_update(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        action_trace = get_action_trace_recorder().context(
            source="ws_agent",
            action="agent.update.request",
            category="update",
            tool_name="update",
        )
        recommendation = await self._fetch_update_status(force=True)
        recommended_build = recommendation.get("recommended_build")
        if not recommendation.get("update_available") or not isinstance(recommended_build, dict):
            get_action_trace_recorder().record(
                action_trace,
                stage="request",
                status="skipped",
                summary="recommended update is not available",
                details={"recommendation": recommendation},
            )
            logger.info(
                "[update] update request skipped: "
                f"device_id={self.device_id or 'unknown'} available={bool(recommendation.get('update_available'))} "
                f"recommended={recommendation.get('recommended_version') or 'none'} "
                f"comparison={recommendation.get('comparison') or 'unknown'}"
            )
            return {
                "status": "ok",
                "update_available": False,
                "message": "Recommended update is not available",
                "recommendation": recommendation,
            }
        if not self.auth_token:
            raise RuntimeError("auth token is missing")
        if not self.device_id:
            raise RuntimeError("device_id is missing")

        api_url = get_config().server.api_url.rstrip("/")
        update_url = f"{api_url}/devices/{quote(self.device_id)}/agent/update"
        request_body = {
            "target": recommended_build.get("target"),
            "channel": recommended_build.get("channel"),
            "version": recommended_build.get("version"),
            "reason": str(payload.get("reason") or "agent_gui_self_update"),
        }
        action_trace.operation_id = None
        action_trace.request_id = str(uuid.uuid4())
        action_trace.trace_id = recommendation.get("pending_update_operation_id") or recommendation.get("last_update_operation_id")
        get_action_trace_recorder().record(
            action_trace,
            stage="request",
            status="started",
            summary="requesting recommended update from server",
            details={"request_body": request_body, "recommendation": recommendation},
        )
        logger.info(
            "[update] requesting recommended build: "
            f"device_id={self.device_id} target={request_body['target']} "
            f"channel={request_body['channel']} version={request_body['version']} "
            f"reason={request_body['reason']}"
        )

        session = self._http_session
        created_session = False
        if session is None or session.closed:
            session = ClientSession(timeout=ClientTimeout(total=15))
            created_session = True
        try:
            async with session.post(
                update_url,
                json=request_body,
                headers={"Authorization": f"Bearer {self.auth_token}"},
            ) as response:
                result = await response.json(content_type=None)
                if response.status != 202:
                    error_message = result.get("error") if isinstance(result, dict) else None
                    get_action_trace_recorder().record(
                        action_trace,
                        stage="response",
                        status="error",
                        summary=error_message or f"HTTP {response.status}",
                        details={"status": response.status, "response": result},
                    )
                    raise RuntimeError(error_message or f"HTTP {response.status}")
                operation_id = (result or {}).get("operation_id") if isinstance(result, dict) else None
                action_trace.operation_id = str(operation_id) if operation_id else action_trace.operation_id
                logger.info(
                    "[update] request accepted: "
                    f"device_id={self.device_id} "
                    f"operation_id={(result or {}).get('operation_id') if isinstance(result, dict) else 'unknown'} "
                    f"version={request_body['version']}"
                )
                get_action_trace_recorder().record(
                    action_trace,
                    stage="response",
                    status="accepted",
                    summary="server accepted update request",
                    details={"request_body": request_body, "response": result},
                )
                requested_at = datetime.now(timezone.utc).isoformat()
                self._cached_update_checked_at = requested_at
                self._cached_update_status = {
                    **recommendation,
                    "update_available": False,
                    "recommended_reason": "update_requested",
                    "update_request_state": "requested",
                    "update_request_version": request_body["version"],
                    "update_request_operation_id": operation_id,
                    "update_request_requested_at": requested_at,
                    "update_request_reason": request_body["reason"],
                }
                return {
                    "status": "accepted",
                    "message": "Update request sent",
                    "recommendation": recommendation,
                    "server_response": result if isinstance(result, dict) else {"result": result},
                }
        except Exception as exc:
            get_action_trace_recorder().record(
                action_trace,
                stage="response",
                status="error",
                summary="recommended update request failed",
                details={"exception_type": type(exc).__name__, "message": str(exc)},
            )
            logger.error(f"[update] request failed: {exc!r}")
            raise
        finally:
            if created_session:
                await session.close()

    def get_runtime_logs(self, source: str = "agent", lines: int = 120) -> Dict[str, Any]:
        normalized_source = str(source or "agent").strip().lower()
        max_lines = max(1, min(int(lines), 400))
        data_root = self._data_root or runtime_paths.resolve_data_root()
        logs_dir = runtime_paths.resolve_logs_dir(Path(data_root))
        launcher_candidates = [
            Path(data_root).parent / "launcher.log",
            Path(data_root) / "launcher.log",
        ]
        if normalized_source == "memory":
            return {
                "source": "memory",
                "path": None,
                "lines": self._runtime_log_buffer.snapshot(max_lines),
                "text": format_log_tail(self._runtime_log_buffer.snapshot(max_lines)),
            }
        if normalized_source == "actions":
            rows = search_action_trace(limit=max_lines)
            return {
                "source": "actions",
                "path": str(get_action_trace_recorder().path) if getattr(get_action_trace_recorder(), "path", None) else None,
                "entries": rows,
                "lines": [jsonlib.dumps(item, ensure_ascii=False) for item in rows],
                "text": "\n".join(jsonlib.dumps(item, ensure_ascii=False) for item in rows),
            }

        file_map = {
            "agent": Path(self._logging_runtime.get("file") or (logs_dir / "agent.log")),
            "launcher": next((candidate for candidate in launcher_candidates if candidate.exists()), launcher_candidates[0]),
        }
        log_path = file_map.get(normalized_source)
        if log_path is None:
            raise ValueError(f"Unknown log source: {source}")
        tail_lines = read_log_tail(log_path, max_lines)
        return {
            "source": normalized_source,
            "path": str(log_path),
            "lines": [line.rstrip("\n") for line in tail_lines],
            "text": format_log_tail(tail_lines),
        }
    
    async def initialize(self):
        """
        Инициализация базы данных, оркестратора и идентификации.
        Пути к логам, identity, БД берутся из data_root (runtime_paths), если задан при создании агента.
        """
        try:
            cfg = get_config()
            data_root = self._data_root
            if data_root is None:
                data_root = Path(__file__).resolve().parent / cfg.paths.data_dir
            data_root = data_root.resolve()

            # Настраиваем production-friendly runtime logging из конфига.
            self._logging_runtime = configure_runtime_logging(
                data_root=data_root,
                logging_config=cfg.logging,
                role_name="agent",
                memory_buffer=self._runtime_log_buffer,
            )
            configure_action_trace(data_root)
            logger.success(
                "✅ Логирование настроено: "
                f"level={self._logging_runtime['level']}, "
                f"file={self._logging_runtime['file']}"
            )
            
            # Инициализируем менеджер идентификации: data_root/identity.json
            identity_path = data_root / "identity.json"
            self.identity_manager = IdentityManager(str(identity_path))
            self.identity_manager.load_or_create()
            
            # Используем UUID из identity файла как device_id
            self.device_id = self.identity_manager.device_id
            logger.success("✅ Менеджер идентификации инициализирован")
            logger.info(f"🆔 Device ID установлен из identity: {self.device_id}")

            # HTTP клиент для REST вызовов
            self.http = AioHttpClient(cfg.server.api_url, default_timeout=10)
            self._validate_server_config(cfg.server.ws_url, cfg.server.api_url)
            await self._check_server_reachability(cfg.server.api_url)
            
            # Инициализируем глобальный FileUploader (для модуля screen и др.)
            get_uploader(identity_manager=self.identity_manager)
            logger.success("✅ FileUploader инициализирован")
            
            # База данных: data_root/storage.db
            db_path = runtime_paths.resolve_storage_db_path(data_root)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_manager = DatabaseManager(str(db_path))
            await self.db_manager.init_db()
            logger.success("✅ База данных инициализирована")
            
            # Создаем универсальный оркестратор (data_root передаём для modules_store)
            self.orchestrator = AgentOrchestrator(
                db_manager=self.db_manager,
                enabled_modules=cfg.enabled_modules,
                identity_manager=self.identity_manager,
                data_root=data_root,
                schedule_update_exit=self.schedule_update_shutdown,
            )
            
            # Инициализируем оркестратор (загружает модули)
            await self.orchestrator.initialize()
            logger.success(f"✅ Оркестратор инициализирован")
            # Создаем JobManager и подключаем к оркестратору
            job_manager = JobManager(
                db_manager=self.db_manager,
                outbox_enqueue_func=self.db_manager.enqueue_job_event,
                logger_instance=logger
            )
            self.orchestrator.attach_job_manager(job_manager)
            logger.success("✅ JobManager создан и подключен к оркестратору")
            
            # Очищаем старые записи из seen_messages (TTL 14 дней)
            await self.db_manager.cleanup_old_seen_messages()
            logger.success("✅ Очистка старых seen_messages выполнена")
            
            # Очищаем старые записи из seen_commands (TTL 14 дней)
            await self.db_manager.cleanup_seen_commands()
            logger.success("✅ Очистка старых seen_commands выполнена")
            
            # Инициализируем UI Bridge
            self.event_bus = EventBus()
            logger.success("✅ EventBus инициализирован")
            
            # Подключаем EventBus к оркестратору
            self.orchestrator.ui_bus = self.event_bus
            logger.success("✅ EventBus подключен к оркестратору")
            
            # Создаем очередь для логов и задачу для публикации в EventBus
            # Используем обычную queue.Queue для синхронного sink
            self._log_queue = queue.Queue(maxsize=1000)  # Ограничение размера очереди
            self._log_publisher_task: Optional[asyncio.Task] = None
            
            # Создаем sink для loguru, который отправляет логи в EventBus
            def log_sink(message):
                """Sink для loguru, который добавляет логи в очередь для публикации в EventBus."""
                try:
                    # Парсим сообщение loguru (message - это объект LogRecord)
                    record = message.record
                    
                    # Исключаем логи, которые связаны с EventBus или SSE, чтобы избежать бесконечного цикла
                    log_message = record["message"]
                    module_name = record.get("name", "")
                    
                    # Пропускаем логи от модулей EventBus и API сервера, чтобы избежать рекурсии
                    if "event_bus" in module_name.lower() or "api_server" in module_name.lower():
                        return
                    
                    # Пропускаем логи, которые содержат упоминания о публикации событий или отправке SSE
                    if any(keyword in log_message.lower() for keyword in [
                        "событие опубликовано",
                        "sse событие отправлено",
                        "event published",
                        "sse event sent",
                        "подписчик",
                        "subscriber"
                    ]):
                        return
                    
                    # Получаем чистое сообщение без форматирования времени и уровня
                    # Используем record["message"] для получения исходного сообщения
                    
                    # Формируем событие для EventBus
                    log_event = {
                        "level": record["level"].name.lower(),
                        "message": log_message,
                        "time": record["time"].isoformat(),
                        "module": module_name,
                        "function": record.get("function", ""),
                        "line": record.get("line", 0)
                    }
                    
                    # Добавляем в очередь (неблокирующе)
                    try:
                        self._log_queue.put_nowait(log_event)
                    except queue.Full:
                        # Если очередь переполнена, просто пропускаем
                        pass
                except Exception:
                    # Не логируем ошибки в sink, чтобы избежать рекурсии
                    pass
            
            # Добавляем sink для EventBus (используем enqueue=True для thread-safe)
            logger.add(
                log_sink,
                level=self._logging_runtime.get("level", "INFO"),
                enqueue=True,  # Thread-safe очередь
                format="{message}"
            )
            logger.success("✅ Sink для EventBus добавлен в loguru")
            
            # Запускаем задачу для публикации логов в EventBus
            async def log_publisher():
                """Публикует логи из очереди в EventBus."""
                while True:
                    try:
                        # Ждем лог из очереди (используем asyncio.sleep для проверки)
                        # Проверяем очередь каждые 0.1 секунды
                        await asyncio.sleep(0.10)
                        
                        # Пытаемся получить лог из очереди (неблокирующе)
                        try:
                            log_event = self._log_queue.get_nowait()
                        except queue.Empty:
                            continue
                        
                        # Формируем событие для EventBus
                        event = {
                            "event_type": "log",
                            "data": {
                                "level": log_event["level"],
                                "message": log_event["message"],
                                "module": log_event["module"],
                                "function": log_event["function"],
                                "line": log_event["line"]
                            },
                            "timestamp": log_event["time"]
                        }
                        
                        # Публикуем в EventBus
                        if self.event_bus:
                            await self.event_bus.publish(event)
                        
                    except asyncio.CancelledError:
                        break
                    except Exception:
                        # Игнорируем ошибки публикации, чтобы не ломать логирование
                        pass
            
            self._log_publisher_task = asyncio.create_task(log_publisher())
            
            # Housekeeping task для cleanup_seen_commands (раз в сутки)
            async def housekeeping_cleanup_seen_commands_task():
                """Периодический cleanup seen_commands (раз в сутки)."""
                while True:
                    try:
                        await asyncio.sleep(24 * 3600)  # 24 часа
                        if self.db_manager:
                            deleted_count = await self.db_manager.cleanup_seen_commands(
                                max_age_days=14,
                                max_records=50000
                            )
                            logger.info(f"Housekeeping: cleaned up {deleted_count} seen_commands records")
                    except Exception as e:
                        logger.error(f"Housekeeping cleanup error: {e}", exc_info=True)
            
            self._housekeeping_task = asyncio.create_task(housekeeping_cleanup_seen_commands_task())
            logger.success("✅ Housekeeping task для seen_commands запущен")
            
            # Housekeeping task для cleanup_expired_consents (раз в час)
            async def housekeeping_cleanup_expired_consents_task():
                """Периодический cleanup expired pending_consents (раз в час)."""
                while True:
                    try:
                        await asyncio.sleep(3600)  # 1 час
                        if self.db_manager:
                            deleted_count = await self.db_manager.cleanup_expired_consents()
                            if deleted_count > 0:
                                logger.info(f"Housekeeping: cleaned up {deleted_count} expired pending_consents records")
                    except Exception as e:
                        logger.error(f"Housekeeping cleanup expired consents error: {e}", exc_info=True)
            
            self._consent_cleanup_task = asyncio.create_task(housekeeping_cleanup_expired_consents_task())
            logger.success("✅ Housekeeping task для expired_consents запущен")

            # Runtime loop планировщика (MVP).
            self._scheduler_task = asyncio.create_task(self._scheduler_runtime_loop())
            logger.success("✅ Scheduler runtime loop запущен")
            # Даем задаче время на инициализацию в event loop
            await asyncio.sleep(0)
            logger.success("✅ Задача публикации логов в EventBus запущена")
            
            # Создаем callback для обработки решений о согласии
            async def on_consent_decision(decision: ConsentDecision):
                """Обработчик решений о согласии."""
                logger.info(f"📋 Получено решение о согласии: job_id={decision.job_id}, approved={decision.approved}, reason={decision.reason}")
                
                try:
                    # Формируем команду для оркестратора
                    cmd = {
                        "cmd": "consent_decision",
                        "consent_token": decision.consent_token,
                        "approved": decision.approved,
                        "session_key": decision.session_key or decision.job_id or "",
                        "request_id": str(uuid.uuid4()),
                        "device_id": self.device_id,
                        "actor_role": "user"  # consent_decision всегда от пользователя
                    }
                    
                    # Вызываем оркестратор
                    result = await self.orchestrator.handle_command(cmd)
                    logger.info(f"✅ Решение о согласии обработано оркестратором: approved={decision.approved}")
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки решения о согласии: {e}")
                    logger.exception(e)
            
            # Создаем UI API сервер (используем настройки из конфига)
            ui_config = get_config().ui
            ui_host = ui_config.host if ui_config else "127.0.0.1"
            ui_port = ui_config.port if ui_config else 8765
            self.settings_service = AgentSettingsService(data_root=data_root)

            async def on_get_settings() -> Dict[str, Any]:
                if not self.settings_service:
                    raise RuntimeError("settings service not initialized")
                settings = await self.settings_service.get_settings()
                installed_modules: list[dict[str, Any]] = []
                try:
                    module_manager = getattr(self.orchestrator, "module_manager", None)
                    if module_manager is not None and hasattr(module_manager, "list_installed"):
                        installed = module_manager.list_installed()
                        modules = installed.get("modules", []) if isinstance(installed, dict) else []
                        if isinstance(modules, list):
                            installed_modules = modules
                except Exception as exc:
                    logger.warning(f"[settings] failed to get installed modules: {exc}")
                settings["installed_modules"] = installed_modules
                return settings

            async def on_update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
                if not self.settings_service:
                    raise RuntimeError("settings service not initialized")
                return await self.settings_service.update_settings(payload)

            async def on_test_connection(payload: Dict[str, Any]) -> Dict[str, Any]:
                if not self.settings_service:
                    raise RuntimeError("settings service not initialized")
                return await self.settings_service.test_connection(payload)

            async def on_restart_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
                return await self.schedule_restart(payload)

            async def on_trigger_update(payload: Dict[str, Any]) -> Dict[str, Any]:
                return await self.trigger_recommended_update(payload)

            async def on_get_runtime_status() -> Dict[str, Any]:
                return await self.get_runtime_status_async()

            def on_get_runtime_logs(payload: Dict[str, Any]) -> Dict[str, Any]:
                source = str(payload.get("source") or "agent")
                lines_raw = payload.get("lines", 120)
                try:
                    lines = int(lines_raw)
                except (TypeError, ValueError):
                    lines = 120
                if source.strip().lower() != "actions":
                    return self.get_runtime_logs(source=source, lines=lines)
                rows = search_action_trace(
                    limit=lines,
                    action_id=payload.get("action_id"),
                    parent_action_id=payload.get("parent_action_id"),
                    ticket_id=payload.get("ticket_id"),
                    operation_id=payload.get("operation_id"),
                    message_id=payload.get("message_id"),
                    tool_name=payload.get("tool_name"),
                    status=payload.get("status"),
                    text=payload.get("text"),
                )
                recorder = get_action_trace_recorder()
                return {
                    "source": "actions",
                    "path": str(recorder.path) if getattr(recorder, "path", None) else None,
                    "entries": rows,
                    "lines": [jsonlib.dumps(item, ensure_ascii=False) for item in rows],
                    "text": "\n".join(jsonlib.dumps(item, ensure_ascii=False) for item in rows),
                }

            async def on_chat_send(
                ticket_id: str,
                text: str,
                from_role: str = "user",
                attachment_refs: Optional[List[str]] = None,
                metadata: Optional[Dict[str, Any]] = None,
            ) -> Dict[str, Any]:
                """Отправка сообщения в тикет через Ticket API сервера."""
                api_url = get_config().server.api_url
                client = TicketApiClient(
                    api_url,
                    self.device_id,
                    user_display_name="User",
                    auth_token=self.auth_token,
                )
                try:
                    return await client.send_message(
                        ticket_id,
                        text,
                        from_role=from_role,
                        attachment_refs=attachment_refs,
                        metadata=metadata,
                    )
                finally:
                    await client.close()

            self.ui_api_server = UiApiServer(
                event_bus=self.event_bus,
                host=ui_host,
                port=ui_port,
                on_consent_decision=on_consent_decision,
                on_get_settings=on_get_settings,
                on_update_settings=on_update_settings,
                on_test_connection=on_test_connection,
                on_restart_agent=on_restart_agent,
                on_trigger_update=on_trigger_update,
                on_get_runtime_status=on_get_runtime_status,
                on_get_runtime_logs=on_get_runtime_logs,
                on_chat_send=on_chat_send,
            )
            logger.success(f"✅ UiApiServer создан на {ui_host}:{ui_port}")
            
            # Подключаем callback on_request_support к agent.chat_raise
            async def on_request_support(payload: dict) -> dict:
                title = payload.get("title", "Support needed")
                reason = payload.get("reason", "user_requested")
                severity = payload.get("severity", "warning")
                context = payload.get("context") or {}

                result = await self.chat_raise(title=title, reason=reason, severity=severity, context=context)
                if not result:
                    return {"ok": False, "error": "chat_raise failed"}
                if result.get("ok") is False:
                    return result
                return {"ok": True, **result}

            self.ui_api_server.on_request_support = on_request_support
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            raise
    
    async def cleanup(self):
        """
        Очистка ресурсов.
        """
        try:
            await self._close_agent_ws(reason="agent_cleanup")

            # Останавливаем задачу публикации логов
            if self._log_publisher_task:
                logger.info("🛑 Останавливаю задачу публикации логов...")
                self._log_publisher_task.cancel()
                try:
                    await self._log_publisher_task
                except asyncio.CancelledError:
                    pass
                self._log_publisher_task = None
                logger.info("✅ Задача публикации логов остановлена")
            
            if self._housekeeping_task:
                logger.info("🛑 Останавливаю housekeeping task для seen_commands...")
                self._housekeeping_task.cancel()
                try:
                    await self._housekeeping_task
                except asyncio.CancelledError:
                    pass
                self._housekeeping_task = None
                logger.info("✅ Housekeeping task остановлен")
            
            if self._consent_cleanup_task:
                logger.info("🛑 Останавливаю housekeeping task для expired_consents...")
                self._consent_cleanup_task.cancel()
                try:
                    await self._consent_cleanup_task
                except asyncio.CancelledError:
                    pass
                self._consent_cleanup_task = None
                logger.info("✅ Housekeeping task для expired_consents остановлен")

            if self._scheduler_task:
                logger.info("🛑 Останавливаю scheduler runtime task...")
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
                self._scheduler_task = None
                logger.info("✅ Scheduler runtime task остановлен")

            if self._background_command_tasks:
                logger.info("🛑 Останавливаю фоновые задачи command dispatch...")
                for task in list(self._background_command_tasks):
                    task.cancel()
                await asyncio.gather(*list(self._background_command_tasks), return_exceptions=True)
                self._background_command_tasks.clear()
                logger.info("✅ Фоновые задачи command dispatch остановлены")
             
            # Останавливаем UI API сервер
            if self.ui_api_server and self.ui_api_task:
                logger.info("🛑 Останавливаю UI API сервер...")
                try:
                    # Если ui_api_task - это Task, отменяем его
                    if isinstance(self.ui_api_task, asyncio.Task):
                        self.ui_api_task.cancel()
                        try:
                            await self.ui_api_task
                        except asyncio.CancelledError:
                            pass
                    # Останавливаем сам сервер
                    await asyncio.wait_for(self.ui_api_server.stop(), timeout=2.0)
                    logger.info("✅ UI API сервер остановлен")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ UI API сервер не остановился за 2 секунды")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при остановке UI API сервера: {e}")
                finally:
                    self.ui_api_task = None
            
            # Корректное завершение оркестратора
            if self.orchestrator:
                await self.orchestrator.shutdown()
                logger.info("🛑 Оркестратор остановлен")
            
            # Закрываем базу данных
            if self.db_manager:
                await self.db_manager.close()
                logger.info("🔒 База данных закрыта")
            
            # Закрываем HTTP сессию
            if self._http_session:
                await self._http_session.close()
                logger.info("🔒 HTTP сессия закрыта")

            # Закрываем обертку HTTP клиента
            if self.http:
                try:
                    await self.http.close()
                except Exception as e:
                    logger.warning(f"Failed to close http client: {e}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при очистке: {e}")

    async def _close_agent_ws(
        self,
        *,
        reason: str,
        code: int = aiohttp.WSCloseCode.GOING_AWAY,
        message: bytes = b"agent_shutdown",
        timeout: float = 1.5,
    ) -> None:
        ws = self._agent_ws
        if ws is None:
            return

        response = getattr(ws, "_response", None)
        wait_for_close = getattr(response, "wait_for_close", None)

        try:
            if not ws.closed:
                await asyncio.wait_for(ws.close(code=code, message=message), timeout=timeout)
            if callable(wait_for_close):
                await asyncio.wait_for(wait_for_close(), timeout=timeout)
        except Exception as e:
            logger.debug(f"Ошибка закрытия WebSocket ({reason}): {e}")
        finally:
            self._agent_ws = None

    async def schedule_restart(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await helper_schedule_restart(self, payload)

    async def schedule_update_shutdown(self, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return await helper_schedule_update_shutdown(self, payload)

    async def _shutdown_for_update(
        self,
        *,
        delay_sec: float,
        reason: str,
        version: str,
        operation_id: str,
    ) -> None:
        await helper_shutdown_for_update(
            self,
            delay_sec=delay_sec,
            reason=reason,
            version=version,
            operation_id=operation_id,
        )

    async def _restart_self(self, delay_sec: float, reason: str) -> None:
        await helper_restart_self(self, delay_sec, reason)
    
    def normalize_envelope(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Нормализует входящее сообщение в формат Protocol V3 envelope.
        Обеспечивает обратную совместимость со старыми форматами (V2/legacy).
        
        Args:
            data: Распарсенное JSON сообщение
        
        Returns:
            Нормализованный envelope (V3): {
                "type": str,
                "request_id": str,
                "device_id": str,
                "protocol_version": str,
                "trace_id": str (optional),
                "ticket_id": str (optional),
                "job_id": str (optional),
                "payload": dict,
                "meta": dict
            }
        """
        # Protocol V3 формат - уже нормализован
        if "type" in data and "payload" in data and "protocol_version" in data:
            # Извлекаем trace_id и context для последующего использования
            if "trace_id" in data:
                self._current_trace_id = data["trace_id"]
            if "ticket_id" in data:
                self._current_ticket_id = data["ticket_id"]
            if "job_id" in data:
                self._current_job_id = data["job_id"]
            
            # Убеждаемся, что есть request_id
            if "request_id" not in data:
                data["request_id"] = str(uuid.uuid4())
                logger.debug(f"🔑 [V3] Сгенерирован request_id: {data['request_id']}")
            
            # Убеждаемся, что есть meta
            if "meta" not in data:
                data["meta"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_role": "unknown"
                }
            
            return data
        
        # Legacy V2 envelope формат: {"type": "...", "payload": {...}}
        if "type" in data and "payload" in data:
            request_id = data.get("request_id") or str(uuid.uuid4())
            trace_id = data.get("trace_id") or str(uuid.uuid4())
            
            # Извлекаем actor_role из payload для V2 совместимости
            actor_role = data.get("payload", {}).get("actor_role", "unknown")
            
            envelope = {
                "type": data["type"],
                "request_id": request_id,
                "device_id": data.get("device_id") or self.device_id,
                "protocol_version": "legacy_v2",  # Маркируем как legacy
                "trace_id": trace_id,
                "payload": data["payload"],
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_role": actor_role
                }
            }
            
            # Сохраняем контекст
            self._current_trace_id = trace_id
            if "ticket_id" in data:
                envelope["ticket_id"] = data["ticket_id"]
                self._current_ticket_id = data["ticket_id"]
            if "job_id" in data:
                envelope["job_id"] = data["job_id"]
                self._current_job_id = data["job_id"]
            
            logger.debug(f"🔄 [V2→V3] Конвертирован legacy envelope: type={data['type']}")
            return envelope
        
        # Старый формат: {"command": "...", "params": {...}}
        if "command" in data:
            request_id = data.get("request_id") or str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            
            envelope = {
                "type": "command",
                "request_id": request_id,
                "device_id": data.get("device_id") or self.device_id,
                "protocol_version": "legacy_command",
                "trace_id": trace_id,
                "payload": {
                    "command": data["command"],
                    "params": data.get("params", {})
                },
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_role": data.get("params", {}).get("actor_role", "unknown")
                }
            }
            
            self._current_trace_id = trace_id
            logger.debug(f"🔄 [Legacy→V3] Конвертирована старая команда: {data['command']}")
            return envelope
        
        # Старый формат: {"type": "ping"}
        if data.get("type") == "agent_observer_batch_ack":
            trace_id = data.get("trace_id") or self._current_trace_id or str(uuid.uuid4())
            self._current_trace_id = trace_id
            return {
                "type": "agent_observer_batch_ack",
                "request_id": data.get("request_id") or str(uuid.uuid4()),
                "device_id": data.get("device_id") or self.device_id,
                "protocol_version": data.get("protocol_version") or "ws_ticket_v3",
                "trace_id": trace_id,
                "payload": data,
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_role": "server",
                },
            }

        if data.get("type") == "ping":
            trace_id = str(uuid.uuid4())
            self._current_trace_id = trace_id
            return {
                "type": "ping",
                "request_id": data.get("request_id") or str(uuid.uuid4()),
                "device_id": data.get("device_id") or self.device_id,
                "protocol_version": "legacy_ping",
                "trace_id": trace_id,
                "payload": {},
                "meta": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "actor_role": "server"
                }
            }
        
        # Неизвестный формат - создаем envelope с исходными данными в payload
        logger.warning(f"⚠️  Неизвестный формат сообщения, оборачиваю в V3 envelope: {data}")
        trace_id = str(uuid.uuid4())
        self._current_trace_id = trace_id
        return {
            "type": "unknown",
            "request_id": data.get("request_id") or str(uuid.uuid4()),
            "device_id": data.get("device_id") or self.device_id,
            "protocol_version": "unknown",
            "trace_id": trace_id,
            "payload": data,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor_role": "unknown"
            }
        }
    
    async def send_envelope(
        self, 
        ws: ClientWebSocketResponse, 
        msg_type: str, 
        request_id: Optional[str], 
        payload_dict: Dict[str, Any],
        trace_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        job_id: Optional[str] = None,
        actor_role: Optional[str] = None
    ) -> None:
        """
        Отправляет сообщение в формате Protocol V3 envelope.
        
        Args:
            ws: WebSocket соединение
            msg_type: Тип сообщения (command_result, pong, error и т.д.)
            request_id: Идентификатор запроса (если None, генерируется uuid4)
            payload_dict: Словарь с данными payload
            trace_id: Идентификатор трассировки для корреляции запросов
            ticket_id: Контекст тикета (если применимо)
            job_id: Контекст джоба (если применимо)
            actor_role: Роль актора (agent, user, support, admin)
        """
        # Гарантируем наличие request_id
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Используем trace_id из контекста или генерируем новый
        if not trace_id:
            trace_id = self._current_trace_id or str(uuid.uuid4())
        
        # Protocol V3 envelope
        envelope = {
            "type": msg_type,
            "request_id": request_id,
            "device_id": self.device_id,
            "protocol_version": PROTOCOL_VERSION,  # "ws_ticket_v3"
            "payload": payload_dict,
            "meta": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor_role": actor_role or "agent"
            }
        }
        
        # Добавляем опциональные поля контекста
        if trace_id:
            envelope["trace_id"] = trace_id
        if ticket_id or self._current_ticket_id:
            envelope["ticket_id"] = ticket_id or self._current_ticket_id
        if job_id or self._current_job_id:
            envelope["job_id"] = job_id or self._current_job_id
        
        async with self._ws_send_lock:
            await ws.send_json(envelope)
        if msg_type in {"command_ack", "command_result"}:
            logger.info(
                f"[V3] Sent command lifecycle envelope: type={msg_type}, "
                f"request_id={request_id}, status={payload_dict.get('status') if isinstance(payload_dict, dict) else None}"
            )
        logger.debug(
            f"📤 [V3] Отправлен envelope: type={msg_type}, request_id={request_id}, "
            f"trace_id={trace_id}, ticket_id={ticket_id or self._current_ticket_id}"
        )

    def _track_background_command_task(self, task: asyncio.Task) -> None:
        """Keeps a strong reference to detached command tasks until completion."""
        self._background_command_tasks.add(task)
        task.add_done_callback(self._background_command_tasks.discard)

    def _should_run_command_in_background(self, command: Optional[str]) -> bool:
        """Commands that can take noticeable time should not block the WS receive loop."""
        return command in {"run_tool", "call_tool", "run_recipe", "remote_assist.request"}

    async def _execute_command_and_send_result(
        self,
        ws: ClientWebSocketResponse,
        *,
        command: str,
        params: Dict[str, Any],
        request_id: str,
        command_id: str,
        device_id: Optional[str],
        actor_role: Optional[str],
        trace_id: Optional[str],
        ticket_id_ctx: Optional[str],
        job_id_ctx: Optional[str],
        actor_role_meta: Optional[str],
    ) -> None:
        """Executes a command, persists idempotency, and sends command_result."""
        command_result_payload: Optional[Dict[str, Any]] = None
        try:
            tool_response = await self.execute_command(
                command,
                params,
                request_id=request_id,
                device_id=device_id,
                actor_role=actor_role,
            )
            command_result_payload = {
                "status": tool_response.get("status", "error"),
                "data": tool_response.get("data", {}),
                "error": tool_response.get("error"),
                "meta": tool_response.get("meta", {}),
            }
            if self.db_manager:
                status = "success" if command_result_payload["status"] == "success" else "error"
                result_json = jsonlib.dumps(command_result_payload, ensure_ascii=False)
                was_updated = await self.db_manager.mark_command_seen(
                    command_id=command_id,
                    status=status,
                    result_json=result_json,
                )
                if was_updated:
                    logger.debug(f"✅ Команда {command_id} сохранена в seen_commands (status={status})")
                else:
                    logger.debug(f"⚠️  Команда {command_id} уже была success, не перезаписали")
        except asyncio.CancelledError:
            command_result_payload = {
                "status": "canceled",
                "data": {
                    "observations": {
                        "cancel_status": "canceled",
                        "target_operation_id": request_id,
                    }
                },
                "error": {
                    "code": "OPERATION_CANCELED",
                    "message": "Command was canceled",
                },
                "meta": {
                    "request_id": request_id,
                    "command": command,
                },
            }
            if self.db_manager:
                result_json = jsonlib.dumps(command_result_payload, ensure_ascii=False)
                was_updated = await self.db_manager.mark_command_seen(
                    command_id=command_id,
                    status="canceled",
                    result_json=result_json,
                )
                if was_updated:
                    logger.debug(f"✅ Команда {command_id} сохранена в seen_commands (status=canceled)")
                else:
                    logger.debug(f"⚠️  Команда {command_id} уже была terminal, не перезаписали")
        except Exception as e:
            logger.exception(e)
            command_result_payload = {
                "status": "error",
                "data": {},
                "error": {"message": str(e)},
                "meta": {},
            }
        finally:
            future = self._running_commands.pop(command_id, None)
            if future and not future.done():
                future.set_result(
                    command_result_payload or {
                        "status": "error",
                        "data": {},
                        "error": {"message": "Unknown"},
                        "meta": {},
                    }
                )

        logger.debug(f"📤 Отправка ответа: {command_result_payload}")
        await self.send_envelope(
            ws,
            "command_result",
            request_id,
            command_result_payload,
            trace_id=trace_id,
            ticket_id=ticket_id_ctx,
            job_id=job_id_ctx,
            actor_role=actor_role_meta,
        )
        logger.success(
            f"✅ [V3] Команда {command} выполнена "
            f"(request_id={request_id}, trace_id={trace_id}, command_id={command_id})"
        )
    
    async def handle_message(self, ws: ClientWebSocketResponse, message: str) -> None:
        """
        Обрабатывает входящее сообщение от сервера.
        
        Поддерживает единый формат envelope:
        {
            "type": str,
            "request_id": str,
            "device_id": str,
            "payload": dict
        }
        
        Обеспечивает обратную совместимость со старыми форматами.
        
        Args:
            ws: WebSocket соединение
            message: Строка сообщения от сервера
        """
        try:
            logger.debug(f"📩 Получено сообщение от сервера (длина: {len(message)} байт)")
            logger.debug(f"📄 Содержимое сообщения: {message}")
            
            data = jsonlib.loads(message)
            logger.debug(f"📦 Распарсенные данные: {data}")
            
            # Нормализуем входящее сообщение в формат envelope
            envelope = self.normalize_envelope(data)
            msg_type = envelope["type"]
            request_id = envelope["request_id"]
            payload = envelope["payload"]
            
            logger.debug(f"📦 Нормализованный envelope: type={msg_type}, request_id={request_id}")
            
            # Ping/Pong
            if msg_type == "ping":
                trace_id = envelope.get("trace_id")
                logger.debug(f"📶 Получен ping от сервера (trace_id={trace_id})")
                await self.send_envelope(
                    ws, "pong", request_id, {},
                    trace_id=trace_id,
                    actor_role="agent"
                )
                return
            
            # Handshake ACK
            if msg_type == "handshake_ack":
                server_capabilities = payload.get("server_capabilities", [])
                if isinstance(server_capabilities, list):
                    self.server_capabilities = set(str(item) for item in server_capabilities)
                else:
                    self.server_capabilities = set()
                registration = payload.get("registration")
                if isinstance(registration, dict):
                    try:
                        from pc_agent.core.user_profile import UserProfileManager

                        manager = UserProfileManager()
                        profile = manager.load()
                        profile["registration_status"] = str(registration.get("status") or "unknown")
                        if registration.get("pending_claim_id"):
                            profile["last_claim_id"] = str(registration.get("pending_claim_id"))
                        manager.save(profile)
                    except Exception as exc:
                        logger.debug("Registration status persistence skipped: {}", exc)
                if self.flusher:
                    self.flusher.supports_outbox_batch = "outbox_batch_v1" in self.server_capabilities
                try:
                    await self._upload_agent_observer_events_once(ws)
                except Exception as exc:
                    logger.debug(f"[agent-observer] telemetry upload skipped: {exc}")
                logger.info("✅ Получен handshake_ack от сервера")
                await self._publish_connection_state("connected", "WS подключён")
                return
            
            # Protocol V3: outbox_ack (предпочтительный)
            if msg_type == "agent_observer_batch_ack":
                await self._handle_agent_observer_batch_ack(payload)
                return

            if msg_type == "outbox_ack":
                trace_id = envelope.get("trace_id", "unknown")
                logger.info(f"✅ [V3] Получен outbox_ack от сервера (trace_id={trace_id})")
                if self.flusher:
                    outbox_ids_raw = payload.get("outbox_ids", [])
                    server_seq = payload.get("server_seq")  # Опциональная последовательность сервера
                    if isinstance(outbox_ids_raw, list) and outbox_ids_raw:
                        # Нормализуем к int: сервер может прислать числа или строки, inflight_deadlines ключи — int
                        outbox_ids = [int(oid) for oid in outbox_ids_raw]
                        await self.flusher.handle_ack(outbox_ids)
                        logger.debug(f"✅ ACK обработан: {len(outbox_ids)} сообщений, server_seq={server_seq}")
                    else:
                        logger.warning(f"⚠️  outbox_ack с пустым/неверным outbox_ids: {outbox_ids_raw}")
                return
            
            # Legacy ACK для обратной совместимости (deprecated, будет удалено)
            if msg_type == "ack":
                logger.warning("⚠️  Получен legacy ACK от сервера (deprecated, используйте outbox_ack)")
                if self.flusher and "outbox_ids" in payload:
                    outbox_ids = payload["outbox_ids"]
                    if isinstance(outbox_ids, list):
                        await self.flusher.handle_ack(outbox_ids)
                        logger.debug(f"✅ Legacy ACK обработан: {len(outbox_ids)} сообщений")
                    else:
                        logger.warning(f"⚠️  Неверный формат outbox_ids в legacy ACK: {outbox_ids}")
                return
            
            # Protocol V3: outbox_nack (Фаза 3.2)
            # КРИТИЧНО: обрабатываем NACK синхронно (await), чтобы mark_outbox_failed выполнился
            # до следующей итерации sender loop — иначе те же outbox_id снова claim'ятся и шлются.
            if msg_type == "outbox_nack":
                if self.flusher:
                    outbox_ids = payload.get("outbox_ids", [])
                    retryable = payload.get("retryable", False)
                    retry_after_sec = payload.get("retry_after_sec")
                    error = payload.get("error", {}) or {}
                    err_code = error.get("code", "")
                    err_msg = error.get("message", "")
                    # Пояснение: NACK приходит по конкретным outbox_id; "тикет X not found" значит,
                    # что отклонённые события относились к тикету X (старый/удалённый тикет), а не
                    # к тикету текущей операции — чтобы в логах было понятно.
                    if err_code == "UNKNOWN_TICKET" and "not found" in (err_msg or "").lower():
                        logger.warning(
                            f"⚠️  NACK для outbox_ids={outbox_ids}: сервер не нашёл тикет "
                            f"(события в outbox относились к старому/удалённому тикету). "
                            f"Помечаем как failed. retryable={retryable}"
                        )
                    else:
                        logger.warning(
                            f"⚠️  NACK для outbox_ids={outbox_ids}, retryable={retryable}, error={error}"
                        )
                    await self.flusher.handle_nack(
                        outbox_ids=outbox_ids,
                        retryable=retryable,
                        retry_after_sec=retry_after_sec,
                        error=error
                    )
                return
            
            # Protocol V3: rpc_request (Фаза 4)
            if msg_type == "rpc_request":
                method = payload.get("method")
                params = payload.get("params", {})
                ticket_id = envelope.get("ticket_id")
                job_id = envelope.get("job_id")
                idempotency_key = envelope.get("idempotency_key")
                trace_id = envelope.get("trace_id")
                
                logger.info(f"⚙️  Получен rpc_request: method={method}")
                
                # Замечание 10: Генерируем trace_id если нет
                if not trace_id:
                    trace_id = str(uuid.uuid4())
                    logger.warning(f"⚠️  missing trace_id, generated: {trace_id}")
                
                # Замечание 5: Проверяем idempotency_key для mutating методов
                if method in IDEMPOTENT_METHODS:
                    if not idempotency_key:
                        logger.error(
                            f"Method '{method}' requires idempotency_key"
                        )
                        await self.send_envelope(
                            ws, "rpc_response", request_id,
                            {
                                "status": "error",
                                "error": {
                                    "code": "MISSING_IDEMPOTENCY_KEY",
                                    "message": f"Method '{method}' requires idempotency_key"
                                }
                            },
                            trace_id=trace_id,
                            ticket_id=ticket_id,
                            job_id=job_id,
                            actor_role="agent"
                        )
                        return
                    
                    # Проверяем cache
                    cached = await self.db_manager.check_idempotency_cache(idempotency_key)
                    if cached:
                        logger.info(f"Idempotency cache HIT for {idempotency_key}")
                        await self.send_envelope(
                            ws, "rpc_response", request_id, cached
                        )
                        return
                
                # Scheduler MVP: отдельная обработка scheduler RPC.
                if method in SCHEDULER_METHODS:
                    result = await self._handle_scheduler_rpc(
                        method=method,
                        params=params if isinstance(params, dict) else {},
                        request_id=request_id,
                    )
                    await self.send_envelope(
                        ws, "rpc_response", request_id, result,
                        trace_id=trace_id,
                        ticket_id=ticket_id,
                        job_id=job_id,
                        actor_role="agent"
                    )
                    return
                
                # Прокидываем ticket/job контекст из envelope в params для оркестратора.
                if isinstance(params, dict):
                    if ticket_id and "ticket_id" not in params:
                        params["ticket_id"] = ticket_id
                    if job_id and "job_id" not in params and "chat_job_id" not in params:
                        params["chat_job_id"] = job_id
                else:
                    logger.warning(f"rpc_request params has invalid type: {type(params).__name__}, fallback to empty dict")
                    params = {}
                    if ticket_id:
                        params["ticket_id"] = ticket_id
                    if job_id:
                        params["chat_job_id"] = job_id

                # Выполняем метод как команду
                result = await self.execute_command(
                    method,
                    params,
                    request_id=request_id,
                    device_id=envelope.get("device_id"),
                    actor_role=payload.get("actor_role", "user")
                )
                
                # Сохраняем в cache
                if idempotency_key:
                    await self.db_manager.save_idempotency_cache(
                        idempotency_key,
                        method,
                        ticket_id,
                        result,
                        ttl_seconds=IDEMPOTENCY_TTL_SECONDS
                    )
                
                # Отправляем rpc_response с полным контекстом
                await self.send_envelope(
                    ws, "rpc_response", request_id, result,
                    trace_id=trace_id,
                    ticket_id=ticket_id,
                    job_id=job_id,
                    actor_role="agent"
                )
                return
            
            # Команда
            if msg_type == "command":
                command = payload.get("command")
                params = payload.get("params", {})
                actor_role = payload.get("actor_role", "user")
                
                # КРИТИЧНО: command_id == request_id (Protocol V3)
                # Ключ идемпотентности = request_id, нигде не генерировать отдельный command_id
                command_id = request_id
                
                # КРИТИЧНО: Получаем ticket_id и job_id из envelope (Protocol V3)
                ticket_id_from_envelope = envelope.get("ticket_id")
                job_id_from_envelope = envelope.get("job_id")
                
                # Добавляем ticket_id и job_id в params если они есть в envelope
                # Это нужно для того, чтобы оркестратор мог использовать их
                if ticket_id_from_envelope and "ticket_id" not in params:
                    params["ticket_id"] = ticket_id_from_envelope
                if job_id_from_envelope and "job_id" not in params and "chat_job_id" not in params:
                    params["chat_job_id"] = job_id_from_envelope
                
                logger.info(f"⚙️  Получена команда: {command}")
                logger.debug(f"🔧 Параметры команды: {params}")
                logger.debug(f"📋 request_id: {request_id}, command_id: {command_id}, device_id: {envelope.get('device_id')}, actor_role: {actor_role}")
                logger.debug(f"📋 ticket_id from envelope: {ticket_id_from_envelope}, job_id from envelope: {job_id_from_envelope}")
                
                # ИДЕМПОТЕНТНОСТЬ: Проверяем, не выполняли ли мы эту команду ранее
                if self.db_manager:
                    cached_result = await self.db_manager.get_command_result(command_id)
                    
                    if cached_result:
                        if cached_result["status"] in {"success", "canceled"}:
                            logger.info(f"♻️  Команда {command_id} уже выполнена (cached), возвращаем кэшированный результат")
                            
                            # Возвращаем кэшированный payload (в точности тот же формат)
                            try:
                                import json
                                cached_payload = jsonlib.loads(cached_result["result_json"]) if cached_result["result_json"] else {}
                            except Exception:
                                cached_payload = {"status": cached_result["status"], "data": {}}
                            
                            # Добавляем cached: true в meta
                            if "meta" not in cached_payload:
                                cached_payload["meta"] = {}
                            cached_payload["meta"]["cached"] = True
                            cached_payload["meta"]["completed_at"] = cached_result["completed_at"]
                            
                            trace_id = envelope.get("trace_id")
                            ticket_id_ctx = envelope.get("ticket_id")
                            job_id_ctx = envelope.get("job_id")
                            actor_role_meta = envelope.get("meta", {}).get("actor_role", "agent")
                            
                            await self.send_envelope(
                                ws, "command_result", request_id, cached_payload,
                                trace_id=trace_id,
                                ticket_id=ticket_id_ctx,
                                job_id=job_id_ctx,
                                actor_role=actor_role_meta
                            )
                            return  # Не выполняем команду повторно
                        
                        elif cached_result["status"] == "in_progress":
                            # Команда в процессе: либо ждём тот же execution, либо разрешаем повтор по TTL
                            started_at = cached_result.get("started_at") or 0
                            age_sec = time.time() - started_at if started_at else float("inf")
                            if age_sec > IN_PROGRESS_STALE_SEC:
                                stale_retry_count = int(cached_result.get("stale_retry_count") or 0)
                                if stale_retry_count >= 1:
                                    logger.warning(
                                        f"⚠️  Команда {command_id} stale in_progress (age={age_sec:.0f}s), "
                                        "но controlled retry уже использован"
                                    )
                                    await self.send_envelope(
                                        ws, "command_result", request_id,
                                        {
                                            "status": "error",
                                            "error": {
                                                "code": "COMMAND_IN_PROGRESS",
                                                "message": "Command is still in progress on another attempt",
                                                "retryable": True,
                                            },
                                            "data": {},
                                            "meta": {},
                                        },
                                        trace_id=envelope.get("trace_id"),
                                        ticket_id=envelope.get("ticket_id"),
                                        job_id=envelope.get("job_id"),
                                        actor_role=envelope.get("meta", {}).get("actor_role", "agent"),
                                    )
                                    return
                                logger.warning(
                                    f"⚠️  Команда {command_id} in_progress stale "
                                    f"(age={age_sec:.0f}s), запускаем controlled retry"
                                )
                                await self.db_manager.mark_command_started(
                                    command_id,
                                    owner_instance_id=self._session_id,
                                    stale_retry=True,
                                )
                            elif command_id in self._running_commands:
                                # Тот же command_id уже выполняется — ждём результат первой задачи
                                future = self._running_commands[command_id]
                                try:
                                    command_result_payload = await asyncio.wait_for(future, timeout=60.0)
                                except asyncio.TimeoutError:
                                    command_result_payload = {
                                        "status": "error",
                                        "error": {"message": "Timeout waiting for duplicate command"},
                                        "data": {},
                                        "meta": {},
                                    }
                                trace_id = envelope.get("trace_id")
                                ticket_id_ctx = envelope.get("ticket_id")
                                job_id_ctx = envelope.get("job_id")
                                actor_role_meta = envelope.get("meta", {}).get("actor_role", "agent")
                                await self.send_envelope(
                                    ws, "command_result", request_id, command_result_payload,
                                    trace_id=trace_id, ticket_id=ticket_id_ctx,
                                    job_id=job_id_ctx, actor_role=actor_role_meta
                                )
                                return
                            else:
                                # In progress, не stale, нет выполняющейся задачи — не запускаем второй раз
                                logger.warning(
                                    f"⚠️  Команда {command_id} в статусе in_progress (age={age_sec:.0f}s), "
                                    f"retry later"
                                )
                                await self.send_envelope(
                                    ws, "command_result", request_id,
                                    {
                                        "status": "error",
                                        "error": {
                                            "code": "COMMAND_IN_PROGRESS",
                                            "message": "Command still in progress, retry later",
                                            "retryable": True,
                                        },
                                        "data": {},
                                        "meta": {},
                                    },
                                    trace_id=envelope.get("trace_id"),
                                    ticket_id=envelope.get("ticket_id"),
                                    job_id=envelope.get("job_id"),
                                    actor_role=envelope.get("meta", {}).get("actor_role", "agent"),
                                )
                                return
                    
                    # Помечаем команду как начатую
                    await self.db_manager.mark_command_started(
                        command_id,
                        owner_instance_id=self._session_id,
                    )
                
                # КРИТИЧНО: Отправляем command_ack ПОСЛЕ seen_commands проверки и минимальной валидации,
                # НО ДО PolicyEngine/Consent (это бизнес-решения, не протокольные reject)
                trace_id = envelope.get("trace_id")
                ticket_id_ctx = envelope.get("ticket_id")
                job_id_ctx = envelope.get("job_id")
                actor_role_meta = envelope.get("meta", {}).get("actor_role", "agent")
                
                try:
                    # Минимальная валидация envelope
                    if not request_id:
                        raise ValueError("Missing request_id")
                    if not envelope.get("device_id"):
                        raise ValueError("Missing device_id")
                    
                    # Отправить command_ack со статусом 'accepted'
                    await self.send_envelope(
                        ws, "command_ack", request_id,
                        {"status": "accepted"},
                        trace_id=trace_id,
                        ticket_id=ticket_id_ctx,
                        job_id=job_id_ctx,
                        actor_role=actor_role_meta
                    )
                    logger.debug(f"✅ [command_ack] Отправлен accepted для command_id={command_id}")
                    
                except ValueError as e:
                    # Протокольная ошибка (invalid payload/schema) - отправляем rejected
                    logger.warning(f"⚠️  [command_ack] Протокольная ошибка: {e}, отправляем rejected")
                    await self.send_envelope(
                        ws, "command_ack", request_id,
                        {"status": "rejected", "reason": str(e)},
                        trace_id=trace_id
                    )
                    return  # Не выполняем команду
                
                # Process-local dedupe: другие запросы с тем же command_id будут ждать этот Future
                run_future = asyncio.get_event_loop().create_future()
                self._running_commands[command_id] = run_future
                execution_kwargs = {
                    "command": command,
                    "params": params,
                    "request_id": request_id,
                    "command_id": command_id,
                    "device_id": envelope.get("device_id"),
                    "actor_role": actor_role,
                    "trace_id": envelope.get("trace_id"),
                    "ticket_id_ctx": envelope.get("ticket_id"),
                    "job_id_ctx": envelope.get("job_id"),
                    "actor_role_meta": envelope.get("meta", {}).get("actor_role", "agent"),
                }
                if self._should_run_command_in_background(command):
                    task = asyncio.create_task(
                        self._execute_command_and_send_result(ws, **execution_kwargs),
                        name=f"agent.command.{command_id}",
                    )
                    self._track_background_command_task(task)
                    logger.debug(
                        f"📦 Команда {command} переведена в background dispatch "
                        f"(command_id={command_id})"
                    )
                    return

                await self._execute_command_and_send_result(ws, **execution_kwargs)
                return
            
            # Command result - ответ на команду, отправленную агентом серверу (например, chat_raise)
            if msg_type == "command_result":
                logger.debug(f"📬 Получен command_result: request_id={request_id}")
                
                # Проверяем, ждем ли мы этот ответ (для chat_raise)
                if request_id in self._pending_chat_raise:
                    future = self._pending_chat_raise.pop(request_id)
                    if not future.done():
                        future.set_result(envelope)
                        logger.debug(f"✅ command_result обработан: request_id={request_id}")
                    return
                
                # Если не нашли pending future, просто логируем
                logger.debug(f"📬 command_result без ожидающего future: request_id={request_id}")
                return
            
            # Неизвестный тип сообщения
            trace_id = envelope.get("trace_id")
            logger.warning(f"⚠️  Неизвестный тип сообщения: {msg_type} (trace_id={trace_id})")
            await self.send_envelope(
                ws, "error", request_id, {
                    "status": "error",
                    "error": {
                        "code": "UNKNOWN_MESSAGE_TYPE",
                        "message": f"Неизвестный тип сообщения: {msg_type}"
                    }
                },
                trace_id=trace_id,
                actor_role="agent"
            )
                
        except jsonlib.JSONDecodeError as e:
            # Текстовые команды (ping)
            if message.strip().lower() == "ping":
                logger.debug("📶 Получен ping от сервера (текст)")
                request_id = str(uuid.uuid4())
                trace_id = str(uuid.uuid4())
                await self.send_envelope(
                    ws, "pong", request_id, {},
                    trace_id=trace_id,
                    actor_role="agent"
                )
                return
            logger.error(f"❌ Ошибка декодирования JSON: {e}")
            logger.debug(f"Сообщение: {message}")
            # Отправляем ошибку в формате Protocol V3 envelope
            request_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            await self.send_envelope(
                ws, "error", request_id, {
                    "status": "error",
                    "error": {
                        "code": "JSON_DECODE_ERROR",
                        "message": f"Ошибка декодирования JSON: {str(e)}"
                    }
                },
                trace_id=trace_id,
                actor_role="agent"
            )
        
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
            logger.exception(e)
            request_id = str(uuid.uuid4())
            trace_id = str(uuid.uuid4())
            await self.send_envelope(
                ws, "error", request_id, {
                    "status": "error",
                    "error": {
                        "code": "MESSAGE_HANDLING_ERROR",
                        "message": str(e)
                    }
                },
                trace_id=trace_id,
                actor_role="agent"
            )
    
    async def execute_command(
        self, 
        command: str, 
        params: Dict[str, Any],
        request_id: Optional[str] = None,
        device_id: Optional[str] = None,
        actor_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Выполняет команду и возвращает результат в формате ToolResponse (dict).
        
        Команды делегируются оркестратору, кроме специфичных для ws_agent:
        - get_status, get_info, get_history - обрабатываются здесь
        - ping, collect, list_modules, update, exec_script, get_manifest, list_tools - делегируются оркестратору
        
        ВАЖНО: Результат НЕ должен содержать device_id в top-level.
        device_id добавляется только в envelope при отправке.
        
        Args:
            command: Название команды
            params: Параметры команды
            request_id: Идентификатор запроса (из входящего envelope)
            device_id: Идентификатор устройства (из входящего envelope)
            actor_role: Роль актора (из payload входящего envelope)
        
        Returns:
            Dict с результатом выполнения (ToolResponse.model_dump())
        """
        try:
            logger.info(f"🎯 Начинаю выполнение команды: {command}")
            logger.debug(f"📋 Параметры: {params}")
            logger.debug(f"📋 request_id: {request_id}, device_id: {device_id}, actor_role: {actor_role}")
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # КОМАНДЫ ОРКЕСТРАТОРА (делегируем через handle_command)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            orchestrator_commands = ["ping", "collect", "list_modules", "update", "install_module_package", "exec_script", "get_manifest", "list_tools", "run_tool", "call_tool", "run_recipe", "list_installed_modules", "activate_module", "rollback_module", "deactivate_module", "remove_module_version", "remove_module", "start_job", "stop_job", "get_job_status", "list_jobs", "job_send_event", "ui_notify", "cancel_operation"]
            
            if command in orchestrator_commands:
                logger.info(f"📨 Делегирую команду '{command}' оркестратору")   
                
                # Формируем команду для оркестратора
                orchestrator_cmd = {"cmd": command}
                if command == "cancel_operation":
                    orchestrator_cmd["params"] = dict(params)
                else:
                    orchestrator_cmd.update(params)  # Добавляем все параметры
                
                # Фикс для run_tool: переименовываем tool_name в tool
                if command == "run_tool" and "tool_name" in orchestrator_cmd:
                    orchestrator_cmd["tool"] = orchestrator_cmd.pop("tool_name")
                    logger.debug(f"🔧 Переименован параметр tool_name → tool: {orchestrator_cmd.get('tool')}")
                
                # ОБЯЗАТЕЛЬНО добавляем request_id, device_id, actor_role
                if request_id:
                    orchestrator_cmd["request_id"] = request_id
                if device_id:
                    orchestrator_cmd["device_id"] = device_id
                if actor_role:
                    orchestrator_cmd["actor_role"] = actor_role
                
                logger.debug(f"🔧 Команда для оркестратора: {orchestrator_cmd}")
                
                # Вызываем оркестратор
                result = await self.orchestrator.handle_command(orchestrator_cmd)
                
                logger.debug(f"📬 Результат от оркестратора: {result}")
                
                # НЕ добавляем device_id - он будет в envelope
                if result.get("status") == "success":
                    logger.success(f"✅ Команда '{command}' успешно выполнена оркестратором")
                else:
                    logger.warning(
                        f"Команда '{command}' завершилась со статусом {result.get('status')}"
                    )
                return result
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # СТАТУС АГЕНТА (специфичная команда ws_agent)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            elif command == "remote_assist.request":
                if self.event_bus:
                    await self.event_bus.publish(
                        {
                            "event_type": "remote_assist_request",
                            "data": dict(params or {}),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                return {
                    "status": "success",
                    "data": {
                        "accepted": True,
                        "session_id": params.get("session_id"),
                    },
                    "error": None,
                    "meta": {"command": command, "request_id": request_id},
                }

            elif command == "get_status":
                """Получить расширенный статус агента"""
                uptime = time.time() - self.start_time
                
                # Возвращаем в формате ToolResponse
                from pc_agent.core.tool_response import ToolResponse, ToolMeta, ToolData, ok
                
                meta = ToolMeta(
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    command=command,
                    request_id=request_id,  # Используем request_id из входящего envelope
                    agent_id=None,
                    duration_ms=None
                )
                
                observations = {
                    "agent": {
                        "version": "2.0.0",
                        "device_id": self.device_id,
                        "uptime": round(uptime, 2),
                        "uptime_human": self._format_uptime(uptime),
                    },
                    "config": {
                        "db_path": str(runtime_paths.resolve_storage_db_path(self._data_root or Path(get_config().paths.data_dir))),
                        "ws_url": get_config().server.ws_url,
                        "api_url": get_config().server.api_url,
                        "modules_enabled": get_config().enabled_modules,
                    },
                }
                
                data = ToolData(observations=observations)
                response = ok(data=data, meta=meta)
                return response.model_dump()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ИНФОРМАЦИЯ О СИСТЕМЕ (специфичная команда ws_agent)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            elif command == "search_action_trace":
                """Поиск action trace для tech/observer drilldown."""
                from pc_agent.core.tool_response import ToolMeta, ToolData, ok

                meta = ToolMeta(
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    command=command,
                    request_id=request_id,
                    agent_id=None,
                    duration_ms=None,
                )
                limit_raw = params.get("limit", 50)
                try:
                    limit = max(1, min(int(limit_raw), 200))
                except (TypeError, ValueError):
                    limit = 50
                rows = search_action_trace(
                    limit=limit,
                    action_id=params.get("action_id"),
                    parent_action_id=params.get("parent_action_id"),
                    ticket_id=params.get("ticket_id"),
                    operation_id=params.get("operation_id"),
                    message_id=params.get("message_id"),
                    tool_name=params.get("tool_name"),
                    status=params.get("status"),
                    text=resolve_action_trace_text_filter(
                        text=params.get("text"),
                        trace_id=params.get("trace_id"),
                        operation_id=params.get("operation_id"),
                        ticket_id=params.get("ticket_id"),
                    ),
                )
                recorder = get_action_trace_recorder()
                data = ToolData(
                    observations={
                        "entries": rows,
                        "count": len(rows),
                        "path": str(recorder.path) if getattr(recorder, "path", None) else None,
                    }
                )
                response = ok(data=data, meta=meta)
                return response.model_dump()

            elif command == "get_info":
                """Получить системную информацию (быстрый запрос без модулей)"""
                from pc_agent.core.tool_response import ToolResponse, ToolMeta, ToolData, ok
                
                meta = ToolMeta(
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    command=command,
                    request_id=request_id,  # Используем request_id из входящего envelope
                    agent_id=None,
                    duration_ms=None
                )
                
                observations = {
                    "hostname": socket.gethostname(),
                    "os": platform.system(),
                    "os_version": platform.release(),
                    "python_version": platform.python_version(),
                    "architecture": platform.machine(),
                }
                
                data = ToolData(observations=observations)
                response = ok(data=data, meta=meta)
                return response.model_dump()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # ИСТОРИЯ СОБЫТИЙ (специфичная команда ws_agent)
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            elif command == "get_history":
                """Получить историю событий из БД"""
                from pc_agent.core.tool_response import ToolResponse, ToolMeta, ToolData, ok
                
                limit = params.get("limit", 10)
                module = params.get("module")
                
                logger.info(f"📜 Получаю историю (limit={limit}, module={module})")
                
                events = await self.db_manager.get_events(
                    limit=limit,
                    module_name=module
                )
                
                meta = ToolMeta(
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    command=command,
                    request_id=request_id,  # Используем request_id из входящего envelope
                    agent_id=None,
                    duration_ms=None
                )
                
                observations = {
                    "events": events,
                    "count": len(events),
                }
                
                data = ToolData(observations=observations)
                response = ok(data=data, meta=meta)
                return response.model_dump()
            
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # НЕИЗВЕСТНАЯ КОМАНДА
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            else:
                from pc_agent.core.tool_response import ToolResponse, ToolMeta, fail
                
                meta = ToolMeta(
                    timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    command=command,
                    request_id=request_id,  # Используем request_id из входящего envelope
                    agent_id=None,
                    duration_ms=None
                )
                
                response = fail(
                    code="UNKNOWN_COMMAND",
                    message=f"Неизвестная команда: {command}",
                    meta=meta,
                    details={
                        "available_commands": [
                            "ping",           # Оркестратор
                            "collect",        # Оркестратор
                            "list_modules",   # Оркестратор
                            "update",         # Оркестратор (заглушка)
                            "exec_script",    # Оркестратор
                            "get_manifest",   # Оркестратор
                            "list_tools",     # Оркестратор
                            "run_tool",       # Оркестратор
                            "call_tool",      # Оркестратор (алиас для run_tool)
                            "get_status",     # WS Agent
                            "get_info",       # WS Agent
                            "get_history",    # WS Agent
                            "ui_notify"       # Оркестратор
                        ]
                    }
                )
                return response.model_dump()
        
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения команды {command}: {e}")
            logger.exception(e)
            from pc_agent.core.tool_response import ToolResponse, ToolMeta, fail
            
            meta = ToolMeta(
                timestamp_iso=datetime.now(timezone.utc).isoformat(),
                command=command,
                request_id=request_id,  # Используем request_id из входящего envelope
                agent_id=None,
                duration_ms=None
            )
            
            response = fail(
                code="COMMAND_EXECUTION_ERROR",
                message=str(e),
                meta=meta,
                details={"exception_type": type(e).__name__}
            )
            return response.model_dump()

    def _scheduler_success(self, observations: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
        return helper_scheduler_success(observations, request_id)

    def _scheduler_error(self, code: str, message: str, request_id: Optional[str]) -> Dict[str, Any]:
        return helper_scheduler_error(code, message, request_id)

    async def _handle_scheduler_rpc(
        self,
        method: str,
        params: Dict[str, Any],
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        return await helper_handle_scheduler_rpc(self, method, params, request_id)

    async def _scheduler_runtime_loop(self) -> None:
        await helper_scheduler_runtime_loop(self)

    async def _execute_scheduled_task(self, task: Dict[str, Any]) -> None:
        await helper_execute_scheduled_task(self, task)
    
    def _format_uptime(self, seconds: float) -> str:
        return helper_format_uptime(seconds)
    
    async def authenticate(self) -> bool:
        return await helper_authenticate(self)
    
    def _connection_rejected_flag_path(self) -> Path:
        return connection_rejected_flag_path_for(self)

    async def request_connection_flow(self, wait_for_approval_seconds: int = 600) -> Tuple[bool, bool]:
        return await helper_request_connection_flow(self, wait_for_approval_seconds)

    async def _request_token_from_console(self) -> bool:
        return await helper_request_token_from_console(self)
    
    async def chat_raise(self, title: str = "Support needed", reason: str = "agent_report", severity: str = "warning", context: dict | None = None) -> dict[str, Any] | None:
        """
        Инициирует чат через WebSocket команду к серверу.
        
        Args:
            title: Заголовок чат-сессии
            reason: Причина инициации чата
            severity: Уровень важности (warning, error, info и т.д.)
            context: Дополнительный контекст
        
        Returns:
            Словарь с job_id и ticket_id или None при ошибке
        """
        if not hasattr(self, '_agent_ws') or not self._agent_ws:
            logger.error("[chat_raise] WebSocket not connected")
            return None
        
        # Формируем команду для сервера (не для агента!)
        request_id = str(uuid.uuid4())
        envelope = {
            "type": "command",
            "request_id": request_id,
            "device_id": self.device_id,
            "payload": {
                "command": "chat_raise",
                "params": {
                    "title": title,
                    "reason": reason,
                    "severity": severity,
                    "context": context or {}
                }
            }
        }
        
        # Создаем Future для ожидания ответа
        future = asyncio.get_event_loop().create_future()
        self._pending_chat_raise[request_id] = future
        
        try:
            # Отправляем команду серверу
            await self._agent_ws.send_json(envelope)
            logger.info(f"[chat_raise] command sent request_id={request_id}")
            
            # Ждем ответ с таймаутом
            response = await asyncio.wait_for(future, timeout=30)
            
            # Извлекаем job_id и ticket_id из ответа
            payload = response.get("payload", {})
            if payload.get("status") == "error":
                error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
                error_code = str(error.get("code") or "CHAT_RAISE_FAILED")
                error_message = str(error.get("message") or "chat_raise failed")
                logger.warning(f"[chat_raise] server error code={error_code} message={error_message}")
                return {"ok": False, "error_code": error_code, "error": error_message}
            data = payload.get("data", {})
            observations = data.get("observations", {})
            job_id = observations.get("job_id")
            ticket_id = observations.get("ticket_id")

            if job_id and ticket_id:
                logger.info(f"[chat_raise] success job_id={job_id} ticket_id={ticket_id}")
                return {"job_id": job_id, "ticket_id": ticket_id}
            else:
                logger.warning(f"[chat_raise] incomplete response: {response}")
                return None
                
        except asyncio.TimeoutError:
            logger.error(f"[chat_raise] timeout waiting for response")
            # Удаляем из pending
            self._pending_chat_raise.pop(request_id, None)
            return None
        except Exception as e:
            logger.error(f"[chat_raise] failed: {e}")
            # Удаляем из pending
            self._pending_chat_raise.pop(request_id, None)
            return None
    
    async def run(self):
        """
        Основной цикл работы агента с WebSocket.
        """
        await self.authenticate()

        # Если токена нет — используем flow «запрос на подключение» (connection request)
        if not self.auth_token:
            flag_path = self._connection_rejected_flag_path()
            if flag_path.exists():
                logger.warning("Подключение ранее было отклонено администратором. Новые запросы не отправляются.")
                await self._publish_connection_state("rejected", "подключение отклонено")
                if self.event_bus:
                    await self.event_bus.publish({
                        "event_type": "connection_rejected",
                        "data": {"message": "Администратор отклонил подключение"},
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                return
            ok, rejected = await self.request_connection_flow()
            if not ok:
                if rejected:
                    error_code = getattr(self.identity_manager, "last_connection_request_error_code", None)
                    if error_code != "DEVICE_ARCHIVED":
                        try:
                            flag_path.parent.mkdir(parents=True, exist_ok=True)
                            flag_path.write_text("rejected", encoding="utf-8")
                        except Exception as e:
                            logger.warning(f"Не удалось записать флаг отклонения: {e}")
                    else:
                        logger.info("Локальный reject-флаг не записан: устройство архивировано на сервере")
                return
            # Токен получен и сохранён в request_connection_flow(), продолжаем

        # Запускаем UI API сервер (если main_async с GUI уже поднял — start() no-op)
        if self.ui_api_server and not self.ui_api_task:
            try:
                ok = await self.ui_api_server.start()
                if ok:
                    logger.info("🚀 UI API сервер запущен")
            finally:
                self.ui_api_task = True

        
        # Создаем или используем существующую HTTP сессию
        if not self._http_session:
            self._http_session = ClientSession()
        
        self._run_task = asyncio.current_task()
        try:
            async with ClientSession() as session:
                while True:
                    should_exit = False
                    try:
                        await self._publish_connection_state("connecting", "подключение к серверу")
                        logger.info(f"🔄 Подключаюсь к серверу: {get_config().server.ws_url}")
                        
                        async with session.ws_connect(get_config().server.ws_url) as ws:
                            logger.success("✅ Подключено к серверу")
                            await self._publish_connection_state("authorizing", "ожидание handshake_ack")
                            
                            # Сохраняем ссылку на WebSocket для использования в chat_raise и других методах
                            self._agent_ws = ws
                            
                            # Protocol V3 Handshake с полным набором capabilities
                            handshake_data = self.identity_manager.get_handshake_data()
                            handshake_request_id = str(uuid.uuid4())
                            handshake_trace_id = str(uuid.uuid4())
                            latest_update_confirmation = self._get_latest_update_handshake_payload()
                            
                            # Получить tools_list через orchestrator для toolset_hash
                            try:
                                tools_list = self.orchestrator._build_tools_list()
                                tools_count = len(tools_list)
                                # Вычислить toolset_hash (compute_toolset_hash сама отсортирует tools_list)
                                from pc_agent.utils.toolset_hash import compute_toolset_hash
                                toolset_hash = compute_toolset_hash(tools_list) if tools_list else None
                            except Exception as e:
                                logger.warning(f"⚠️ Ошибка при вычислении toolset_hash: {e}")
                                tools_list = []
                                tools_count = 0
                                toolset_hash = None
                            
                            # Получить installed modules через orchestrator.module_manager для modules_inventory
                            modules_inventory = []
                            module_manager = getattr(self.orchestrator, "module_manager", None) if self.orchestrator else None
                            if module_manager:
                                try:
                                    installed_modules_data = module_manager.list_installed()
                                    for module_info in installed_modules_data.get("modules", []):
                                        module_name = module_info["name"]
                                        active_version = module_info.get("active")
                                        versions = module_info.get("versions", [])
                                        # Flattened format: [{name, version, state, active}]
                                        for version in versions:
                                            modules_inventory.append({
                                                "name": module_name,
                                                "version": version,
                                                "state": "active" if version == active_version else "installed",
                                                "active": version == active_version
                                            })
                                except Exception as e:
                                    logger.warning(f"⚠️ Ошибка при получении modules_inventory: {e}")
                                    modules_inventory = []
                            
                            handshake_message = {
                                "type": "handshake",
                                "request_id": handshake_request_id,
                                "protocol_version": PROTOCOL_VERSION,  # "ws_ticket_v3"
                                "device_id": self.device_id,
                                "trace_id": handshake_trace_id,
                                "payload": {
                                    "token": handshake_data.get("token"),
                                    "uuid": handshake_data.get("uuid"),  # Backward-compatible alias of machine_id
                                    "device_id": self.device_id,  # Canonical machine_id
                                    "machine_id": handshake_data.get("machine_id"),
                                    "install_id": handshake_data.get("install_id"),
                                    "machine_id_source": handshake_data.get("machine_id_source"),
                                    "hostname": handshake_data.get("hostname"),
                                    "os": handshake_data.get("os"),
                                    "agent_version": AGENT_VERSION,
                                    "db_schema_version": DB_SCHEMA_VERSION,
                                    "tools_version": "tools_v1",
                                    "toolset_hash": toolset_hash,  # NEW: для синхронизации toolset с сервером
                                    "tools_count": tools_count,    # NEW: количество tools
                                    # Список реально загруженных модулей (включая пакетные из modules_store).
                                    # Fallback на конфиг если оркестратор ещё не инициализирован.
                                    "modules": [m.name for m in getattr(self.orchestrator, 'loaded_modules', [])] or get_config().enabled_modules,
                                    "modules_inventory": modules_inventory  # NEW: full inventory
                                },
                                "meta": {
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "actor_role": "agent",
                                    "capabilities": [
                                        # Core Protocol V3 features (Critical for server)
                                        "protocol_v3",
                                        "envelope_v3",
                                        "trace_correlation",
                                        
                                        # Event handling (V3)
                                        "deterministic_event_id",
                                        "agent_seq_per_ticket",
                                        "device_seq_per_device",  # NEW: для device events
                                        
                                        # Context tracking (Critical for server)
                                        "ticket_context",
                                        "job_context",
                                        
                                        # Reliability (Critical for server)
                                        "idempotency_keys",
                                        "nack_support",
                                        "outbox_ack_v3",  # Critical: новый формат ACK
                                        "retry_policy",
                                        "outbox_batch_v1",
                                        
                                        # Advanced features
                                        "reconcile_tickets",
                                        "scheduled_tasks",
                                        "attachment_refs",
                                        "consent_flow",
                                        
                                        # Message types
                                        "rpc_request",
                                        "rpc_response",
                                        "outbox_item",
                                        "job_events",
                                        "device_events"  # NEW: поддержка событий без ticket_id
                                    ],
                                    "supported_message_types": list(ALLOWED_MESSAGE_TYPES)
                                },
                                # Legacy fields for backward compatibility with V2 servers
                                "token": handshake_data.get("token"),
                                "agent_version": AGENT_VERSION,
                                "tools_version": "tools_v1",
                                "supported_message_types": list(ALLOWED_MESSAGE_TYPES),
                                "modules": get_config().enabled_modules
                            }
                            
                            # Сохраняем trace_id для последующей корреляции
                            if latest_update_confirmation:
                                handshake_message["payload"].update(latest_update_confirmation)
                                logger.info(
                                    "[update] Including latest update report in handshake: "
                                    + ", ".join(f"{key}={value}" for key, value in latest_update_confirmation.items())
                                )

                            self._current_trace_id = handshake_trace_id

                            await ws.send_json(handshake_message)
                            has_tok = bool(handshake_data.get("token"))
                            logger.info(f"🤝 Отправлен handshake с аутентификацией")
                            logger.debug(f"   Токен в handshake: {'да' if has_tok else 'нет'}" + (f" ({handshake_data['token'][:12]}...)" if has_tok else ""))
                            logger.debug(f"   Device ID: {handshake_data['uuid'][:8]}...")
                            logger.debug(f"   Hostname: {handshake_data['hostname']}")
                            logger.debug(f"   Protocol: {PROTOCOL_VERSION}")
                            
                            # Небольшая задержка для обработки сервером
                            await asyncio.sleep(0.1)
                            
                            # Проверяем состояние соединения сразу после handshake
                            # Сервер может закрыть соединение сразу, если токен невалидный
                            if ws.closed:
                                close_code = getattr(ws, 'close_code', None)
                                close_message = getattr(ws, 'close_message', None)
                                
                                if close_code == 4003:
                                    error_msg = close_message.decode('utf-8', errors='ignore') if close_message else "Invalid token"
                                    logger.error(f"🔴 Ошибка аутентификации при handshake: {error_msg}")
                                    logger.warning("🔑 Токен невалиден или отсутствует. Требуется ввести новый токен.")
                                    await self._publish_connection_state("auth_required", "невалидный токен")
                                    
                                    # НЕ очищаем токен сразу - возможно, GUI еще работает или пользователь вставил токен вручную
                                    # Очищаем токен только если GUI не включен или если авторизация через GUI не удалась
                                    # Используем глобальный config (импортирован на строке 48)
                                    gui_enabled = get_config().ui and get_config().ui.enabled
                                    
                                    if not gui_enabled:
                                        # Если GUI не включен, очищаем токен и запрашиваем через консоль
                                        self.identity_manager.clear_token()
                                        if self.db_manager:
                                            try:
                                                await self.db_manager.clear_auth_token(self.identity_manager.device_id)
                                            except Exception as e:
                                                logger.debug(f"Не удалось очистить токен из БД: {e}")
                                        
                                        # Запрашиваем новый токен через консоль
                                        logger.info("=" * 70)
                                        logger.info("💡 Инструкция:")
                                        logger.info("   1. Откройте admin панель сервера: http://server:8666/admin")
                                        logger.info("   2. Перейдите в раздел 'Generate Agent Token'")
                                        logger.info(f"   3. Введите canonical device ID: {self.device_id}")
                                        logger.info("   4. Скопируйте токен и вставьте его в диалог ниже")
                                        logger.info("=" * 70)
                                        
                                        # Запрашиваем токен через консоль (GUI отключен)
                                        if not await self._request_token_from_console():
                                            logger.error("❌ Не удалось получить токен. Завершение работы.")
                                            should_exit = True
                                            break
                                    else:
                                        logger.info("🖥️ GUI включен, запускаю automatic reprovision flow...")
                                        if not await self._request_token_from_console():
                                            logger.error("❌ Не удалось получить токен. Завершение работы.")
                                            should_exit = True
                                            break
                                    
                                    logger.info("✅ Токен получен. Переподключаемся...")
                                    continue  # Переподключаемся
                                else:
                                    msg_text = close_message.decode('utf-8', errors='ignore') if close_message else "Unknown"
                                    logger.warning(f"🔌 Соединение закрыто сервером: code={close_code}, message={msg_text}")
                                    await self._publish_connection_state("disconnected", msg_text)
                                    break
                            
                            # Ждем ответ handshake_ack (опционально, не блокируем если нет)
                            # Первое сообщение может быть handshake_ack
                        
                            # Создаем и запускаем WSOutboxFlusher
                            self.flusher = WSOutboxFlusher(
                                db_manager=self.db_manager,
                                device_id=self.device_id,
                                logger_instance=logger
                            )
                            
                            # Создаем функцию-обертку для отправки через ws (Protocol V3)
                            # sender.py может передавать trace_id для batched outbox envelopes
                            async def send_wrapper(
                                msg_type: str,
                                request_id: Optional[str],
                                payload_dict: Dict[str, Any],
                                ticket_id: Optional[str] = None,
                                job_id: Optional[str] = None,
                                trace_id: Optional[str] = None,
                            ):
                                # Protocol V3: передаем ticket_id и job_id в send_envelope
                                await self.send_envelope(
                                    ws, msg_type, request_id, payload_dict,
                                    trace_id=trace_id or str(uuid.uuid4()),
                                    ticket_id=ticket_id,
                                    job_id=job_id,
                                    actor_role="agent"
                                )
                            
                            # Запускаем flusher в отдельной задаче
                            self.flusher_task = asyncio.create_task(
                                self.flusher.run(send_wrapper)
                            )
                            logger.info("📤 WSOutboxFlusher запущен")
                            
                            # Восстанавливаем jobs после перезапуска (только при первом подключении)
                            # Вызываем recover_jobs_on_startup через оркестратор
                            if self.orchestrator and self.orchestrator.job_manager:
                                try:
                                    recovery_result = await self.orchestrator.job_manager.recover_jobs_on_startup()
                                    logger.success(
                                        f"✅ Восстановление jobs завершено: "
                                        f"recovered={recovery_result['recovered']}, "
                                        f"stopped={recovery_result['stopped']}, "
                                        f"errors={recovery_result['errors']}"
                                    )
                                except Exception as e:
                                    logger.error(f"❌ Ошибка восстановления jobs: {e}")
                            
                            # Цикл чтения сообщений
                            connection_closed_auth_error = False
                            first_msg_processed = False
                            try:
                                async for msg in ws:
                                    first_msg_processed = True
                                    if msg.type == WSMsgType.TEXT:
                                        await self.handle_message(ws, msg.data)
                                        
                                    elif msg.type == WSMsgType.CLOSED:
                                        # Проверяем код закрытия
                                        close_code = getattr(ws, 'close_code', None)
                                        close_message = getattr(ws, 'close_message', None)
                                        
                                        if close_code == 4003:
                                            connection_closed_auth_error = True
                                            # Токен невалидный или отсутствует
                                            error_msg = close_message.decode('utf-8', errors='ignore') if close_message else "Invalid token"
                                            logger.error(f"🔴 Ошибка аутентификации: {error_msg}")
                                            logger.warning("🔑 Токен невалиден или отсутствует. Требуется ввести новый токен.")
                                            await self._publish_connection_state("auth_required", "невалидный токен")
                                            
                                            # Очищаем токен
                                            self.identity_manager.clear_token()
                                            if self.db_manager:
                                                try:
                                                    await self.db_manager.clear_auth_token(self.identity_manager.device_id)
                                                except Exception as e:
                                                    logger.debug(f"Не удалось очистить токен из БД: {e}")
                                            
                                            # Запрашиваем новый токен
                                            logger.info("=" * 70)
                                            logger.info("💡 Инструкция:")
                                            logger.info("   1. Откройте admin панель сервера: http://server:8666/admin")
                                            logger.info("   2. Перейдите в раздел 'Generate Agent Token'")
                                            logger.info(f"   3. Введите canonical device ID: {self.device_id}")
                                            logger.info("   4. Скопируйте токен и вставьте его в диалог ниже")
                                            logger.info("=" * 70)
                                            
                                            # Запрашиваем токен через консоль (GUI отключен)
                                            if not await self._request_token_from_console():
                                                logger.error("❌ Не удалось получить токен. Завершение работы.")
                                                should_exit = True
                                                break
                                            
                                            logger.info("✅ Токен получен. Переподключаемся...")
                                        else:
                                            msg_text = close_message.decode('utf-8', errors='ignore') if close_message else "Unknown"
                                            logger.warning(f"🔌 Соединение закрыто сервером: code={close_code}, message={msg_text}")
                                            await self._publish_connection_state("disconnected", msg_text)
                                        break
                                        
                                    elif msg.type == WSMsgType.ERROR:
                                        logger.error(f"❌ Ошибка WebSocket: {ws.exception()}")
                                        await self._publish_connection_state("disconnected", "ошибка websocket")
                                        break
                            except asyncio.CancelledError:
                                logger.info("🛑 Получен сигнал отмены, завершаю работу...")
                                raise
                            except Exception as read_error:
                                # Если соединение было закрыто во время чтения - проверяем код закрытия
                                if ws.closed:
                                    close_code = getattr(ws, 'close_code', None)
                                    if close_code == 4003:
                                        connection_closed_auth_error = True
                                        close_message = getattr(ws, 'close_message', None)
                                        error_msg = close_message.decode('utf-8', errors='ignore') if close_message else "Invalid token"
                                        logger.error(f"🔴 Ошибка аутентификации (при чтении): {error_msg}")
                                        logger.warning("🔑 Токен невалиден или отсутствует. Требуется ввести новый токен.")
                                        await self._publish_connection_state("auth_required", "невалидный токен")
                                        
                                        # Очищаем токен
                                        self.identity_manager.clear_token()
                                        if self.db_manager:
                                            try:
                                                await self.db_manager.clear_auth_token(self.identity_manager.device_id)
                                            except Exception as e:
                                                logger.debug(f"Не удалось очистить токен из БД: {e}")
                                        
                                        # Запрашиваем новый токен
                                        logger.info("=" * 70)
                                        logger.info("💡 Инструкция:")
                                        logger.info("   1. Откройте admin панель сервера: http://server:8666/admin")
                                        logger.info("   2. Перейдите в раздел 'Generate Agent Token'")
                                        logger.info(f"   3. Введите canonical device ID: {self.device_id}")
                                        logger.info("   4. Скопируйте токен и вставьте его в диалог ниже")
                                        logger.info("=" * 70)
                                        
                                        if not await self._request_token_from_console():
                                            logger.error("❌ Не удалось получить токен. Завершение работы.")
                                            should_exit = True
                                    else:
                                        logger.error(f"❌ Ошибка при чтении сообщений: {read_error}")
                                        await self._publish_connection_state("disconnected", "ошибка чтения")
                                else:
                                    logger.error(f"❌ Неожиданная ошибка при чтении: {read_error}")
                                    await self._publish_connection_state("disconnected", "ошибка чтения")
                            finally:
                                # Если соединение было закрыто до начала чтения - проверяем код закрытия
                                if not first_msg_processed and ws.closed:
                                    close_code = getattr(ws, 'close_code', None)
                                    if close_code == 4003:
                                        connection_closed_auth_error = True
                                        close_message = getattr(ws, 'close_message', None)
                                        error_msg = close_message.decode('utf-8', errors='ignore') if close_message else "Invalid token"
                                        logger.error(f"🔴 Ошибка аутентификации при handshake: {error_msg}")
                                        logger.warning("🔑 Токен невалиден или отсутствует. Требуется ввести новый токен.")
                                        await self._publish_connection_state("auth_required", "невалидный токен")
                                        
                                        # Очищаем токен
                                        self.identity_manager.clear_token()
                                        if self.db_manager:
                                            try:
                                                await self.db_manager.clear_auth_token(self.identity_manager.device_id)
                                            except Exception as e:
                                                logger.debug(f"Не удалось очистить токен из БД: {e}")
                                        
                                        # Запрашиваем новый токен
                                        logger.info("=" * 70)
                                        logger.info("💡 Инструкция:")
                                        logger.info("   1. Откройте admin панель сервера: http://server:8666/admin")
                                        logger.info("   2. Перейдите в раздел 'Generate Agent Token'")
                                        logger.info(f"   3. Введите canonical device ID: {self.device_id}")
                                        logger.info("   4. Скопируйте токен и вставьте его в диалог ниже")
                                        logger.info("=" * 70)
                                        
                                        if not await self._request_token_from_console():
                                            logger.error("❌ Не удалось получить токен. Завершение работы.")
                                            should_exit = True
                            
                            # Останавливаем flusher при разрыве соединения
                            if self.flusher_task:
                                logger.info("🛑 Останавливаю WSOutboxFlusher...")
                                self.flusher_task.cancel()
                                try:
                                    await self.flusher_task
                                except asyncio.CancelledError:
                                    pass
                                self.flusher_task = None
                                self.flusher = None
                                logger.info("✅ WSOutboxFlusher остановлен")
                            
                            # Обнуляем ссылку на WebSocket
                            self._agent_ws = None
                            
                            # Отменяем все pending chat_raise запросы
                            for req_id, future in self._pending_chat_raise.items():
                                if not future.done():
                                    future.cancel()
                            self._pending_chat_raise.clear()
                            
                            # Проверяем причину закрытия
                            if connection_closed_auth_error:
                                # Уже обработали выше, просто логируем
                                logger.info("⏳ Переподключение с новым токеном...")
                            else:
                                logger.warning("❌ Потеря связи с сервером")
                                await self._publish_connection_state("disconnected", "соединение потеряно")
                
                    except asyncio.CancelledError:
                        logger.info("🛑 Получен сигнал отмены в цикле подключения")
                        raise
                    except aiohttp.ClientConnectorError as e:
                        logger.error(f"❌ Ошибка подключения к серверу: {e}")
                        logger.info(f"   Проверьте, что сервер запущен на {get_config().server.ws_url}")
                        await self._publish_connection_state("disconnected", "сервер недоступен")
                    except aiohttp.WSServerHandshakeError as e:
                        # Ошибка при handshake - возможно проблема с токеном
                        error_msg = str(e)
                        status = getattr(e, 'status', None)
                        message = getattr(e, 'message', b'')
                        
                        if status == 4003 or "4003" in error_msg or (isinstance(message, bytes) and b"Invalid token" in message or b"Token required" in message):
                            logger.error("🔴 Сервер отклонил подключение: невалидный токен")
                            logger.warning("🔑 Требуется ввести новый токен.")
                            await self._publish_connection_state("auth_required", "невалидный токен")
                            
                            # Очищаем токен
                            self.identity_manager.clear_token()
                            if self.db_manager:
                                try:
                                    await self.db_manager.clear_auth_token(self.identity_manager.device_id)
                                except Exception as db_err:
                                    logger.debug(f"Не удалось очистить токен из БД: {db_err}")
                            
                            # Запрашиваем токен
                            logger.info("=" * 70)
                            logger.info("💡 Инструкция:")
                            logger.info("   1. Откройте admin панель сервера: http://server:8666/admin")
                            logger.info("   2. Перейдите в раздел 'Generate Agent Token'")
                            logger.info(f"   3. Введите canonical device ID: {self.device_id}")
                            logger.info("   4. Скопируйте токен и вставьте его в диалог ниже")
                            logger.info("=" * 70)
                            
                            if not await self._request_token_from_console():
                                logger.error("❌ Не удалось получить токен. Завершение работы.")
                                should_exit = True
                                break
                            
                            logger.info("✅ Токен получен. Переподключаемся...")
                        else:
                            logger.error(f"❌ Ошибка handshake: {e}")
                            logger.info(f"   Status: {status}, Message: {message}")
                            await self._publish_connection_state("disconnected", "ошибка handshake")
                    except Exception as e:
                        logger.error(f"❌ Неожиданная ошибка подключения: {e}")
                        logger.exception(e)
                        await self._publish_connection_state("disconnected", "ошибка подключения")
                    
                    # Проверяем, нужно ли завершить работу
                    if should_exit:
                        logger.info("🛑 Завершение работы агента...")
                        break
                    
                    # Переподключение
                    logger.info(f"⏳ Реконнект через {get_config().server.reconnect_interval} сек...")
                    await asyncio.sleep(get_config().server.reconnect_interval)
        
        except asyncio.CancelledError:
            if self._requested_exit_code == EXIT_UPDATE_PENDING:
                logger.info("🛑 Получен сигнал update shutdown, выполняю clean shutdown под launcher exit code 42...")
            else:
                logger.info("🛑 Получен сигнал отмены, выполняю clean shutdown...")
            # Закрываем WebSocket соединение явно, иначе выход из ws_connect может зависать на closing handshake.
            await self._close_agent_ws(reason="run_cancelled")
            # Закрываем HTTP сессию
            if self._http_session:
                try:
                    await asyncio.wait_for(self._http_session.close(), timeout=1.5)
                except Exception as e:
                    logger.debug(f"Ошибка закрытия HTTP сессии при shutdown: {e}")
                finally:
                    self._http_session = None
            # Останавливаем flusher если запущен
            if self.flusher_task:
                self.flusher_task.cancel()
                try:
                    await asyncio.wait_for(self.flusher_task, timeout=1.5)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.debug("Ожидание остановки WSOutboxFlusher превысило таймаут")
            raise
        finally:
            self._run_task = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🧪 ТЕСТИРОВАНИЕ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_envelope_format():
    """
    Тест-функция для проверки формата envelope.
    
    Принимает примеры входящих сообщений и показывает сформированный envelope.
    Можно запустить без WebSocket соединения.
    """
    print("=" * 70)
    print("🧪 Тест формата WS envelope")
    print("=" * 70)
    
    # Создаем экземпляр агента (без инициализации)
    agent = WSAgent()
    
    # Тест 1: Старый формат команды
    print("\n1️⃣ Старый формат команды:")
    old_command = {
        "command": "collect",
        "params": {"modules": ["system", "screen"]}
    }
    print(f"Входное сообщение: {jsonlib.dumps(old_command, indent=2, ensure_ascii=False)}")
    envelope1 = agent.normalize_envelope(old_command)
    print(f"Сформированный envelope:")
    print(jsonlib.dumps(envelope1, indent=2, ensure_ascii=False))
    
    # Тест 2: Старый формат ping
    print("\n2️⃣ Старый формат ping:")
    old_ping = {"type": "ping"}
    print(f"Входное сообщение: {jsonlib.dumps(old_ping, indent=2, ensure_ascii=False)}")
    envelope2 = agent.normalize_envelope(old_ping)
    print(f"Сформированный envelope:")
    print(jsonlib.dumps(envelope2, indent=2, ensure_ascii=False))
    
    # Тест 3: Новый формат envelope (команда)
    print("\n3️⃣ Новый формат envelope (команда):")
    new_command = {
        "type": "command",
        "request_id": "test-request-123",
        "device_id": "test_pc_01",
        "payload": {
            "command": "collect",
            "params": {"modules": ["system"]}
        }
    }
    print(f"Входное сообщение: {jsonlib.dumps(new_command, indent=2, ensure_ascii=False)}")
    envelope3 = agent.normalize_envelope(new_command)
    print(f"Сформированный envelope (без изменений):")
    print(jsonlib.dumps(envelope3, indent=2, ensure_ascii=False))
    
    # Тест 4: Пример ответа (command_result)
    print("\n4️⃣ Пример ответа (command_result):")
    # Симулируем ToolResponse от оркестратора
    tool_response = {
        "status": "success",
        "data": {
            "observations": {
                "results": {
                    "system": {
                        "ok": True,
                        "observations": {
                            "cpu": 25.5,
                            "ram": 60.2
                        }
                    }
                }
            }
        },
        "meta": {
            "timestamp_iso": "2025-01-15T10:30:00.000Z",
            "command": "collect",
            "request_id": "test-request-123",
            "duration_ms": 150
        }
    }
    print(f"ToolResponse (payload):")
    print(jsonlib.dumps(tool_response, indent=2, ensure_ascii=False))
    
    # Формируем envelope для ответа
    response_envelope = {
        "type": "command_result",
        "request_id": "test-request-123",
        "device_id": agent.device_id,
        "payload": tool_response
    }
    print(f"\nСформированный envelope для ответа:")
    print(jsonlib.dumps(response_envelope, indent=2, ensure_ascii=False))
    
    # Проверка: device_id НЕ должен быть в payload
    assert "device_id" not in tool_response, "❌ device_id не должен быть в ToolResponse!"
    assert "device_id" in response_envelope, "✅ device_id должен быть в envelope"
    print("\n✅ Проверка: device_id только в envelope, не в ToolResponse")
    
    print("\n" + "=" * 70)
    print("✅ Все тесты формата envelope пройдены!")
    print("=" * 70)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 ТОЧКА ВХОДА
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _run_verify_mode(data_root: Path) -> None:
    """Режим --verify: init_config уже вызван, только БД миграции и проверка загрузки компонентов. Выход 0/1."""
    import sys
    logs_dir = runtime_paths.resolve_logs_dir(data_root)
    logs_dir.mkdir(parents=True, exist_ok=True)
    verify_log = logs_dir / "verify.log"
    logger.add(verify_log, level="DEBUG", encoding="utf-8")
    try:
        db_path = runtime_paths.resolve_storage_db_path(data_root)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = DatabaseManager(str(db_path))
        await db.init_db()
        logger.info("Verify: БД инициализирована, миграции применены")
        # Пробная загрузка оркестратора/модулей без подключения к серверу
        orch = AgentOrchestrator(db_manager=db, enabled_modules=get_config().enabled_modules, data_root=data_root)
        await orch.initialize()
        logger.info("Verify: оркестратор инициализирован")
        sys.exit(0)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


async def main_async(
    enable_gui: bool = True,
    data_root: Optional[Path] = None,
    install_root: Optional[Path] = None,
) -> int:
    """
    Главная асинхронная функция.

    Args:
        enable_gui: Запускать ли GUI
        data_root: Корень данных (из runtime_paths)
        install_root: Корень установки (опционально)
    """
    cfg = get_config()
    logger.info("=" * 70)
    logger.info("🤖 PC Agent WebSocket Client v2.0 (с AgentOrchestrator)")
    logger.info(f"📡 WebSocket сервер: {cfg.server.ws_url}")
    logger.info(f"🌐 API сервер: {cfg.server.api_url}")
    logger.info(f"💾 База данных: {runtime_paths.resolve_storage_db_path(data_root or Path(cfg.paths.data_dir))}")
    logger.info(f"⚙️  Уровень логирования: {cfg.logging.level}")
    logger.info(f"📦 Модули: {', '.join(cfg.enabled_modules)}")
    logger.info(f"🔍 main_async получил enable_gui={enable_gui}")
    if enable_gui:
        logger.info("🖥️  GUI: включен")
    logger.info("=" * 70)

    agent = WSAgent(data_root=data_root, install_root=install_root)
    exit_code = 0
    
    # Событие для остановки
    stop_event = asyncio.Event()
    stop_wait_task: Optional[asyncio.Task] = None
    agent_task: Optional[asyncio.Task] = None
    gui_task: Optional[asyncio.Task] = None
    auth_state_machine: Optional[GuiAuthStateMachine] = None
    
    async def sync_agent_token_from_db(*, retries: int = 1, delay: float = 0.0, log_reason: str) -> Optional[str]:
        token_from_db_local = None
        try:
            identity_device_id = getattr(agent.identity_manager, "device_id", None) or getattr(agent.identity_manager, "uuid", None)
            if agent.db_manager and identity_device_id:
                for attempt in range(max(1, retries)):
                    token_from_db_local = await load_auth_token_from_db(agent.db_manager, agent.identity_manager)
                    if token_from_db_local:
                        break
                    if delay > 0 and attempt + 1 < max(1, retries):
                        await asyncio.sleep(delay)
        except Exception as e:
            logger.debug(f"Не удалось загрузить токен из БД ({log_reason}): {e}")
            return None
        if token_from_db_local:
            if agent.auth_token != token_from_db_local:
                logger.info(f"✅ Токен загружен из БД ({log_reason})")
            agent.auth_token = token_from_db_local
            agent.identity_manager.token = token_from_db_local
        return token_from_db_local

    try:
        # Инициализация
        await agent.initialize()

        async def on_shutdown_agent(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            reason = str((payload or {}).get("reason") or "ui_shutdown")
            logger.warning(f"🛑 Получен запрос на полное завершение агента (reason={reason})")
            agent._requested_exit_code = 0
            await agent._publish_connection_state("shutting_down", reason)
            stop_event.set()
            return {"accepted": True, "reason": reason}

        if agent.ui_api_server:
            agent.ui_api_server.on_shutdown_agent = on_shutdown_agent
        
        # Выводим Device ID после инициализации (когда он уже установлен из identity)
        logger.info(f"🆔 Device ID: {agent.device_id}")
        
        # Если GUI включен, запускаем UI API сервер до запуска GUI
        
        
        # Даем event loop возможность обработать инициализацию
        await asyncio.sleep(0)
        
        # Если GUI включен, сначала запускаем GUI и ждем авторизации
        # Затем запускаем агента, который будет использовать уже сохраненный токен
        logger.info(f"🔍 Проверка enable_gui в main_async: {enable_gui}")
        if enable_gui:
            ui_config = get_config().ui
            # При enable_gui=True (--gui от launcher/CLI) всегда показываем окно; ui.enabled в конфиге только для автозапуска без --gui
            show_gui = True
            logger.info(f"🔍 GUI: enable_gui=True, ui.enabled={ui_config.enabled if ui_config else None}, show_gui={show_gui}")
            if show_gui:
                logger.info("✅ Запуск GUI")
                
                # КРИТИЧНО: Запускаем UI API сервер ДО запуска GUI
                # GUI будет пытаться подключиться к серверу сразу после запуска
                ui_bridge_listening: Optional[bool] = None
                if agent.ui_api_server and not agent.ui_api_task:
                    try:
                        ui_bridge_listening = await agent.ui_api_server.start()
                        if ui_bridge_listening:
                            logger.info("🚀 UI API сервер запущен перед запуском GUI")
                        else:
                            logger.warning(
                                "⚠️ UI API не поднят (порт занят). GUI не будет опрашивать SSE, пока на порту нет ui_bridge."
                            )
                    except Exception as e:
                        ui_bridge_listening = False
                        logger.error(f"❌ Ошибка запуска UI API сервера: {e}")
                        logger.exception(e)
                    finally:
                        agent.ui_api_task = True

                from pc_agent.ui_gui.main import run_gui
                host = ui_config.host
                port = ui_config.port
                logger.info(f"🖥️  Запускаю GUI на {host}:{port} (ожидаю авторизации)...")
                
                # Создаем событие для завершения авторизации (токен получен — одобрение или ввод вручную)
                gui_auth_complete = asyncio.Event()
                auth_state_machine = GuiAuthStateMachine(agent)
                
                # Обертываем run_gui: при отсутствии токена GUI сразу покажет «Ожидании подтверждения администратором»
                async def run_gui_with_auth():
                    try:
                        await run_gui(
                            host,
                            port,
                            stop_event,
                            gui_auth_complete,
                            ui_bridge_listening=ui_bridge_listening,
                            ui_api_server=agent.ui_api_server,
                        )
                        gui_auth_complete.set()
                    except Exception as e:
                        logger.error(f"Ошибка в GUI: {e}")
                        logger.exception(e)
                        gui_auth_complete.set()
                
                gui_task = asyncio.create_task(run_gui_with_auth(), name="run_gui")
                
                # Даем GUI время показать окно и диалог «Ожидании подтверждения администратором»
                await asyncio.sleep(1.0)

                # GUI может уже открыть основное окно по токену из БД, поэтому сначала
                # синхронизируем токен в агенте и только потом решаем, нужен ли request flow.
                await sync_agent_token_from_db(log_reason="before gui auth decision")
                
                # Явная state machine для переходов auth GUI->request->token.
                if gui_auth_complete.is_set():
                    logger.info("GUI уже завершил авторизацию до запуска request_connection_flow")
                elif auth_state_machine.should_request_connection():
                    auth_state_machine.start_connection_flow(gui_auth_complete)
                elif agent._connection_rejected_flag_path().exists():
                    logger.warning("Подключение ранее отклонено; в GUI доступен ввод токена вручную или сброс через scripts/clear_local_agent_tokens.py")
                
                # Ждем, пока GUI завершит авторизацию (одобрение или ввод токена)
                logger.info("⏳ Ожидаю завершения авторизации в GUI...")
                await auth_state_machine.wait_for_gui_auth(gui_auth_complete, timeout_seconds=620)
                
                # Токен хранится только в БД — опрашиваем БД, не identity.json
                token_from_db_after_gui = await sync_agent_token_from_db(
                    retries=10,
                    delay=0.1,
                    log_reason="after gui auth wait",
                )
                if token_from_db_after_gui:
                    logger.info("✅ Токен найден в БД после ожидания GUI авторизации")
                else:
                    logger.warning("⚠️ Токен не найден в БД после ожидания GUI авторизации")
            else:
                logger.warning(f"⚠️ GUI не включен в конфиге: ui_config={ui_config}, enabled={ui_config.enabled if ui_config else 'None'}")
        
        # Теперь запускаем агента (токен должен быть уже сохранен GUI в БД)
        # Загружаем токен из БД агента — identity.json токен не хранит (основной источник — storage.db)
        token_from_db = await sync_agent_token_from_db(log_reason="before agent.run")
        if not token_from_db and enable_gui and gui_task:
            logger.warning("⚠️ Токен не найден в БД перед запуском агента")
            logger.info("💡 Агент при run() попытается загрузить токен из БД в authenticate()")
        
        agent_task = asyncio.create_task(agent.run(), name="agent.run")
        stop_wait_task = asyncio.create_task(stop_event.wait(), name="agent.stop_wait")

        while True:
            tasks_to_wait = [agent_task, stop_wait_task]
            if gui_task:
                tasks_to_wait.append(gui_task)

            done, pending = await asyncio.wait(
                tasks_to_wait,
                return_when=asyncio.FIRST_COMPLETED
            )

            if stop_wait_task in done:
                logger.info("🛑 Получен явный запрос на завершение агента")
                agent_task.cancel()
                try:
                    await asyncio.wait_for(agent_task, timeout=5.0)
                except asyncio.CancelledError:
                    pass
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Агент не завершился за 5 секунд после сигнала shutdown")
                break

            if gui_task and gui_task in done:
                try:
                    await gui_task
                except asyncio.CancelledError:
                    pass
                except Exception as gui_error:
                    logger.error(f"❌ GUI завершился с ошибкой: {gui_error}")
                    logger.exception(gui_error)
                if stop_event.is_set():
                    continue
                logger.warning("⚠️ GUI завершился, агент продолжает работать в background/headless режиме")
                gui_task = None
                continue

            if agent_task in done:
                try:
                    await agent_task
                except asyncio.CancelledError:
                    exit_code = agent.requested_exit_code or 0
                if gui_task:
                    logger.info("🛑 Агент завершился, останавливаю GUI...")
                    gui_task.cancel()
                    try:
                        await asyncio.wait_for(gui_task, timeout=3.0)
                    except asyncio.CancelledError:
                        pass
                    except asyncio.TimeoutError:
                        logger.warning("⚠️ GUI не завершился за 3 секунды после остановки агента")
                break
        
    except KeyboardInterrupt:
        logger.info("⛔ Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        exit_code = 1
        logger.error(f"❌ Критическая ошибка: {e}")
        logger.exception(e)
    finally:
        # Очистка
        if stop_wait_task and not stop_wait_task.done():
            stop_wait_task.cancel()
            try:
                await stop_wait_task
            except asyncio.CancelledError:
                pass
        if auth_state_machine:
            try:
                await auth_state_machine.cleanup()
            except Exception as e:
                logger.debug(f"Ошибка cleanup auth_state_machine: {e}")
        try:
            await asyncio.wait_for(agent.cleanup(), timeout=8.0)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Очистка агента превысила таймаут 8 секунд")
        logger.info("👋 Завершение работы агента")
    return exit_code


def main():
    """
    Главная функция. Сначала парсим --data-dir/--install-root, инициализируем конфиг от data_root, затем запускаем агент или verify.
    """
    _configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="PC Agent WebSocket Client")
    parser.add_argument("--data-dir", type=str, default=None, help="Корень данных (БД, логи, модули). По умолчанию: по ОС (LOCALAPPDATA/XDG)")
    parser.add_argument("--install-root", type=str, default=None, help="Корень установки (для launcher; опционально)")
    parser.add_argument("--gui", action="store_true", help="Запустить GUI (альтернатива: config.ui.autostart_gui)")
    parser.add_argument("--no-gui", action="store_true", help="Запустить агент без GUI, игнорируя config.ui.autostart_gui")
    parser.add_argument("--verify", action="store_true", help="Режим проверки: только init + миграции БД, без WS/GUI (для launcher)")
    parser.add_argument("--remote-assist-elevated-helper", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--host", type=str, default="127.0.0.1", help=argparse.SUPPRESS)
    parser.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    parser.add_argument("--token", type=str, default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.remote_assist_elevated_helper:
        from pc_agent.remote_assist.elevated_helper import run_elevated_helper_client

        raise SystemExit(
            run_elevated_helper_client(
                host=args.host,
                port=args.port,
                token=args.token,
            )
        )

    data_root = runtime_paths.resolve_data_root(cli_value=args.data_dir)
    install_root = runtime_paths.resolve_install_root(cli_value=args.install_root) if args.install_root else None
    instance_lock = SingleInstanceLock(data_root / "agent.lock")
    if not instance_lock.acquire():
        logger.warning("Another agent instance is already running; exiting.")
        raise SystemExit(2)
    atexit.register(instance_lock.release)
    init_config(data_root)

    if args.verify:
        asyncio.run(_run_verify_mode(data_root))
        return

    cfg = get_config()
    enable_gui = False if args.no_gui else bool(args.gui or (cfg.ui and cfg.ui.autostart_gui))
    logger.info(f"🔍 Аргумент --gui: {args.gui}, итоговый enable_gui: {enable_gui}")

    if enable_gui:
        # Используем qasync для интеграции Qt и asyncio
        try:
            import qasync
            from PySide6.QtWidgets import QApplication
            
            # Создаем QApplication
            app = QApplication([])
            
            # Создаем qasync event loop
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)
            exit_code = 0
            
            # Запускаем главную функцию в qasync loop
            with loop:
                exit_code = loop.run_until_complete(main_async(enable_gui=True, data_root=data_root, install_root=install_root))
                # После возврата main_async завершаем приложение. app.quit() только ставит событие в очередь;
                # без повторного запуска цикла процесс зависал. Ждём фактического выхода (aboutToQuit).
                quit_done = loop.create_future()
                def on_about_to_quit():
                    try:
                        if not quit_done.done():
                            loop.call_soon_threadsafe(quit_done.set_result, None)
                    except Exception:
                        pass
                app.aboutToQuit.connect(on_about_to_quit)
                app.quit()
                try:
                    loop.run_until_complete(asyncio.wait_for(quit_done, timeout=3.0))
                except asyncio.TimeoutError:
                    pass
            raise SystemExit(exit_code)
        except ImportError as e:
            logger.error(
                "❌ Не удалось запустить GUI: Qt/PySide6 не загрузились. "
                "Сборка агента требует GUI; автоматический fallback в --no-gui отключён."
            )
            logger.exception(e)
            raise SystemExit(1)
        except Exception as e:
            logger.error(f"❌ Ошибка запуска GUI: {e}")
            logger.exception(e)
            logger.error("❌ GUI обязателен для штатного запуска; автоматический fallback в --no-gui отключён.")
            raise SystemExit(1)
    else:
        try:
            raise SystemExit(asyncio.run(main_async(enable_gui=False, data_root=data_root, install_root=install_root)))
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
