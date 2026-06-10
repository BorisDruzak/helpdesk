"""
HTTP authentication middleware for /api/* endpoints.

Protects all /api/* endpoints (except whitelist) with token authentication.
Creates AuthContext from token and attaches it to request.
"""
from aiohttp import web
from collections import deque
from datetime import datetime, timezone
from loguru import logger
from typing import Optional
from urllib.parse import urlsplit
import config
from auth.context import AuthContext, AuthType
from auth.service import AuthService
from app.db import get_session
from app.repos.agent_runtime_audit_repo import AgentRuntimeAuditRepo


WEB_SESSION_COOKIE_NAME = "pc_client_web_session"
WEB_AUTH_AUDIT_DEVICE_ID = "00000000-0000-0000-0000-00000000a11d"
WEB_AUTH_AUDIT_WINDOW_SEC = 60
_WEB_AUTH_AUDIT_LAST_SEEN: dict[tuple[str, str, str, str], datetime] = {}
WEB_SESSION_AUTH_PATH_PREFIXES = (
    "/api/web/",
    "/api/upload",
    "/api/artifacts/",
    "/api/modules/",
    "/api/admin/tech/",
    "/api/admin/settings/observer",
    "/api/ticket_forms/",
    "/api/notifications",
)
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
QUERY_TOKEN_ATTEMPT_MAX = 500
_QUERY_TOKEN_AUTH_ATTEMPTS: deque[dict[str, object]] = deque(maxlen=QUERY_TOKEN_ATTEMPT_MAX)


# Whitelist of endpoints that don't require authentication
AUTH_WHITELIST = {
    "/api/ui_login",  # UI login endpoint
    "/api/web/session/login",
    "/api/web/session/me",
    "/api/health",
    "/api/connection_request",
    "/api/connection_request/status",
}


def _record_query_token_attempt(request: web.Request, *, rejected: bool) -> None:
    _QUERY_TOKEN_AUTH_ATTEMPTS.append(
        {
            "ts": datetime.now(timezone.utc),
            "path": str(getattr(request, "path", "")),
            "rejected": bool(rejected),
        }
    )


def get_query_token_auth_attempts(window_seconds: int = 3600) -> int:
    cutoff = datetime.now(timezone.utc).timestamp() - max(int(window_seconds or 0), 0)
    return sum(
        1
        for item in list(_QUERY_TOKEN_AUTH_ATTEMPTS)
        if isinstance(item.get("ts"), datetime) and item["ts"].timestamp() >= cutoff
    )


def get_recent_query_token_auth_paths(limit: int = 10) -> list[dict[str, object]]:
    capped = max(1, min(int(limit or 10), 50))
    recent = list(_QUERY_TOKEN_AUTH_ATTEMPTS)[-capped:]
    return [
        {
            "path": str(item.get("path") or ""),
            "ts": item["ts"].isoformat() if isinstance(item.get("ts"), datetime) else None,
            "rejected": bool(item.get("rejected")),
        }
        for item in recent
    ]


def reset_query_token_auth_attempts() -> None:
    _QUERY_TOKEN_AUTH_ATTEMPTS.clear()


def extract_token_from_header(request: web.Request) -> Optional[str]:
    """
    Extract token from Authorization header.
    
    Supports:
    - Bearer <token>
    - Token <token>
    - X-Auth-Token header
    
    Args:
        request: aiohttp request
        
    Returns:
        Token string or None if not found
    """
    # Try Authorization header (Bearer or Token)
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) == 2:
            scheme, token = parts
            if scheme.lower() in ("bearer", "token"):
                return (token or "").strip() or None
    
    # Try X-Auth-Token header (fallback)
    token = request.headers.get("X-Auth-Token")
    if token:
        return token.strip()
    
    # Try query parameter (fallback, with warning)
    token = request.query.get("token")
    if token:
        rejected = not bool(getattr(config, "AUTH_ALLOW_QUERY_TOKEN", False))
        _record_query_token_attempt(request, rejected=rejected)
        if rejected:
            logger.warning(
                f"[AuthMiddleware] Token passed via query parameter was rejected by policy: "
                f"path={request.path}"
            )
            return None
        logger.warning(
            f"[AuthMiddleware] Token passed via query parameter (insecure): "
            f"path={request.path}"
        )
        return token.strip()
    
    return None


def extract_token_from_web_cookie(request: web.Request) -> Optional[str]:
    if not any(request.path.startswith(prefix) for prefix in WEB_SESSION_AUTH_PATH_PREFIXES):
        return None

    token = request.cookies.get(WEB_SESSION_COOKIE_NAME)
    if token:
        return token.strip() or None

    return None


def _origin_value(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _same_origin_error(request: web.Request) -> tuple[str, str] | None:
    if not bool(getattr(config, "WEB_CSRF_SAME_ORIGIN_ENABLED", True)):
        return None
    if request.method.upper() in SAFE_METHODS:
        return None
    if not any(request.path.startswith(prefix) for prefix in WEB_SESSION_AUTH_PATH_PREFIXES):
        return None

    supplied = _origin_value(request.headers.get("Origin")) or _origin_value(request.headers.get("Referer"))
    if supplied is None:
        return "CSRF_ORIGIN_REQUIRED", "Origin or Referer header is required for cookie-auth state changes"

    scheme = "https" if request.secure else "http"
    allowed = {f"{scheme}://{request.host.lower()}"}
    public_base = _origin_value(getattr(config, "SERVER_PUBLIC_BASE_URL", ""))
    if public_base:
        allowed.add(public_base)
    if supplied not in allowed:
        return "CSRF_ORIGIN_MISMATCH", "Origin or Referer does not match this server"
    return None


async def extract_auth_context(request: web.Request) -> Optional[AuthContext]:
    """
    Extract AuthContext from request.
    
    Tries to extract token and verify it, creating AuthContext if valid.
    
    Args:
        request: aiohttp request
        
    Returns:
        AuthContext if authentication successful, None otherwise
    """
    web_session_token = extract_token_from_web_cookie(request)
    request["web_session_auth"] = bool(web_session_token)
    token = web_session_token or extract_token_from_header(request)
    if not token:
        return None
    
    state = request.app.get('state')
    if not state:
        logger.error("[AuthMiddleware] State not found in app")
        return None
    
    auth_service = AuthService(state)
    
    if not web_session_token:
        # Non-web API paths may still use agent tokens.
        token_info = await auth_service.verify_agent_token(token)
        if token_info:
            return AuthContext(
                actor_id=token_info["device_id"],
                actor_role="agent",
                auth_type=AuthType.AGENT_TOKEN,
                token=token
            )

    # Try UI token
    token_info = await auth_service.verify_ui_token(token)
    if token_info:
        return AuthContext(
            actor_id=token_info["user_login"],
            actor_role=token_info["actor_role"],
            auth_type=AuthType.UI_TOKEN,
            token=token
        )

    allow_public_ticket_token = (
        request.path == "/api/tickets"
        or request.path.startswith("/api/tickets/")
        or request.path == "/api/upload"
        or request.path.startswith("/api/artifacts/")
    )
    if allow_public_ticket_token:
        token_info = await auth_service.verify_ticket_public_session_token(token)
        if token_info:
            return AuthContext(
                actor_id=token_info["actor_id"],
                actor_role="user",
                auth_type=AuthType.PUBLIC_TICKET_TOKEN,
                token=token,
                ticket_scope=token_info["ticket_id"],
            )

    # Token not found or invalid
    return None


def _route_pattern(request: web.Request) -> str:
    route = getattr(request, "match_info", None)
    route_obj = getattr(route, "route", None)
    resource = getattr(route_obj, "resource", None)
    canonical = getattr(resource, "canonical", None)
    return str(canonical or request.path)


async def _write_web_auth_audit(
    request: web.Request,
    *,
    event_type: str,
    error_code: str,
    auth_state: str,
    actor_id: str | None = None,
    actor_role: str | None = None,
    severity: str = "warning",
) -> None:
    route = _route_pattern(request)
    key = (event_type, request.method, route, auth_state)
    now = datetime.now(timezone.utc)
    previous = _WEB_AUTH_AUDIT_LAST_SEEN.get(key)
    if previous and (now - previous).total_seconds() < WEB_AUTH_AUDIT_WINDOW_SEC:
        return
    _WEB_AUTH_AUDIT_LAST_SEEN[key] = now
    details = {
        "route": route,
        "path": request.path,
        "method": request.method,
        "error_code": error_code,
        "error_kind": error_code,
        "failure_stage": event_type,
        "auth_state": auth_state,
        "remote": request.remote,
        "user_agent": request.headers.get("User-Agent", "")[:160],
    }
    try:
        async with get_session() as session:
            await AgentRuntimeAuditRepo(session).add(
                device_id=WEB_AUTH_AUDIT_DEVICE_ID,
                event_type=event_type,
                severity=severity,
                source="web_auth",
                actor_id=actor_id,
                actor_role=actor_role,
                details_json=details,
            )
            await session.commit()
    except Exception as exc:
        logger.debug(f"[AuthMiddleware] web auth audit write skipped: {exc}")


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """
    Authentication middleware for /api/* endpoints.
    
    КРИТИЧНО: No graceful degradation without token → always 401 for unprotected endpoints.
    
    Whitelist:
    - /api/login
    - /api/health
    
    All other /api/* endpoints require valid token.
    
    Args:
        request: aiohttp request
        handler: Next handler in chain
        
    Returns:
        Response from handler or 401 if authentication failed
    """
    # Skip authentication for non-API endpoints
    if not request.path.startswith("/api/"):
        return await handler(request)
    
    # Skip authentication for whitelisted endpoints
    if request.path in AUTH_WHITELIST:
        return await handler(request)
    if request.method == "GET" and request.path.startswith("/api/service-catalog"):
        return await handler(request)
    if request.method == "POST" and request.path == "/api/service-catalog/preview":
        return await handler(request)
    if request.method == "POST" and request.path in {
        "/api/knowledge/search",
        "/api/knowledge/suggest",
        "/api/knowledge/feedback",
    }:
        return await handler(request)
    if request.path.startswith("/api/connection_request"):
        return await handler(request)

    web_session_auth = bool(extract_token_from_web_cookie(request))

    # Extract and verify token
    auth_context = await extract_auth_context(request)
    
    if not auth_context:
        # GET к /api/tickets/... часто приходит без токена (prefetch, первая загрузка до cookie) — логируем как DEBUG
        is_get_ticket_resource = (
            request.method == "GET"
            and request.path.startswith("/api/tickets/")
            and "/" in request.path[len("/api/tickets/"):]
        )
        if is_get_ticket_resource:
            logger.debug(
                f"[AuthMiddleware] Authentication failed (no token): path={request.path}, method={request.method}"
            )
        else:
            logger.warning(
                f"[AuthMiddleware] Authentication failed: path={request.path}, "
                f"method={request.method}"
            )
        await _write_web_auth_audit(
            request,
            event_type="web_auth_failed",
            error_code="AUTH_REQUIRED",
            auth_state="missing_or_invalid_token",
        )
        return web.json_response(
            {
                "status": "error",
                "error": "Требуется аутентификация",
                "error_code": "AUTH_REQUIRED"
            },
            status=401
        )
    
    # Attach AuthContext to request for handler access
    request['auth_context'] = auth_context
    request["web_session_auth"] = web_session_auth

    if web_session_auth:
        same_origin_error = _same_origin_error(request)
        if same_origin_error is not None:
            error_code, message = same_origin_error
            logger.warning(
                f"[AuthMiddleware] Cookie-auth same-origin check failed: "
                f"path={request.path}, method={request.method}, error_code={error_code}"
            )
            await _write_web_auth_audit(
                request,
                event_type="web_csrf_failed",
                error_code=error_code,
                auth_state="cookie_authenticated_origin_failed",
                actor_id=auth_context.actor_id,
                actor_role=auth_context.actor_role,
            )
            return web.json_response(
                {
                    "status": "error",
                    "error": message,
                    "error_code": error_code,
                },
                status=403,
            )

    logger.debug(
        f"[AuthMiddleware] Authenticated: path={request.path}, "
        f"actor_id={auth_context.actor_id}, actor_role={auth_context.actor_role}"
    )
    
    return await handler(request)


def require_auth(*allowed_roles: str):
    """
    Decorator to require specific roles for handler.
    
    Usage:
        @require_auth("admin", "support")
        async def handle_something(request):
            auth_context = request['auth_context']
            ...
    
    Args:
        *allowed_roles: Allowed actor roles
        
    Returns:
        Decorated handler function
    """
    def decorator(handler):
        async def wrapper(request: web.Request):
            auth_context: AuthContext = request.get('auth_context')
            
            if not auth_context:
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Authentication required",
                        "error_code": "AUTH_REQUIRED"
                    },
                    status=401
                )
            
            if allowed_roles and auth_context.actor_role not in allowed_roles:
                logger.warning(
                    f"[require_auth] Access denied: path={request.path}, "
                    f"actor_role={auth_context.actor_role}, allowed_roles={allowed_roles}"
                )
                await _write_web_auth_audit(
                    request,
                    event_type="web_auth_forbidden",
                    error_code="FORBIDDEN",
                    auth_state="forbidden_role",
                    actor_id=auth_context.actor_id,
                    actor_role=auth_context.actor_role,
                    severity="warning",
                )
                return web.json_response(
                    {
                        "status": "error",
                        "error": "Insufficient permissions",
                        "error_code": "FORBIDDEN"
                    },
                    status=403
                )
            
            return await handler(request)
        
        return wrapper
    
    return decorator
