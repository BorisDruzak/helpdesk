from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from domain_ports.endpoint_modules import (
    EndpointModuleCatalogProjection,
    EndpointModuleDefinitionProjection,
    EndpointModuleRecipe,
    EndpointModuleRecipeInput,
    EndpointModuleRecipeStep,
    EndpointModuleInputBinding,
    EndpointModuleVersionCreateRequest,
    EndpointModuleVersionProjection,
    EndpointModuleVersionRef,
    EndpointModuleRef,
)


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
