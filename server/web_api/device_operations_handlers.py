from __future__ import annotations

from aiohttp import web
from loguru import logger

from app.db import get_session
from auth.middleware import require_auth
from device_operations.service import DeviceOperationsNotFound, DeviceOperationsService
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.device_operations import DeviceOperationsPayload


def _bool_query(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_query(value: str | None, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except ValueError:
        parsed = default
    return max(minimum, min(parsed, maximum))


@require_auth("admin", "support")
async def handle_web_admin_device_operations(request: web.Request) -> web.Response:
    device_id = str(request.match_info.get("device_id") or request.query.get("device_id") or "").strip()
    if not device_id:
        return web.json_response(
            {
                "status": "error",
                "error": "device_id is required",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )

    try:
        async with get_session() as session:
            payload = await DeviceOperationsService(session, state=request.app.get("state")).build_payload(
                device_id,
                include_traces=_bool_query(request.query.get("include_traces"), default=True),
                include_outbox=_bool_query(request.query.get("include_outbox"), default=True),
                include_history=_bool_query(request.query.get("include_history"), default=False),
                trace_limit=_int_query(request.query.get("trace_limit"), default=10, minimum=1, maximum=100),
                outbox_limit=_int_query(request.query.get("outbox_limit"), default=20, minimum=1, maximum=100),
                operation_limit=_int_query(request.query.get("operation_limit"), default=20, minimum=1, maximum=100),
            )
    except DeviceOperationsNotFound:
        return web.json_response(
            {
                "status": "error",
                "error": "Устройство не найдено",
                "error_code": "DEVICE_NOT_FOUND",
                "device_id": device_id,
            },
            status=404,
        )
    except Exception as exc:
        logger.exception(f"[device_operations] failed: device_id={device_id} error={exc}")
        return web.json_response(
            {
                "status": "error",
                "error": "Не удалось загрузить рабочее пространство устройства",
                "error_code": "DEVICE_OPERATIONS_FAILED",
                "device_id": device_id,
            },
            status=500,
        )

    return json_model_response(SuccessResponse[DeviceOperationsPayload](data=payload))
