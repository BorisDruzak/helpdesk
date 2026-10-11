"""Authenticated Guided Studio admin endpoints; preserve legacy Studio routes."""
from dataclasses import asdict
import json
from typing import Literal

from aiohttp import web
from loguru import logger
from pydantic import Field, TypeAdapter, ValidationError
from sqlalchemy.exc import DBAPIError

from app.db import get_session
from app.repos.request_scenario_repo import RequestScenarioRepo, ScenarioAdminError, serialize
from auth.middleware import require_auth
from tickets.request_scenario_runtime import ScenarioConflict, ScenarioInputError
from tickets.request_scenario_validation import ScenarioValidationError
from web_api.dto.request_scenario import StrictModel
from web_api.dto.request_scenario_admin import CategoryInput, Identifier, RevisionInput, ScenarioCreate, ScenarioSave, SimulationInput


class CatalogQuery(StrictModel):
    q: str = Field(default="", max_length=300)
    category_id: Identifier | None = None
    status: Literal["all", "draft", "published", "errors", "archived", "form_only"] = "all"
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=100, ge=1, le=500)


async def _payload(request, model):
    # Bound bytes before JSON/Pydantic parsing; do not echo failed input.
    body = bytearray()
    async for chunk in request.content.iter_chunked(65536):
        body.extend(chunk)
        if len(body) > 1048576:
            raise ScenarioAdminError("PAYLOAD_TOO_LARGE", 413)
    return model.model_validate(json.loads(body))


def _id(request):
    return TypeAdapter(Identifier).validate_python(request.match_info["identifier"])


async def _run(request, operation, *, write=False):
    try:
        async with get_session() as session:
            result = await operation(RequestScenarioRepo(session, request["auth_context"]))
            if write:
                await session.commit()
        return web.json_response({"status": "success", "data": result})
    except ScenarioAdminError as exc:
        return web.json_response({"status": "error", "error_code": exc.code}, status=exc.status)
    except ScenarioValidationError as exc:
        return web.json_response({"status": "error", "error_code": "SCENARIO_INVALID", "issues": [asdict(issue) for issue in exc.issues]}, status=400)
    except ScenarioConflict:
        return web.json_response({"status": "error", "error_code": "REVISION_CONFLICT"}, status=409)
    except ScenarioInputError as exc:
        return web.json_response({"status": "error", "error_code": "INVALID_ANSWERS", "errors": exc.errors}, status=400)
    except (ValidationError, ValueError, TypeError):
        return web.json_response({"status": "error", "error_code": "VALIDATION_ERROR"}, status=400)
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None)
        if code in {"23505", "23503", "23514"}:
            return web.json_response({"status": "error", "error_code": "CONSTRAINT_CONFLICT" if code != "23514" else "VALIDATION_ERROR"}, status=409 if code != "23514" else 400)
        logger.error("[request_scenario_admin] database operation failed")
        return web.json_response({"status": "error", "error_code": "SCENARIO_ADMIN_FAILED"}, status=500)
    except Exception as exc:
        logger.error("[request_scenario_admin] operation failed: {}", type(exc).__name__)
        return web.json_response({"status": "error", "error_code": "SCENARIO_ADMIN_FAILED"}, status=500)


@require_auth("admin", "auditor")
async def handle_scenario_catalog(request):
    async def operation(repo):
        query = CatalogQuery.model_validate_strings(dict(request.query))
        return await repo.catalog_view(query=query.q, status=query.status, offset=query.offset, limit=query.limit, category_id=query.category_id)
    return await _run(request, operation)


@require_auth("admin")
async def handle_scenario_category_create(request):
    async def operation(repo):
        return await repo.save_category(await _payload(request, CategoryInput))
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_category_update(request):
    async def operation(repo):
        return await repo.save_category(await _payload(request, CategoryInput), _id(request))
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_category_archive(request):
    async def operation(repo):
        revision = RevisionInput(revision=int(request.query.get("revision", "")))
        return await repo.archive_category(_id(request), revision.revision)
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_create(request):
    async def operation(repo):
        payload = await _payload(request, ScenarioCreate)
        return await repo.create(payload.definition)
    return await _run(request, operation, write=True)


@require_auth("admin", "auditor")
async def handle_scenario_detail(request):
    async def operation(repo):
        row, draft = await repo.detail(_id(request))
        return {"scenario": serialize(row), "draft": serialize(draft)}
    return await _run(request, operation)


@require_auth("admin")
async def handle_scenario_draft_save(request):
    async def operation(repo):
        return await repo.save(_id(request), await _payload(request, ScenarioSave))
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_archive(request):
    async def operation(repo):
        payload = await _payload(request, RevisionInput)
        return await repo.archive(_id(request), payload.revision)
    return await _run(request, operation, write=True)


@require_auth("admin", "auditor")
async def handle_scenario_versions(request):
    async def operation(repo):
        return await repo.versions(_id(request))
    return await _run(request, operation)


@require_auth("admin", "auditor")
async def handle_scenario_simulate(request):
    async def operation(repo):
        return await repo.simulate(_id(request), await _payload(request, SimulationInput))
    return await _run(request, operation)
