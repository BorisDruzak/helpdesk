"""Typed module discovery fails closed on permission, identity and wire defects."""
from datetime import UTC, datetime

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from domain_ports.endpoint import EndpointDeviceRef, EndpointForbidden, EndpointInvalidProjection, EndpointOperationRef
from endpoint_adapter.http import ExternalEndpointHttpAdapter

pytestmark = pytest.mark.no_db
DEVICE = "11111111-1111-4111-8111-111111111111"


def page():
    return {"schema_version": "endpoint_device_modules_v1", "device_id": DEVICE,
        "observed_at": datetime.now(UTC).isoformat(), "items": [], "next_cursor": None}


async def read_with_response(payload, status=200, headers=None):
    async def handle(request):
        return web.json_response(payload, status=status,
            headers=headers if headers is not None else {"X-Correlation-ID": "module-test"})
    app = web.Application()
    app.router.add_get("/api/v1/devices/{device_id}/modules", handle)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalEndpointHttpAdapter(base_url=str(server.make_url("")), service_token="test-only",
            ca_file="", timeout_seconds=1, correlation_id_factory=lambda: "module-test", allow_insecure_test_url=True)
        assert callable(getattr(adapter, "list_device_modules", None)), "device-scoped module discovery is required"
        return await adapter.list_device_modules(EndpointDeviceRef(external_id=DEVICE), limit=50, cursor=None)
    finally:
        await server.close()


@pytest.mark.asyncio
async def test_registry_does_not_make_unpublished_module_runnable():
    payload = page()
    payload["items"] = [{"module_key": "network.dns", "display_name": "DNS", "version": "1.0.0", "state": "draft",
        "recipe": None, "availability": "available", "reason_code": None}]
    assert isinstance(await read_with_response(payload), EndpointInvalidProjection)


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["device", "oversize", "timestamp", "correlation", "redirect"])
async def test_catalog_rejects_wrong_device_or_unbounded_projection(defect):
    payload, headers, status = page(), None, 200
    if defect == "device": payload["device_id"] = "22222222-2222-4222-8222-222222222222"
    if defect == "oversize": payload["unexpected"] = "x" * 1_048_576
    if defect == "timestamp": payload["observed_at"] = "2026-10-12T10:00:00"
    if defect == "correlation": headers = {"X-Correlation-ID": "wrong"}
    if defect == "redirect": status, headers = 302, {"Location": "https://example.test", "X-Correlation-ID": "module-test"}
    assert isinstance(await read_with_response(payload, status, headers), EndpointInvalidProjection)


@pytest.mark.asyncio
async def test_catalog_permission_error_is_explicit():
    assert isinstance(await read_with_response({"detail": "forbidden"}, 403), EndpointForbidden)


def operation_payload():
    now = datetime.now(UTC).isoformat()
    return {"schema_version": "endpoint_module_operation_v1", "operation_id": DEVICE, "device_id": DEVICE,
        "module_key": "network.dns", "version": "1.0.0", "status": "succeeded", "created_at": now,
        "deadline_at": now, "completed_at": now, "expected_step_count": 1,
        "steps": [{"sequence": 0, "capability": "dns.resolve", "status": "succeeded", "error_code": None,
            "safe_result": {"schema_version": "dns_resolve_result_v1", "target": "example.test", "canonical_name": None,
                "addresses": [], "address_count": 0, "status": "succeeded", "error_code": None, "collected_at": now}}]}


async def read_operation(payload):
    async def handle(request):
        return web.json_response({"data": payload}, headers={"X-Correlation-ID": "module-test"})
    app = web.Application()
    app.router.add_get("/api/v1/module-operations/{operation_id}", handle)
    server = TestServer(app)
    await server.start_server()
    try:
        adapter = ExternalEndpointHttpAdapter(base_url=str(server.make_url("")), service_token="test-only", ca_file="",
            timeout_seconds=1, correlation_id_factory=lambda: "module-test", allow_insecure_test_url=True)
        return await adapter.read_module_operation(EndpointOperationRef(external_id=DEVICE))
    finally:
        await server.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["unknown_schema", "capability", "extra_field", "count", "result_error", "unsafe_target", "foreign_operation"])
async def test_closed_safe_result_codec_rejects_invalid_evidence(defect):
    payload = operation_payload()
    result = payload["steps"][0]["safe_result"]
    if defect == "unknown_schema": result["schema_version"] = "raw_telemetry_v1"
    if defect == "capability": payload["steps"][0]["capability"] = "tcp.connect"
    if defect == "extra_field": result["raw_log"] = "unapproved"
    if defect == "count": result["address_count"] = 1
    if defect == "result_error": result["error_code"] = "dns_failed"
    if defect == "unsafe_target": result["target"] = "https://example.test/private"
    if defect == "foreign_operation": payload["operation_id"] = "22222222-2222-4222-8222-222222222222"
    assert isinstance(await read_operation(payload), EndpointInvalidProjection)


@pytest.mark.asyncio
async def test_empty_success_keeps_its_own_run_and_collection_time():
    payload = operation_payload()
    result = await read_operation(payload)
    assert str(result.operation_id) == DEVICE
    assert result.steps[0].safe_result.address_count == 0
    assert result.steps[0].safe_result.status == "succeeded"
    assert result.steps[0].safe_result.collected_at.isoformat() == payload["steps"][0]["safe_result"]["collected_at"]


@pytest.mark.asyncio
async def test_successful_step_cannot_carry_failed_facts():
    payload=operation_payload()
    payload["steps"][0]["safe_result"].update(status="failed",error_code="dns_failed")
    assert isinstance(await read_operation(payload),EndpointInvalidProjection)


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["overflow", "missing_fact"])
async def test_resource_snapshot_retains_nullable_bounds_and_requires_success_facts(defect):
    payload = operation_payload()
    payload["steps"][0]["capability"] = "system.resource_snapshot"
    payload["steps"][0]["safe_result"] = {"schema_version": "system_resource_snapshot_result_v1",
        "uptime_seconds": 10, "cpu_percent": 1.0, "memory_total_bytes": 100, "memory_available_bytes": 50,
        "system_drive_free_bytes": 100, "status": "succeeded", "error_code": None,
        "collected_at": datetime.now(UTC).isoformat()}
    result = payload["steps"][0]["safe_result"]
    if defect == "overflow": result["uptime_seconds"] = 2**65
    if defect == "missing_fact": result["cpu_percent"] = None
    assert isinstance(await read_operation(payload), EndpointInvalidProjection)


@pytest.mark.asyncio
@pytest.mark.parametrize("capability,schema,facts", [
    ("network.ping", "network_ping_result_v1", {"target": "example.test", "transmitted": 1, "received": 1,
        "reachable": False, "packet_loss_percent": 0.0, "min_ms": 1.0, "avg_ms": 1.0, "max_ms": 1.0}),
    ("tcp.connect", "tcp_connect_result_v1", {"target": "example.test", "port": 443, "reachable": True, "latency_ms": None}),
    ("route.get", "route_get_result_v1", {"target": "example.test", "port": 443}),
    ("adapter.list", "adapter_list_result_v1", {"adapters": [], "adapter_count": 0, "up_count": 1}),
    ("process.find", "process_find_result_v1", {"process_count": 0, "present": True, "matches": []}),
    ("service.status", "service_status_v2_result_v1", {"service": None}),
    ("printer.queue.summary", "printer_queue_summary_result_v1", {"job_count": 0, "printing_count": 1,
        "queued_count": 0, "paused_count": 0, "error_count": 0}),
    ("software.find", "software_find_result_v1", {"present": True, "matches": []}),
    ("filesystem.file_metadata", "filesystem_file_metadata_result_v1", {"path_key": "endpoint_runtime_manifest", "exists": True}),
])
async def test_result_facts_cannot_contradict_their_success(capability, schema, facts):
    payload = operation_payload()
    payload["steps"][0]["capability"] = capability
    payload["steps"][0]["safe_result"] = {"schema_version": schema, "status": "succeeded", "error_code": None,
        "collected_at": datetime.now(UTC).isoformat(), **facts}
    assert isinstance(await read_operation(payload), EndpointInvalidProjection)
