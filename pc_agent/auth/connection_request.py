import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
from aiohttp import ClientSession
from loguru import logger


async def _publish_event(event_bus: Any, event_type: str, data: dict[str, Any]) -> None:
    if not event_bus:
        return
    await event_bus.publish(
        {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


async def run_connection_request_flow(
    api_url: str,
    device_id: str,
    hostname: Optional[str],
    db_manager: Any,
    identity_manager: Any,
    event_bus: Any,
    wait_seconds: int,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[bool, bool]:
    """
    Запрос авторизации у сервера (connection request flow).

    Returns:
        (True, False) — токен получен и сохранён, можно подключаться по WS.
        (False, True) — явно отклонено администратором (нужно записать флаг).
        (False, False) — ошибка или таймаут ожидания (флаг не ставить).
    """
    api_url = (api_url or "").rstrip("/")
    if not api_url:
        logger.error("request_connection_flow: server.api_url не задан")
        return (False, False)
    if not device_id:
        logger.error("request_connection_flow: device_id отсутствует")
        return (False, False)
    if metadata is None:
        metadata = {}

    async with ClientSession() as session:
        try:
            resp = await session.post(
                f"{api_url}/connection_request",
                json={
                    "device_id": device_id,
                    "hostname": hostname,
                    "metadata": metadata,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )
        except Exception as e:
            logger.error(f"Ошибка запроса подключения: {e}")
            return (False, False)

        if resp.status == 403:
            data = await resp.json() if resp.content_type == "application/json" else {}
            logger.warning(f"Администратор отклонил подключение: {data.get('message', '')}")
            await _publish_event(
                event_bus,
                "connection_rejected",
                {"message": "Администратор отклонил подключение"},
            )
            return (False, True)

        if resp.status != 200:
            logger.error(f"Сервер вернул {resp.status} при запросе подключения")
            return (False, False)

        data = await resp.json()
        status = data.get("status")

        if status == "approved":
            token = data.get("token")
            if not token:
                logger.error("Нет токена в ответе approved")
                return (False, False)
            identity_manager.token = token
            if db_manager:
                try:
                    await db_manager.save_auth_token(token, device_id)
                except Exception as e:
                    logger.warning(f"Не удалось сохранить токен в БД: {e}")
            logger.info("✅ Токен получен по запросу подключения (accept_all)")
            await _publish_event(event_bus, "connection_approved", {})
            return (True, False)

        if status == "pending":
            await _publish_event(
                event_bus,
                "connection_request_pending",
                {"message": "Дождитесь авторизации от Администратора"},
            )
            logger.info("Запрос на подключение в ожидании; ожидаю одобрения/отклонения администратором...")
            # Ожидаем одобрения/отклонения: каждые 5 сек обновляем запрос (POST) и опрашиваем статус (GET)
            # — чтобы в админке запрос отображался только пока агент активен
            poll_interval = 5
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                await asyncio.sleep(poll_interval)
                # Heartbeat: POST обновляет last_request_at на сервере (запрос остаётся в списке админки)
                try:
                    await session.post(
                        f"{api_url}/connection_request",
                        json={
                            "device_id": device_id,
                            "hostname": hostname,
                            "metadata": metadata,
                        },
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
                except Exception as e:
                    logger.debug(f"Ошибка heartbeat connection_request: {e}")
                try:
                    status_resp = await session.get(
                        f"{api_url}/connection_request/status",
                        params={"device_id": device_id},
                        timeout=aiohttp.ClientTimeout(total=10),
                    )
                except Exception as e:
                    logger.warning(f"Ошибка опроса статуса: {e}")
                    continue
                if status_resp.status != 200:
                    continue
                status_data = await status_resp.json()
                st = status_data.get("status")
                if st == "approved":
                    token = status_data.get("token")
                    if token:
                        identity_manager.token = token
                        if db_manager:
                            try:
                                await db_manager.save_auth_token(token, device_id)
                            except Exception as e:
                                logger.warning(f"Не удалось сохранить токен в БД: {e}")
                        logger.info("✅ Токен получен по опросу (одобрено администратором)")
                        await _publish_event(event_bus, "connection_approved", {})
                        return (True, False)
                elif st == "rejected":
                    logger.warning("Администратор отклонил подключение")
                    await _publish_event(
                        event_bus,
                        "connection_rejected",
                        {"message": "Администратор отклонил подключение"},
                    )
                    return (False, True)
            logger.warning("Таймаут ожидания одобрения администратором")
            return (False, False)

    return (False, False)
