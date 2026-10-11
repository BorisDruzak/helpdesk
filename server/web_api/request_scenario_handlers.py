"""Authenticated requester commands; no graph, actor or policy from the client."""
from aiohttp import web
from loguru import logger
from pydantic import TypeAdapter, ValidationError

from app.db import get_session
from app.repos.request_scenario_repo import ScenarioAdminError
from app.repos.request_scenario_session_repo import RequestScenarioSessionRepo, SessionAccessError
from auth.middleware import require_auth
from tickets.request_scenario_runtime import ScenarioConflict, ScenarioInputError
from web_api.dto.request_scenario import ScenarioAnswerRequest
from web_api.dto.request_scenario_admin import Identifier
from web_api.dto.request_scenario_session import SessionBack, SessionRevision, SessionStart
from web_api.request_scenario_admin_handlers import _payload


def _reply(payload, status=200):
    return web.json_response(payload, status=status, headers={"Cache-Control": "no-store"})


async def _run(request, kind):
    try:
        model = {"start": SessionStart, "back": SessionBack, "finish": SessionRevision,
                 "answer": ScenarioAnswerRequest, "advance": ScenarioAnswerRequest,
                 "preview": ScenarioAnswerRequest}.get(kind)
        payload = await _payload(request, model) if model else None
        identifier = None if kind == "start" else TypeAdapter(Identifier).validate_python(request.match_info["identifier"])
        async with get_session() as session:
            repo = RequestScenarioSessionRepo(session, request["auth_context"])
            if kind == "start":
                result = await repo.start(payload.offering_full_code)
            elif kind == "read":
                result = await repo.read(identifier)
            elif kind == "preview":
                result = await repo.preview(identifier, payload)
            else:
                result = await repo.command(identifier, kind, payload)
            await session.commit()
        return _reply({"status": "success", "data": result})
    except (SessionAccessError, ScenarioAdminError) as exc:
        return _reply({"status": "error", "error_code": exc.code}, status=exc.status)
    except ScenarioConflict:
        return _reply({"status": "error", "error_code": "REVISION_CONFLICT"}, status=409)
    except ScenarioInputError as exc:
        return _reply({"status": "error", "error_code": "INVALID_ANSWERS", "errors": exc.errors}, status=400)
    except (ValidationError, ValueError, TypeError):
        return _reply({"status": "error", "error_code": "VALIDATION_ERROR"}, status=400)
    except Exception as exc:
        logger.error("[request_scenario_session] operation failed: {}", type(exc).__name__)
        return _reply({"status": "error", "error_code": "SESSION_OPERATION_FAILED"}, status=500)


@require_auth("user")
async def handle_web_requester_scenario_start(request):
    return await _run(request, "start")


@require_auth("user")
async def handle_web_requester_scenario_session(request):
    return await _run(request, "read")


@require_auth("user")
async def handle_web_requester_scenario_answer(request):
    return await _run(request, "answer")


@require_auth("user")
async def handle_web_requester_scenario_advance(request):
    return await _run(request, "advance")


@require_auth("user")
async def handle_web_requester_scenario_back(request):
    return await _run(request, "back")


@require_auth("user")
async def handle_web_requester_scenario_finish(request):
    return await _run(request, "finish")


@require_auth("user")
async def handle_web_requester_scenario_step_preview(request):
    return await _run(request, "preview")
