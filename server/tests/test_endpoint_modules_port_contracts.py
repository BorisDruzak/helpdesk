from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from domain_ports.endpoint_modules import (
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


pytestmark = pytest.mark.no_db


def test_module_port_contracts_are_frozen_and_do_not_accept_recipe_or_command_content() -> None:
    module = EndpointModuleRef(module_key="network.basic.check")
    version = EndpointModuleVersionRef(module=module, version="1.0.0")
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
                step_id="dns",
                capability="dns.resolve",
                status="succeeded",
                error_code=None,
                safe_values={"address_count": 1},
            ),
        ),
    )

    assert projection.status == "succeeded"
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


def test_module_version_states_are_closed_and_versioned() -> None:
    assert EndpointModuleVersionState("published") == "published"
    with pytest.raises(ValueError):
        EndpointModuleVersionState("unknown")
