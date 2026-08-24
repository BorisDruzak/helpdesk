from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from types import SimpleNamespace

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
from diagnostics.provider_config import DiagnosticReadinessMaps
from domain_ports.endpoint import (
    EndpointAvailability,
    EndpointCapabilitiesProjection,
    EndpointCapabilityProjection,
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointUnavailable,
)


pytestmark = pytest.mark.no_db


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
        self.calls = []

    async def availability(self):
        self.calls.append("availability")
        return self._availability

    async def read_device(self, device):
        self.calls.append("read_device")
        return EndpointDeviceProjection(
            device=device,
            display_name="Endpoint device",
            retired=False,
            last_seen_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        )

    async def list_capabilities(self, device):
        self.calls.append("list_capabilities")
        return EndpointCapabilitiesProjection(
            device=device,
            items=(EndpointCapabilityProjection(),),
        )


class _HandlerResult:
    def __init__(self, value=None) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return []


class _HandlerSession:
    def __init__(self, ticket) -> None:
        self.ticket = ticket
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        return _HandlerResult(self.ticket if self.calls == 1 else None)


class _HandlerRequest(dict):
    def __init__(self, *, payload: object, auth_context) -> None:
        super().__init__(auth_context=auth_context)
        self.match_info = {
            "ticket_id": "ticket-1",
            "capability_id": ENDPOINT_DIAGNOSTIC_CAPABILITY_ID,
        }
        self.app = {"state": object()}
        self._payload = payload

    async def json(self):
        return self._payload


class _NoopExecutionObserver:
    def __init__(self, **_kwargs) -> None:
        pass

    async def record_started(self, **_kwargs) -> None:
        return None

    async def record_finished(self, **_kwargs) -> None:
        return None


def _install_handler_fakes(monkeypatch, *, ticket, endpoint_port, operation_service) -> None:
    import diagnostics.handlers as handlers

    @asynccontextmanager
    async def fake_get_session():
        yield _HandlerSession(ticket)

    class _ProviderConfigService:
        def __init__(self, _session) -> None:
            pass

        async def build_readiness_maps(self):
            return DiagnosticReadinessMaps({}, {}, {}, {}, {})

    class _RemoteAccessRepo:
        def __init__(self, _session) -> None:
            pass

        async def active_for_ticket_device(self, *_args):
            return None

    class _BombToolService:
        def __init__(self, _state) -> None:
            raise AssertionError("Endpoint handler must not construct ToolExecutionService")

    async def _bomb(*_args, **_kwargs):
        raise AssertionError("Endpoint handler must not dispatch legacy agent work")

    monkeypatch.setattr(handlers.config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "endpoint")
    monkeypatch.setattr(handlers, "get_session", fake_get_session)
    monkeypatch.setattr(handlers, "DiagnosticProviderConfigService", _ProviderConfigService)
    monkeypatch.setattr(handlers, "RemoteAccessRepo", _RemoteAccessRepo)
    monkeypatch.setattr(handlers, "RuntimeAuditCapabilityExecutionObserver", _NoopExecutionObserver)
    monkeypatch.setattr(handlers, "ToolExecutionService", _BombToolService)
    monkeypatch.setattr(
        handlers,
        "_build_endpoint_platform_provider",
        lambda _ticket_id: (
            endpoint_port,
            EndpointPlatformDiagnosticProvider(operation_service=operation_service),
        ),
    )
    monkeypatch.setattr("websocket.protocol.send_ws_command", _bomb)
    monkeypatch.setattr("websocket.protocol.enqueue_command_async", _bomb)
    monkeypatch.setattr("app.repos.device_outbox_repo.DeviceOutboxRepo.enqueue_command", _bomb)


def _handler_auth_context():
    return SimpleNamespace(actor_id="support-1", actor_role="support")


def test_endpoint_provider_composition_uses_context_managed_session_for_device_resolution(monkeypatch):
    import diagnostics.handlers as handlers

    endpoint_port = object()
    captured = {}

    @asynccontextmanager
    async def fake_get_session():
        yield object()

    def fake_get_session_maker():
        return object()

    class _Container:
        endpoint = endpoint_port

    class _DeviceResolver:
        def __init__(self, port, session_factory) -> None:
            captured["device_port"] = port
            captured["device_session_factory"] = session_factory

    class _OperationStore:
        def __init__(self, session_factory) -> None:
            captured["store_session_factory"] = session_factory

    class _OperationService:
        def __init__(self, **kwargs) -> None:
            captured["operation_service"] = kwargs

    monkeypatch.setattr(
        handlers.DomainPortContainer,
        "from_config",
        lambda: _Container(),
    )
    monkeypatch.setattr(handlers, "get_session", fake_get_session)
    monkeypatch.setattr(handlers, "get_session_maker", fake_get_session_maker)
    monkeypatch.setattr(handlers, "EndpointDeviceReferenceService", _DeviceResolver)
    monkeypatch.setattr(handlers, "SqlAlchemyEndpointDiagnosticOperationStore", _OperationStore)
    monkeypatch.setattr(handlers, "EndpointDiagnosticOperationService", _OperationService)

    returned_port, _provider = handlers._build_endpoint_platform_provider("ticket-1")

    assert returned_port is endpoint_port
    assert captured["device_port"] is endpoint_port
    assert captured["device_session_factory"] is fake_get_session
    assert captured["store_session_factory"] is fake_get_session_maker


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
        ReadinessContext(
            endpoint_execution_mode="endpoint",
            endpoint_port=_EndpointPort(EndpointUnavailable()),
            endpoint_device_ref="endpoint-device-1",
        ),
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


def test_handler_uses_only_stored_endpoint_device_ref_for_readiness():
    import diagnostics.handlers as handlers

    ticket = SimpleNamespace(endpoint_device_ref=None, device_id="legacy-device-1")

    assert handlers._stored_endpoint_device_ref(ticket) is None


@pytest.mark.no_db
@pytest.mark.asyncio
@pytest.mark.parametrize("raw_params", [["not-an-object"], {"unexpected": True}])
async def test_endpoint_handler_rejects_nonempty_or_non_object_params_before_routing(monkeypatch, raw_params):
    import diagnostics.handlers as handlers

    ticket = SimpleNamespace(
        ticket_id="ticket-1",
        device_id=None,
        endpoint_device_ref="endpoint-device-1",
        observer_root_trace_id=None,
    )
    _install_handler_fakes(
        monkeypatch,
        ticket=ticket,
        endpoint_port=_EndpointPort(EndpointAvailability(status="available")),
        operation_service=_OperationService(),
    )

    response = await handlers.handle_ticket_diagnostics_capability_run(
        _HandlerRequest(
            payload={"params": raw_params, "idempotency_key": "browser-request-0001"},
            auth_context=_handler_auth_context(),
        )
    )

    assert response.status == 400
    assert json.loads(response.body)["error_code"] == "ENDPOINT_DIAGNOSTIC_PARAMS_INVALID"


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_endpoint_handler_with_only_legacy_device_id_fails_mapping_without_port_call(monkeypatch):
    import diagnostics.handlers as handlers

    ticket = SimpleNamespace(
        ticket_id="ticket-1",
        device_id="legacy-device-1",
        endpoint_device_ref=None,
        observer_root_trace_id=None,
    )
    endpoint_port = _EndpointPort(EndpointAvailability(status="available"))
    _install_handler_fakes(
        monkeypatch,
        ticket=ticket,
        endpoint_port=endpoint_port,
        operation_service=_OperationService(),
    )

    response = await handlers.handle_ticket_diagnostics_capability_run(
        _HandlerRequest(
            payload={"params": {}, "idempotency_key": "browser-request-0001"},
            auth_context=_handler_auth_context(),
        )
    )
    payload = json.loads(response.body)

    assert response.status == 409
    assert payload["error_code"] == "CAPABILITY_NOT_READY"
    assert payload["reason_code"] == "ENDPOINT_DEVICE_MAPPING_MISSING"
    assert endpoint_port.calls == []


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_endpoint_handler_returns_queued_202_without_legacy_dispatch(monkeypatch):
    import diagnostics.handlers as handlers

    ticket = SimpleNamespace(
        ticket_id="ticket-1",
        device_id="legacy-device-1",
        endpoint_device_ref="endpoint-device-1",
        observer_root_trace_id=None,
    )
    operation_service = _OperationService()
    endpoint_port = _EndpointPort(EndpointAvailability(status="available"))
    _install_handler_fakes(
        monkeypatch,
        ticket=ticket,
        endpoint_port=endpoint_port,
        operation_service=operation_service,
    )

    response = await handlers.handle_ticket_diagnostics_capability_run(
        _HandlerRequest(
            payload={"params": {}, "idempotency_key": "browser-request-0001"},
            auth_context=_handler_auth_context(),
        )
    )
    payload = json.loads(response.body)

    assert response.status == 202
    assert payload["status"] == "queued"
    assert payload["operation_id"] == "local-endpoint-operation-1"
    assert payload["execution_target"] == "endpoint_operation"
    assert operation_service.requests[0][1].ticket_id == "ticket-1"
