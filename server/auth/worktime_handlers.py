"""Browser-cookie authorization and confidential WorkTime protocol endpoints."""
import html
import secrets
from urllib.parse import urlencode

from aiohttp import web
import config
from app.db import get_session
from auth.identity_handlers import read_bounded, response
from auth.middleware import WEB_SESSION_COOKIE_NAME
from auth.rate_limit import check_rate_limit, client_ip
from auth.worktime_handoff import HandoffError, WorktimeHandoffService, configured_callback, digest, require_opaque


def failure(error):return response({'error':error.code},error.status)


async def handle_worktime_authorize(request):
    try:
        expected=configured_callback()
        if set(request.query)!={'state','code_challenge','code_challenge_method','redirect_uri'} or any(len(request.query.getall(key))!=1 for key in request.query):
            raise HandoffError('invalid_authorization_request',400)
        state=require_opaque(request.query['state']);challenge=require_opaque(request.query['code_challenge'])
        if request.query['code_challenge_method']!='S256' or request.query['redirect_uri']!=expected:
            raise HandoffError('invalid_authorization_request',400)
        if not check_rate_limit('worktime_authorize',client_ip(request),limit=30,window_seconds=60):raise HandoffError('rate_limited',429)
        raw=request.cookies.get(WEB_SESSION_COOKIE_NAME,'')
        if not raw or len(raw)>1024 or not raw.isascii():
            return web.HTTPFound('/app/worktime/connect?'+urlencode(list(request.query.items())),headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        async with get_session() as session:
            code=await WorktimeHandoffService(session).authorize(digest(raw),challenge,expected)
            await session.commit()
        nonce=secrets.token_urlsafe(24)
        page=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Переход в WorkTime</title>
<h1>Открываем рабочее время</h1><p>Повторный ввод пароля не требуется.</p>
<form method="post" action="{html.escape(expected,quote=True)}"><input type="hidden" name="code" value="{html.escape(code,quote=True)}"><input type="hidden" name="state" value="{html.escape(state,quote=True)}"><button type="submit">Продолжить в WorkTime</button></form>
<script nonce="{nonce}">document.forms[0].submit()</script></html>'''
        return web.Response(text=page,content_type='text/html',headers={'Cache-Control':'no-store','Pragma':'no-cache','Referrer-Policy':'origin','X-Frame-Options':'DENY',
            'Content-Security-Policy':f"default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action {expected}; script-src 'nonce-{nonce}'"})
    except HandoffError as error:
        if error.status==401:
            continuation='/app/worktime/connect?'+urlencode(list(request.query.items()))
            return web.HTTPFound('/app/login?'+urlencode({'next':continuation}),headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        if error.code=='profile_incomplete':
            return web.Response(text='<!doctype html><html lang="ru"><meta charset="utf-8"><title>Заполните профиль</title><h1>Сначала заполните профиль Helpdesk</h1><p>После сохранения профиля откройте «Рабочее время» в кабинете.</p><a href="/app/requester/profile/setup">Заполнить профиль</a></html>',content_type='text/html',status=403,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
        return failure(error)
    except Exception:return failure(HandoffError('source_unavailable',503))


async def handle_worktime_integration(request):
    expected=config.IDENTITY_RESOLVE_SERVICE_TOKEN;supplied=request.headers.get('Authorization','')
    if not expected or len(expected)<32 or len(supplied)>1024 or not secrets.compare_digest(supplied.encode(),('Bearer '+expected).encode()):
        return response({'error':'service_authority_required'},401)
    if not check_rate_limit('worktime_identity_service',client_ip(request),limit=config.IDENTITY_RESOLVE_RATE_LIMIT_PER_MINUTE,window_seconds=60):return response({'error':'rate_limited'},429)
    action=request.match_info['action']
    required={'exchange':{'code','code_verifier','redirect_uri'},'introspect':{'handle'},'resolve':{'person_id'}}.get(action)
    try:
        configured_callback();data=await read_bounded(request)
        if required is None or set(data)!=required or any(not isinstance(value,str) for value in data.values()):raise HandoffError('invalid_protocol_request',400)
        async with get_session() as session:
            service=WorktimeHandoffService(session)
            if action=='exchange':result=await service.exchange(data['code'],data['code_verifier'],data['redirect_uri'])
            elif action=='introspect':result=await service.introspect(data['handle'])
            else:result=await service.resolve_person(data['person_id'])
            await session.commit()
        return response(result)
    except HandoffError as error:return failure(error)
    except (ValueError,TypeError):return failure(HandoffError('invalid_protocol_request',400))
    except Exception:return failure(HandoffError('source_unavailable',503))
