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
from tickets.request_scenario_validation import ScenarioValidationError, ScenarioIssue
from web_api.dto.request_scenario import CatalogCode, StrictModel
from web_api.dto.request_scenario_admin import CategoryInput, Identifier, RevisionInput, ScenarioCreate, ScenarioSave, SimulationInput, ScenarioPublish, ScenarioRollback
from tickets.request_scenario_publication import ScenarioPublicationService
from tickets.request_studio_publication import RequestStudioConfirmationError
from web_api.dto.request_scenario_admin import ScenarioDocumentInput, ServiceScenarioCreate, ScenarioConversionInput


class CatalogQuery(StrictModel):
    q: str = Field(default="", max_length=300)
    category_id: Identifier | None = None
    service_code: CatalogCode | None = None
    offering_code: str | None = Field(default=None, min_length=3, max_length=220, pattern=r"^[a-z0-9][a-z0-9_-]*\.[a-z0-9][a-z0-9_-]*$")
    status: Literal["all", "draft", "published", "errors", "archived", "form_only", "guided", "available", "hidden"] = "all"
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


def _validation_issues(exc):
    # Never expose Pydantic input, validator exception text, patterns or context.
    messages = {"missing": "Заполните обязательное поле.", "extra_forbidden": "Удалите неподдерживаемую настройку.",
                "literal_error": "Выберите одно из допустимых значений.",
                "string_pattern_mismatch": "Используйте допустимый формат значения.",
                "string_type": "Введите текст.", "int_type": "Введите целое число.",
                "int_parsing": "Введите целое число.", "bool_type": "Выберите да или нет.",
                "finite_number": "Введите конечное число.", "union_tag_invalid": "Выберите поддерживаемый тип блока или условия.",
                "union_tag_not_found": "Укажите тип блока или условия."}
    issues = []
    for item in exc.errors(include_input=False, include_url=False)[:100]:
        code = item["type"]
        message = messages.get(code, "Проверьте тип, формат и допустимый диапазон значения.")
        if code == "value_error":
            reasons = {
                "choice field requires options": "Добавьте варианты ответа для вопроса с выбором.",
                "option values must be unique": "Значения вариантов ответа должны различаться.",
                "process roles must be unique": "Удалите повторяющиеся роли вопроса.",
                "lower validation bound exceeds upper": "Минимальное значение не должно превышать максимальное.",
                "calendar time must not select a business calendar": "Для календарных сроков уберите рабочий календарь.",
                "offering must belong to the selected service": "Выберите услугу из раздела сценария.",
                "definition exceeds nesting or item limit": "Уменьшите число элементов или вложенность карты.",
                "definition exceeds byte limit": "Уменьшите размер карты: превышен допустимый объём данных.",
                "attachment URL must identify its canonical asset": "Удалите и заново добавьте вложение: ссылка не соответствует файлу.",
                "answer requires field; current_result permits only null or omitted field": "В условии по ответу выберите вопрос; в условии по результату шага уберите вопрос.",
                "schema_version must be an integer": "Версия карты должна быть целым числом.",
                "map-owned processing requires schema_version 3": "Обработка на карте требует версию схемы 3.",
                "processing effects require schema_version 2": "Влияние ответов на обработку требует версию схемы 2 или 3.",
            }
            message = reasons.get(str(item.get("ctx", {}).get("error", "")), message)
        # Only numeric bounds from built-in constraint errors are public.
        limits = {"string_too_long": ("max_length", "Сократите текст: не более {} символов."),
                  "string_too_short": ("min_length", "Введите текст: не менее {} символов."),
                  "too_long": ("max_length", "Уменьшите список: не более {} элементов."),
                  "too_short": ("min_length", "Дополните список: не менее {} элементов."),
                  "greater_than_equal": ("ge", "Укажите число не меньше {}."),
                  "less_than_equal": ("le", "Укажите число не больше {}.")}
        if code in limits:
            key, template = limits[code]
            bound = item.get("ctx", {}).get(key)
            if type(bound) in (int, float):
                message = template.format(bound)
        issues.append({"code": code, "path": ".".join(str(part)[:100] for part in item["loc"])[:1000], "message": message})
    return issues


async def _run(request, operation, *, write=False):
    try:
        async with get_session() as session:
            result = await operation(RequestScenarioRepo(session, request["auth_context"]))
            if write:
                await session.commit()
        return web.json_response({"status": "success", "data": result}, headers={"Cache-Control": "no-store"})
    except RequestStudioConfirmationError as exc:
        return web.json_response({"status": "error", "error_code": exc.error_code}, status=exc.status, headers={"Cache-Control": "no-store"})
    except ScenarioAdminError as exc:
        return web.json_response({"status": "error", "error_code": exc.code}, status=exc.status)
    except ScenarioValidationError as exc:
        return web.json_response({"status": "error", "error_code": "SCENARIO_INVALID", "issues": [asdict(issue) for issue in exc.issues]}, status=400)
    except ScenarioConflict:
        return web.json_response({"status": "error", "error_code": "REVISION_CONFLICT"}, status=409)
    except ScenarioInputError as exc:
        return web.json_response({"status": "error", "error_code": "INVALID_ANSWERS", "errors": exc.errors}, status=400)
    except ValidationError as exc:
        return web.json_response({"status": "error", "error_code": "VALIDATION_ERROR", "issues": _validation_issues(exc)}, status=400, headers={"Cache-Control": "no-store"})
    except (ValueError, TypeError):
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
        return await repo.catalog_view(query=query.q, status=query.status, offset=query.offset, limit=query.limit, category_id=query.category_id, service_code=query.service_code, offering_code=query.offering_code)
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


@require_auth("admin")
async def handle_scenario_service_create(request):
    async def operation(repo):
        payload = await _payload(request, ServiceScenarioCreate)
        return await repo.create_service(payload.definition, copy_source_id=payload.copy_source_id)
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_convert_forms(request):
    async def operation(repo):
        payload = await _payload(request, ScenarioConversionInput)
        codes = [payload.offering_full_code] if payload.offering_full_code else sorted(
            item["full_code"] for item in await repo.catalog.list_offerings() if item["lifecycle_status"] != "retired")
        if len(codes) > 500:
            raise ScenarioAdminError("CONVERSION_LIMIT", 400)
        return {"items": [await repo.convert_offering(code, apply=payload.apply) for code in codes]}
    return await _run(request, operation, write=True)


@require_auth("admin", "auditor")
async def handle_scenario_document_validate(request):
    async def operation(repo):
        from tickets.request_scenario_document import parse_scenario_document, document_issues, document_reference_issues
        from tickets.request_scenario_publication import scenario_diff
        payload = await _payload(request, ScenarioDocumentInput)
        try:
            definition = parse_scenario_document(payload.content, payload.format)
        except ValidationError as exc:
            messages = {"extra_forbidden": "Неизвестное поле документа.", "missing": "Заполните обязательное поле.",
                        "literal_error": "Выберите поддерживаемую версию, тип или значение."}
            issues = [ScenarioIssue(item["type"], ".".join(str(part)[:100] for part in item["loc"])[:1000] or "document",
                       messages.get(item["type"], "Проверьте тип и допустимый диапазон значения."))
                      for item in exc.errors(include_input=False, include_context=False, include_url=False)[:100]]
            raise ScenarioValidationError(issues) from exc
        except ValueError as exc:
            path = f"document.line.{exc.lineno}" if isinstance(exc, json.JSONDecodeError) else "document"
            raise ScenarioValidationError([ScenarioIssue("invalid_document", path,
                "Проверьте синтаксис JSON/YAML: ключи должны быть уникальными, ссылки и исполняемые конструкции запрещены.")]) from exc
        identifier = request.query.get("scenario_id")
        before = {}
        if identifier:
            identifier = TypeAdapter(Identifier).validate_python(identifier)
            row, draft = await repo.detail(identifier)
            incoming = definition
            if (incoming.scenario_key, incoming.service_code, incoming.offering_full_code, incoming.process_binding.request_template_key) != (
                row.scenario_key, row.service_code, row.offering_full_code, draft.definition["process_binding"]["request_template_key"]):
                raise ScenarioAdminError("CATALOG_BINDING_IMMUTABLE", 409)
            from web_api.dto.request_scenario import ScenarioDraftDefinition
            before = ScenarioDraftDefinition.model_validate(draft.definition).model_dump(mode="json")
        issues = [asdict(issue) for issue in document_issues(definition)]
        issues.extend(await document_reference_issues(repo.session, definition))
        return {"definition": definition.model_dump(mode="json"), "issues": issues,
                "diff": scenario_diff(before, definition.model_dump(mode="json"))}
    return await _run(request, operation)


@require_auth("admin", "auditor")
async def handle_scenario_document_export(request):
    async def operation(repo):
        from tickets.request_scenario_document import export_scenario_document
        _, draft = await repo.detail(_id(request))
        format = request.query.get("format", "json")
        return {"format": format, "content": export_scenario_document(draft.definition, format)}
    return await _run(request, operation)


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


@require_auth("admin", "auditor")
async def handle_scenario_readiness(request):
    async def operation(repo):
        payload = await _payload(request, RevisionInput)
        return await ScenarioPublicationService(repo).preview(_id(request), payload.revision, issue_token=False)
    return await _run(request, operation)


@require_auth("admin")
async def handle_scenario_publish_preview(request):
    async def operation(repo):
        payload = await _payload(request, RevisionInput)
        return await ScenarioPublicationService(repo).preview(_id(request), payload.revision)
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_publish(request):
    async def operation(repo):
        return await ScenarioPublicationService(repo).publish(_id(request), await _payload(request, ScenarioPublish))
    return await _run(request, operation, write=True)


@require_auth("admin")
async def handle_scenario_rollback_draft(request):
    async def operation(repo):
        return await ScenarioPublicationService(repo).rollback_draft(_id(request), await _payload(request, ScenarioRollback))
    return await _run(request, operation, write=True)
