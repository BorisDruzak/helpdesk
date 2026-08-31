from __future__ import annotations

from datetime import datetime, timezone

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports.endpoint_modules import (
    EndpointModuleCapabilityCatalog,
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
    EndpointModuleUnavailable,
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


def _catalog_wire() -> dict[str, object]:
    return {
        "schema_version": "endpoint_module_capability_catalog_v1",
        "items": [
            {
                "capability": "dns.resolve",
                "parameter_schema_version": "dns_resolve_parameters_v1",
                "result_schema_version": "dns_resolve_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.27",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_network_primitives_enabled",
                "policy": "network_target_policy",
                "parameters": [
                    {"name": "target", "value_type": "string", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                    {"name": "family", "value_type": "enum", "required": True, "allowed_sources": ["input", "literal"], "enum_values": ["any", "ipv4", "ipv6"], "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                ],
            },
            {
                "capability": "network.ping",
                "parameter_schema_version": "network_ping_parameters_v1",
                "result_schema_version": "network_ping_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.27",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_network_primitives_enabled",
                "policy": "network_target_policy",
                "parameters": [
                    {"name": "target", "value_type": "string", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                    {"name": "count", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 1, "maximum": 5, "default_literal": None, "secret": False},
                    {"name": "timeout_ms", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 100, "maximum": 5_000, "default_literal": None, "secret": False},
                ],
            },
            {
                "capability": "tcp.connect",
                "parameter_schema_version": "tcp_connect_parameters_v1",
                "result_schema_version": "tcp_connect_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.27",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_network_primitives_enabled",
                "policy": "network_target_policy",
                "parameters": [
                    {"name": "target", "value_type": "string", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                    {"name": "port", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 1, "maximum": 65_535, "default_literal": None, "secret": False},
                    {"name": "timeout_ms", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 100, "maximum": 10_000, "default_literal": None, "secret": False},
                ],
            },
            {
                "capability": "route.get",
                "parameter_schema_version": "route_get_parameters_v1",
                "result_schema_version": "route_get_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.29",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_read_only_primitives_enabled",
                "policy": "network_target_policy",
                "parameters": [
                    {"name": "target", "value_type": "string", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                    {"name": "port", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 1, "maximum": 65_535, "default_literal": None, "secret": False},
                    {"name": "family", "value_type": "enum", "required": True, "allowed_sources": ["input", "literal"], "enum_values": ["any", "ipv4", "ipv6"], "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                    {"name": "timeout_ms", "value_type": "integer", "required": True, "allowed_sources": ["input", "literal"], "enum_values": None, "minimum": 100, "maximum": 5_000, "default_literal": None, "secret": False},
                ],
            },
            {
                "capability": "adapter.list",
                "parameter_schema_version": "adapter_list_parameters_v1",
                "result_schema_version": "adapter_list_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.29",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_read_only_primitives_enabled",
                "policy": "none",
                "parameters": [],
            },
            {
                "capability": "system.service_status",
                "parameter_schema_version": "service_status_parameters_v1",
                "result_schema_version": "service_status_result_v1",
                "platforms": ["linux_amd64", "windows_amd64"],
                "minimum_agent_version": "3.2.29",
                "risk": "safe_read",
                "consent_required": False,
                "feature_flag": "endpoint_read_only_primitives_enabled",
                "policy": "none",
                "parameters": [
                    {"name": "service_key", "value_type": "enum", "required": True, "allowed_sources": ["literal"], "enum_values": ["endpoint_agent", "endpoint_agent_updater"], "minimum": None, "maximum": None, "default_literal": None, "secret": False},
                ],
            },
        ],
    }


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
async def test_adapter_lists_recipe_capabilities_from_only_fixed_get_route_without_query_parameters() -> None:
    received: dict[str, object] = {}

    async def list_capabilities(request: web.Request) -> web.Response:
        received["method"] = request.method
        received["path"] = request.path
        received["query"] = dict(request.query)
        return _wire_response(_catalog_wire())

    app = web.Application()
    app.router.add_get("/api/v1/module-capabilities", list_capabilities)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).list_recipe_capabilities()

        assert isinstance(result, EndpointModuleCapabilityCatalog)
        assert [item.capability for item in result.items] == [
            "dns.resolve", "network.ping", "tcp.connect", "route.get", "adapter.list", "system.service_status",
        ]
        assert received == {"method": "GET", "path": "/api/v1/module-capabilities", "query": {}}
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response_correlation",
    [None, "different-module-http-correlation"],
    ids=["missing", "mismatched"],
)
async def test_adapter_rejects_catalog_without_matching_correlation_id(
    response_correlation: str | None,
) -> None:
    async def list_capabilities(_request: web.Request) -> web.Response:
        headers = (
            {"X-Correlation-ID": response_correlation}
            if response_correlation is not None
            else {}
        )
        return web.json_response({"data": _catalog_wire()}, headers=headers)

    app = web.Application()
    app.router.add_get("/api/v1/module-capabilities", list_capabilities)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await _adapter(server).list_recipe_capabilities()

        assert isinstance(result, EndpointModuleInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_catalog_with_undeclared_provider_content() -> None:
    catalog = _catalog_wire()
    catalog["items"][0]["handler_path"] = "endpoint.providers.dns.resolve"  # type: ignore[index]

    async def list_capabilities(_request: web.Request) -> web.Response:
        return _wire_response(catalog)

    app = web.Application()
    app.router.add_get("/api/v1/module-capabilities", list_capabilities)
    server = TestServer(app)
    await server.start_server()
    try:
        assert isinstance(
            await _adapter(server).list_recipe_capabilities(), EndpointModuleInvalidProjection
        )
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_catalog_with_unreleased_metadata_mutation() -> None:
    catalog = _catalog_wire()
    catalog["items"][1]["parameters"][2]["maximum"] = 9_999  # type: ignore[index]

    async def list_capabilities(_request: web.Request) -> web.Response:
        return _wire_response(catalog)

    app = web.Application()
    app.router.add_get("/api/v1/module-capabilities", list_capabilities)
    server = TestServer(app)
    await server.start_server()
    try:
        assert isinstance(
            await _adapter(server).list_recipe_capabilities(), EndpointModuleInvalidProjection
        )
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
                "expected_step_count": 1,
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
async def test_adapter_preserves_typed_ping_result_without_compatibility_scalars() -> None:
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
                "expected_step_count": 1,
                "steps": [
                    {
                        "sequence": 0,
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
        assert result.safe_result[0].safe_values == {}
        assert result.safe_result[0].safe_result == {
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
        }
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_step_status", ["succeeded", "running"])
async def test_adapter_rejects_succeeded_parent_when_any_step_lacks_result(
    invalid_step_status: str,
) -> None:
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
                "expected_step_count": 2,
                "steps": [
                    {
                        "sequence": 0,
                        "capability": "dns.resolve",
                        "status": "succeeded",
                        "error_code": None,
                        "safe_result": {
                            "schema_version": "dns_resolve_result_v1",
                            "target": "example.test",
                            "canonical_name": "example.test",
                            "addresses": [{"family": "ipv4", "address": "192.0.2.10"}],
                            "address_count": 1,
                            "status": "succeeded",
                            "error_code": None,
                            "collected_at": now,
                        },
                    },
                    {
                        "sequence": 1,
                        "capability": "network.ping",
                        "status": invalid_step_status,
                        "error_code": None,
                        "safe_result": None,
                    },
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability", "safe_result"),
    [
        (
            "dns.resolve",
            {
                "schema_version": "dns_resolve_result_v1",
                "target": "example.test",
                "canonical_name": "example.test",
                "addresses": [{"family": "ipv4", "address": "192.0.2.10"}],
                "address_count": 1,
                "status": "succeeded",
                "error_code": None,
            },
        ),
        (
            "tcp.connect",
            {
                "schema_version": "tcp_connect_result_v1",
                "target": "example.test",
                "resolved_ip": "192.0.2.10",
                "port": 443,
                "reachable": True,
                "latency_ms": 4.25,
                "status": "succeeded",
                "error_code": None,
            },
        ),
        (
            "route.get",
            {
                "schema_version": "route_get_result_v1",
                "target": "example.test",
                "resolved_ip": "192.0.2.10",
                "family": "ipv4",
                "port": 443,
                "source_ip": "192.0.2.20",
                "interface_name": "Ethernet 1",
                "strategy": "udp_socket_inference",
                "status": "succeeded",
                "error_code": None,
            },
        ),
        (
            "adapter.list",
            {
                "schema_version": "adapter_list_result_v1",
                "adapters": [
                    {
                        "name": "Ethernet 1",
                        "state": "up",
                        "kind": "ethernet",
                        "primary": True,
                        "ipv4_addresses": ["192.0.2.20"],
                        "ipv6_addresses": [],
                        "mtu": 1500,
                        "speed_mbps": 1000,
                    }
                ],
                "adapter_count": 1,
                "up_count": 1,
                "status": "succeeded",
                "error_code": None,
            },
        ),
        (
            "system.service_status",
            {
                "schema_version": "service_status_result_v1",
                "service_key": "endpoint_agent",
                "installed": True,
                "state": "running",
                "start_mode": "automatic",
                "status": "succeeded",
                "error_code": None,
            },
        ),
    ],
)
async def test_adapter_preserves_typed_results_without_compatibility_scalars(
    capability: str,
    safe_result: dict[str, object],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    typed_result = {**safe_result, "collected_at": now}

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
                "expected_step_count": 1,
                "steps": [
                    {
                        "sequence": 0,
                        "capability": capability,
                        "status": "succeeded",
                        "error_code": None,
                        "safe_result": typed_result,
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
        assert result.safe_result[0].safe_values == {}
        assert result.safe_result[0].safe_result == typed_result
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("expected_step_count", "sequences"),
    (
        (2, (0,)),  # truncated tail
        (3, (0, 2, 3)),  # internal gap
        (2, (0, 0)),  # duplicate
        (2, (1, 0)),  # out of order and missing prefix
    ),
)
async def test_adapter_rejects_succeeded_operation_with_incomplete_provider_sequence(
    expected_step_count: int,
    sequences: tuple[int, ...],
) -> None:
    now = datetime.now(timezone.utc).isoformat()

    def step(sequence: int) -> dict[str, object]:
        return {
            "sequence": sequence,
            "capability": "dns.resolve",
            "status": "succeeded",
            "error_code": None,
            "safe_result": {
                "schema_version": "dns_resolve_result_v1",
                "target": "example.test",
                "canonical_name": "example.test",
                "addresses": [{"family": "ipv4", "address": "192.0.2.10"}],
                "address_count": 1,
                "status": "succeeded",
                "error_code": None,
                "collected_at": now,
            },
        }

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
                "expected_step_count": expected_step_count,
                "steps": [step(sequence) for sequence in sequences],
            }
        )

    app = web.Application()
    app.router.add_get("/api/v1/module-operations/{operation_id}", read_operation)
    server = TestServer(app)
    await server.start_server()
    try:
        assert isinstance(
            await _adapter(server).read_operation(
                EndpointModuleOperationRef(external_id=OPERATION_ID)
            ),
            EndpointModuleInvalidProjection,
        )
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_adapter_rejects_capability_result_schema_mismatch() -> None:
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
                "expected_step_count": 1,
                "steps": [
                    {
                        "sequence": 0,
                        "capability": "dns.resolve",
                        "status": "succeeded",
                        "error_code": None,
                        "safe_result": {
                            "schema_version": "tcp_connect_result_v1",
                            "target": "example.test",
                            "resolved_ip": "192.0.2.10",
                            "port": 443,
                            "reachable": True,
                            "latency_ms": 1.0,
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

        assert isinstance(result, EndpointModuleInvalidProjection)
    finally:
        await server.close()
