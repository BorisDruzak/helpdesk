import importlib.util
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.no_db
def test_browser_intent_cannot_supply_device_recipe_or_coerce_inputs():
    assert importlib.util.find_spec("web_api.dto.endpoint_tools") is not None
    from web_api.dto.endpoint_tools import EndpointToolRunCreateV1
    valid = dict(schema_version="endpoint_tool_run_create_v1", expected_device_ref=str(uuid4()),module_key="helpdesk.dns", version="1.0.0", inputs={"target": "example.test"}, caller_key="key")
    assert EndpointToolRunCreateV1(**valid).inputs["target"] == "example.test"
    for field in ("device_id", "recipe", "service_token"):
        with pytest.raises(ValidationError): EndpointToolRunCreateV1(**valid, **{field:"untrusted"})
    with pytest.raises(ValidationError): EndpointToolRunCreateV1(**{**valid,"inputs":{"count":True}})


@pytest.mark.no_db
def test_foreign_ticket_or_changed_device_cannot_read_run():
    assert importlib.util.find_spec("web_api.endpoint_tool_handlers") is not None
    from web_api.endpoint_tool_handlers import require_run_identity
    from app.services.endpoint_tool_run_service import ToolAdmissionError
    run = SimpleNamespace(ticket_id="ticket", device_ref="device")
    require_run_identity(run, "ticket", "device")
    with pytest.raises(ToolAdmissionError): require_run_identity(run, "other", "device")
    with pytest.raises(ToolAdmissionError): require_run_identity(run, "ticket", "other")


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_cache_metadata_ttl_is_independent_of_device_availability():
    from web_api.endpoint_tool_handlers import EndpointToolCatalogCache
    from domain_ports.endpoint import EndpointDeviceRef
    clock=[0]
    provider=SimpleNamespace(list_primitives=AsyncMock(return_value="primitives"), list_device_modules=AsyncMock(return_value="device"))
    cache=EndpointToolCatalogCache(provider, clock=lambda:clock[0])
    device=EndpointDeviceRef(external_id=str(uuid4()))
    await cache.primitives(); await cache.device_page(device)
    clock[0]=6
    await cache.primitives(); await cache.device_page(device)
    assert provider.list_primitives.await_count == 1 and provider.list_device_modules.await_count == 2
    clock[0]=61
    await cache.primitives()
    assert provider.list_primitives.await_count == 2


@pytest.mark.no_db
def test_provider_authentication_error_does_not_log_out_browser():
    from web_api.endpoint_tool_handlers import tool_error_response
    from app.services.endpoint_tool_run_service import ToolAdmissionError
    response=tool_error_response(ToolAdmissionError("endpoint_forbidden",502))
    assert response.status == 502 and response.headers["Cache-Control"] == "no-store"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_auditor_can_read_but_cannot_run(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from auth.context import AuthContext, AuthType
    import web_api.endpoint_tool_handlers as handlers
    @web.middleware
    async def auth(request, handler):
        request["auth_context"]=AuthContext(actor_id="auditor",actor_role="auditor",auth_type=AuthType.UI_TOKEN,token="fixture")
        return await handler(request)
    app=web.Application(middlewares=[auth])
    app.router.add_post('/api/web/support/tickets/{ticket_id}/endpoint-tools/runs',handlers.handle_tool_run_create)
    async with TestClient(TestServer(app)) as client:
        response=await client.post('/api/web/support/tickets/ticket/endpoint-tools/runs',json={})
        assert response.status==403


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_cookie_tool_mutation_requires_same_origin(monkeypatch):
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from auth.context import AuthContext, AuthType
    import auth.middleware as auth
    from web_api.endpoint_tool_handlers import handle_tool_run_create
    actor=AuthContext(actor_id="support",actor_role="support",auth_type=AuthType.UI_TOKEN,token="fixture")
    monkeypatch.setattr(auth,"extract_auth_context",AsyncMock(return_value=actor))
    monkeypatch.setattr(auth,"extract_token_from_web_cookie",lambda _:"fixture")
    monkeypatch.setattr(auth,"_write_web_auth_audit",AsyncMock())
    app=web.Application(middlewares=[auth.auth_middleware])
    app.router.add_post('/api/web/support/tickets/{ticket_id}/endpoint-tools/runs',handle_tool_run_create)
    async with TestClient(TestServer(app)) as client:
        response=await client.post('/api/web/support/tickets/t/endpoint-tools/runs',json={})
        assert response.status==403
        assert (await response.json())["error_code"]=="CSRF_ORIGIN_REQUIRED"


@pytest.mark.asyncio
async def test_real_ticket_api_batch_replay_and_foreign_run_denial(test_client_light,test_engine,monkeypatch):
    from datetime import datetime,timezone
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from app.db.models import Ticket, DiagnosticStep
    from domain_ports.endpoint import EndpointDeviceRef,EndpointDevicePresenceProjection
    from app.services.endpoint_device_reference_service import EndpointDeviceSnapshotV1
    import web_api.endpoint_tool_handlers as handlers
    import config
    monkeypatch.setattr(config,"ENDPOINT_TOOLS_WORKSPACE_ENABLED",True)
    device=str(uuid4()); ticket=str(uuid4()); other=str(uuid4()); now=datetime.now(timezone.utc)
    snapshot=EndpointDeviceSnapshotV1(device_ref=device,display_name="Fixture device",retired=False,last_seen_at=now,captured_at=now).model_dump(mode="json")
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    async with maker() as session:
        session.add_all([Ticket(ticket_id=t,title="Tools fixture",description="Tools",status="in_progress",
            endpoint_device_ref=device,endpoint_device_snapshot_json=snapshot) for t in (ticket,other)])
        await session.commit()
    endpoint=SimpleNamespace(read_device_presence=AsyncMock(return_value=EndpointDevicePresenceProjection(device=EndpointDeviceRef(external_id=device),display_name="Fixture",retired=False,online=True,last_seen_at=now)))
    ports=SimpleNamespace(endpoint=endpoint,endpoint_modules=None)
    monkeypatch.setattr(handlers,"_runtime",lambda _:(ports,None))
    headers={"Authorization":"Bearer test-ui-admin-token"}
    path=f"/api/web/support/tickets/{ticket}/endpoint-tools/collections"
    body={"schema_version":"endpoint_tool_batch_create_v1","expected_device_ref":device,"caller_key":"batch-replay"}
    first=await test_client_light.post(path,json=body,headers=headers)
    assert first.status==202,await first.text()
    data=(await first.json())["data"]
    replay=await test_client_light.post(path,json=body,headers=headers)
    assert replay.status==202 and (await replay.json())["data"]["batch_id"]==data["batch_id"]
    assert len(data["runs"])==6 and len({r["run_id"] for r in data["runs"]})==6
    run_id=data["runs"][0]["run_id"]
    foreign=await test_client_light.get(f"/api/web/support/tickets/{other}/endpoint-tools/runs/{run_id}",headers=headers)
    assert foreign.status==404
    async with maker() as session:
        assert await session.get(DiagnosticStep,run_id) is not None
    auditor=await test_client_light.get(f"{path}/{data['batch_id']}",headers={"Authorization":"Bearer test-ui-auditor-token"})
    assert auditor.status==200,await auditor.text()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["module", "batch"])
async def test_stale_panel_device_precondition_rejects_before_durable_intent(test_client_light,test_engine,monkeypatch,kind):
    from datetime import datetime,timezone
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import select
    from app.db.models import Ticket,EndpointToolRun
    from app.services.endpoint_device_reference_service import EndpointDeviceSnapshotV1
    import web_api.endpoint_tool_handlers as handlers
    import config
    monkeypatch.setattr(config,"ENDPOINT_TOOLS_WORKSPACE_ENABLED",True)
    device=str(uuid4());old=str(uuid4());ticket=str(uuid4());now=datetime.now(timezone.utc)
    snapshot=EndpointDeviceSnapshotV1(device_ref=device,display_name="Device B",retired=False,last_seen_at=now,captured_at=now).model_dump(mode="json")
    maker=async_sessionmaker(test_engine,expire_on_commit=False)
    async with maker() as session:
        session.add(Ticket(ticket_id=ticket,title="Changed mapping",description="Tools",status="in_progress",endpoint_device_ref=device,endpoint_device_snapshot_json=snapshot));await session.commit()
    modules=SimpleNamespace(list_device_modules=AsyncMock())
    endpoint=SimpleNamespace(read_device_presence=AsyncMock())
    monkeypatch.setattr(handlers,"_runtime",lambda _:(SimpleNamespace(endpoint=endpoint,endpoint_modules=modules),None))
    body={"schema_version":"endpoint_tool_run_create_v1" if kind=="module" else "endpoint_tool_batch_create_v1","caller_key":"stale", "expected_device_ref":old}
    if kind=="module":body.update(module_key="helpdesk.dns",version="1.0.0",inputs={"target":"example.test"})
    path=f"/api/web/support/tickets/{ticket}/endpoint-tools/"+("runs" if kind=="module" else "collections")
    response=await test_client_light.post(path,json=body,headers={"Authorization":"Bearer test-ui-admin-token"})
    assert response.status==409,await response.text()
    assert (await response.json())["error_code"]=="endpoint_device_changed"
    modules.list_device_modules.assert_not_awaited();endpoint.read_device_presence.assert_not_awaited()
    async with maker() as session:assert not (await session.execute(select(EndpointToolRun).where(EndpointToolRun.ticket_id==ticket))).scalars().all()


@pytest.mark.asyncio
async def test_operator_mcp_selects_device_and_reads_printer_tool_result(
    test_client_light, test_engine, monkeypatch, tmp_path,
):
    import hashlib
    import json
    import sys
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    from sqlalchemy.ext.asyncio import async_sessionmaker

    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    import config
    from app.db.models import Device, DeviceUserBinding, RegistryEndpointDeviceMapping, RegistryPerson, Ticket
    from app.services.endpoint_tool_reconciler import EndpointToolReconciler
    from auth import middleware
    from domain_ports.container import DomainPortContainer
    from domain_ports.endpoint import EndpointDeviceProjection, EndpointDeviceRef
    from domain_ports.endpoint_module_contracts_generated import (
        EndpointDeviceModulesPageV1, ModuleCapabilityAuthoringV1, ModuleCapabilityCatalogV1,
        ModuleOperationDetailV1, ModuleOperationV1, ModuleVersionViewV1,
    )
    from tests.test_web_support_api import _seed_support_ticket, real_extract_auth_context

    monkeypatch.setattr(middleware, "extract_auth_context", real_extract_auth_context)
    monkeypatch.setattr(config, "ENDPOINT_TOOLS_WORKSPACE_ENABLED", True)
    now = datetime.now(UTC)
    device_id, person_id, endpoint_id, remote_id = (str(uuid4()) for _ in range(4))
    ticket_id = await _seed_support_ticket(test_engine)
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    async with sessions.begin() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.requester_person_id = person_id
        session.add_all([
            RegistryPerson(person_id=person_id, display_name="Fixture requester"),
            Device(device_id=device_id, protocol_version="3", agent_version="3", hostname="fixture-cups"),
        ])
        await session.flush()
        session.add_all([
            DeviceUserBinding(person_id=person_id, device_id=device_id, confirmed_at=now),
            RegistryEndpointDeviceMapping(device_id=device_id, endpoint_device_ref=endpoint_id, verified_at=now),
        ])

    capabilities = ("printer.list", "printer.status", "printer.queue.summary")
    schemas = ("printer_list_result_v1", "printer_status_result_v1", "printer_queue_summary_result_v1")
    name_binding = {"printer_name": {"kind": "input", "name": "printer_name"}}
    module = ModuleVersionViewV1(
        module_key="helpdesk.printer.check", display_name="Fixture printer check", version="1.0.0", state="published",
        recipe={"schema_version": "endpoint_recipe_module_v1", "module_key": "helpdesk.printer.check",
                "supported_platforms": ["linux_amd64"], "inputs": [{"name": "printer_name", "value_type": "string"}],
                "steps": [{"step_id": f"step_{index}", "capability": capability,
                           "parameters": name_binding if capability == "printer.status" else {}}
                          for index, capability in enumerate(capabilities)]},
    )
    printer_name_parameter = {"name": "printer_name", "allowed_sources": ["input", "literal"], "value_type": "string",
                              "required": True, "secret": False, "enum_values": None, "default_literal": None,
                              "maximum": None, "minimum": None}
    primitives = ModuleCapabilityCatalogV1.model_construct(
        schema_version="endpoint_module_capability_catalog_v1",
        items=[ModuleCapabilityAuthoringV1(
            capability=capability, category="printer", consent_required=False, display_name_ru=capability,
            execution_timeout_seconds=10, feature_flag="endpoint_printer_primitives_enabled",
            max_result_items=16 if capability == "printer.list" else 1, minimum_agent_version="3.2.67",
            parameter_schema_version=f"{schema.removesuffix('_result_v1')}_parameters_v1",
            result_schema_version=schema, platforms=["linux_amd64", "windows_amd64"], policy="local_printers",
            risk="controlled_read", parameters=[printer_name_parameter] if capability == "printer.status" else [],
        ) for capability, schema in zip(capabilities, schemas)],
    )
    facts = (
        {"printers": [{"name": "office", "default": True, "port_type": "network", "state": "paused"}]},
        {"exists": True, "offline": False, "paused": True, "error": False, "state": "paused"},
        {"job_count": 2, "printing_count": 0, "queued_count": 2, "paused_count": 0, "error_count": 0},
    )
    remote_projection = {
        "schema_version": "endpoint_module_operation_v1", "operation_id": remote_id,
        "device_id": endpoint_id, "module_key": module.module_key, "version": module.version,
        "created_at": now, "deadline_at": now + timedelta(minutes=1),
    }
    modules = SimpleNamespace(
        list_primitives=AsyncMock(return_value=primitives),
        list_device_modules=AsyncMock(return_value=EndpointDeviceModulesPageV1(
            device_id=endpoint_id, observed_at=now, next_cursor=None,
            items=[{**module.model_dump(), "availability": "available", "reason_code": None}],
        )),
        read_module_version=AsyncMock(return_value=module),
        create_module_operation=AsyncMock(return_value=ModuleOperationV1(**remote_projection, status="queued")),
        read_module_operation=AsyncMock(return_value=ModuleOperationDetailV1(
            **remote_projection, status="succeeded", completed_at=now, expected_step_count=3,
            steps=[{"sequence": index, "status": "succeeded", "capability": capability,
                    "safe_result": {"schema_version": schema, "status": "succeeded", "collected_at": now, **values}}
                   for index, (capability, schema, values) in enumerate(zip(capabilities, schemas, facts))],
        )),
    )
    endpoint = SimpleNamespace(read_device=AsyncMock(return_value=EndpointDeviceProjection(
        device=EndpointDeviceRef(external_id=endpoint_id), display_name="Fixture", retired=False, last_seen_at=now,
    )))
    monkeypatch.setattr(DomainPortContainer, "from_config", lambda: SimpleNamespace(endpoint=endpoint, endpoint_modules=modules))

    token = "hdo_" + "p" * 43
    token_file = tmp_path / "operator.token"
    token_file.write_text(token, encoding="ascii")
    grant_file = tmp_path / "grant.json"
    grant_file.write_text(json.dumps([{
        "operator": "support-test", "sha256": hashlib.sha256(token.encode()).hexdigest(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
        "scopes": ["tickets.read", "diagnostics.read", "diagnostics.run"],
    }]), encoding="utf-8")
    monkeypatch.setenv("HELPDESK_OPERATOR_GRANTS_FILE", str(grant_file))
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_helpdesk_operator.server"], cwd=Path(__file__).resolve().parents[2],
        env={"HELPDESK_OPERATOR_BASE_URL": str(test_client_light.make_url("/")),
             "HELPDESK_OPERATOR_TOKEN_FILE": str(token_file)},
    )
    async with stdio_client(parameters) as (read, write), ClientSession(read, write) as client:
        await client.initialize()

        async def call(name, **arguments):
            result = await client.call_tool(name, {"ticket": ticket_id, **arguments})
            assert not result.isError, result.structuredContent
            return result.structuredContent["data"]

        selected = await call("ticket_device_select", device_id=device_id)
        assert selected["diagnostic_device_ref"] == endpoint_id
        catalog = await call("ticket_tools")
        assert catalog["items"][0]["capabilities"] == list(capabilities)
        intent = {"operation_id": str(uuid4()), "device_ref": endpoint_id, "module_key": module.module_key,
                  "version": module.version, "inputs": {"printer_name": "office"}}
        started = await call("ticket_tool_run", **intent)
        assert started["status"] == "create_pending"
        assert (await call("ticket_tool_run", **intent))["run_id"] == started["run_id"]
        worker = EndpointToolReconciler(endpoint_port=endpoint, modules_port=modules, session_factory=sessions)
        dispatch_at = now + timedelta(seconds=30)
        assert await worker.run_once(limit=1, now=dispatch_at) == 1
        assert await worker.run_once(limit=1, now=dispatch_at + timedelta(seconds=3)) == 1
        result = await call("ticket_tool_result", run_id=started["run_id"])
        assert result["status"] == "succeeded"
        assert [step["safe_result"]["schema_version"] for step in result["safe_result"]["steps"]] == list(schemas)
        assert result["safe_result"]["steps"][2]["safe_result"]["queued_count"] == 2
    modules.create_module_operation.assert_awaited_once()
    modules.read_module_operation.assert_awaited_once()
