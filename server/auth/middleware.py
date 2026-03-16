"""
HTTP authentication middleware for /api/* endpoints.

Protects all /api/* endpoints (except whitelist) with token authentication.
Creates AuthContext from token and attaches it to request.
"""
from aiohttp import web
from loguru import logger
from typing import Optional
from auth.context import AuthContext, AuthType
from auth.service import AuthService


# Whitelist of endpoints that don't require authentication
AUTH_WHITELIST = {
    "/api/login",
    "/api/ui_login",  # UI login endpoint
    "/api/health",
}


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
        logger.warning(
            f"[AuthMiddleware] Token passed via query parameter (insecure): "
            f"path={request.path}"
        )
        return token.strip()
    
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
    token = extract_token_from_header(request)
    if not token:
        return None
    
    state = request.app.get('state')
    if not state:
        logger.error("[AuthMiddleware] State not found in app")
        return None
    
    auth_service = AuthService(state)
    
    # Try agent token first
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

    # Скачивание артефакта по ссылке тикета: GET .../download?ticket_id=... — без токена (проверка в handler)
    if (
        request.method == "GET"
        and request.path.startswith("/api/artifacts/")
        and request.path.endswith("/download")
        and request.query.get("ticket_id")
    ):
        return await handler(request)
    
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
