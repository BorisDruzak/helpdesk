"""Authenticated, bounded, best-effort UX measurements; never ticket authority."""
import json
from uuid import UUID
from aiohttp import web
from loguru import logger
from auth.middleware import require_auth
from auth.rate_limit import check_rate_limit

EVENTS={'opened','search_ready','result_selected','service_selected','service_changed','catalog_selected','fallback_selected','submitted','abandoned'}
KEYS={'flow_id','sequence','event','elapsed_ms','rank','result_count'}

def validate_metric(data):
    if not isinstance(data,dict) or set(data)!=KEYS: raise ValueError('contract')
    if not isinstance(data['flow_id'],str) or str(UUID(data['flow_id']))!=data['flow_id']: raise ValueError('flow')
    if data['event'] not in EVENTS: raise ValueError('event')
    for key,lower,upper in [('sequence',1,10000),('elapsed_ms',0,86400000),('rank',0,50),('result_count',0,50)]:
        if type(data[key]) is not int or not lower<=data[key]<=upper: raise ValueError('range')
    return data

@require_auth('user','admin')
async def handle_catalog_funnel(request):
    actor=request['auth_context']
    if not check_rate_limit('catalog_funnel',actor.actor_id,limit=120,window_seconds=60):
        return web.Response(status=429)
    try:
        # clone gives this endpoint its own limit, including chunked request bodies.
        data=validate_metric(await request.clone(client_max_size=1024).json())
    except (ValueError,TypeError,KeyError):
        return web.Response(status=400)
    logger.info('[catalog_funnel] {}',json.dumps(data,separators=(',',':')))
    return web.Response(status=204)
