from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlencode

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest
import httpx

import config
from auth import worktime_handlers as handlers
from auth.rate_limit import reset_rate_limits
from auth.worktime_handoff import HandoffError

pytestmark=pytest.mark.no_db
CALLBACK='https://endpoint-staging.sosnadmin.local/auth/worktime/helpdesk/callback'


def install(monkeypatch):
    reset_rate_limits()
    for key,value in {'WORKTIME_HANDOFF_ENABLED':True,'SERVER_PUBLIC_BASE_URL':'https://helpdesk-staging.sosnadmin.local',
        'WORKTIME_PORTAL_URL':'https://endpoint-staging.sosnadmin.local/employee','WEB_SESSION_COOKIE_SECURE':True,'WEB_CSRF_SAME_ORIGIN_ENABLED':True,
        'IDENTITY_RESOLVE_SERVICE_TOKEN':'s'*48}.items():monkeypatch.setattr(config,key,value)
    @asynccontextmanager
    async def sessions():yield SimpleNamespace(commit=AsyncMock())
    monkeypatch.setattr(handlers,'get_session',sessions)
    service=SimpleNamespace(authorize=AsyncMock(return_value='c'*43),exchange=AsyncMock(return_value={'version':1}),introspect=AsyncMock(return_value={'version':1}),resolve_person=AsyncMock(return_value={'version':1}))
    monkeypatch.setattr(handlers,'WorktimeHandoffService',lambda session:service)
    app=web.Application();app.router.add_get('/authorize',handlers.handle_worktime_authorize)
    app.router.add_post('/{action:exchange|introspect|resolve}',handlers.handle_worktime_integration)
    query=urlencode({'state':'a'*43,'code_challenge':'b'*43,'code_challenge_method':'S256','redirect_uri':CALLBACK})
    return app,service,query


@pytest.mark.asyncio
async def test_cookie_only_authority_form_post_never_puts_code_in_location(monkeypatch):
    app,service,query=install(monkeypatch)
    async with TestClient(TestServer(app)) as client:
        denied=await client.get('/authorize?'+query,headers={'Authorization':'Bearer '+'s'*48},allow_redirects=False)
        assert denied.status==302 and denied.headers['Location'].startswith('/app/worktime/connect?')
        service.authorize.assert_not_called()
        client.session.cookie_jar.update_cookies({handlers.WEB_SESSION_COOKIE_NAME:'test-cookie'})
        accepted=await client.get('/authorize?'+query,allow_redirects=False)
        assert accepted.status==200 and 'Location' not in accepted.headers
        page=await accepted.text();assert 'method="post"' in page and 'c'*43 in page and CALLBACK in page
        assert accepted.headers['Cache-Control']=='no-store' and "frame-ancestors 'none'" in accepted.headers['Content-Security-Policy']
        assert accepted.headers['Referrer-Policy']=='origin'  # Keep strict callback Origin; send no path/query.
        assert (await client.get('/authorize?'+query+'&person_id=other',allow_redirects=False)).status==400


@pytest.mark.asyncio
async def test_expired_cookie_returns_to_login_continuation(monkeypatch):
    app,service,query=install(monkeypatch);service.authorize.side_effect=HandoffError()
    async with TestClient(TestServer(app)) as client:
        client.session.cookie_jar.update_cookies({handlers.WEB_SESSION_COOKIE_NAME:'expired-cookie'})
        result=await client.get('/authorize?'+query,allow_redirects=False)
        assert result.status==302
        assert result.headers['Location'].startswith('/app/login?next=')


@pytest.mark.asyncio
async def test_service_authority_closed_payloads_and_unavailable_errors(monkeypatch):
    app,service,_=install(monkeypatch)
    async with TestClient(TestServer(app)) as client:
        body={'code':'c'*43,'code_verifier':'v'*43,'redirect_uri':CALLBACK}
        assert (await client.post('/exchange',json=body)).status==401
        auth={'Authorization':'Bearer '+'s'*48}
        assert (await client.post('/exchange',headers=auth,json={**body,'person_id':'other'})).status==400
        assert (await client.post('/exchange',headers=auth,json=body)).status==200
        service.introspect.side_effect=HandoffError('source_unavailable',503)
        result=await client.post('/introspect',headers=auth,json={'handle':'h'*43})
        assert result.status==503 and await result.json()=={'error':'source_unavailable'}


@pytest.mark.asyncio
@pytest.mark.parametrize('outage',[httpx.ConnectError('fixture outage'),ValueError('invalid metadata'),KeyError('missing endpoint')])
async def test_opt_in_oidc_provider_outage_is_distinct_from_legacy_invalid_session(monkeypatch,outage):
    from auth import oidc
    from datetime import datetime,timezone,timedelta
    now=datetime.now(timezone.utc)
    record=SimpleNamespace(max_expires_at=now+timedelta(hours=1),binding_id='binding')
    binding=SimpleNamespace(user_login='fixture',issuer=config.OIDC_ISSUER)
    session=SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda:record)),get=AsyncMock(return_value=binding))
    monkeypatch.setattr(oidc.IdentityService,'_active',AsyncMock())
    monkeypatch.setattr(oidc,'metadata',AsyncMock(side_effect=outage))
    token=SimpleNamespace(token_hash='a'*64);user=SimpleNamespace(user_login='fixture')
    assert await oidc.validate_oidc_session(session,token,user) is False
    with pytest.raises(oidc.OidcAuthorityUnavailable):await oidc.validate_oidc_session(session,token,user,raise_unavailable=True)
