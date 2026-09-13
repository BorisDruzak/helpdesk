"""
HTTP обработчики для аутентификации.
"""

from aiohttp import web
from loguru import logger
from auth.context import AuthType
from auth.rate_limit import check_rate_limit, client_ip, rate_limited_response
from app.repos.ui_users_repo import VALID_ROLES
import config
from .service import AuthService


async def handle_ui_login(request):
    """
    HTTP API для UI логина: POST /api/ui_login
    
    Простая аутентификация для UI пользователей.
    Проверяет логин/пароль и возвращает UI токен.
    
    Параметры:
    - login: Логин пользователя
    - password: Пароль пользователя
    """
    try:
        data = await request.json()
        login = data.get("login")
        password = data.get("password")
        expected_role = str(data.get("expected_role") or "").strip().lower()
        if not config.LEGACY_UI_TOKEN_LOGIN_ENABLED:
            return web.json_response(
                {
                    "status": "error",
                    "error": "Legacy token login is disabled; use /api/web/session/login",
                    "error_code": "LEGACY_AUTH_DISABLED",
                },
                status=410,
            )
        if not check_rate_limit("ui_login", f"{client_ip(request)}:{login or ''}", limit=10, window_seconds=60):
            return rate_limited_response()
        
        if not login or not password:
            return web.json_response({
                "status": "error",
                "error": "Missing login or password"
            }, status=400)
        
        # Получаем state и создаём service
        state = request.app['state']
        auth_service = AuthService(state)
        
        # Stage 10: authenticate возвращает (success, actor_role); при DB-режиме роль из ui_users
        ok, actor_role = await auth_service.authenticate(login, password)
        if not ok:
            logger.warning(f"⚠️  Failed login attempt: login={login}")
            return web.json_response({
                "status": "error",
                "error": "Invalid login or password"
            }, status=401)
        if actor_role not in VALID_ROLES:
            return web.json_response(
                {"status": "error", "error": "Invalid account role", "error_code": "ROLE_INVALID"},
                status=403,
            )
        if expected_role and expected_role in VALID_ROLES and actor_role != expected_role:
            logger.warning(
                f"⚠️  UI login rejected due to role mismatch: login={login}, "
                f"actual_role={actor_role}, expected_role={expected_role}"
            )
            return web.json_response(
                {
                    "status": "error",
                    "error": f"Account role mismatch: expected {expected_role}, got {actor_role}",
                    "actor_role": actor_role,
                },
                status=403,
            )
        
        # Генерируем UI токен (срок действия 24 часа)
        try:
            token = await auth_service.generate_ui_token(
                user_login=login,
                actor_role=actor_role,
                expires_hours=24
            )
        except Exception as e:
            logger.error(f"❌ Ошибка при генерации UI токена: {e}")
            return web.json_response({
                "status": "error",
                "error": "Failed to generate token"
            }, status=500)
        
        logger.info(f"✅ UI токен сгенерирован для user_login={login}, role={actor_role}")
        
        return web.json_response({
            "status": "success",
            "token": token,
            "user_login": login,
            "actor_role": actor_role
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка при UI логине: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_ui_session(request):
    """GET /api/ui_session - returns current UI session actor and role."""
    auth_context = request.get("auth_context")
    if not auth_context or auth_context.auth_type != AuthType.UI_TOKEN:
        return web.json_response(
            {
                "status": "error",
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
            },
            status=401,
        )

    return web.json_response(
        {
            "status": "success",
            "user_login": auth_context.actor_id,
            "actor_role": auth_context.actor_role,
            "auth_type": auth_context.auth_type.value,
        }
    )
