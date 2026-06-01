from __future__ import annotations

from aiohttp import web
from loguru import logger
from pydantic import ValidationError

from app.db import get_session
from auth.middleware import require_auth
from tickets.request_studio_publication import RequestStudioPublicationService, RequestStudioPublishBlocked
from web_api.dto.common import SuccessResponse, json_model_response
from web_api.dto.request_studio import (
    RequestStudioCapabilities,
    RequestStudioDraftRequest,
    RequestStudioPublishPreview,
    RequestStudioPublishResult,
    RequestStudioValidationResult,
)


async def _payload(request: web.Request) -> RequestStudioDraftRequest:
    raw_payload = await request.json()
    return RequestStudioDraftRequest.model_validate(raw_payload)


@require_auth("admin", "auditor")
async def handle_web_admin_request_studio_capabilities(_request: web.Request) -> web.Response:
    return json_model_response(SuccessResponse[RequestStudioCapabilities](data=RequestStudioCapabilities()))


@require_auth("admin", "auditor")
async def handle_web_admin_request_studio_validate_draft(request: web.Request) -> web.Response:
    try:
        payload = await _payload(request)
    except (ValidationError, ValueError):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру draft из Request Studio",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    try:
        async with get_session() as session:
            result = await RequestStudioPublicationService(session).validate_draft(payload)
        return json_model_response(SuccessResponse[RequestStudioValidationResult](data=result))
    except Exception:
        logger.exception("[request_studio] failed to validate draft")
        return web.json_response({"status": "error", "error": "Не удалось проверить draft Request Studio", "error_code": "REQUEST_STUDIO_VALIDATE_FAILED"}, status=500)


@require_auth("admin", "auditor")
async def handle_web_admin_request_studio_publish_preview(request: web.Request) -> web.Response:
    try:
        payload = await _payload(request)
    except (ValidationError, ValueError):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру draft из Request Studio",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    try:
        async with get_session() as session:
            result = await RequestStudioPublicationService(session).preview_publish(payload)
        return json_model_response(SuccessResponse[RequestStudioPublishPreview](data=result))
    except Exception:
        logger.exception("[request_studio] failed to build publish preview")
        return web.json_response({"status": "error", "error": "Не удалось подготовить preview публикации", "error_code": "REQUEST_STUDIO_PREVIEW_FAILED"}, status=500)


@require_auth("admin")
async def handle_web_admin_request_studio_publish(request: web.Request) -> web.Response:
    try:
        payload = await _payload(request)
    except (ValidationError, ValueError):
        return web.json_response(
            {
                "status": "error",
                "error": "Проверьте структуру draft из Request Studio",
                "error_code": "VALIDATION_ERROR",
            },
            status=400,
        )
    try:
        async with get_session() as session:
            result = await RequestStudioPublicationService(session).publish(
                payload,
                auth_context=request["auth_context"],
            )
            await session.commit()
        return json_model_response(SuccessResponse[RequestStudioPublishResult](data=result))
    except RequestStudioPublishBlocked as exc:
        return json_model_response(SuccessResponse[RequestStudioValidationResult](data=exc.validation), status=409)
    except ValueError as exc:
        return web.json_response({"status": "error", "error": str(exc), "error_code": "VALIDATION_ERROR"}, status=400)
    except Exception:
        logger.exception("[request_studio] failed to publish")
        return web.json_response({"status": "error", "error": "Не удалось опубликовать тип обращения из Studio", "error_code": "REQUEST_STUDIO_PUBLISH_FAILED"}, status=500)
