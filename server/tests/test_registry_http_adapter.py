from __future__ import annotations

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports import (
    ActorRef,
    DirectorySearchText,
    PersonRef,
    RegistryInvalidProjection,
    RegistryReadActor,
    RegistryUnavailable,
)
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
                },
                "correlation_id": "registry-correlation-1",
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
            allow_insecure_test_url=True,
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
async def test_http_adapter_reads_redacted_inventory_quality_projection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"active_pc_without_location_count": 4},
                "correlation_id": "registry-correlation-inventory-quality",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-inventory-quality",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert result.model_dump(mode="json") == {
            "active_pc_without_location_count": 4,
            "source": "external_authoritative",
        }
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_invalid_inventory_quality_projection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {"active_pc_without_location_count": "four"},
                "correlation_id": "registry-correlation-invalid-inventory-quality",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-invalid-inventory-quality",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_rejects_inventory_quality_source_before_local_source_injection() -> None:
    async def inventory_quality(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "active_pc_without_location_count": 4,
                    "source": "external_authoritative",
                },
                "correlation_id": "registry-correlation-unexpected-source",
            }
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/inventory-quality", inventory_quality)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-unexpected-source",
            allow_insecure_test_url=True,
        ).inventory_quality()

        assert isinstance(result, RegistryInvalidProjection)
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
            allow_insecure_test_url=True,
        ).requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_unavailable"
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("response_correlation_id", [None, "registry-correlation-other"])
async def test_http_adapter_rejects_success_envelope_without_matching_correlation_id(
    response_correlation_id: str | None,
) -> None:
    async def snapshot(_request: web.Request) -> web.Response:
        envelope: dict[str, object] = {
            "data": {
                "person": {"external_id": "registry-ref-opaque-1"},
                "display_name": "Requester One",
            }
        }
        if response_correlation_id is not None:
            envelope["correlation_id"] = response_correlation_id
        return web.json_response(envelope)

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        result = await ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-expected",
            allow_insecure_test_url=True,
        ).requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_never_sends_bearer_to_non_https_url() -> None:
    received_headers: dict[str, str] = {}

    async def snapshot(request: web.Request) -> web.Response:
        received_headers.update(request.headers)
        return web.json_response({"data": {}, "correlation_id": "unexpected"})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/snapshot", snapshot)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
        )

        result = await adapter.requester_snapshot(PersonRef(external_id="registry-ref-opaque-1"))

        assert isinstance(result, RegistryUnavailable)
        assert result.code == "registry_external_unconfigured"
        assert received_headers == {}
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_bounds_directory_limit_before_http_request() -> None:
    received_query: dict[str, str] = {}

    async def search(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {"data": {"items": []}, "correlation_id": "registry-correlation-limit"}
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/directory/people", search)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-limit",
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        await adapter.search_people(DirectorySearchText("requester"), actor=actor, limit=999)

        assert received_query["limit"] == "50"
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_http_adapter_bounds_history_limit_before_http_request() -> None:
    received_query: dict[str, str] = {}

    async def history(request: web.Request) -> web.Response:
        received_query.update(request.query)
        return web.json_response(
            {"data": {"items": []}, "correlation_id": "registry-correlation-history"}
        )

    app = web.Application()
    app.router.add_get("/v1/helpdesk/requesters/{person_ref}/history", history)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            correlation_id_factory=lambda: "registry-correlation-history",
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        await adapter.requester_history(
            PersonRef(external_id="registry-ref-opaque-1"),
            actor=actor,
            limit=999,
        )

        assert received_query["limit"] == "100"
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, True])
async def test_http_adapter_rejects_invalid_collection_limit_before_http_request(limit: int) -> None:
    received = False

    async def search(_request: web.Request) -> web.Response:
        nonlocal received
        received = True
        return web.json_response({"data": {"items": []}, "correlation_id": "unexpected"})

    app = web.Application()
    app.router.add_get("/v1/helpdesk/directory/people", search)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalRegistryHttpAdapter(
            base_url=str(server.make_url("")),
            service_token="test-service-token",
            timeout_seconds=1,
            allow_insecure_test_url=True,
        )
        actor = RegistryReadActor(
            actor=ActorRef(external_id="registry-ref-opaque-actor-1"),
            role="support",
        )

        result = await adapter.search_people(DirectorySearchText("requester"), actor=actor, limit=limit)

        assert isinstance(result, RegistryInvalidProjection)
        assert received is False
    finally:
        await server.close()
