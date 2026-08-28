from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from auth.context import AuthContext, AuthType
from domain_ports.endpoint_modules import (
    EndpointModuleCapabilityCatalog,
    EndpointModuleCapabilityDescriptor,
    EndpointModuleCapabilityParameterDescriptor,
    EndpointModuleCatalogProjection,
    EndpointModuleDefinitionProjection,
    EndpointModuleInvalidProjection,
    EndpointModuleRecipe,
    EndpointModuleRecipeInput,
    EndpointModuleRecipeStep,
    EndpointModuleInputBinding,
    EndpointModuleUnavailable,
    EndpointModuleVersionCreateRequest,
    EndpointModuleVersionProjection,
    EndpointModuleVersionRef,
    EndpointModuleRef,
)
from routes import setup_routes


pytestmark = pytest.mark.no_db


class _Request(dict):
    def __init__(self, body: dict[str, object]) -> None:
        super().__init__()
        self.app = {"endpoint_module_port": _Port()}
        self.headers = {}
        self.match_info = {}
        self._body = body

    async def json(self) -> dict[str, object]:
        return self._body


class _Port:
    def __init__(self) -> None:
        self.catalog: object = _capability_catalog()
        self.list_recipe_capabilities_calls = 0

    async def list_recipe_capabilities(self):
        self.list_recipe_capabilities_calls += 1
        return self.catalog

    async def list_modules(self):
        return (
            EndpointModuleCatalogProjection(
                module=EndpointModuleRef(module_key="network.basic.check"),
                display_name="Network basic check",
            ),
        )

    async def read_module(self, module: EndpointModuleRef):
        return EndpointModuleDefinitionProjection(
            module=module,
            display_name="Network basic check",
            latest_version=EndpointModuleVersionRef(module=module, version="1.0.0"),
            latest_state="published",
        )

    async def create_module_version(self, request: EndpointModuleVersionCreateRequest):
        self.request = request
        return EndpointModuleVersionProjection(
            version=EndpointModuleVersionRef(
                module=EndpointModuleRef(module_key=request.recipe.module_key), version=request.version
            ),
            display_name=request.display_name,
            state="draft",
        )


def _parameter(
    name: str,
    value_type: str,
    allowed_sources: tuple[str, ...],
    *,
    enum_values: tuple[str, ...] | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> EndpointModuleCapabilityParameterDescriptor:
    return EndpointModuleCapabilityParameterDescriptor(
        name=name,
        value_type=value_type,
        required=True,
        allowed_sources=allowed_sources,
        enum_values=enum_values,
        minimum=minimum,
        maximum=maximum,
        default_literal=None,
        secret=False,
    )


def _descriptor(
    capability: str,
    parameter_schema_version: str,
    result_schema_version: str,
    minimum_agent_version: str,
    feature_flag: str,
    policy: str,
    parameters: tuple[EndpointModuleCapabilityParameterDescriptor, ...] = (),
) -> EndpointModuleCapabilityDescriptor:
    return EndpointModuleCapabilityDescriptor(
        capability=capability,
        parameter_schema_version=parameter_schema_version,
        result_schema_version=result_schema_version,
        platforms=("linux_amd64", "windows_amd64"),
        minimum_agent_version=minimum_agent_version,
        risk="safe_read",
        consent_required=False,
        feature_flag=feature_flag,
        policy=policy,
        parameters=parameters,
    )


def _capability_catalog() -> EndpointModuleCapabilityCatalog:
    return EndpointModuleCapabilityCatalog(
        schema_version="endpoint_module_capability_catalog_v1",
        items=(
            _descriptor(
                "dns.resolve", "dns_resolve_parameters_v1", "dns_resolve_result_v1", "3.2.27",
                "endpoint_network_primitives_enabled", "network_target_policy",
                (
                    _parameter("target", "string", ("input", "literal")),
                    _parameter("family", "enum", ("input", "literal"), enum_values=("any", "ipv4", "ipv6")),
                ),
            ),
            _descriptor(
                "network.ping", "network_ping_parameters_v1", "network_ping_result_v1", "3.2.27",
                "endpoint_network_primitives_enabled", "network_target_policy",
                (
                    _parameter("target", "string", ("input", "literal")),
                    _parameter("count", "integer", ("input", "literal"), minimum=1, maximum=5),
                    _parameter("timeout_ms", "integer", ("input", "literal"), minimum=100, maximum=5_000),
                ),
            ),
            _descriptor(
                "tcp.connect", "tcp_connect_parameters_v1", "tcp_connect_result_v1", "3.2.27",
                "endpoint_network_primitives_enabled", "network_target_policy",
                (
                    _parameter("target", "string", ("input", "literal")),
                    _parameter("port", "integer", ("input", "literal"), minimum=1, maximum=65_535),
                    _parameter("timeout_ms", "integer", ("input", "literal"), minimum=100, maximum=10_000),
                ),
            ),
            _descriptor(
                "route.get", "route_get_parameters_v1", "route_get_result_v1", "3.2.29",
                "endpoint_read_only_primitives_enabled", "network_target_policy",
                (
                    _parameter("target", "string", ("input", "literal")),
                    _parameter("port", "integer", ("input", "literal"), minimum=1, maximum=65_535),
                    _parameter("family", "enum", ("input", "literal"), enum_values=("any", "ipv4", "ipv6")),
                    _parameter("timeout_ms", "integer", ("input", "literal"), minimum=100, maximum=5_000),
                ),
            ),
            _descriptor(
                "adapter.list", "adapter_list_parameters_v1", "adapter_list_result_v1", "3.2.29",
                "endpoint_read_only_primitives_enabled", "none",
            ),
            _descriptor(
                "system.service_status", "service_status_parameters_v1", "service_status_result_v1", "3.2.29",
                "endpoint_read_only_primitives_enabled", "none",
                (_parameter("service_key", "enum", ("literal",), enum_values=("endpoint_agent", "endpoint_agent_updater")),),
            ),
        ),
    )


@pytest.fixture
async def catalog_bff_client(monkeypatch: pytest.MonkeyPatch):
    import web_api.endpoint_module_handlers as handlers

    permissions: set[str] = set()
    port = _Port()
    actor = {"role": "admin"}

    @asynccontextmanager
    async def fake_session():
        yield object()

    async def fake_can(_session: object, _auth: object, code: str) -> bool:
        return code in permissions

    @web.middleware
    async def auth_context_middleware(request: web.Request, handler):
        request["auth_context"] = AuthContext(
            actor_id="admin-1",
            actor_role=actor["role"],
            auth_type=AuthType.UI_TOKEN,
            token="test-token",
        )
        return await handler(request)

    monkeypatch.setattr(handlers, "get_session", fake_session)
    monkeypatch.setattr(handlers, "can", fake_can)
    monkeypatch.setattr(handlers, "_port", lambda _request: port)
    app = web.Application(middlewares=[auth_context_middleware])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client, permissions, port, actor


@pytest.mark.asyncio
async def test_catalog_bff_requires_modules_read_permission(catalog_bff_client) -> None:
    client, _permissions, _port, _actor = catalog_bff_client

    response = await client.get("/api/web/admin/endpoint-modules/capabilities")

    assert response.status == 403
    assert await response.json() == {
        "status": "error",
        "error_code": "FORBIDDEN",
        "required_permission": "admin.modules.view",
    }


@pytest.mark.asyncio
async def test_catalog_bff_exposes_only_catalog_dto_fields(catalog_bff_client) -> None:
    client, permissions, port, _actor = catalog_bff_client
    permissions.add("modules.audit")

    response = await client.get("/api/web/admin/endpoint-modules/capabilities")

    assert response.status == 200
    assert await response.json() == {"data": _capability_catalog().model_dump(mode="json")}
    text = await response.text()
    assert '"recipe"' not in text
    assert '"command"' not in text
    assert '"handler_path"' not in text


@pytest.mark.asyncio
async def test_catalog_bff_allows_auditor_with_modules_audit_permission(catalog_bff_client) -> None:
    client, permissions, port, actor = catalog_bff_client
    actor["role"] = "auditor"
    permissions.add("modules.audit")

    response = await client.get("/api/web/admin/endpoint-modules/capabilities")

    assert response.status == 200
    assert await response.json() == {"data": _capability_catalog().model_dump(mode="json")}
    assert port.list_recipe_capabilities_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_code"),
    [
        (EndpointModuleUnavailable(), 503, "endpoint_module_unavailable"),
        (EndpointModuleInvalidProjection(), 502, "endpoint_module_invalid_projection"),
    ],
)
async def test_catalog_bff_preserves_typed_failure_mapping(
    catalog_bff_client,
    outcome: object,
    expected_status: int,
    expected_code: str,
) -> None:
    client, permissions, port, _actor = catalog_bff_client
    permissions.add("admin.modules.view")
    port.catalog = outcome

    response = await client.get("/api/web/admin/endpoint-modules/capabilities")

    assert response.status == expected_status
    assert await response.json() == {"status": "error", "error_code": expected_code}


@pytest.mark.asyncio
async def test_bff_create_returns_safe_projection_not_recipe_source(monkeypatch: pytest.MonkeyPatch) -> None:
    import web_api.endpoint_module_handlers as handlers

    @asynccontextmanager
    async def fake_session():
        class _Session:
            async def commit(self) -> None:
                return None

        yield _Session()

    events: list[dict[str, object]] = []

    class _Audit:
        def __init__(self, _session: object) -> None:
            pass

        async def add(self, **values: object) -> None:
            events.append(values)

    monkeypatch.setattr(handlers, "get_session", fake_session)
    monkeypatch.setattr(handlers, "can", lambda *_args: _true())
    monkeypatch.setattr(handlers, "TicketAdminAuditRepo", _Audit)

    request = _Request({
        "schema_version": "module_version_create_v1", "display_name": "Network basic check", "version": "1.0.0",
        "recipe": {
            "schema_version": "endpoint_recipe_module_v1", "module_key": "network.basic.check",
            "supported_platforms": ["linux_amd64"],
            "inputs": [{"name": "target", "value_type": "string"}],
            "steps": [{"step_id": "dns", "capability": "dns.resolve", "parameters": {
                "target": {"kind": "input", "name": "target"},
            }}],
        },
    })
    request["auth_context"] = SimpleNamespace(actor_id="admin-1", actor_role="admin")

    response = await handlers.handle_endpoint_module_create_version(request)

    assert response.status == 201
    assert response.text == '{"data": {"module_key": "network.basic.check", "version": "1.0.0", "state": "draft"}}'
    assert events[0]["after_json"] == {"module_key": "network.basic.check", "version": "1.0.0", "service_result": {"module_key": "network.basic.check", "version": "1.0.0", "state": "draft"}}


@pytest.mark.asyncio
async def test_bff_list_exposes_safe_latest_version_and_state(monkeypatch: pytest.MonkeyPatch) -> None:
    import web_api.endpoint_module_handlers as handlers

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(handlers, "get_session", fake_session)
    monkeypatch.setattr(handlers, "can", lambda *_args: _true())
    request = _Request({})
    request["auth_context"] = SimpleNamespace(actor_id="admin-1", actor_role="admin")

    response = await handlers.handle_endpoint_modules_list(request)

    assert response.status == 200
    assert response.text == (
        '{"data": [{"module_key": "network.basic.check", "display_name": '
        '"Network basic check", "version": "1.0.0", "state": "published"}]}'
    )


async def _true() -> bool:
    return True
