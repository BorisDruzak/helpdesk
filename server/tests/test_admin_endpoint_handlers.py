"""Actual route registration and guarded Context orchestration."""
from aiohttp import web
import pytest
from routes import setup_routes

pytestmark = pytest.mark.no_db


def test_admin_endpoint_context_routes_are_registered():
    app = web.Application()
    setup_routes(app)
    registered = {(r.method, r.resource.canonical) for r in app.router.routes()}
    assert {
        ("GET", "/api/web/admin/endpoint/devices"),
        ("GET", "/api/web/admin/endpoint/devices/{device_id}"),
        ("POST", "/api/web/admin/endpoint/devices/{device_id}/context/refresh"),
        ("GET", "/api/web/admin/endpoint/context/collections/{collection_id}"),
        ("GET", "/api/web/admin/endpoint/devices/{device_id}/context/history"),
        ("GET", "/api/web/admin/endpoint/devices/{device_id}/context/compare"),
    } <= registered


import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
from aiohttp.test_utils import make_mocked_request
from domain_ports.endpoint import EndpointUnavailable, EndpointNotFound
from domain_ports.endpoint_context import EndpointDeviceContext, EndpointDeviceFleet, EndpointContextCollection
from registry.endpoint_device_overlay import RegistryDeviceOverlay, read_registry_device_overlays
from web_api import admin_endpoint_handlers as handlers


def request(path, *, role="admin", device_id=None, method="GET"):
    req = make_mocked_request(method, path, match_info={"device_id": device_id or str(uuid4())})
    if role:
        req["auth_context"] = SimpleNamespace(actor_role=role, actor_id="test")
    return req


def install_endpoint(monkeypatch, endpoint):
    monkeypatch.setattr(handlers.DomainPortContainer, "from_config", lambda: SimpleNamespace(endpoint=endpoint))


@pytest.mark.asyncio
async def test_exact_detail_never_lists_devices_or_substitutes_another_id(monkeypatch):
    device_id = uuid4()
    calls = []
    async def read(device):
        calls.append(device.external_id)
        return EndpointNotFound()
    install_endpoint(monkeypatch, SimpleNamespace(read_device_context=read))
    response = await handlers.handle_admin_endpoint_device(request("/detail", device_id=str(device_id)))
    assert response.status == 404
    assert json.loads(response.text)["error_code"] == "endpoint_not_found"
    assert calls == [str(device_id)]
    invalid = await handlers.handle_admin_endpoint_device(request("/detail", device_id="invalid"))
    assert invalid.status == 400 and len(calls) == 1


@pytest.mark.asyncio
async def test_fleet_unavailable_is_unknown_and_does_not_read_registry(monkeypatch):
    async def fleet(**kwargs):
        return EndpointUnavailable()
    install_endpoint(monkeypatch, SimpleNamespace(list_device_fleet=fleet))
    response = await handlers.handle_admin_endpoint_devices(request("/fleet"))
    assert response.status == 503
    assert "offline" not in response.text
    assert json.loads(response.text)["error_code"] == "endpoint_unavailable"


@pytest.mark.asyncio
async def test_fleet_uses_one_provider_call_and_one_bulk_overlay(monkeypatch):
    values = sorted((uuid4(), uuid4()))
    payload = EndpointDeviceFleet.model_validate({"items": [{"device": {
        "id": str(value), "device_identifier": "WIN", "display_name": "WIN", "online": True,
        "last_seen_at": None, "retired_at": None}, "profiles": [], "inventory_summary": None} for value in values], "next_cursor": None})
    calls = []
    async def fleet(**kwargs):
        calls.append(kwargs)
        return payload
    async def overlays(devices):
        assert devices == tuple(values)
        calls.append("overlay")
        return {value: RegistryDeviceOverlay(status="unmapped") for value in devices}
    install_endpoint(monkeypatch, SimpleNamespace(list_device_fleet=fleet))
    monkeypatch.setattr(handlers, "_overlays", overlays)
    response = await handlers.handle_admin_endpoint_devices(request("/fleet?limit=2"))
    data = json.loads(response.text)["data"]
    assert len(calls) == 2
    assert data["items"][0]["registry"]["status"] == "unmapped"
    assert data["technical_source"] == "endpoint"
    assert response.headers["Cache-Control"] == "no-store"
    assert (await handlers.handle_admin_endpoint_devices(request("/fleet?limit=251"))).status == 400
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_refresh_is_bounded_server_idempotency_and_preserves_partial_failure(monkeypatch):
    value = uuid4()
    calls = []
    async def create(device, profile, *, idempotency_key):
        calls.append((device.external_id, profile, idempotency_key))
        if profile == "health_v1":
            return EndpointUnavailable()
        return EndpointContextCollection(id=uuid4(), device_id=value, profile=profile, status="requested",
            requested_at="2026-10-01T00:00:00Z", completed_at=None, result_received_at=None, failure_code=None)
    install_endpoint(monkeypatch, SimpleNamespace(request_context_collection=create))
    req = request("/refresh", device_id=str(value), method="POST")
    async def body():
        return {"profiles": ["inventory_v1", "health_v1"]}
    monkeypatch.setattr(req, "json", body)
    response = await handlers.handle_admin_endpoint_context_refresh(req)
    data = json.loads(response.text)["data"]
    assert response.status == 202 and data["status"] == "partial"
    assert len(calls) == 2 and calls[0][2] != calls[1][2]
    assert all(1 <= len(call[2]) <= 128 and call[0] == str(value) for call in calls)
    assert data["results"][1]["error_code"] == "endpoint_unavailable"
    for invalid in ({"profiles": ["activity_v1"]}, {"profiles": ["inventory_v1", "inventory_v1"]}, {"idempotency_key": "browser"}, {"profiles": []}):
        async def invalid_body():
            return invalid
        monkeypatch.setattr(req, "json", invalid_body)
        assert (await handlers.handle_admin_endpoint_context_refresh(req)).status == 400
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_reads_require_auth_and_auditor_cannot_refresh(monkeypatch):
    async def audit(*args, **kwargs):
        pass
    import auth.middleware as middleware
    monkeypatch.setattr(middleware, "_write_web_auth_audit", audit)
    assert (await handlers.handle_admin_endpoint_devices(request("/fleet", role=None))).status == 401
    assert (await handlers.handle_admin_endpoint_context_refresh(request("/refresh", method="POST", role="auditor"))).status == 403


@pytest.mark.asyncio
async def test_overlay_never_infers_a_mapping_and_uses_only_canonical_tables():
    from sqlalchemy.dialects import postgresql
    statements = []
    class EmptySession:
        async def execute(self, statement):
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: []))
    value = uuid4()
    result = await read_registry_device_overlays(EmptySession(), (value,))
    assert result[value].status == "unmapped"
    assert len(statements) == 1
    assert "registry_endpoint_device_mappings" in statements[0]
    assert "device_inventory" not in statements[0] and "presence" not in statements[0]
