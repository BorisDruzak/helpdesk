"""Path-only HTTP diagnostics: callback query/header authority is never logged."""
import json
import logging

from aiohttp import web
from aiohttp.abc import AbstractAccessLogger

_callback_logger = logging.getLogger('helpdesk.oidc_callback')
_CALLBACK = '/api/web/session/oidc/callback'


class QuerySafeAccessLogger(AbstractAccessLogger):
    @property
    def enabled(self):
        return self.logger.isEnabledFor(logging.INFO)

    def log(self, request, response, time):
        # Deliberately enumerate safe fields. Never use request_line, rel_url,
        # query_string, headers, exceptions, or the caller's format string.
        self.logger.info(json.dumps({
            'method':request.method,'path':request.path,'status':response.status,
            'body_bytes_sent':response.body_length,'request_time':round(time,6),
        },ensure_ascii=True,separators=(',',':')))


@web.middleware
async def safe_oidc_callback_errors(request, handler):
    if request.path != _CALLBACK:
        return await handler(request)
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as error:
        # aiohttp's generic error logger includes exception messages/tracebacks.
        # Keep a bounded type and outcome for this credential-bearing endpoint;
        # normal auth/observer audit paths and other error diagnostics remain.
        _callback_logger.warning('OIDC callback failed: method=%s path=%s status=503 error_type=%s',
            request.method,_CALLBACK,type(error).__name__)
        return web.json_response({'error':'oidc_authentication_failed'},status=503,
            headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
