import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
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


def _set_last_error_code(identity_manager: Any, error_code: Optional[str]) -> None:
    if identity_manager is None:
        return
    try:
        setattr(identity_manager, "last_connection_request_error_code", error_code)
    except Exception:
        pass


def _connection_error_path(identity_manager: Any, db_manager: Any = None) -> Optional[Path]:
    identity_file = getattr(identity_manager, "identity_file", None)
    if identity_file:
        return Path(identity_file).parent / "connection_request_error.json"
    db_path = getattr(db_manager, "_db_path", None)
    if db_path:
        return Path(db_path).parent / "connection_request_error.json"
    return None


def _write_connection_error(identity_manager: Any, db_manager: Any, *, error_code: str, message: str) -> None:
    _set_last_error_code(identity_manager, error_code)
    try:
        setattr(identity_manager, "last_connection_request_error_message", message)
    except Exception:
        pass
    path = _connection_error_path(identity_manager, db_manager)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "error_code": error_code,
                    "message": message,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug(f"Не удалось записать connection_request_error.json: {exc}")


def _clear_connection_error(identity_manager: Any, db_manager: Any = None) -> None:
    _set_last_error_code(identity_manager, None)
    try:
        setattr(identity_manager, "last_connection_request_error_message", None)
    except Exception:
        pass
    path = _connection_error_path(identity_manager, db_manager)
    if not path:
        return
    try:
        if path.exists():
            path.unlink()
    except Exception as exc:
        logger.debug(f"Не удалось очистить connection_request_error.json: {exc}")


async def _read_response_json(response: aiohttp.ClientResponse) -> dict[str, Any]:
    if response.content_type != "application/json":
        return {}
    try:
        data = await response.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


async def _handle_blocked_response(
    *,
    response: aiohttp.ClientResponse,
    identity_manager: Any,
    db_manager: Any,
    event_bus: Any,
    fallback_code: str,
    fallback_message: str,
) -> tuple[bool, bool]:
    data = await _read_response_json(response)
    error_code = str(data.get("error_code") or fallback_code)
    message = str(data.get("message") or data.get("error") or fallback_message)
    _write_connection_error(identity_manager, db_manager, error_code=error_code, message=message)
    logger.warning(f"Запрос на подключение заблокирован: code={error_code}, message={message}")
    await _publish_event(
        event_bus,
        "connection_rejected",
        {"message": message, "error_code": error_code},
    )
    return (False, True)


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
        (False, True) — явно отклонено администратором или соединение заблокировано.
        (False, False) — ошибка или таймаут ожидания.
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
    _clear_connection_error(identity_manager, db_manager)

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
            return await _handle_blocked_response(
                response=resp,
                identity_manager=identity_manager,
                db_manager=db_manager,
                event_bus=event_bus,
                fallback_code="CONNECTION_REJECTED",
                fallback_message="Администратор отклонил подключение",
            )

        if resp.status == 409:
            return await _handle_blocked_response(
                response=resp,
                identity_manager=identity_manager,
                db_manager=db_manager,
                event_bus=event_bus,
                fallback_code="CONNECTION_BLOCKED",
                fallback_message="Запрос на подключение заблокирован",
            )

        if resp.status == 429:
            return await _handle_blocked_response(
                response=resp,
                identity_manager=identity_manager,
                db_manager=db_manager,
                event_bus=event_bus,
                fallback_code="TOKEN_LIMIT_EXCEEDED",
                fallback_message=(
                    "На сервере уже есть 2 активных токена для этого устройства. "
                    "Отзовите старый токен в админке или восстановите локальный токен агента."
                ),
            )

        if resp.status != 200:
            logger.error(f"Сервер вернул {resp.status} при запросе подключения")
            return (False, False)

        data = await resp.json()
        status = data.get("status")
        request_id = str(data.get("request_id") or "").strip() or None
        poll_secret = str(data.get("poll_secret") or "").strip() or None

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
            _clear_connection_error(identity_manager, db_manager)
            await _publish_event(event_bus, "connection_approved", {})
            return (True, False)

        if status == "pending":
            if not request_id or not poll_secret:
                _write_connection_error(
                    identity_manager,
                    db_manager,
                    error_code="POLL_SECRET_REQUIRED",
                    message="Server did not return connection request polling credentials",
                )
                return (False, False)
            await _publish_event(
                event_bus,
                "connection_request_pending",
                {"message": "Дождитесь авторизации от Администратора"},
            )
            logger.info("Запрос на подключение в ожидании; ожидаю одобрения/отклонения администратором...")
            poll_interval = 5
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                await asyncio.sleep(poll_interval)
                try:
                    heartbeat_resp = await session.post(
                        f"{api_url}/connection_request",
                        json={
                            "device_id": device_id,
                            "hostname": hostname,
                            "metadata": metadata,
                            "request_id": request_id,
                            "poll_secret": poll_secret,
                        },
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
                    if heartbeat_resp.status == 429:
                        return await _handle_blocked_response(
                            response=heartbeat_resp,
                            identity_manager=identity_manager,
                            db_manager=db_manager,
                            event_bus=event_bus,
                            fallback_code="TOKEN_LIMIT_EXCEEDED",
                            fallback_message=(
                                "На сервере уже есть 2 активных токена для этого устройства. "
                                "Отзовите старый токен в админке или восстановите локальный токен агента."
                            ),
                        )
                except Exception as e:
                    logger.debug(f"Ошибка heartbeat connection_request: {e}")
                try:
                    status_resp = await session.get(
                        f"{api_url}/connection_request/status",
                        params={
                            "device_id": device_id,
                            "request_id": request_id,
                            "poll_secret": poll_secret,
                        },
                        timeout=aiohttp.ClientTimeout(total=10),
                    )
                except Exception as e:
                    logger.warning(f"Ошибка опроса статуса: {e}")
                    continue
                if status_resp.status == 429:
                    return await _handle_blocked_response(
                        response=status_resp,
                        identity_manager=identity_manager,
                        db_manager=db_manager,
                        event_bus=event_bus,
                        fallback_code="TOKEN_LIMIT_EXCEEDED",
                        fallback_message=(
                            "На сервере уже есть 2 активных токена для этого устройства. "
                            "Отзовите старый токен в админке или восстановите локальный токен агента."
                        ),
                    )
                if status_resp.status in (400, 403):
                    status_error = await _read_response_json(status_resp)
                    error_code = str(status_error.get("error_code") or "")
                    if error_code in {"POLL_SECRET_REQUIRED", "INVALID_POLL_SECRET"}:
                        _write_connection_error(
                            identity_manager,
                            db_manager,
                            error_code=error_code,
                            message="Connection request polling credentials were rejected; create a new request",
                        )
                        return (False, False)
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
                        _clear_connection_error(identity_manager, db_manager)
                        await _publish_event(event_bus, "connection_approved", {})
                        return (True, False)
                elif st == "rejected":
                    error_code = status_data.get("error_code") or "CONNECTION_REJECTED"
                    message = status_data.get("message") or "Администратор отклонил подключение"
                    _write_connection_error(identity_manager, db_manager, error_code=error_code, message=message)
                    logger.warning(f"Администратор отклонил подключение: code={error_code}")
                    await _publish_event(
                        event_bus,
                        "connection_rejected",
                        {"message": message, "error_code": error_code},
                    )
                    return (False, True)
            logger.warning("Таймаут ожидания одобрения администратором")
            return (False, False)

    return (False, False)
