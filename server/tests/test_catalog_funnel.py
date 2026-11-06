import json
from types import SimpleNamespace
import pytest

pytestmark=pytest.mark.no_db

class Request(dict):
    path='/api/web/requester/catalog-events'
    content_length=128
    def __init__(self, payload, auth=True):
        super().__init__();self.payload=payload
        if auth:self['auth_context']=SimpleNamespace(actor_id='synthetic',actor_role='user')
    def clone(self, **kwargs): return self
    async def json(self): return self.payload

def payload(**extra):
    return {'flow_id':'a82270f9-1287-4df5-81aa-996ed532942b','sequence':1,'event':'opened','elapsed_ms':0,'rank':0,'result_count':0,**extra}

@pytest.mark.asyncio
async def test_unauthenticated_metrics_are_rejected():
    from web_api.catalog_funnel_handlers import handle_catalog_funnel
    assert (await handle_catalog_funnel(Request(payload(),False))).status==401

@pytest.mark.asyncio
@pytest.mark.parametrize('extra',[{'query':'private text'},{'actor_id':'foreign'},{'elapsed_ms':True},{'event':'forged'},{'rank':51},{'flow_id':'not-a-uuid'}])
async def test_metric_contract_rejects_arbitrary_data(extra):
    from web_api.catalog_funnel_handlers import handle_catalog_funnel
    assert (await handle_catalog_funnel(Request(payload(**extra)))).status==400

@pytest.mark.asyncio
async def test_valid_event_logs_only_allowlisted_data(monkeypatch):
    from web_api import catalog_funnel_handlers as h
    calls=[]
    monkeypatch.setattr(h,'check_rate_limit',lambda *a,**kw:True)
    monkeypatch.setattr(h,'logger',SimpleNamespace(info=lambda *args:calls.append(args)))
    assert (await h.handle_catalog_funnel(Request(payload()))).status==204
    assert json.loads(calls[0][1])==payload()
    assert 'synthetic' not in str(calls)


@pytest.mark.asyncio
@pytest.mark.parametrize('chunked',[False,True])
async def test_real_http_body_limit_rejects_oversize_before_logging(monkeypatch,chunked):
    from aiohttp import web
    from aiohttp.test_utils import TestServer, TestClient
    from web_api import catalog_funnel_handlers as h
    calls=[]
    monkeypatch.setattr(h,'check_rate_limit',lambda *a,**kw:True)
    monkeypatch.setattr(h,'logger',SimpleNamespace(info=lambda *args:calls.append(args)))
    async def route(request):
        request['auth_context']=SimpleNamespace(actor_id='synthetic',actor_role='user')
        return await h.handle_catalog_funnel(request)
    app=web.Application();app.router.add_post('/event',route)
    async def chunks():
        yield b' '*800
        yield b' '*800
    async with TestClient(TestServer(app)) as client:
        response=await client.post('/event',data=chunks() if chunked else b' '*1600,headers={'Content-Type':'application/json'})
        assert response.status==413
    assert not calls

@pytest.mark.asyncio
async def test_rate_limited_events_are_not_logged(monkeypatch):
    from web_api import catalog_funnel_handlers as h
    calls=[]
    monkeypatch.setattr(h,'check_rate_limit',lambda *a,**kw:False)
    monkeypatch.setattr(h,'logger',SimpleNamespace(info=lambda *args:calls.append(args)))
    assert (await h.handle_catalog_funnel(Request(payload()))).status==429
    assert not calls
