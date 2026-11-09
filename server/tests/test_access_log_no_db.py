"""Exercise the actual HTTP logger without retaining callback credentials."""
import inspect
import json
import logging
from pathlib import Path
import re

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize('status',[200,302,400,503])
async def test_callback_access_and_failure_logs_keep_path_status_without_secrets(caplog,status):
    from observability.access_log import QuerySafeAccessLogger, safe_oidc_callback_errors
    from auth.middleware import request_id_middleware
    access = logging.getLogger('test.helpdesk.safe_access')
    caplog.set_level(logging.INFO)
    app = web.Application(middlewares=[request_id_middleware,safe_oidc_callback_errors])
    async def callback(request):
        if status == 503:
            raise RuntimeError('exception-code-secret exception-state-secret')
        if status == 302:
            raise web.HTTPFound('/app')
        return web.json_response({'result':'test'},status=status)
    app.router.add_get('/api/web/session/oidc/callback',callback)
    server = TestServer(app)
    await server.start_server(access_log=access,access_log_class=QuerySafeAccessLogger)
    async with TestClient(server) as client:
        result = await client.get('/api/web/session/oidc/callback?code=query-code-secret&state=query-state-secret',
            headers={'Referer':'https://sso.example.test/?secret=referer-secret','Authorization':'Bearer header-secret'},
            allow_redirects=False)
        assert result.status == status
        assert result.headers.get('X-Server-Request-ID')
        await result.read()
    records=[json.loads(record.getMessage()) for record in caplog.records if record.name==access.name]
    assert len(records)==1
    assert records[0]['path']=='/api/web/session/oidc/callback'
    assert records[0]['status']==status and records[0]['method']=='GET'
    assert records[0]['body_bytes_sent']>=0 and records[0]['request_time']>=0
    text=caplog.text
    for secret in ('query-code-secret','query-state-secret','referer-secret','header-secret',
                   'exception-code-secret','exception-state-secret','?code=','Referer'):
        assert secret not in text
    if status==503:
        assert 'RuntimeError' in text and 'status=503' in text


def test_server_startup_wires_safe_access_logger_and_callback_error_boundary():
    import server
    assert 'access_log_class=QuerySafeAccessLogger' in inspect.getsource(server.main)
    assert 'safe_oidc_callback_errors' in inspect.getsource(server.create_app)
    source=inspect.getsource(server.create_app)
    assert source.index('append(request_id_middleware)') < source.index('append(safe_oidc_callback_errors)')


async def test_ordinary_error_diagnostics_are_not_suppressed():
    from aiohttp.test_utils import make_mocked_request
    from observability.access_log import safe_oidc_callback_errors
    async def ordinary_failure(request):
        raise RuntimeError('ordinary diagnostic retained')
    with pytest.raises(RuntimeError,match='ordinary diagnostic retained'):
        await safe_oidc_callback_errors(make_mocked_request('GET','/api/other'),ordinary_failure)


def test_helpdesk_nginx_callback_suppression_keeps_path_only_access_on_both_ports():
    config=(Path(__file__).resolve().parents[2]/'deploy/helpdesk/helpdesk.nginx.conf').read_text(encoding='utf-8')
    format_body=re.search(r'log_format helpdesk_path_only escape=json\s+(.*?);',config,re.S).group(1)
    assert set(re.findall(r'\$\w+',format_body)) == {
        '$time_iso8601','$remote_addr','$request_method','$uri','$status','$body_bytes_sent','$request_time'}
    assert config.count('access_log /var/log/nginx/helpdesk.access.log helpdesk_path_only;')==2
    callback=re.search(r'location = /api/web/session/oidc/callback\s*\{(.*?)\}',config,re.S).group(1)
    assert 'error_log /dev/null crit;' in callback
    assert 'proxy_pass http://127.0.0.1:8666;' in callback
    assert 'proxy_set_header X-Forwarded-For $remote_addr;' in callback
    assert config.count('error_log /dev/null crit;')==1
    assert 'return 308 https://helpdesk.sosnadmin.local$request_uri;' in config
