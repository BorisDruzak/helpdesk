"""Endpoint-only ticket operation actions.

These handlers never dispatch an agent command locally.  Helpdesk owns only
the ticket-facing link; Endpoint Platform remains the operation authority.
"""

from __future__ import annotations

from aiohttp import web

from app.db import get_session
from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo
from app.repos.operations_repo import OperationsRepo
from auth.middleware import require_auth
from domain_ports.container import DomainPortContainer
from domain_ports.endpoint import (
    EndpointConflict,
    EndpointForbidden,
    EndpointInvalidProjection,
    EndpointNotFound,
    EndpointOperationProjection,
    EndpointOperationRef,
    EndpointUnauthorized,
    EndpointUnavailable,
)


def _error(*, status: int, code: str, message: str) -> web.Response:
    return web.json_response(
        {"status": "error", "error_code": code, "error": message}, status=status
    )


def _operation_payload(operation: object) -> dict[str, object]:
    return {
        "operation_id": getattr(operation, "operation_id", None),
        "device_id": getattr(operation, "device_id", None),
        "ticket_id": getattr(operation, "ticket_id", None),
        "kind": getattr(operation, "kind", None),
        "status": getattr(operation, "status", None),
        "phase": getattr(operation, "phase", None),
        "error_code": getattr(operation, "error_code", None),
        "error_message": getattr(operation, "error_message", None),
        "result_summary": getattr(operation, "result_summary", None),
    }


@require_auth("admin", "support", "auditor")
async def handle_web_admin_endpoint_operation_get(request: web.Request) -> web.Response:
    operation_id = str(request.match_info.get("operation_id") or "").strip()
    async with get_session() as session:
        operation = await OperationsRepo(session).get_by_operation_id(operation_id)
    if operation is None:
        return _error(status=404, code="NOT_FOUND", message="Operation not found")
    return web.json_response({"status": "success", "operation": _operation_payload(operation)})


@require_auth("admin", "support")
async def handle_web_support_endpoint_operation_cancel(request: web.Request) -> web.Response:
    """Cancel a not-yet-delivered Endpoint operation through its exact link."""

    operation_id = str(request.match_info.get("operation_id") or "").strip()
    if not operation_id:
        return _error(status=400, code="OPERATION_ID_REQUIRED", message="operation_id is required")

    async with get_session() as session:
        operation = await OperationsRepo(session).get_by_operation_id(operation_id)
        if operation is None:
            return _error(status=404, code="OPERATION_NOT_FOUND", message="Operation not found")
        link = await EndpointOperationLinksRepo(session).get_by_operation_id(operation_id)

    if link is None or not link.endpoint_operation_ref or operation.status != "queued":
        return _error(
            status=409,
            code="operation_cancel_not_supported",
            message="Only a queued, delivered Endpoint operation can be canceled",
        )

    outcome = await DomainPortContainer.from_config().endpoint.cancel_operation(
        EndpointOperationRef(external_id=link.endpoint_operation_ref)
    )
    if isinstance(outcome, EndpointOperationProjection):
        return web.json_response(
            {
                "status": "success",
                "operation_id": operation_id,
                "endpoint_operation_ref": outcome.operation.external_id,
                "endpoint_status": outcome.status,
                "cancelable": outcome.status == "queued",
            }
        )
    if isinstance(outcome, EndpointNotFound):
        return _error(status=404, code=outcome.code, message="Endpoint operation not found")
    if isinstance(outcome, EndpointConflict):
        return _error(status=409, code=outcome.code, message="Endpoint operation cannot be canceled")
    if isinstance(outcome, EndpointUnavailable):
        return _error(status=503, code=outcome.code, message="Endpoint Platform is unavailable")
    if isinstance(outcome, (EndpointUnauthorized, EndpointForbidden, EndpointInvalidProjection)):
        return _error(status=502, code=outcome.code, message="Endpoint operation projection is unavailable")
    return _error(status=502, code="endpoint_invalid_projection", message="Endpoint operation projection is invalid")
