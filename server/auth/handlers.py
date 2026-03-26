"""
HTTP обработчики для аутентификации.
"""

from datetime import datetime, timezone
from aiohttp import web
from loguru import logger
from .service import AuthService, ArchivedDeviceError
from .connection_request_service import ConnectionRequestService
from tech.runtime_audit import write_agent_runtime_audit


async def handle_login(request):
    """
    HTTP API для генерации токена агента: POST /api/login
    
    Генерирует токен для агента по device_id (UUID).
    Авторизация теперь только по токену, без логина/пароля.
    
    Параметры:
    - uuid (device_id): UUID устройства (обязательно)
    """
    try:
        data = await request.json()
        uuid_str = data.get("uuid")
        
        if not uuid_str:
            return web.json_response({
                "status": "error",
                "error": "Missing uuid (device_id)"
            }, status=400)
        
        # Валидация UUID
        try:
            import uuid as uuid_lib
            uuid_lib.UUID(uuid_str)
        except ValueError:
            return web.json_response({
                "status": "error",
                "error": "Invalid UUID format"
            }, status=400)
        
        # Получаем state и создаём service
        state = request.app['state']
        auth_service = AuthService(state)
        
        # Генерируем токен (без проверки пароля)
        try:
            token = await auth_service.generate_agent_token(
                device_id=uuid_str,
                expires_hours=4320  # 180 дней (180 * 24 = 4320 часов)
            )
        except ArchivedDeviceError:
            return web.json_response({
                "status": "error",
                "error": "Агент архивирован. Сначала восстановите его или используйте новое устройство."
            }, status=409)
        except ValueError as e:
            # Active token limit exceeded
            logger.warning(f"⚠️  Token limit exceeded for device_id={uuid_str}: {e}")
            return web.json_response({
                "status": "error",
                "error": "Token limit exceeded. Please revoke old tokens first."
            }, status=429)
        
        logger.info(f"✅ Токен сгенерирован для device_id={uuid_str[:8]}...")
        
        # Если для устройства был pending запрос на подключение, считаем его закрытым.
        connection_request_service = ConnectionRequestService()
        await connection_request_service.clear_pending_after_manual_token_issue(device_id=uuid_str)
        
        return web.json_response({
            "status": "success",
            "token": token,
            "device_id": uuid_str
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка при генерации токена: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


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
        valid_roles = ("admin", "support", "auditor", "user")
        if actor_role not in valid_roles:
            actor_role = "admin"
        
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


async def handle_get_device_tokens(request):
    """
    HTTP API для получения списка токенов устройства: GET /api/devices/{device_id}/tokens
    
    Возвращает все токены устройства (включая аннулированные).
    """
    try:
        device_id = request.match_info.get('device_id')
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        # Получаем state и создаём service
        state = request.app['state']
        auth_service = AuthService(state)
        
        # Получаем токены из БД
        from app.db import get_session
        from app.repos.auth_tokens_repo import AuthTokensRepo
        
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            tokens = await repo.get_agent_tokens_by_device(device_id)
            
            tokens_list = []
            for token in tokens:
                tokens_list.append({
                    "token_hash": token.token_hash,
                    "token_prefix": token.token_prefix,
                    "device_id": token.device_id,
                    "created_at": token.created_at.isoformat() if token.created_at else None,
                    "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    "revoked_at": token.revoked_at.isoformat() if token.revoked_at else None,
                    "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
                    "is_active": token.revoked_at is None and (
                        token.expires_at is None or token.expires_at > datetime.now(timezone.utc)
                    )
                })
        
        return web.json_response({
            "status": "success",
            "device_id": device_id,
            "tokens": tokens_list
        })
    
    except Exception as e:
        logger.error(f"❌ Ошибка при получении токенов устройства: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)


async def handle_revoke_device_token(request):
    """
    HTTP API для аннулирования токена устройства: POST /api/devices/{device_id}/tokens/revoke
    
    Аннулирует токен по его hash.
    
    Параметры:
    - token_hash: SHA256 hash токена (обязательно)
    """
    try:
        device_id = request.match_info.get('device_id')
        data = await request.json()
        token_hash = data.get("token_hash")
        
        if not device_id:
            return web.json_response({
                "status": "error",
                "error": "Missing device_id"
            }, status=400)
        
        if not token_hash:
            return web.json_response({
                "status": "error",
                "error": "Missing token_hash"
            }, status=400)
        
        # Получаем state и создаём service
        state = request.app['state']
        auth_service = AuthService(state)
        
        # Аннулируем токен через репозиторий
        from app.db import get_session
        from app.repos.auth_tokens_repo import AuthTokensRepo
        
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            success = await repo.revoke_agent_token_by_hash(token_hash)
            
            if success:
                logger.info(f"✅ Токен аннулирован для device_id={device_id[:8]}..., hash={token_hash[:16]}...")
                await write_agent_runtime_audit(
                    device_id=device_id,
                    event_type="token_revoked",
                    severity="warning",
                    source="auth_handlers",
                    details_json={"token_hash_prefix": token_hash[:12]},
                )
                return web.json_response({
                    "status": "success",
                    "message": "Token revoked successfully"
                })
            else:
                return web.json_response({
                    "status": "error",
                    "error": "Token not found or already revoked"
                }, status=404)
    
    except Exception as e:
        logger.error(f"❌ Ошибка при аннулировании токена: {e}")
        logger.exception(e)
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)
