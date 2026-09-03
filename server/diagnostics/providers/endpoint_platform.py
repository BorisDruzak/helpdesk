"""Endpoint Platform diagnostic capability provider.

This provider creates only the Helpdesk-local operation facade.  The separate
reconciler owns every remote Endpoint API call; this module must never acquire
an agent WebSocket, an outbox record or a ToolExecutionService.
"""

from __future__ import annotations

from typing import Any

from app.services.endpoint_diagnostic_operation_service import (
    EndpointDiagnosticOperationConflict,
    EndpointDiagnosticOperationRequest,
    EndpointDiagnosticOperationService,
    EndpointDiagnosticOperationUnavailable,
)
from diagnostics.capability_models import CapabilityDescriptor


ENDPOINT_DIAGNOSTIC_CAPABILITY_ID = "endpoint.context.diagnostic.collect"
_EXTERNAL_ENDPOINT_CAPABILITY = "context.diagnostic.collect"


def _configured_execution_mode() -> str:
    try:
        import config
    except ModuleNotFoundError:
        from server import config  # type: ignore[no-redef]
    return str(config.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE or "endpoint").strip().lower()


def list_endpoint_platform_capabilities(*, execution_mode: str | None = None) -> list[CapabilityDescriptor]:
    """Expose the single accepted endpoint capability only during its cutover."""

    mode = _configured_execution_mode() if execution_mode is None else str(execution_mode).strip().lower()
    if mode != "endpoint":
        return []
    return [
        CapabilityDescriptor(
            id=ENDPOINT_DIAGNOSTIC_CAPABILITY_ID,
            title="Диагностика устройства через Endpoint Platform",
            description="Собирает ограниченный диагностический контекст через защищённый Endpoint Agent",
            provider_id="endpoint_platform",
            provider_type="endpoint_platform",
            execution_target="endpoint_operation",
            risk_level="low",
            side_effects=False,
            requires_consent=False,
            requires_device=True,
            requires_agent_online=False,
            supports_auto_install=False,
            params_schema={"type": "object", "additionalProperties": False, "maxProperties": 0},
            source="external_endpoint",
            output_contract={
                "kind": "endpoint.diagnostic_operation",
                "status_field": "status",
                "primary_id_field": "operation_id",
                "external_capability": _EXTERNAL_ENDPOINT_CAPABILITY,
            },
        )
    ]


class EndpointPlatformDiagnosticProvider:
    """Injectable, local-only endpoint-operation facade provider."""

    def __init__(self, *, operation_service: EndpointDiagnosticOperationService) -> None:
        self._operation_service = operation_service

    async def run(self, capability: CapabilityDescriptor, **kwargs: Any) -> dict[str, Any]:
        if capability.id != ENDPOINT_DIAGNOSTIC_CAPABILITY_ID:
            return {"status": "error", "error_code": "ENDPOINT_DIAGNOSTIC_CAPABILITY_INVALID"}
        params = kwargs.get("params")
        if not isinstance(params, dict) or params:
            return {"status": "error", "error_code": "ENDPOINT_DIAGNOSTIC_PARAMS_INVALID"}
        ticket_id = str(kwargs.get("ticket_id") or "").strip()
        idempotency_key = kwargs.get("idempotency_key")
        if not ticket_id or not isinstance(idempotency_key, str):
            return {"status": "error", "error_code": "ENDPOINT_DIAGNOSTIC_REQUEST_INVALID"}
        try:
            operation = await self._operation_service.create(
                actor=kwargs.get("actor"),
                request=EndpointDiagnosticOperationRequest(
                    ticket_id=ticket_id,
                    idempotency_key=idempotency_key,
                ),
            )
        except EndpointDiagnosticOperationUnavailable as exc:
            return {"status": "error", "error_code": str(exc) or "ENDPOINT_DIAGNOSTIC_UNAVAILABLE"}
        except EndpointDiagnosticOperationConflict:
            return {"status": "error", "error_code": "ENDPOINT_DIAGNOSTIC_OPERATION_CONFLICT"}
        except ValueError:
            return {"status": "error", "error_code": "ENDPOINT_DIAGNOSTIC_REQUEST_INVALID"}
        return {
            "status": "queued",
            "operation_id": operation.operation_id,
            "trace_id": operation.trace_id,
            "endpoint_operation_ref": None,
            "execution_target": "endpoint_operation",
            "provider_id": "endpoint_platform",
            "provider_type": "endpoint_platform",
        }
