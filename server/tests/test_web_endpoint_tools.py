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
    valid = dict(schema_version="endpoint_tool_run_create_v1", module_key="helpdesk.dns", version="1.0.0", inputs={"target": "example.test"}, caller_key="key")
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
    body={"schema_version":"endpoint_tool_batch_create_v1","caller_key":"batch-replay"}
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
