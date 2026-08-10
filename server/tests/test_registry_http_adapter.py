from __future__ import annotations

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports import PersonRef, RegistryUnavailable
from registry_adapter.http import ExternalRegistryHttpAdapter


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_http_adapter_returns_only_redacted_requester_snapshot() -> None:
    received_headers: dict[str, str] = {}

    async def snapshot(request: web.Request) -> web.Response:
        received_headers.update(request.headers)
        return web.json_response(
            {
                "data": {
                    "person": {"external_id": "registry-ref-opaque-1"},
                    "display_name": "Иван",
                }
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-1",
        )

        result = await adapter.requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert result.display_name == "Иван"
        assert result.model_dump(mode="json") == {
            "person": {"external_id": "registry-ref-opaque-1"},
            "display_name": "Иван",
        }
        assert received_headers["Authorization"] == "Bearer test-service-token"
        assert received_headers["X-Registry-Service-Scope"] == "registry.helpdesk.read.v1"
        assert received_headers["X-Correlation-ID"] == "registry-correlation-1"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_maps_timeout_to_typed_unavailable_without_diagnostics() -> None:
    async def slow_snapshot(_request: web.Request) -> web.Response:
        await __import__("asyncio").sleep(0.05)
        return web.json_response({"data": {}})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", slow_snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=0.001,
        ).requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_unavailable"
    finally:
        await server.close()
