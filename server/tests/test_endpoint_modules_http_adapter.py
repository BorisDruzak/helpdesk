from __future__ import annotations

from datetime import datetime, timezone

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports.endpoint_modules import (
    EndpointModuleDefinitionProjection,
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModuleNotFound,
    EndpointModuleInvalidProjection,
    EndpointModuleRef,
    EndpointModuleVersionRef,
    EndpointModuleVersionCreateRequest,
    EndpointModuleRecipe,
    EndpointModuleRecipeInput,
    EndpointModuleRecipeStep,
    EndpointModuleInputBinding,
)
from endpoint_adapter.modules_http import ExternalEndpointModuleHttpAdapter


pytestmark = pytest.mark.no_db
DEVICE_ID = "11111111-1111-4111-8111-111111111111"
OPERATION_ID = "22222222-2222-4222-8222-222222222222"


def _adapter(server: TestServer) -> ExternalEndpointModuleHttpAdapter:
    return ExternalEndpointModuleHttpAdapter(
        base_url=str(server.make_url("")),
        service_token="test-service-token",
        ca_file="",
        timeout_seconds=1,
        correlation_id_factory=lambda: "module-http-correlation",
        allow_insecure_test_url=True,
    )


def _wire_response(data: object, *, status: int = 200) -> web.Response:
    return web.json_response(
        {"data": data},
        status=status,
        headers={"X-Correlation-ID": "module-http-correlation"},
    )


@pytest.mark.asyncio
async def test_adapter_lists_catalog_from_the_single_typed_route_without_query_parameters() -> None:
    received: dict[str, object] = {}

    async def list_modules(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["query"] = dict(request.query)
        return _wire_response(
            [{"module_key": "network.basic.check", "display_name": "Network basic check"}]
        )

    app = web.Application()
    app.router.add_get("/api/v1/modules", list_modules)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).list_modules()

        assert len(result) == 1
        assert result[0].module.module_key == "network.basic.check"
        assert received == {"path": "/api/v1/modules", "query": {}}
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_creates_typed_module_operation_with_device_only_in_path() -> None:
    received: dict[str, object] = {}
    now = datetime.now(timezone.utc).isoformat()

    async def create_operation(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["query"] = dict(request.query)
        received["idempotency"] = request.headers.get("Idempotency-Key")
        received["body"] = await request.json()
        return _wire_response(
            {
                "schema_version": "endpoint_module_operation_v1",
                "operation_id": OPERATION_ID,
                "device_id": DEVICE_ID,
                "module_key": "network.basic.check",
                "version": "1.0.0",
                "status": "queued",
                "created_at": now,
                "deadline_at": now,
                "completed_at": None,
            },
            status=201,
        )

    app = web.Application()
    app.router.add_post("/api/v1/devices/{device_id}/module-operations", create_operation)
    server = TestServer(app)
    await server.start_server()
    try:
        module = EndpointModuleRef(module_key="network.basic.check")
        request = EndpointModuleOperationCreateRequest(
            module_version=EndpointModuleVersionRef(module=module, version="1.0.0"),
            device_external_id=DEVICE_ID,
            inputs={"target": "example.test"},
        )
        result = await _adapter(server).create_operation(
            request,
            idempotency_key="stable-module-operation-key",
        )

        assert isinstance(result, EndpointModuleOperationProjection)
        assert result.operation.external_id == OPERATION_ID
        assert received["path"] == f"/api/v1/devices/{DEVICE_ID}/module-operations"
        assert received["query"] == {}
        assert received["idempotency"] == "stable-module-operation-key"
        assert received["body"] == {
            "schema_version": "endpoint_module_operation_create_v1",
            "module_key": "network.basic.check",
            "version": "1.0.0",
            "inputs": {"target": "example.test"},
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_creates_declarative_version_without_any_local_execution_fields() -> None:
    received: dict[str, object] = {}

    async def create_version(request: web.Request) -> web.Response:
        received["path"] = request.path
        received["body"] = await request.json()
        return _wire_response({"module_version_id": OPERATION_ID, "state": "draft"}, status=201)

    app = web.Application()
    app.router.add_post("/api/v1/modules/versions", create_version)
    server = TestServer(app)
    await server.start_server()
    try:
        request = EndpointModuleVersionCreateRequest(
            display_name="Network basic check", version="1.0.0",
            recipe=EndpointModuleRecipe(
                module_key="network.basic.check", supported_platforms=("linux_amd64",),
                inputs=(EndpointModuleRecipeInput(name="target", value_type="string"),),
                steps=(EndpointModuleRecipeStep(
                    step_id="dns", capability="dns.resolve",
                    parameters={"target": EndpointModuleInputBinding(kind="input", name="target")},
                ),),
            ),
        )
        result = await _adapter(server).create_module_version(request)

        assert result.version.module.module_key == "network.basic.check"
        assert received["path"] == "/api/v1/modules/versions"
        assert received["body"] == {
            "schema_version": "module_version_create_v1", "display_name": "Network basic check",
            "version": "1.0.0", "recipe": {
                "schema_version": "endpoint_recipe_module_v1", "module_key": "network.basic.check",
                "supported_platforms": ["linux_amd64"],
                "inputs": [{"name": "target", "value_type": "string"}],
                "steps": [{"step_id": "dns", "capability": "dns.resolve", "parameters": {
                    "target": {"kind": "input", "name": "target"},
                }}],
            },
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_reads_module_as_external_definition_without_retaining_recipe() -> None:
    async def read_module(_request: web.Request) -> web.Response:
        return _wire_response(
            {
                "module_key": "network.basic.check",
                "display_name": "Network basic check",
                "version": "1.0.0",
                "state": "published",
                "recipe": {
                    "schema_version": "endpoint_recipe_module_v1",
                    "module_key": "network.basic.check",
                    "supported_platforms": ["linux_amd64"],
                    "steps": [],
                },
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/modules/{module_key}", read_module)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_module(
            EndpointModuleRef(module_key="network.basic.check")
        )

        assert isinstance(result, EndpointModuleDefinitionProjection)
        assert result.latest_version.version == "1.0.0"
        assert not hasattr(result, "recipe")
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_reads_module_operation_detail_without_gateway_dispatch() -> None:
    now = datetime.now(timezone.utc).isoformat()

    async def read_operation(_request: web.Request) -> web.Response:
        return _wire_response(
            {
                "schema_version": "endpoint_module_operation_v1",
                "operation_id": OPERATION_ID,
                "device_id": DEVICE_ID,
                "module_key": "network.basic.check",
                "version": "1.0.0",
                "status": "queued",
                "created_at": now,
                "deadline_at": now,
                "completed_at": None,
                "steps": [
                    {
                        "sequence": 0,
                        "capability": "dns.resolve",
                        "status": "queued",
                        "error_code": None,
                        "safe_result": None,
                    }
                ],
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/module-operations/{operation_id}", read_operation)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_operation(
            EndpointModuleOperationRef(external_id=OPERATION_ID)
        )

        assert isinstance(result, EndpointModuleOperationProjection)
        assert result.status == "queued"
        assert result.result_available is False
        assert result.safe_result == ()
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_bounds_network_ping_safe_values_before_port_projection() -> None:
    now = datetime.now(timezone.utc).isoformat()

    async def read_operation(_request: web.Request) -> web.Response:
        return _wire_response(
            {
                "schema_version": "endpoint_module_operation_v1",
                "operation_id": OPERATION_ID,
                "device_id": DEVICE_ID,
                "module_key": "network.canary.check",
                "version": "1.0.0",
                "status": "succeeded",
                "created_at": now,
                "deadline_at": now,
                "completed_at": now,
                "steps": [
                    {
                        "sequence": 1,
                        "capability": "network.ping",
                        "status": "succeeded",
                        "error_code": None,
                        "safe_result": {
                            "schema_version": "network_ping_result_v1",
                            "target": "helpdesk-staging.sosnadmin.local",
                            "resolved_ip": "192.0.2.10",
                            "transmitted": 4,
                            "received": 4,
                            "packet_loss_percent": 0.0,
                            "min_ms": 1.1,
                            "avg_ms": 2.2,
                            "max_ms": 3.3,
                            "reachable": True,
                            "status": "succeeded",
                            "collected_at": now,
                        },
                    }
                ],
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/module-operations/{operation_id}", read_operation)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_operation(
            EndpointModuleOperationRef(external_id=OPERATION_ID)
        )

        assert isinstance(result, EndpointModuleOperationProjection)
        assert result.safe_result[0].safe_values == {
            "target": "helpdesk-staging.sosnadmin.local",
            "resolved_ip": "192.0.2.10",
            "packet_loss_percent": 0.0,
            "min_ms": 1.1,
            "avg_ms": 2.2,
            "max_ms": 3.3,
            "reachable": True,
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_preserves_remote_not_found_as_a_typed_module_outcome() -> None:
    async def read_module(_request: web.Request) -> web.Response:
        return web.json_response(
            {},
            status=404,
            headers={"X-Correlation-ID": "module-http-correlation"},
        )

    app = web.Application()
    app.router.add_get("/api/v1/modules/{module_key}", read_module)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_module(
            EndpointModuleRef(module_key="network.basic.check")
        )

        assert isinstance(result, EndpointModuleNotFound)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_module_step_result_with_unknown_content() -> None:
    now = datetime.now(timezone.utc).isoformat()

    async def read_operation(_request: web.Request) -> web.Response:
        return _wire_response(
            {
                "schema_version": "endpoint_module_operation_v1",
                "operation_id": OPERATION_ID,
                "device_id": DEVICE_ID,
                "module_key": "network.basic.check",
                "version": "1.0.0",
                "status": "succeeded",
                "created_at": now,
                "deadline_at": now,
                "completed_at": now,
                "steps": [
                    {
                        "sequence": 0,
                        "capability": "dns.resolve",
                        "status": "succeeded",
                        "error_code": None,
                        "safe_result": {
                            "schema_version": "dns_resolve_result_v1",
                            "target": "example.test",
                            "address_count": 1,
                            "status": "succeeded",
                            "collected_at": now,
                            "raw_output": "must not cross the boundary",
                        },
                    }
                ],
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/module-operations/{operation_id}", read_operation)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).read_operation(
            EndpointModuleOperationRef(external_id=OPERATION_ID)
        )

        assert isinstance(result, EndpointModuleInvalidProjection)
    finally:
        await server.close()
