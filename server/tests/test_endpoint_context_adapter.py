"""Safe Context service port, never legacy telemetry or direct browser transport."""
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from domain_ports.endpoint import (EndpointDeviceRef, EndpointInvalidProjection, EndpointForbidden,
    EndpointUnauthorized, EndpointNotFound, EndpointUnavailable)
from endpoint_adapter.http import ExternalEndpointHttpAdapter

pytestmark = pytest.mark.no_db


def device(device_id):
    return {"id": str(device_id), "device_identifier": "WIN", "display_name": "Windows",
        "retired_at": None, "last_seen_at": None, "online": True}


async def adapter_for(handler):
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    server = TestServer(app)
    await server.start_server()
    adapter = ExternalEndpointHttpAdapter(base_url=str(server.make_url("/")).rstrip("/"),
        service_token="synthetic-test", ca_file="", timeout_seconds=0.2, allow_insecure_test_url=True)
    return server, adapter


@pytest.mark.asyncio
async def test_context_fleet_and_exact_device():
    value = uuid4()
    async def handler(request):
        if request.path.endswith("context-summary"):
            return web.json_response({"data": {"items": [{"device": device(value), "profiles": [], "inventory_summary": None}], "next_cursor": None}})
        return web.json_response({"data": {"device": device(value), "profiles": [], "snapshots": []}})
    server, adapter = await adapter_for(handler)
    try:
        fleet = await adapter.list_device_fleet(limit=250)
        assert fleet.items[0].device.online is True
        context = await adapter.read_device_context(EndpointDeviceRef(external_id=str(value)))
        assert context.device.id == value
        assert isinstance(await adapter.read_device_context(EndpointDeviceRef(external_id=str(uuid4()))), EndpointInvalidProjection)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_context_forbidden_remains_typed_failure():
    async def handler(request):
        return web.json_response({"detail": "forbidden"}, status=403)
    server, adapter = await adapter_for(handler)
    try:
        assert isinstance(await adapter.list_device_fleet(), EndpointForbidden)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_collection_history_and_compare_use_safe_contracts():
    value, collection_id, snapshot_id, after_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc).isoformat()
    collection = {"id": str(collection_id), "device_id": str(value), "profile": "inventory_v1",
        "status": "requested", "requested_at": now, "result_received_at": None, "completed_at": None, "failure_code": None}
    snapshot = {"id": str(snapshot_id), "profile": "inventory_v1", "collected_at": now,
        "semantic_hash": "a" * 64, "warnings": [], "sections": {"system": {"hostname": "WIN"}, "hardware": {},
            "memory": {"module_count": 0, "modules": []}, "storage": {"physical_devices": []}, "interfaces": []}}
    seen = []
    async def handler(request):
        seen.append(request.path)
        if request.method == "POST":
            assert await request.json() == {"profile": "inventory_v1"}
            assert request.headers["Idempotency-Key"] == "server-generated-key"
            return web.json_response({"data": collection}, status=201)
        if request.path.endswith("compare"):
            assert request.query["before_snapshot_id"] == str(snapshot_id)
            return web.json_response({"data": {"schema_version": "device_context_diff_v1", "profile": "inventory_v1",
                "from_hash": "a" * 64, "to_hash": "b" * 64, "changes": []}})
        if request.path.endswith("snapshots"):
            assert request.query["profile"] == "inventory_v1"
            return web.json_response({"data": {"snapshots": [snapshot]}})
        return web.json_response({"data": {"collection": collection, "snapshot": snapshot}})
    server, adapter = await adapter_for(handler)
    ref = EndpointDeviceRef(external_id=str(value))
    try:
        created = await adapter.request_context_collection(ref, "inventory_v1", idempotency_key="server-generated-key")
        assert created.id == collection_id
        details = await adapter.read_context_collection(collection_id)
        assert details.collection.id == collection_id
        history = await adapter.list_context_history(ref, "inventory_v1", limit=20)
        assert history.snapshots[0].sections.system.hostname == "WIN"
        assert isinstance(history.snapshots[0].sections.interfaces, tuple)
        compare = await adapter.compare_context_snapshots(ref, snapshot_id, after_id)
        assert compare.to_hash == "b" * 64
        count = len(seen)
        for profile in ("diagnostic_v1", "activity_v1", "arbitrary"):
            assert isinstance(await adapter.request_context_collection(ref, profile, idempotency_key="key"), EndpointInvalidProjection)
            assert isinstance(await adapter.list_context_history(ref, profile), EndpointInvalidProjection)
        assert len(seen) == count
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected", [(201, EndpointUnavailable), (401, EndpointUnauthorized), (403, EndpointForbidden), (404, EndpointNotFound), (500, EndpointUnavailable), (302, EndpointUnavailable)])
async def test_context_transport_failure_is_not_offline(status, expected):
    async def handler(request):
        return web.json_response({"detail": "unavailable"}, status=status, headers={"Location": "/elsewhere"})
    server, adapter = await adapter_for(handler)
    try:
        assert isinstance(await adapter.read_device_context(EndpointDeviceRef(external_id=str(uuid4()))), expected)
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["coerced_online", "duplicate_devices", "oversize", "extra_field", "unsafe_profile"])
async def test_fleet_rejects_invalid_provider_projection(mutation):
    value = uuid4()
    item = {"device": device(value), "profiles": [], "inventory_summary": None}
    page = {"items": [item], "next_cursor": None}
    if mutation == "coerced_online":
        item["device"]["online"] = "true"
    elif mutation == "duplicate_devices":
        page["items"].append(item)
    elif mutation == "extra_field":
        item["credential"] = "forbidden"
    elif mutation == "unsafe_profile":
        item["profiles"] = [{"profile": "diagnostic_v1", "status": "completed", "last_collected_at": None}]
    async def handler(request):
        if mutation == "oversize":
            return web.Response(text=" " * 1_048_577)
        return web.json_response({"data": page})
    server, adapter = await adapter_for(handler)
    try:
        assert isinstance(await adapter.list_device_fleet(), EndpointInvalidProjection)
    finally:
        await server.close()
