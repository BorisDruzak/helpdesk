import os
from typing import Any, Awaitable, Callable, Optional

from loguru import logger


async def load_auth_token(
    db_manager: Any,
    identity_manager: Any,
    gui_wait_callback: Optional[Callable[[], Awaitable[Optional[str]]]] = None,
) -> Optional[str]:
    """
    Загружает токен аутентификации в порядке приоритета:
    1) ENV AUTH_TOKEN
    2) БД агента (auth_tokens)
    3) Опциональный GUI callback ожидания токена
    """
    env_token = os.getenv("AUTH_TOKEN")
    if env_token:
        logger.info("✅ Токен найден в переменной окружения AUTH_TOKEN")
        identity_manager.token = env_token
        if db_manager:
            try:
                await db_manager.save_auth_token(env_token, identity_manager.uuid)
                logger.info("✅ Токен из ENV сохранен в БД агента")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось сохранить токен в БД: {e}")
        return env_token

    try:
        if db_manager:
            token = await db_manager.get_auth_token(identity_manager.uuid)
            if token:
                logger.info("✅ Токен найден в БД агента")
                identity_manager.token = token
                return token
    except Exception as e:
        logger.debug(f"Не удалось проверить токен в БД: {e}")

    if gui_wait_callback is not None:
        token = await gui_wait_callback()
        if token:
            identity_manager.token = token
            return token

    return None
