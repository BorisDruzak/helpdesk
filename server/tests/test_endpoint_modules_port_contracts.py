from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import certifi

import pytest
from pydantic import ValidationError

from domain_ports.endpoint_modules import (
    EndpointModuleCapabilityCatalog,
    EndpointModuleCapabilityDescriptor,
    EndpointModuleCapabilityParameterDescriptor,
    EndpointModuleCatalogProjection,
    EndpointModuleDefinitionProjection,
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModuleOperationStepProjection,
    EndpointModuleRef,
    EndpointModuleUnavailable,
    EndpointModuleVersionProjection,
    EndpointModuleVersionRef,
    EndpointModuleVersionState,
)
from domain_ports.unavailable import UnavailableEndpointModulePort
from endpoint_adapter.modules_http import ExternalEndpointModuleHttpAdapter


pytestmark = pytest.mark.no_db


def _catalog_descriptor(
    capability: str,
    *,
    parameters: tuple[EndpointModuleCapabilityParameterDescriptor, ...] = (),
) -> EndpointModuleCapabilityDescriptor:
    return EndpointModuleCapabilityDescriptor(
        capability=capability,
        parameter_schema_version=f"{capability.replace('.', '_')}_parameters_v1",
        result_schema_version=f"{capability.replace('.', '_')}_result_v1",
        platforms=("linux_amd64", "windows_amd64"),
        minimum_agent_version="3.2.29",
        risk="safe_read",
        consent_required=False,
        feature_flag="endpoint_read_only_primitives_enabled",
        policy="none",
        parameters=parameters,
    )


def test_module_capability_catalog_is_closed_immutable_and_preserves_public_metadata() -> None:
    catalog = EndpointModuleCapabilityCatalog(
        schema_version="endpoint_module_capability_catalog_v1",
        items=(
            _catalog_descriptor("dns.resolve"),
            _catalog_descriptor("network.ping"),
            _catalog_descriptor("tcp.connect"),
            _catalog_descriptor("route.get"),
            _catalog_descriptor("adapter.list"),
            _catalog_descriptor("system.service_status"),
        ),
    )

    assert [item.capability for item in catalog.items] == [
        "dns.resolve",
        "network.ping",
        "tcp.connect",
        "route.get",
        "adapter.list",
        "system.service_status",
    ]
    assert catalog.items[0].risk == "safe_read"
    with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
        catalog.items = ()  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EndpointModuleCapabilityCatalog(
            schema_version="endpoint_module_capability_catalog_v1",
            items=catalog.items[:5],
        )
    with pytest.raises(ValidationError):
        EndpointModuleCapabilityCatalog(
            schema_version="endpoint_module_capability_catalog_v1",
            items=(*catalog.items[:5], catalog.items[4]),
        )
    with pytest.raises(ValidationError):
        _catalog_descriptor("network.trace")


def test_module_capability_parameter_descriptor_is_fail_closed() -> None:
    parameter = EndpointModuleCapabilityParameterDescriptor(
        name="timeout_ms",
        value_type="integer",
        required=True,
        allowed_sources=("input", "literal"),
        enum_values=None,
        minimum=100,
        maximum=5_000,
        default_literal=None,
        secret=False,
    )

    assert parameter.minimum == 100
    assert parameter.secret is False
    with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
        parameter.minimum = 1  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EndpointModuleCapabilityParameterDescriptor(
            name="service_key",
            value_type="enum",
            required=True,
            allowed_sources=("literal",),
            enum_values=("endpoint_agent",),
            minimum=1,
            maximum=None,
            default_literal=None,
            secret=False,
        )
    with pytest.raises(ValidationError):
        EndpointModuleCapabilityParameterDescriptor(
            name="family",
            value_type="enum",
            required=True,
            allowed_sources=("literal", "literal"),
            enum_values=("any", "ipv4", "ipv6"),
            minimum=None,
            maximum=None,
            default_literal="ipv5",
            secret=False,
        )
    with pytest.raises(ValidationError):
        EndpointModuleCapabilityParameterDescriptor(
            name="target",
            value_type="string",
            required=True,
            allowed_sources=("input",),
            enum_values=None,
            minimum=None,
            maximum=None,
            default_literal=None,
            secret=True,
        )


@pytest.mark.asyncio
async def test_unavailable_port_rejects_catalog() -> None:
    assert (await UnavailableEndpointModulePort().list_recipe_capabilities()).status == "unavailable"


def test_module_port_contracts_are_frozen_and_do_not_accept_recipe_or_command_content() -> None:
    module = EndpointModuleRef(module_key="network.basic.check")
    version = EndpointModuleVersionRef(module=module, version="1.0.0")
    catalog_entry = EndpointModuleCatalogProjection(
        module=module,
        display_name="Network basic check",
    )
    definition = EndpointModuleDefinitionProjection(
        module=module,
        display_name="Network basic check",
        latest_version=version,
        latest_state="published",
    )
    version_projection = EndpointModuleVersionProjection(
        version=version,
        display_name="Network basic check",
        state="published",
    )

    assert catalog_entry.module == module
    assert definition.latest_state == "published"
    assert version_projection.state == "published"
    with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
        definition.display_name = "changed"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        EndpointModuleDefinitionProjection(
            module=module,
            display_name="Network basic check",
            latest_version=version,
            latest_state="published",
            recipe={"steps": []},
        )
    with pytest.raises(ValidationError):
        EndpointModuleOperationCreateRequest(
            module_version=version,
            device_external_id="endpoint-device-1",
            inputs={"target": "example.test"},
            command={"capability": "network.ping"},
        )


def test_module_operation_projection_exposes_only_bounded_safe_result_and_lifecycle() -> None:
    module = EndpointModuleRef(module_key="network.basic.check")
    version = EndpointModuleVersionRef(module=module, version="1.0.0")
    now = datetime.now(timezone.utc)
    projection = EndpointModuleOperationProjection(
        operation=EndpointModuleOperationRef(external_id="module-operation-1"),
        module_version=version,
        device_external_id="endpoint-device-1",
        status="succeeded",
        created_at=now,
        deadline_at=now,
        completed_at=now,
        result_available=True,
        safe_result=(
            EndpointModuleOperationStepProjection(
                sequence=0,
                capability="dns.resolve",
                status="succeeded",
                error_code=None,
                safe_values={"address_count": 1},
            ),
        ),
    )

    assert projection.status == "succeeded"
    assert projection.safe_result[0].sequence == 0
    assert projection.safe_result[0].safe_values == {"address_count": 1}
    with pytest.raises(ValidationError):
        EndpointModuleOperationProjection(
            operation=EndpointModuleOperationRef(external_id="module-operation-1"),
            module_version=version,
            device_external_id="endpoint-device-1",
            status="queued",
            created_at=now,
            deadline_at=None,
            completed_at=None,
            result_available=True,
            safe_result=(),
        )


@pytest.mark.asyncio
async def test_unavailable_module_port_fails_closed_for_every_module_operation() -> None:
    port = UnavailableEndpointModulePort()
    module = EndpointModuleRef(module_key="network.basic.check")
    version = EndpointModuleVersionRef(module=module, version="1.0.0")
    request = EndpointModuleOperationCreateRequest(
        module_version=version,
        device_external_id="endpoint-device-1",
        inputs={"target": "example.test"},
    )

    results = (
        await port.list_modules(),
        await port.read_module(module),
        await port.read_module_version(version),
        await port.create_operation(request, idempotency_key="module-operation-1"),
        await port.read_operation(EndpointModuleOperationRef(external_id="module-operation-1")),
    )

    assert all(isinstance(result, EndpointModuleUnavailable) for result in results)
    assert all(result.code == "endpoint_module_unavailable" for result in results)


def test_module_port_composition_defaults_to_unavailable_and_rejects_unknown_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config
    from domain_ports import DomainPortContainer

    monkeypatch.setattr(config, "ENDPOINT_MODULE_PORT_MODE", "unavailable")
    assert isinstance(
        DomainPortContainer.from_config().endpoint_modules,
        UnavailableEndpointModulePort,
    )

    monkeypatch.setattr(config, "ENDPOINT_MODULE_PORT_MODE", "unexpected")
    with pytest.raises(ValueError, match="ENDPOINT_MODULE_PORT_MODE"):
        DomainPortContainer.from_config()


def test_module_port_composition_uses_its_dedicated_service_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config
    from domain_ports import DomainPortContainer

    monkeypatch.setattr(config, "ENDPOINT_MODULE_PORT_MODE", "external")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_BASE_URL", "https://endpoint.example.test")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_SERVICE_TOKEN", "diagnostic-service-token")
    monkeypatch.setattr(
        config,
        "ENDPOINT_MODULE_EXTERNAL_SERVICE_TOKEN",
        "module-service-token",
        raising=False,
    )
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_CA_FILE", certifi.where())

    endpoint_modules = DomainPortContainer.from_config().endpoint_modules

    assert Path(certifi.where()).is_file()
    assert isinstance(endpoint_modules, ExternalEndpointModuleHttpAdapter)
    assert endpoint_modules._service_token == "module-service-token"


def test_module_version_states_are_closed_and_versioned() -> None:
    assert EndpointModuleVersionState("published") == "published"
    with pytest.raises(ValueError):
        EndpointModuleVersionState("unknown")


def test_module_execution_flags_default_to_disabled_with_legacy_path_retained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib
    import config

    monkeypatch.delenv("ENDPOINT_MODULE_EXECUTION_MODE", raising=False)
    monkeypatch.delenv("LEGACY_MODULE_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("MODULE_WORKBENCH_AUTHORITY", raising=False)
    loaded = importlib.reload(config)

    assert loaded.ENDPOINT_MODULE_EXECUTION_MODE == "disabled"
    assert loaded.LEGACY_MODULE_EXECUTION_ENABLED is True
    assert loaded.MODULE_WORKBENCH_AUTHORITY == "legacy"
