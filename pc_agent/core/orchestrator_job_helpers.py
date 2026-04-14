from typing import Optional

from core.tool_response import ToolData, ToolMeta, ToolResponse, fail, ok
from pc_agent.core.orchestrator_shared import logger


async def handle_start_job(orchestrator, job_type: Optional[str], params: dict, actor_role: str, device_id: Optional[str], meta: ToolMeta) -> ToolResponse:
    try:
        if actor_role == "admin":
            pass
        elif actor_role == "support" and job_type in ["support_chat", "support_ticket"]:
            pass
        elif actor_role == "agent" and job_type in ["support_chat", "support_ticket"]:
            pass
        else:
            return fail(
                code="FORBIDDEN",
                message="Admin only" if actor_role not in ["support", "agent"] else f"{actor_role} role can only start support_chat and support_ticket jobs",
                meta=meta,
                retriable=False,
            )
        if not orchestrator.job_manager:
            return fail(code="JOB_MANAGER_NOT_ATTACHED", message="JobManager not attached to orchestrator", meta=meta, retriable=False)
        if not job_type:
            return fail(code="INVALID_REQUEST", message='Не указан тип задачи (поле "job_type")', meta=meta, retriable=False)

        final_device_id = device_id or orchestrator.agent_uuid or "unknown"
        logger.info(f"Запуск задачи: job_type={job_type}, actor_role={actor_role}, device_id={final_device_id}")
        job_result = await orchestrator.job_manager.start_job(job_type=job_type, device_id=final_device_id, actor_role=actor_role, params=params)
        return ok(data=ToolData(result={"ok": True, "job_id": job_result.get("job_id"), "job_type": job_result.get("job_type")}), meta=meta)
    except Exception as exc:
        error_msg = f"Ошибка запуска задачи: {str(exc)}"
        logger.error(error_msg)
        logger.exception(exc)
        return fail(code="START_JOB_FAILED", message=error_msg, meta=meta, details={"exception_type": type(exc).__name__}, retriable=True)


async def handle_stop_job(orchestrator, job_id: Optional[str], actor_role: str, meta: ToolMeta) -> ToolResponse:
    try:
        if actor_role != "admin":
            return fail(code="FORBIDDEN", message="Admin only", meta=meta, retriable=False)
        if not orchestrator.job_manager:
            return fail(code="JOB_MANAGER_NOT_ATTACHED", message="JobManager not attached to orchestrator", meta=meta, retriable=False)
        if not job_id:
            return fail(code="INVALID_REQUEST", message='Не указан идентификатор задачи (поле "job_id")', meta=meta, retriable=False)
        result = await orchestrator.job_manager.stop_job(job_id)
        if "error" in result:
            return fail(code="JOB_NOT_FOUND", message=f"Задача не найдена: {job_id}", meta=meta, retriable=False)
        return ok(data=ToolData(observations={"job_id": result.get("job_id"), "status": result.get("status")}), meta=meta)
    except Exception as exc:
        error_msg = f"Ошибка остановки задачи: {str(exc)}"
        logger.error(error_msg)
        logger.exception(exc)
        return fail(code="STOP_JOB_FAILED", message=error_msg, meta=meta, details={"exception_type": type(exc).__name__}, retriable=True)


async def handle_get_job_status(orchestrator, job_id: Optional[str], meta: ToolMeta) -> ToolResponse:
    try:
        if not orchestrator.job_manager:
            return fail(code="JOB_MANAGER_NOT_ATTACHED", message="JobManager not attached to orchestrator", meta=meta, retriable=False)
        if not job_id:
            return fail(code="INVALID_REQUEST", message='Не указан идентификатор задачи (поле "job_id")', meta=meta, retriable=False)
        job_data = await orchestrator.job_manager.get_job_status(job_id)
        if not job_data:
            return fail(code="JOB_NOT_FOUND", message=f"Задача не найдена: {job_id}", meta=meta, retriable=False)
        return ok(data=ToolData(observations={"job": job_data}), meta=meta)
    except Exception as exc:
        error_msg = f"Ошибка получения статуса задачи: {str(exc)}"
        logger.error(error_msg)
        logger.exception(exc)
        return fail(code="GET_JOB_STATUS_FAILED", message=error_msg, meta=meta, details={"exception_type": type(exc).__name__}, retriable=True)


async def handle_list_jobs(orchestrator, limit: int, meta: ToolMeta) -> ToolResponse:
    try:
        if not orchestrator.job_manager:
            return fail(code="JOB_MANAGER_NOT_ATTACHED", message="JobManager not attached to orchestrator", meta=meta, retriable=False)
        result = await orchestrator.job_manager.list_jobs(limit=limit)
        return ok(data=ToolData(observations={"jobs": result.get("jobs", []), "count": len(result.get("jobs", []))}), meta=meta)
    except Exception as exc:
        error_msg = f"Ошибка получения списка задач: {str(exc)}"
        logger.error(error_msg)
        logger.exception(exc)
        return fail(code="LIST_JOBS_FAILED", message=error_msg, meta=meta, details={"exception_type": type(exc).__name__}, retriable=True)


async def handle_job_send_event(orchestrator, job_id: Optional[str], event: Optional[dict], actor_role: str, meta: ToolMeta) -> ToolResponse:
    try:
        if actor_role not in {"admin", "support"}:
            return fail(code="FORBIDDEN", message="Admin or support only", meta=meta, retriable=False)
        if not orchestrator.job_manager:
            return fail(code="JOB_MANAGER_NOT_READY", message="JobManager not ready", meta=meta, retriable=False)
        if not job_id or event is None:
            return fail(code="INVALID_REQUEST", message="Не указан job_id или event", meta=meta, retriable=False)
        res = await orchestrator.job_manager.deliver_event(job_id, event)
        if not res.get("ok", False):
            return fail(
                code=res.get("error", "JOB_NOT_FOUND"),
                message=f"Задача не найдена: {job_id}",
                meta=meta,
                retriable=False,
                details={"chat_job_id": job_id, "message_id": event.get("message_id") if event else None},
            )
        return ok(data=ToolData(observations=res), meta=meta)
    except Exception as exc:
        error_msg = f"Ошибка доставки события: {str(exc)}"
        logger.error(error_msg)
        logger.exception(exc)
        return fail(code="JOB_SEND_EVENT_FAILED", message=error_msg, meta=meta, details={"exception_type": type(exc).__name__}, retriable=True)


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
