from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import importlib
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

import domain_ports.endpoint as endpoint_contracts


pytestmark = pytest.mark.no_db


def _type(name: str) -> object:
    return getattr(endpoint_contracts, name)


def _example_correlation() -> object:
    correlation_type = _type("EndpointOperationCorrelation")
    return correlation_type(
        source_entity_id="ticket:opaque-case-sensitive",
        request_id=uuid4(),
    )


def test_endpoint_contract_exports_the_fixed_versioned_surface() -> None:
    expected = {
        "OpaqueEndpointRef",
        "SafeEndpointCode",
        "SafeEndpointText",
        "EndpointDeviceRef",
        "EndpointOperationRef",
        "EndpointAvailability",
        "EndpointDeviceProjection",
        "EndpointCapabilityProjection",
        "EndpointCapabilitiesProjection",
        "EndpointOperationCorrelation",
        "EndpointDiagnosticParameters",
        "EndpointOperationCreateRequest",
        "EndpointOperationProjection",
        "EndpointDiagnosticResultProjection",
        "EndpointUnavailable",
        "EndpointInvalidProjection",
        "EndpointUnauthorized",
        "EndpointForbidden",
        "EndpointNotFound",
        "EndpointConflict",
    }

    assert expected.issubset(set(vars(endpoint_contracts)))


def test_public_domain_ports_package_exports_endpoint_contracts() -> None:
    import domain_ports

    assert domain_ports.EndpointDeviceRef is _type("EndpointDeviceRef")
    assert domain_ports.EndpointOperationCreateRequest is _type("EndpointOperationCreateRequest")
    assert domain_ports.EndpointDiagnosticResultProjection is _type("EndpointDiagnosticResultProjection")


def test_opaque_endpoint_ref_preserves_transport_value_and_rejects_non_string_or_oversize() -> None:
    opaque_ref_type = _type("OpaqueEndpointRef")
    value = "  endpoint:CaseSensitive/ref  "
    opaque_ref = TypeAdapter(opaque_ref_type).validate_python(value)

    assert opaque_ref == value

    with pytest.raises(ValidationError):
        TypeAdapter(opaque_ref_type).validate_python(42)
    with pytest.raises(ValidationError):
        TypeAdapter(opaque_ref_type).validate_python("x" * 129)


def test_safe_endpoint_values_strip_text_and_reject_malformed_codes() -> None:
    safe_code_type = _type("SafeEndpointCode")
    safe_text_type = _type("SafeEndpointText")

    assert TypeAdapter(safe_code_type).validate_python("queued") == "queued"
    assert TypeAdapter(safe_text_type).validate_python("  Endpoint display name  ") == "Endpoint display name"

    for value in ("UPPER", "bad space", "bad/slash", "x" * 129):
        with pytest.raises(ValidationError):
            TypeAdapter(safe_code_type).validate_python(value)
    with pytest.raises(ValidationError):
        TypeAdapter(safe_text_type).validate_python("   ")


def test_endpoint_projections_accept_only_safe_bounded_values() -> None:
    device_ref_type = _type("EndpointDeviceRef")
    device_projection_type = _type("EndpointDeviceProjection")
    capability_projection_type = _type("EndpointCapabilityProjection")
    capabilities_projection_type = _type("EndpointCapabilitiesProjection")
    device = device_ref_type(external_id="endpoint-device-1")
    projection = device_projection_type(
        device=device,
        display_name="Workstation 1",
        retired=False,
        last_seen_at=datetime.now(timezone.utc),
    )
    capability = capability_projection_type()
    caps = capabilities_projection_type(device=device, items=(capability,))

    assert projection.source == "external_authoritative"
    assert caps.items[0].capability == "context.diagnostic.collect"
    assert caps.items[0].transport == "gateway_wss"
    with pytest.raises((FrozenInstanceError, TypeError, ValueError)):
        projection.retired = True  # type: ignore[misc]

    with pytest.raises(ValidationError):
        device_projection_type(
            device=device,
            display_name="Workstation 1",
            retired=False,
            last_seen_at=datetime.now(),
        )
    with pytest.raises(ValidationError):
        capability_projection_type(capability="anything.else")
    with pytest.raises(ValidationError):
        capabilities_projection_type(device=device, items=(capability,) * 33)
    with pytest.raises(ValidationError):
        device_projection_type(
            device=device,
            display_name="Workstation 1",
            retired=False,
            last_seen_at=datetime.now(timezone.utc),
            raw_context={},
        )


def test_operation_contract_binds_only_the_fixed_diagnostic_capability() -> None:
    device_ref_type = _type("EndpointDeviceRef")
    operation_ref_type = _type("EndpointOperationRef")
    parameters_type = _type("EndpointDiagnosticParameters")
    create_request_type = _type("EndpointOperationCreateRequest")
    projection_type = _type("EndpointOperationProjection")

    request = create_request_type(
        parameters=parameters_type(),
        correlation=_example_correlation(),
    )
    projection = projection_type(
        operation=operation_ref_type(external_id="endpoint-operation-1"),
        device=device_ref_type(external_id="endpoint-device-1"),
        created_at=datetime.now(timezone.utc),
        deadline_at=datetime.now(timezone.utc),
        completed_at=None,
        correlation=_example_correlation(),
    )

    assert request.capability == "context.diagnostic.collect"
    assert request.parameters.reason == "Диагностика по обращению"
    assert projection.status == "queued"
    with pytest.raises(ValidationError):
        parameters_type(reason="arbitrary browser reason")
    with pytest.raises(ValidationError):
        create_request_type(
            capability="diag.logs.collect",
            parameters=parameters_type(),
            correlation=_example_correlation(),
        )
    with pytest.raises(ValidationError):
        projection_type(
            operation=operation_ref_type(external_id="endpoint-operation-1"),
            device=device_ref_type(external_id="endpoint-device-1"),
            created_at=datetime.now(timezone.utc),
            deadline_at=datetime.now(timezone.utc),
            completed_at=None,
            correlation=_example_correlation(),
            result={"unbounded": "raw"},
        )


def test_safe_diagnostic_result_rejects_oversized_or_unknown_content() -> None:
    result_type = _type("EndpointDiagnosticResultProjection")
    process_type = _type("EndpointDiagnosticProcessProjection")

    result = result_type(
        collected_at=datetime.now(timezone.utc),
        processes=(process_type(name="service", state="running"),),
    )
    assert result.profile == "diagnostic_v1"
    assert result.log_excerpt is None

    with pytest.raises(ValidationError):
        result_type(collected_at=datetime.now(timezone.utc), log_excerpt="x" * 8193)
    with pytest.raises(ValidationError):
        result_type(
            collected_at=datetime.now(timezone.utc),
            processes=(process_type(name="service", state="running"),) * 65,
        )
    with pytest.raises(ValidationError):
        result_type(collected_at=datetime.now(timezone.utc), raw_context={})


def test_terminal_operation_projection_carries_only_typed_safe_diagnostic_result() -> None:
    device_ref_type = _type("EndpointDeviceRef")
    operation_ref_type = _type("EndpointOperationRef")
    process_type = _type("EndpointDiagnosticProcessProjection")
    result_type = _type("EndpointDiagnosticResultProjection")
    projection_type = _type("EndpointOperationProjection")

    safe_result = result_type(
        collected_at=datetime.now(timezone.utc),
        processes=(process_type(name="service", state="running"),),
    )
    projection = projection_type(
        operation=operation_ref_type(external_id="endpoint-operation-1"),
        device=device_ref_type(external_id="endpoint-device-1"),
        status="succeeded",
        created_at=datetime.now(timezone.utc),
        deadline_at=None,
        completed_at=datetime.now(timezone.utc),
        correlation=_example_correlation(),
        result_available=True,
        safe_result=safe_result,
    )

    assert projection.safe_result == safe_result
    with pytest.raises(ValidationError):
        projection_type(
            operation=operation_ref_type(external_id="endpoint-operation-1"),
            device=device_ref_type(external_id="endpoint-device-1"),
            status="succeeded",
            created_at=datetime.now(timezone.utc),
            deadline_at=None,
            completed_at=datetime.now(timezone.utc),
            correlation=_example_correlation(),
            result_available=False,
            safe_result=safe_result,
        )
    with pytest.raises(ValidationError):
        projection_type(
            operation=operation_ref_type(external_id="endpoint-operation-1"),
            device=device_ref_type(external_id="endpoint-device-1"),
            status="succeeded",
            created_at=datetime.now(timezone.utc),
            deadline_at=None,
            completed_at=datetime.now(timezone.utc),
            correlation=_example_correlation(),
            result_available=True,
        )
    with pytest.raises(ValidationError):
        projection_type(
            operation=operation_ref_type(external_id="endpoint-operation-1"),
            device=device_ref_type(external_id="endpoint-device-1"),
            status="queued",
            created_at=datetime.now(timezone.utc),
            deadline_at=None,
            completed_at=None,
            correlation=_example_correlation(),
            result_available=True,
            safe_result=safe_result,
        )


@pytest.mark.asyncio
async def test_unavailable_endpoint_port_fails_closed_for_every_operation() -> None:
    from domain_ports.unavailable import UnavailableEndpointPort

    device_ref_type = _type("EndpointDeviceRef")
    operation_ref_type = _type("EndpointOperationRef")
    parameters_type = _type("EndpointDiagnosticParameters")
    create_request_type = _type("EndpointOperationCreateRequest")
    unavailable_type = _type("EndpointUnavailable")
    port = UnavailableEndpointPort()
    device = device_ref_type(external_id="endpoint-device-1")

    availability = await port.availability()
    results = (
        await port.read_device(device),
        await port.list_capabilities(device),
        await port.create_operation(
            device,
            create_request_type(parameters=parameters_type(), correlation=_example_correlation()),
            idempotency_key="stable-idempotency-key",
        ),
        await port.read_operation(operation_ref_type(external_id="endpoint-operation-1")),
    )

    assert availability.status == "unavailable"
    assert availability.code == "endpoint_unavailable"
    assert all(isinstance(result, unavailable_type) for result in results)
    assert all(result.code == "endpoint_unavailable" for result in results)


def test_endpoint_configuration_uses_bounded_fail_closed_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    try:
        for name in (
            "ENDPOINT_PORT_MODE",
            "ENDPOINT_EXTERNAL_BASE_URL",
            "ENDPOINT_EXTERNAL_SERVICE_TOKEN",
            "ENDPOINT_EXTERNAL_CA_FILE",
            "ENDPOINT_EXTERNAL_TIMEOUT_SECONDS",
            "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE",
            "ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS",
            "ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE",
        ):
            monkeypatch.delenv(name, raising=False)
        loaded = importlib.reload(config)

        assert loaded.ENDPOINT_PORT_MODE == "unavailable"
        assert loaded.ENDPOINT_EXTERNAL_BASE_URL == ""
        assert loaded.ENDPOINT_EXTERNAL_SERVICE_TOKEN == ""
        assert loaded.ENDPOINT_EXTERNAL_CA_FILE == ""
        assert loaded.ENDPOINT_EXTERNAL_TIMEOUT_SECONDS == 2.0
        assert loaded.ENDPOINT_DIAGNOSTIC_EXECUTION_MODE == "legacy"
        assert loaded.ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS == 5
        assert loaded.ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE == 25

        monkeypatch.setenv("ENDPOINT_EXTERNAL_TIMEOUT_SECONDS", "NaN")
        monkeypatch.setenv("ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS", "0")
        monkeypatch.setenv("ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE", "101")
        loaded = importlib.reload(config)

        assert loaded.ENDPOINT_EXTERNAL_TIMEOUT_SECONDS == 2.0
        assert loaded.ENDPOINT_OPERATION_RECONCILE_INTERVAL_SECONDS == 1
        assert loaded.ENDPOINT_OPERATION_RECONCILE_BATCH_SIZE == 100
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_container_defaults_to_endpoint_unavailable_and_rejects_unknown_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config
    from domain_ports import DomainPortContainer, UnavailableEndpointPort

    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "unavailable")
    assert isinstance(DomainPortContainer.from_config().endpoint, UnavailableEndpointPort)

    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "unexpected")
    with pytest.raises(ValueError, match="ENDPOINT_PORT_MODE"):
        DomainPortContainer.from_config()

    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "unavailable")
    monkeypatch.setattr(config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "unexpected")
    with pytest.raises(ValueError, match="ENDPOINT_DIAGNOSTIC_EXECUTION_MODE"):
        DomainPortContainer.from_config()


@pytest.mark.parametrize(
    ("base_url", "token", "ca_file", "expected_code"),
    (
        ("http://endpoint.invalid", "service-token", "configured-ca.pem", "endpoint_external_invalid_origin"),
        ("https://endpoint.invalid/path?query=1", "service-token", "configured-ca.pem", "endpoint_external_invalid_origin"),
        ("https://endpoint.invalid", "", "configured-ca.pem", "endpoint_external_service_token_missing"),
        ("https://endpoint.invalid", "service-token", "", "endpoint_external_ca_missing"),
        ("https://[::1", "service-token", "configured-ca.pem", "endpoint_external_invalid_origin"),
        ("https://endpoint.invalid:notaport", "service-token", "configured-ca.pem", "endpoint_external_invalid_origin"),
        ("https://endpoint.invalid:99999", "service-token", "configured-ca.pem", "endpoint_external_invalid_origin"),
        ("https://endpoint.invalid", "   ", "configured-ca.pem", "endpoint_external_service_token_missing"),
    ),
)
def test_external_endpoint_configuration_degrades_to_typed_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    token: str,
    ca_file: str,
    expected_code: str,
) -> None:
    import config
    from domain_ports import DomainPortContainer, UnavailableEndpointPort

    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "external")
    monkeypatch.setattr(config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "legacy")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_BASE_URL", base_url)
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_SERVICE_TOKEN", token)
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_CA_FILE", ca_file)

    endpoint = DomainPortContainer.from_config().endpoint

    assert isinstance(endpoint, UnavailableEndpointPort)
    assert endpoint._unavailable.code == expected_code


@pytest.mark.parametrize(
    "status",
    ("available", "unavailable", "invalid_projection", "unauthorized", "forbidden", "not_found", "conflict"),
)
def test_availability_accepts_only_the_documented_outcomes(status: str) -> None:
    availability_type = _type("EndpointAvailability")

    assert availability_type(status=status).status == status
    with pytest.raises(ValidationError):
        availability_type(status="unexpected")


def test_diagnostic_process_rejects_unknown_state_or_raw_fields() -> None:
    process_type = _type("EndpointDiagnosticProcessProjection")

    with pytest.raises(ValidationError):
        process_type(name="service", state="unknown_state")
    with pytest.raises(ValidationError):
        process_type(name="service", state="running", command_line="secret")
