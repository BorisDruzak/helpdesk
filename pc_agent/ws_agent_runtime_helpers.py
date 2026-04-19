import asyncio
import os
import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from pc_agent.auth.connection_request import run_connection_request_flow
from pc_agent.auth.rejected_flag import connection_rejected_flag_path
from pc_agent.auth.token_source import load_auth_token, load_auth_token_from_db
from pc_agent.config.config_loader import get_config
from pc_agent.core.action_trace import get_action_trace_recorder
from pc_agent.version import EXIT_UPDATE_PENDING


async def schedule_restart(agent, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    delay_sec_raw = payload.get("delay_sec", 0.8)
    reason = str(payload.get("reason") or "settings_changed")
    try:
        delay_sec = float(delay_sec_raw)
    except (TypeError, ValueError):
        delay_sec = 0.8
    delay_sec = max(0.2, min(delay_sec, 30.0))

    if agent._restart_task and not agent._restart_task.done():
        return {
            "status": "ok",
            "scheduled": True,
            "already_scheduled": True,
            "delay_sec": delay_sec,
        }

    agent._restart_task = asyncio.create_task(
        restart_self(agent, delay_sec=delay_sec, reason=reason),
        name="agent.self_restart",
    )
    logger.warning(f"♻️ Перезапуск агента запланирован через {delay_sec:.1f}с (reason={reason})")
    return {
        "status": "ok",
        "scheduled": True,
        "delay_sec": delay_sec,
        "reason": reason,
    }


async def schedule_update_shutdown(agent, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = payload or {}
    delay_sec_raw = payload.get("delay_sec", 2)
    reason = str(payload.get("reason") or "self_update")
    version = str(payload.get("version") or "")
    operation_id = str(payload.get("operation_id") or "")
    try:
        delay_sec = float(delay_sec_raw)
    except (TypeError, ValueError):
        delay_sec = 2.0
    delay_sec = max(0.2, min(delay_sec, 60.0))

    if agent._shutdown_task and not agent._shutdown_task.done():
        return {
            "status": "ok",
            "scheduled": True,
            "already_scheduled": True,
            "delay_sec": delay_sec,
            "exit_code": EXIT_UPDATE_PENDING,
        }

    agent._requested_exit_code = EXIT_UPDATE_PENDING
    agent._shutdown_task = asyncio.create_task(
        shutdown_for_update(
            agent,
            delay_sec=delay_sec,
            reason=reason,
            version=version,
            operation_id=operation_id,
        ),
        name="agent.update_shutdown",
    )
    logger.warning(
        f"♻️ Запланирован clean shutdown под update через {delay_sec:.1f}с "
        f"(version={version or '—'}, operation_id={(operation_id[:8] + '...') if operation_id else '—'})"
    )
    return {
        "status": "ok",
        "scheduled": True,
        "delay_sec": delay_sec,
        "reason": reason,
        "exit_code": EXIT_UPDATE_PENDING,
    }


async def shutdown_for_update(
    agent,
    *,
    delay_sec: float,
    reason: str,
    version: str,
    operation_id: str,
) -> None:
    await asyncio.sleep(delay_sec)
    get_action_trace_recorder().record(
        get_action_trace_recorder().context(
            source="runtime",
            action="agent.update.shutdown",
            category="update",
            operation_id=operation_id or None,
            request_id=operation_id or None,
            tool_name="update",
        ),
        stage="triggered",
        status="ok",
        summary="agent runtime is exiting for update",
        details={"reason": reason, "version": version, "delay_sec": delay_sec},
    )
    try:
        await agent._publish_connection_state("restarting", f"self-update: {version or 'pending'}")
    except Exception:
        pass
    logger.warning(
        f"♻️ Выполняю clean shutdown под update "
        f"(reason={reason}, version={version or '—'}, operation_id={(operation_id[:8] + '...') if operation_id else '—'})"
    )
    if agent._run_task and not agent._run_task.done():
        agent._run_task.cancel()


async def restart_self(agent, delay_sec: float, reason: str) -> None:
    await asyncio.sleep(delay_sec)
    try:
        argv = [sys.executable] + (sys.argv if sys.argv else ["-m", "pc_agent.ws_agent"])
        logger.warning(f"♻️ Выполняю self-restart через os.execv (reason={reason})")
        os.execv(sys.executable, argv)
    except Exception as exc:
        logger.exception(exc)
        logger.error(f"❌ Не удалось выполнить self-restart: {exc}")


def scheduler_success(observations: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
    return {
        "status": "success",
        "data": {"observations": observations},
        "meta": {
            "request_id": request_id,
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        },
    }


def scheduler_error(code: str, message: str, request_id: Optional[str]) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": {"code": code, "message": message},
        "data": {},
        "meta": {
            "request_id": request_id,
            "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        },
    }


async def handle_scheduler_rpc(agent, method: str, params: Dict[str, Any], request_id: Optional[str]) -> Dict[str, Any]:
    if not agent.db_manager:
        return scheduler_error("DB_UNAVAILABLE", "Database is not initialized", request_id)

    try:
        if method == "schedule_task":
            kind = str(params.get("kind") or "").strip()
            schedule = str(params.get("schedule") or "").strip()
            task_params = params.get("params")
            if not isinstance(task_params, dict):
                task_params = {}

            if kind != "run_tool":
                return scheduler_error("VALIDATION_ERROR", "Scheduler MVP supports only kind='run_tool'", request_id)
            if schedule not in {"minutely", "hourly", "daily", "weekly"}:
                return scheduler_error(
                    "VALIDATION_ERROR",
                    "Unsupported schedule. Allowed: minutely, hourly, daily, weekly",
                    request_id,
                )
            tool_name = str(task_params.get("tool_name") or "").strip()
            if not tool_name:
                return scheduler_error(
                    "VALIDATION_ERROR",
                    "params.tool_name is required for kind='run_tool'",
                    request_id,
                )

            task_id = str(uuid.uuid4())
            await agent.db_manager.create_scheduled_task(
                task_id=task_id,
                kind=kind,
                schedule=schedule,
                params=task_params,
                enabled=True,
            )
            task = await agent.db_manager.get_scheduled_task(task_id)
            return scheduler_success({"task_id": task_id, "created": True, "task": task}, request_id)

        if method == "cancel_task":
            task_id = str(params.get("task_id") or "").strip()
            if not task_id:
                return scheduler_error("VALIDATION_ERROR", "task_id is required", request_id)
            updated = await agent.db_manager.disable_scheduled_task(task_id)
            if not updated:
                return scheduler_error("NOT_FOUND", f"Task not found: {task_id}", request_id)
            task = await agent.db_manager.get_scheduled_task(task_id)
            return scheduler_success({"task_id": task_id, "canceled": True, "task": task}, request_id)

        if method == "list_tasks":
            tasks = await agent.db_manager.list_scheduled_tasks()
            return scheduler_success({"tasks": tasks, "count": len(tasks)}, request_id)

        if method == "task_run_now":
            task_id = str(params.get("task_id") or "").strip()
            if not task_id:
                return scheduler_error("VALIDATION_ERROR", "task_id is required", request_id)
            updated = await agent.db_manager.request_scheduled_task_run_now(task_id)
            if not updated:
                return scheduler_error("NOT_FOUND", f"Task not found: {task_id}", request_id)
            task = await agent.db_manager.get_scheduled_task(task_id)
            return scheduler_success({"task_id": task_id, "queued_for_immediate_run": True, "task": task}, request_id)

        return scheduler_error("UNKNOWN_METHOD", f"Unknown scheduler method: {method}", request_id)
    except ValueError as exc:
        return scheduler_error("VALIDATION_ERROR", str(exc), request_id)
    except Exception as exc:
        logger.error(f"Scheduler RPC error: method={method}, error={exc}", exc_info=True)
        return scheduler_error("SCHEDULER_ERROR", str(exc), request_id)


async def scheduler_runtime_loop(agent) -> None:
    while True:
        try:
            await asyncio.sleep(1.0)
            if not agent.db_manager:
                continue
            due_tasks = await agent.db_manager.get_due_scheduled_tasks()
            if not due_tasks:
                continue
            for task in due_tasks:
                try:
                    await execute_scheduled_task(agent, task)
                except Exception as exc:
                    logger.error(
                        f"Failed to execute scheduled task: task_id={task.get('task_id')} error={exc}",
                        exc_info=True,
                    )
                finally:
                    task_id = str(task.get("task_id") or "")
                    if task_id:
                        await agent.db_manager.update_scheduled_task_after_run(task_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(f"Scheduler loop error: {exc}", exc_info=True)
            await asyncio.sleep(2.0)


async def execute_scheduled_task(agent, task: Dict[str, Any]) -> None:
    if not agent.db_manager:
        return
    task_id = str(task.get("task_id") or "")
    kind = str(task.get("kind") or "")
    if kind != "run_tool":
        logger.warning(f"Skip unsupported scheduled task kind: task_id={task_id} kind={kind}")
        return

    task_params = task.get("params")
    if not isinstance(task_params, dict):
        task_params = {}
    tool_name = str(task_params.get("tool_name") or "").strip()
    if not tool_name:
        logger.warning(f"Skip scheduled task without tool_name: task_id={task_id}")
        return

    run_tool_params = {
        "tool_name": tool_name,
        "params": task_params.get("params") if isinstance(task_params.get("params"), dict) else {},
        "ticket_id": task_params.get("ticket_id"),
    }
    run_tool_params = {key: value for key, value in run_tool_params.items() if value is not None}
    logger.info(f"Scheduler executing run_tool: task_id={task_id} tool_name={tool_name}")
    await agent.execute_command(
        command="run_tool",
        params=run_tool_params,
        request_id=f"scheduler-{task_id}-{uuid.uuid4()}",
        device_id=agent.device_id,
        actor_role="agent",
    )


def format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if days > 0:
        parts.append(f"{days}д")
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if secs > 0 or not parts:
        parts.append(f"{secs}с")
    return " ".join(parts)


async def authenticate(agent) -> bool:
    async def _wait_token_from_gui_if_enabled() -> Optional[str]:
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            return None

        app = QApplication.instance()
        if app is None:
            return None

        logger.info("🖥️ GUI включен, проверяю авторизацию через GUI...")
        waited = 0
        while waited < 50:
            await asyncio.sleep(0.1)
            waited += 1
            try:
                if agent.db_manager:
                    token = await load_auth_token_from_db(agent.db_manager, agent.identity_manager)
                    if token:
                        logger.info("✅ Токен найден в БД после ожидания GUI авторизации")
                        return token
            except Exception as exc:
                logger.debug(f"Ошибка проверки токена в БД: {exc}")

        logger.warning("⚠️ GUI включен, но токен не найден после ожидания")
        logger.info("💡 Возможно, авторизация еще не завершена или была отменена")
        logger.info("💡 Агент попытается подключиться к серверу для регистрации попытки")
        return None

    token = await load_auth_token(
        db_manager=agent.db_manager,
        identity_manager=agent.identity_manager,
        gui_wait_callback=_wait_token_from_gui_if_enabled,
    )
    if token:
        agent.auth_token = token
        agent.identity_manager.token = token
        return True
    logger.info("💡 Токен не найден")
    logger.info("💡 Агент попытается подключиться к серверу")
    logger.info("💡 После регистрации на сервере админ может сгенерировать токен")
    return False


def connection_rejected_flag_path_for(agent) -> Path:
    return connection_rejected_flag_path(agent._data_root)


async def request_connection_flow(agent, wait_for_approval_seconds: int = 600) -> Tuple[bool, bool]:
    hostname = socket.gethostname() if hasattr(socket, "gethostname") else None
    ok, rejected = await run_connection_request_flow(
        api_url=get_config().server.api_url or "",
        device_id=agent.device_id or agent.identity_manager.device_id,
        hostname=hostname,
        metadata=agent.identity_manager.get_identity_metadata() if agent.identity_manager else {},
        db_manager=agent.db_manager,
        identity_manager=agent.identity_manager,
        event_bus=agent.event_bus,
        wait_seconds=wait_for_approval_seconds,
    )
    if ok and agent.identity_manager and agent.identity_manager.token:
        agent.auth_token = agent.identity_manager.token
    return (ok, rejected)


async def request_token_from_console(agent) -> bool:
    agent.identity_manager.clear_token()
    if agent.db_manager:
        try:
            await agent.db_manager.clear_auth_token(agent.identity_manager.device_id)
        except Exception as exc:
            logger.warning(f"⚠️ Не удалось очистить токен в БД: {exc}")
    await agent._publish_connection_state("reprovision_required", "повторный provisioning после invalid token")
    ok, rejected = await request_connection_flow(agent)
    if rejected:
        logger.error("❌ Reprovision отклонён администратором")
        return False
    if not ok:
        logger.error("❌ Reprovision неуспешен")
        return False
    logger.info("✅ Reprovision завершен, токен обновлён")
    return True
