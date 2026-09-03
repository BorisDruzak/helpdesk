"""Authenticated Helpdesk BFF for Endpoint-owned declarative modules."""

from __future__ import annotations

from typing import Any

from aiohttp import web
from pydantic import ValidationError

from access_control.service import can
from app.db import get_session
from app.db.engine import get_session_maker
from app.repos.ticket_admin_audit_repo import TicketAdminAuditRepo
from app.services.endpoint_module_operation_service import (
    EndpointModuleOperationError,
    EndpointModuleOperationRequest,
    EndpointModuleOperationService,
    SqlAlchemyEndpointModuleOperationStore,
    StoredTicketEndpointModuleDeviceResolver,
)
from auth.middleware import ensure_server_request_id, require_auth
from domain_ports.container import DomainPortContainer
from domain_ports.endpoint_modules import (
    EndpointModuleCapabilityCatalog,
    EndpointModuleFailureOutcome,
    EndpointModuleRef,
    EndpointModuleVersionCreateRequest,
    EndpointModuleVersionRef,
)
from tickets.handlers import _get_ticket_or_response


def _port(request: web.Request):
    return request.app.get("endpoint_module_port") or DomainPortContainer.from_config().endpoint_modules


class _VerifiedTicketAccess:
    def __init__(self, ticket_id: str) -> None:
        self._ticket_id = ticket_id

    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        if actor is None or ticket_id != self._ticket_id:
            raise PermissionError("verified ticket operation access is required")


async def _permission(request: web.Request, code: str) -> web.Response | None:
    async with get_session() as session:
        if await can(session, request["auth_context"], code):
            return None
    return web.json_response({"status": "error", "error_code": "FORBIDDEN", "required_permission": code}, status=403)


async def _one_of_permissions(request: web.Request, *codes: str) -> web.Response | None:
    async with get_session() as session:
        for code in codes:
            if await can(session, request["auth_context"], code):
                return None
    return web.json_response({"status": "error", "error_code": "FORBIDDEN", "required_permission": codes[0]}, status=403)


def _failure(value: EndpointModuleFailureOutcome) -> web.Response:
    status = 404 if value.status == "not_found" else 503 if value.status == "unavailable" else 502
    return web.json_response({"status": "error", "error_code": value.code}, status=status)


def _catalog_response_or_failure(
    value: EndpointModuleCapabilityCatalog | EndpointModuleFailureOutcome,
) -> web.Response:
    if isinstance(value, EndpointModuleFailureOutcome):
        return _failure(value)
    return web.json_response({"data": value.model_dump(mode="json")})


def _safe_version(value: object) -> dict[str, object]:
    version = getattr(value, "version")
    return {
        "module_key": version.module.module_key,
        "version": version.version,
        "state": getattr(value, "state").value if hasattr(getattr(value, "state"), "value") else getattr(value, "state"),
    }


async def _audit(request: web.Request, *, action: str, module_key: str, version: str, service_result: object) -> None:
    auth = request["auth_context"]
    async with get_session() as session:
        await TicketAdminAuditRepo(session).add(
            entity_type="endpoint_module", entity_id=f"{module_key}@{version}", action=action,
            actor_id=str(auth.actor_id), actor_role=str(auth.actor_role),
            after_json={"module_key": module_key, "version": version, "service_result": service_result},
            trace_id=ensure_server_request_id(request),
        )
        await session.commit()


@require_auth("admin", "auditor")
async def handle_endpoint_modules_list(request: web.Request) -> web.Response:
    denied = await _one_of_permissions(request, "admin.modules.view", "modules.audit")
    if denied:
        return denied
    result = await _port(request).list_modules()
    if isinstance(result, tuple):
        data: list[dict[str, object]] = []
        port = _port(request)
        for item in result:
            projection: dict[str, object] = {
                "module_key": item.module.module_key,
                "display_name": item.display_name,
            }
            definition = await port.read_module(item.module)
            if not isinstance(definition, EndpointModuleFailureOutcome):
                projection.update(
                    version=definition.latest_version.version,
                    state=definition.latest_state.value,
                )
            data.append(projection)
        return web.json_response({"data": data})
    return _failure(result)


@require_auth("admin", "auditor")
async def handle_endpoint_module_capabilities(request: web.Request) -> web.Response:
    denied = await _one_of_permissions(request, "admin.modules.view", "modules.audit")
    if denied:
        return denied
    return _catalog_response_or_failure(await _port(request).list_recipe_capabilities())


@require_auth("admin")
async def handle_endpoint_module_create_version(request: web.Request) -> web.Response:
    denied = await _permission(request, "admin.modules.author")
    if denied:
        return denied
    try:
        body = await request.json()
        command = EndpointModuleVersionCreateRequest.model_validate(body)
    except (ValidationError, ValueError, TypeError):
        return web.json_response({"status": "error", "error_code": "VALIDATION_ERROR"}, status=400)
    result = await _port(request).create_module_version(command)
    if isinstance(result, EndpointModuleFailureOutcome):
        return _failure(result)
    payload = _safe_version(result)
    await _audit(request, action="module_create", module_key=command.recipe.module_key, version=command.version, service_result=payload)
    return web.json_response({"data": payload}, status=201)


async def _version_action(request: web.Request, *, action: str) -> web.Response:
    denied = await _permission(request, "admin.modules.author")
    if denied:
        return denied
    try:
        version = EndpointModuleVersionRef(
            module=EndpointModuleRef(module_key=request.match_info["module_key"]),
            version=request.match_info["version"],
        )
    except ValidationError:
        return web.json_response({"status": "error", "error_code": "VALIDATION_ERROR"}, status=400)
    port = _port(request)
    if action == "validate":
        result = await port.validate_module_version(version)
    elif action == "publish":
        result = await port.publish_module_version(version)
    else:
        result = await port.deprecate_module_version(version)
    if isinstance(result, EndpointModuleFailureOutcome):
        return _failure(result)
    if action == "validate":
        payload: dict[str, Any] = {"module_key": version.module.module_key, "version": version.version, "status": result.status, "error_codes": list(result.error_codes), "warning_codes": list(result.warning_codes)}
    else:
        payload = _safe_version(result)
    await _audit(request, action=f"module_{action}", module_key=version.module.module_key, version=version.version, service_result=payload)
    return web.json_response({"data": payload})


@require_auth("admin")
async def handle_endpoint_module_validate(request: web.Request) -> web.Response:
    return await _version_action(request, action="validate")


@require_auth("admin")
async def handle_endpoint_module_publish(request: web.Request) -> web.Response:
    return await _version_action(request, action="publish")


@require_auth("admin")
async def handle_endpoint_module_deprecate(request: web.Request) -> web.Response:
    return await _version_action(request, action="deprecate")


@require_auth("admin", "support")
async def handle_endpoint_module_run(request: web.Request) -> web.Response:
    """Queue one local facade operation; reconciler performs the only remote call."""

    try:
        body = await request.json()
        command = EndpointModuleOperationRequest(
            ticket_id=request.match_info["ticket_id"], module_key=request.match_info["module_key"],
            module_version=request.match_info["version"], inputs=body.get("inputs"),
            idempotency_key=body.get("idempotency_key"),
        )
    except (ValidationError, ValueError, TypeError, AttributeError):
        return web.json_response({"status": "error", "error_code": "VALIDATION_ERROR"}, status=400)
    async with get_session() as session:
        ticket, error, _repo, auth = await _get_ticket_or_response(request, session, write=True)
        if error:
            return error
        if not await can(session, auth, "ticket.tool.run"):
            return web.json_response({"status": "error", "error_code": "FORBIDDEN", "required_permission": "ticket.tool.run"}, status=403)
    version_ref = EndpointModuleVersionRef(
        module=EndpointModuleRef(module_key=command.module_key), version=command.module_version,
    )
    version = await _port(request).read_module_version(version_ref)
    if isinstance(version, EndpointModuleFailureOutcome):
        return _failure(version)
    if version.state.value != "published":
        return web.json_response({"status": "error", "error_code": "ENDPOINT_MODULE_NOT_PUBLISHED"}, status=409)
    service = EndpointModuleOperationService(
        access_service=_VerifiedTicketAccess(ticket.ticket_id),
        device_resolver=StoredTicketEndpointModuleDeviceResolver(get_session_maker()),
        store=SqlAlchemyEndpointModuleOperationStore(get_session_maker()),
    )
    try:
        result = await service.create(actor=auth, request=command)
    except EndpointModuleOperationError as error:
        return web.json_response({"status": "error", "error_code": str(error)}, status=409)
    payload = {"operation_id": result.operation_id, "status": result.status, "trace_id": result.trace_id}
    await _audit(request, action="module_run", module_key=command.module_key, version=command.module_version, service_result=payload)
    return web.json_response({"data": payload}, status=202)
