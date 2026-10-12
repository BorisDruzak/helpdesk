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
from web_api.dto.request_scenario_session import SessionBack, SessionRevision, SessionStart, SessionSubmit, SessionTicketContext
from web_api.request_scenario_admin_handlers import _payload


def _reply(payload, status=200):
    return web.json_response(payload, status=status, headers={"Cache-Control": "no-store"})


async def _run(request, kind):
    try:
        model = {"start": SessionStart, "back": SessionBack, "finish": SessionRevision,
                 "answer": ScenarioAnswerRequest, "advance": ScenarioAnswerRequest,
                 "preview": ScenarioAnswerRequest, "ticket_preview": SessionTicketContext,
                 "submit": SessionSubmit}.get(kind)
        payload = await _payload(request, model) if model else None
        identifier = None if kind == "start" else TypeAdapter(Identifier).validate_python(request.match_info["identifier"])
        async with get_session() as session:
            repo = RequestScenarioSessionRepo(session, request["auth_context"])
            if kind == "start":
                result = await repo.start(payload.offering_full_code, payload.entry_point_key)
            elif kind == "read":
                result = await repo.read(identifier)
            elif kind == "preview":
                result = await repo.preview(identifier, payload)
            elif kind in {"ticket_preview", "submit"}:
                from requester.create_idempotency import CreateRequestKey
                from web_api.requester_handlers import create_requester_ticket_in_session, preview_requester_ticket_in_session
                import json
                row, runtime, data, snapshot = await repo.prepare_submission(identifier, payload.revision)
                if data is not None:
                    if data.get("device_id") and (payload.device_scope or payload.device_id and payload.device_id != data["device_id"]):
                        raise ScenarioInputError({"device": "Device selection differs from the scenario answer"})
                    data.update(payload.model_dump(mode="json", include={"device_id", "device_scope"}, exclude_none=True))
                if data is None:
                    result = await repo._view(row, runtime)
                elif kind == "ticket_preview":
                    response = await preview_requester_ticket_in_session(request, data, session, scenario_snapshot=snapshot)
                    # Preview may emit existing observer records; it must never
                    # commit these or any scenario/ticket mutation.
                    await session.rollback()
                    response.headers["Cache-Control"] = "no-store"
                    return response
                else:
                    checked = await preview_requester_ticket_in_session(request, data, session, scenario_snapshot=snapshot)
                    if checked.status >= 400:
                        await session.rollback()
                        checked.headers["Cache-Control"] = "no-store"
                        return checked
                    if not json.loads(checked.body)["data"]["ok"]:
                        await session.rollback()
                        return _reply({"status": "error", "error_code": "PROCESSING_UNAVAILABLE"}, status=409)
                    key = CreateRequestKey.parse(repo.owner, "scenario:" + identifier, data)
                    response = await create_requester_ticket_in_session(
                        request, data, session, request_key=key, scenario_snapshot=snapshot,
                    )
                    if response.status >= 400:
                        await session.rollback()
                        response.headers["Cache-Control"] = "no-store"
                        return response
                    ticket_id = json.loads(response.body)["data"]["ticket_id"]
                    await repo.complete_submission(row, ticket_id)
                    result = await repo._view(row, runtime)
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


@require_auth("user")
async def handle_web_requester_scenario_ticket_preview(request):
    return await _run(request, "ticket_preview")


@require_auth("user")
async def handle_web_requester_scenario_submit(request):
    return await _run(request, "submit")
