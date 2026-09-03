from __future__ import annotations

from datetime import datetime, timezone
import asyncio
from pathlib import Path
from uuid import uuid4

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports import (
    EndpointCapabilitiesProjection,
    EndpointConflict,
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointForbidden,
    EndpointInvalidProjection,
    EndpointNotFound,
    EndpointOperationCreateRequest,
    EndpointOperationProjection,
    EndpointOperationRef,
    EndpointUnauthorized,
    EndpointUnavailable,
    UnavailableEndpointPort,
)
from endpoint_adapter.http import ExternalEndpointHttpAdapter


pytestmark = pytest.mark.no_db
DEVICE_ID = "11111111-1111-4111-8111-111111111111"
OPERATION_ID = "22222222-2222-4222-8222-222222222222"


def _correlation() -> dict[str, object]:
    return {
        "schema_version": "endpoint_operation_correlation_v1",
        "source_system": "helpdesk",
        "source_entity_type": "ticket",
        "source_entity_id": "opaque-source-ref",
        "request_id": str(uuid4()),
    }


def _operation_data(*, operation_ref: str = OPERATION_ID) -> dict[str, object]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "operation": {
            "schema_version": "endpoint_operation_v1",
            "operation_id": operation_ref,
            "device_id": DEVICE_ID,
            "capability": "context.diagnostic.collect",
            "status": "queued",
            "created_at": now,
            "deadline_at": now,
            "completed_at": None,
            "result_available": False,
            "warnings": [],
        },
        "result": None,
    }


def _envelope(data: object, *, correlation_id: str) -> dict[str, object]:
    del correlation_id
    return {"data": data}


def _wire_response(data: object, *, status: int = 200) -> web.Response:
    return web.json_response(
        _envelope(data, correlation_id="http-correlation"),
        status=status,
        headers={"X-Correlation-ID": "http-correlation"},
    )


def _adapter(server: TestServer, *, correlation_id: str = "http-correlation") -> ExternalEndpointHttpAdapter:
    return ExternalEndpointHttpAdapter(
        base_url=str(server.make_url("")),
        service_token="test-service-token",
        ca_file="",
        timeout_seconds=1,
        correlation_id_factory=lambda: correlation_id,
        allow_insecure_test_url=True,
    )


@pytest.mark.asyncio
async def test_adapter_reads_exact_device_projection_without_putting_ref_in_query() -> None:
    received: dict[str, object] = {}

    async def device(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["query"] = dict(request.query)
        return _wire_response({"schema_version": "endpoint_device_summary_v1", "device_id": DEVICE_ID, "display_name": "Endpoint One", "retired": False, "last_seen_at": datetime.now(timezone.utc).isoformat()})

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_device(EndpointDeviceRef(external_id=DEVICE_ID))

        assert isinstance(result, EndpointDeviceProjection)
        assert result.device.external_id == DEVICE_ID
        assert received == {"path": f"/api/v1/devices/{DEVICE_ID}", "query": {}}
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_reads_exact_capabilities_projection() -> None:
    async def capabilities(_request: web.Request) -> web.Response:
        return _wire_response({"schema_version": "endpoint_device_capabilities_v1", "device_id": DEVICE_ID, "capabilities": [
                        {
                            "capability": "context.diagnostic.collect",
                            "available": True,
                            "transport": "gateway_wss",
                            "risk": "read_only",
                            "consent_required": False,
                            "parameter_schema_version": "diagnostic_collection_parameters_v1",
                        }
                    ]})

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}/capabilities", capabilities)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).list_capabilities(EndpointDeviceRef(external_id=DEVICE_ID))

        assert isinstance(result, EndpointCapabilitiesProjection)
        assert result.items[0].capability == "context.diagnostic.collect"
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", (201, 200), ids=("created", "replayed"))
async def test_adapter_creates_or_replays_exact_operation(status: int) -> None:
    received: dict[str, object] = {}
    correlation = _correlation()

    async def create(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["query"] = dict(request.query)
        received["idempotency"] = request.headers.get("Idempotency-Key")
        received["body"] = await request.json()
        return _wire_response(_operation_data(), status=status)

    app = web.Application()
    app.router.add_post("/api/v1/devices/{device_id}/operations", create)
    server = TestServer(app)
    await server.start_server()
    try:
        request = EndpointOperationCreateRequest.model_validate(
            {"parameters": {}, "correlation": correlation}
        )
        result = await _adapter(server).create_operation(
            EndpointDeviceRef(external_id=DEVICE_ID),
            request,
            idempotency_key="stable-idempotency-key",
        )

        assert isinstance(result, EndpointOperationProjection)
        assert received["path"] == f"/api/v1/devices/{DEVICE_ID}/operations"
        assert received["query"] == {}
        assert received["idempotency"] == "stable-idempotency-key"
        assert "opaque-source-ref" not in str(received["path"])
        assert received["body"] == {"schema_version": "endpoint_operation_create_v1", "capability": "context.diagnostic.collect", "parameters": {"reason": "Collect bounded diagnostic context"}}
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_operation_with_mismatched_response_header() -> None:
    expected = _correlation()

    async def create(_request: web.Request) -> web.Response:
        return web.json_response(
            _envelope(_operation_data(), correlation_id="http-correlation"),
            status=201,
            headers={"X-Correlation-ID": "different-correlation"},
        )

    app = web.Application()
    app.router.add_post("/api/v1/devices/{device_id}/operations", create)
    server = TestServer(app)
    await server.start_server()
    try:
        request = EndpointOperationCreateRequest.model_validate(
            {"parameters": {}, "correlation": expected}
        )
        result = await _adapter(server).create_operation(
            EndpointDeviceRef(external_id=DEVICE_ID),
            request,
            idempotency_key="stable-idempotency-key",
        )

        assert isinstance(result, EndpointInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_reads_exact_operation_projection() -> None:
    async def operation(_request: web.Request) -> web.Response:
        return _wire_response(_operation_data())

    app = web.Application()
    app.router.add_get("/api/v1/operations/{operation_id}", operation)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_operation(
            EndpointOperationRef(external_id=OPERATION_ID)
        )

        assert isinstance(result, EndpointOperationProjection)
        assert result.operation.external_id == OPERATION_ID
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_cancels_exact_operation_projection() -> None:
    received: dict[str, object] = {}

    async def cancel(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["query"] = dict(request.query)
        return _wire_response(_operation_data())

    app = web.Application()
    app.router.add_post("/api/v1/operations/{operation_id}/cancel", cancel)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).cancel_operation(
            EndpointOperationRef(external_id=OPERATION_ID)
        )

        assert isinstance(result, EndpointOperationProjection)
        assert result.operation.external_id == OPERATION_ID
        assert received == {
            "path": f"/api/v1/operations/{OPERATION_ID}/cancel",
            "query": {},
        }
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("http_status", "expected_type"),
    (
        (401, EndpointUnauthorized),
        (403, EndpointForbidden),
        (404, EndpointNotFound),
        (409, EndpointConflict),
        (422, EndpointInvalidProjection),
        (429, EndpointUnavailable),
        (500, EndpointUnavailable),
    ),
)
async def test_adapter_maps_remote_statuses_to_typed_outcomes(
    http_status: int,
    expected_type: type[object],
) -> None:
    async def device(_request: web.Request) -> web.Response:
        return web.json_response(
            {}, status=http_status, headers={"X-Correlation-ID": "http-correlation"}
        )

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_device(EndpointDeviceRef(external_id="device-1"))

        assert isinstance(result, expected_type)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_error_response_with_mismatched_correlation_header() -> None:
    async def device(_request: web.Request) -> web.Response:
        return web.json_response(
            {}, status=404, headers={"X-Correlation-ID": "different-correlation"}
        )

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_device(EndpointDeviceRef(external_id="device-1"))

        assert isinstance(result, EndpointInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_bad_envelope_and_never_uses_redirect_target() -> None:
    received_redirect_target = False

    async def device(_request: web.Request) -> web.Response:
        raise web.HTTPFound("/unexpected")

    async def unexpected(_request: web.Request) -> web.Response:
        nonlocal received_redirect_target
        received_redirect_target = True
        return web.json_response(_envelope({}, correlation_id="http-correlation"))

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    app.router.add_get("/unexpected", unexpected)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_device(EndpointDeviceRef(external_id="device-1"))

        assert isinstance(result, EndpointInvalidProjection)
        assert received_redirect_target is False
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_factory",
    (
        lambda: web.Response(text="not-json", content_type="text/plain"),
        lambda: web.json_response(
            _envelope(
                {
                    "device": {"external_id": "device-1"},
                    "display_name": "Endpoint One",
                    "retired": False,
                    "last_seen_at": None,
                    "raw_context": {"must": "not pass"},
                },
                correlation_id="http-correlation",
            )
        ),
    ),
    ids=("malformed_json", "extra_projection_field"),
)
async def test_adapter_rejects_unsafe_or_malformed_response(
    response_factory: object,
) -> None:
    async def device(_request: web.Request) -> web.Response:
        return response_factory()  # type: ignore[operator]

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_device(EndpointDeviceRef(external_id="device-1"))

        assert isinstance(result, EndpointInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_maps_timeout_to_typed_unavailable() -> None:
    async def device(_request: web.Request) -> web.Response:
        await asyncio.sleep(0.05)
        return web.json_response({})

    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}", device)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalEndpointHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            ca_file="",
            timeout_seconds=0.001,
            allow_insecure_test_url=True,
        )
        result = await adapter.read_device(EndpointDeviceRef(external_id="device-1"))

        assert isinstance(result, EndpointUnavailable)
    finally:
        await server.close()


def test_container_rejects_invalid_pem_ca_before_composing_http_adapter(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import config
    from domain_ports import DomainPortContainer

    ca_file = tmp_path / "endpoint-ca.pem"
    ca_file.write_text("test-only-placeholder", encoding="utf-8")
    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "external")
    monkeypatch.setattr(config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "endpoint")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_BASE_URL", "https://endpoint.invalid")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_SERVICE_TOKEN", "service-token")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_CA_FILE", str(ca_file))
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_TIMEOUT_SECONDS", 1.0)

    endpoint = DomainPortContainer.from_config().endpoint

    assert isinstance(endpoint, UnavailableEndpointPort)
    assert endpoint._unavailable.code == "endpoint_external_ca_invalid"


def test_container_rejects_ca_file_that_ssl_context_cannot_read(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import config
    import domain_ports.container as container_module
    from domain_ports import DomainPortContainer

    ca_file = tmp_path / "endpoint-ca.pem"
    ca_file.write_text("test-only-placeholder", encoding="utf-8")

    def fail_ca_read(*_args: object, **_kwargs: object) -> None:
        raise OSError("CA file is unavailable")

    monkeypatch.setattr(container_module.ssl, "create_default_context", fail_ca_read)
    monkeypatch.setattr(config, "ENDPOINT_PORT_MODE", "external")
    monkeypatch.setattr(config, "ENDPOINT_DIAGNOSTIC_EXECUTION_MODE", "endpoint")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_BASE_URL", "https://endpoint.invalid")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_SERVICE_TOKEN", "service-token")
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_CA_FILE", str(ca_file))
    monkeypatch.setattr(config, "ENDPOINT_EXTERNAL_TIMEOUT_SECONDS", 1.0)

    endpoint = DomainPortContainer.from_config().endpoint

    assert isinstance(endpoint, UnavailableEndpointPort)
    assert endpoint._unavailable.code == "endpoint_external_ca_invalid"


@pytest.mark.asyncio
async def test_adapter_availability_is_local_and_never_invents_a_health_route() -> None:
    app = web.Application()
    server = TestServer(app)
    await server.start_server()
    try:
        availability = await _adapter(server).availability()

        assert availability.status == "available"
        assert availability.code == "endpoint_external"
    finally:
        await server.close()
