"""Authenticated, bounded, best-effort UX measurements; never ticket authority."""
import json
from aiohttp import web
from loguru import logger
from auth.middleware import require_auth
from auth.rate_limit import check_rate_limit

from web_api.catalog_funnel_contract import validate_metric

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
