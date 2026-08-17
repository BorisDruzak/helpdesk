from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.endpoint_diagnostic_operation_service import EndpointDiagnosticOperationResult
from diagnostics.capability_registry import CapabilityRegistry
from diagnostics.execution_router import CapabilityExecutionRouter
from diagnostics.providers.endpoint_platform import (
    ENDPOINT_DIAGNOSTIC_CAPABILITY_ID,
    EndpointPlatformDiagnosticProvider,
    list_endpoint_platform_capabilities,
)
from diagnostics.readiness import CapabilityReadinessService, ReadinessContext
from domain_ports.endpoint import (
    EndpointAvailability,
    EndpointCapabilitiesProjection,
    EndpointCapabilityProjection,
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointUnavailable,
)


class _BombToolService:
    async def get_tools_list(self, _device_id):
        raise AssertionError("Endpoint cutover must not enumerate legacy tools")

    async def get_tools_from_server(self, _device_id):
        raise AssertionError("Endpoint cutover must not enumerate legacy tools")

    async def run_tool(self, **_kwargs):
        raise AssertionError("Endpoint cutover must not dispatch a legacy tool")


class _OperationService:
    def __init__(self) -> None:
        self.requests = []

    async def create(self, *, actor, request):
        self.requests.append((actor, request))
        return EndpointDiagnosticOperationResult(
            operation_id="local-endpoint-operation-1",
            status="queued",
            trace_id="trace-1",
        )


class _EndpointPort:
    def __init__(self, availability) -> None:
        self._availability = availability

    async def availability(self):
        return self._availability

    async def read_device(self, device):
        return EndpointDeviceProjection(
            device=device,
            display_name="Endpoint device",
            retired=False,
            last_seen_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )

    async def list_capabilities(self, device):
        return EndpointCapabilitiesProjection(
            device=device,
            items=(EndpointCapabilityProjection(),),
        )


def test_endpoint_capability_descriptor_is_exact_and_mode_gated():
    assert list_endpoint_platform_capabilities(execution_mode="legacy") == []

    [capability] = list_endpoint_platform_capabilities(execution_mode="endpoint")

    assert capability.id == ENDPOINT_DIAGNOSTIC_CAPABILITY_ID
    assert capability.title == "Диагностика устройства через Endpoint Platform"
    assert capability.description == "Собирает ограниченный диагностический контекст через защищённый Endpoint Agent"
    assert capability.provider_id == "endpoint_platform"
    assert capability.provider_type == "endpoint_platform"
    assert capability.execution_target == "endpoint_operation"
    assert capability.risk_level == "low"
    assert capability.side_effects is False
    assert capability.requires_consent is False
    assert capability.requires_device is True
    assert capability.requires_agent_online is False
    assert capability.supports_auto_install is False
    assert capability.source == "external_endpoint"
    assert capability.params_schema == {"type": "object", "additionalProperties": False, "maxProperties": 0}
    assert capability.aliases == []


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_endpoint_router_creates_local_facade_without_legacy_tool_runtime():
    operation_service = _OperationService()
    tool_service = _BombToolService()
    registry = CapabilityRegistry(
        tool_service=tool_service,
        endpoint_diagnostic_execution_mode="endpoint",
        endpoint_cutover_only=True,
    )
    router = CapabilityExecutionRouter(
        capability_registry=registry,
        tool_service=tool_service,
        endpoint_platform_provider=EndpointPlatformDiagnosticProvider(operation_service=operation_service),
    )

    result = await router.run_capability(
        ticket_id="ticket-1",
        device_id="legacy-device-1",
        capability_id=ENDPOINT_DIAGNOSTIC_CAPABILITY_ID,
        params={},
        actor=object(),
        readiness={"readiness": "available"},
        idempotency_key="browser-request-0001",
    )

    assert result["status"] == "queued"
    assert result["operation_id"] == "local-endpoint-operation-1"
    assert result["execution_target"] == "endpoint_operation"
    assert result["provider_id"] == "endpoint_platform"
    assert result["provider_type"] == "endpoint_platform"
    assert operation_service.requests[0][1].ticket_id == "ticket-1"
    assert operation_service.requests[0][1].idempotency_key == "browser-request-0001"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_endpoint_provider_rejects_browser_params_without_creating_operation():
    operation_service = _OperationService()
    provider = EndpointPlatformDiagnosticProvider(operation_service=operation_service)
    [capability] = list_endpoint_platform_capabilities(execution_mode="endpoint")

    result = await provider.run(
        capability,
        ticket_id="ticket-1",
        device_id="legacy-device-1",
        params={"reason": "browser must not control this"},
        actor=object(),
        idempotency_key="browser-request-0001",
    )

    assert result["status"] == "error"
    assert result["error_code"] == "ENDPOINT_DIAGNOSTIC_PARAMS_INVALID"
    assert operation_service.requests == []


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_endpoint_readiness_requires_cutover_config_mapping_and_capability():
    [capability] = list_endpoint_platform_capabilities(execution_mode="endpoint")
    service = CapabilityReadinessService()
    context = ReadinessContext(
        ticket_id="ticket-1",
        device_id="legacy-device-1",
        endpoint_execution_mode="endpoint",
        endpoint_port=_EndpointPort(EndpointAvailability(status="available")),
        endpoint_device_ref="endpoint-device-1",
    )

    available = await service.get_readiness(capability, context)
    disabled = await service.get_readiness(
        capability,
        ReadinessContext(endpoint_execution_mode="legacy", endpoint_port=context.endpoint_port),
    )
    unconfigured = await service.get_readiness(
        capability,
        ReadinessContext(endpoint_execution_mode="endpoint", endpoint_port=_EndpointPort(EndpointUnavailable())),
    )
    missing_mapping = await service.get_readiness(
        capability,
        ReadinessContext(endpoint_execution_mode="endpoint", endpoint_port=context.endpoint_port),
    )

    assert (available.readiness, available.reason_code) == ("available", "AVAILABLE")
    assert (disabled.readiness, disabled.reason_code) == ("disabled_by_policy", "ENDPOINT_DIAGNOSTIC_MODE_DISABLED")
    assert (unconfigured.readiness, unconfigured.reason_code) == (
        "integration_not_configured",
        "ENDPOINT_INTEGRATION_NOT_CONFIGURED",
    )
    assert (missing_mapping.readiness, missing_mapping.reason_code) == (
        "mapping_missing",
        "ENDPOINT_DEVICE_MAPPING_MISSING",
    )


@pytest.mark.no_db
def test_endpoint_handler_runtime_composition_does_not_construct_tool_service(monkeypatch):
    import diagnostics.handlers as handlers

    class _BombToolService:
        def __init__(self, _state):
            raise AssertionError("Endpoint handler must not construct ToolExecutionService")

    marker = object()
    monkeypatch.setattr(handlers.config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "endpoint")
    monkeypatch.setattr(handlers, "ToolExecutionService", _BombToolService)
    monkeypatch.setattr(handlers, "_build_endpoint_platform_provider", lambda ticket_id: (marker, marker))

    runtime = handlers._build_diagnostic_runtime(state=object(), ticket_id="ticket-1")

    assert runtime.tool_service is None
    assert runtime.endpoint_port is marker
    assert runtime.endpoint_platform_provider is marker
    assert runtime.registry.endpoint_diagnostic_execution_mode == "endpoint"
