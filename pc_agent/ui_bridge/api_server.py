"""
HTTP API сервер для UI Bridge.

Предоставляет эндпоинты:
- GET /ui/events - SSE или long-poll для получения событий
- POST /ui/consent_decision - обработка решений о согласии
- POST /ui/chat_send - отправка сообщения в чат тикета (ticket_id, text, from_role, attachment_refs, metadata)
"""

import asyncio
import inspect
import errno
import json
from typing import Callable, Optional, Dict, Any, Union, Awaitable, List, Set
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response, StreamResponse
from loguru import logger

from .event_bus import EventBus
from .models import ConsentDecision


def _is_address_in_use(exc: OSError) -> bool:
    """Linux EADDRINUSE (98) и Windows WSAEADDRINUSE (10048 / winerror)."""
    if getattr(exc, "winerror", None) == 10048:
        return True
    if exc.errno == errno.EADDRINUSE:
        return True
    if exc.errno == 10048:
        return True
    return False


class UiApiServer:
    """
    HTTP API сервер для UI Bridge.
    
    Предоставляет эндпоинты для получения событий и обработки решений о согласии.
    """
    
    def __init__(
        self,
        event_bus: EventBus,
        host: str = "127.0.0.1",
        port: int = 8765,
        on_consent_decision: Optional[Union[Callable[[ConsentDecision], None], Callable[[ConsentDecision], Awaitable[None]]]] = None,
        on_get_settings: Optional[Callable[[], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_update_settings: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_test_connection: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_restart_agent: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_trigger_update: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_shutdown_agent: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_get_runtime_status: Optional[Callable[[], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_get_runtime_logs: Optional[Callable[[Dict[str, Any]], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]] = None,
        on_chat_send: Optional[
            Callable[..., Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]
        ] = None,
    ):
        """
        Инициализация UiApiServer.
        
        Args:
            event_bus: Экземпляр EventBus для получения событий
            host: Хост для прослушивания (по умолчанию 127.0.0.1)
            port: Порт для прослушивания (по умолчанию 8765)
            on_consent_decision: Callback для обработки решений о согласии (async функция)
        """
        self.event_bus = event_bus
        self.host = host
        self.port = port
        self.on_consent_decision = on_consent_decision
        self.on_request_support = None  # async callable(payload: dict) -> dict
        self.on_get_settings = on_get_settings
        self.on_update_settings = on_update_settings
        self.on_test_connection = on_test_connection
        self.on_restart_agent = on_restart_agent
        self.on_trigger_update = on_trigger_update
        self.on_shutdown_agent = on_shutdown_agent
        self.on_get_runtime_status = on_get_runtime_status
        self.on_get_runtime_logs = on_get_runtime_logs
        self.on_chat_send = on_chat_send
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        self._active_sse_tasks: Set[asyncio.Task] = set()
        self._active_sse_transports: Set[Any] = set()
        self._shutdown_timeout = 0.75
        self._stopping = False
        self._listening = False

        # Регистрируем маршруты
        self._setup_routes()
        
        logger.info(f"UiApiServer инициализирован: {host}:{port}")
    
    def _setup_routes(self):
        """Настройка маршрутов API."""
        self.app.router.add_get("/ui/events", self.handle_events)
        self.app.router.add_post("/ui/consent_decision", self.handle_consent_decision)
        self.app.router.add_post("/ui/chat_send", self.handle_chat_send)
        self.app.router.add_post("/ui/stop_recording", self.handle_stop_recording)
        self.app.router.add_post("/ui/request_support", self.handle_request_support)
        self.app.router.add_get("/ui/settings", self.handle_get_settings)
        self.app.router.add_patch("/ui/settings", self.handle_update_settings)
        # POST — то же тело, что PATCH; часть стеков/прокси отдаёт 501/HTML на PATCH.
        self.app.router.add_post("/ui/settings", self.handle_update_settings)
        self.app.router.add_post("/ui/settings/test_connection", self.handle_test_connection)
        self.app.router.add_post("/ui/agent/restart", self.handle_restart_agent)
        self.app.router.add_post("/ui/agent/update", self.handle_trigger_update)
        self.app.router.add_post("/ui/agent/shutdown", self.handle_shutdown_agent)
        self.app.router.add_get("/ui/agent/status", self.handle_runtime_status)
        self.app.router.add_get("/ui/agent/logs", self.handle_runtime_logs)
        
        # Health check
        self.app.router.add_get("/health", self.handle_health)
    
    async def handle_health(self, request: Request) -> Response:
        """Health check эндпоинт."""
        return web.json_response({
            "status": "ok",
            "service": "ui_bridge",
            "subscribers": self.event_bus.get_subscriber_count()
        })
    
    async def handle_events(self, request: Request) -> StreamResponse:
        """
        Обработчик GET /ui/events.
        
        Поддерживает два режима:
        1. SSE (Server-Sent Events) - если заголовок Accept содержит text/event-stream
        2. Long-poll - ждет одно событие до 30 секунд и возвращает JSON
        
        Args:
            request: HTTP запрос
        
        Returns:
            StreamResponse для SSE или Response для long-poll
        """
        # Проверяем, поддерживает ли клиент SSE
        accept = request.headers.get("Accept", "")
        use_sse = "text/event-stream" in accept
        
        if use_sse:
            return await self._handle_sse(request)
        else:
            return await self._handle_long_poll(request)
    
    async def _handle_sse(self, request: Request) -> StreamResponse:
        """
        Обработчик SSE (Server-Sent Events).
        
        Держит соединение открытым и отправляет события в формате:
        data: <json>\n\n
        """
        if self._stopping:
            raise web.HTTPServiceUnavailable(text="UI bridge is shutting down")

        response = StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        await response.prepare(request)
        transport = request.transport
        handler_task = asyncio.current_task()
        if transport is not None:
            self._active_sse_transports.add(transport)
        if handler_task is not None:
            self._active_sse_tasks.add(handler_task)
        
        # Подписываемся на события
        queue = self.event_bus.subscribe()
        
        try:
            logger.info("SSE соединение установлено")
            
            # Отправляем начальное сообщение
            await response.write(b": connected\n\n")
            for replay_event in self.event_bus.get_replay_events():
                event_json = json.dumps(replay_event, ensure_ascii=False)
                message = f"data: {event_json}\n\n"
                await response.write(message.encode("utf-8"))
            
            while True:
                try:
                    # Ждем событие с таймаутом для проверки соединения
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event and event.get("_shutdown"):
                        break
                    # Форматируем событие для SSE
                    event_json = json.dumps(event, ensure_ascii=False)
                    message = f"data: {event_json}\n\n"
                    
                    await response.write(message.encode("utf-8"))
                    # Не логируем отправку событий, чтобы избежать бесконечного цикла логов
                    
                except asyncio.TimeoutError:
                    # Отправляем keep-alive комментарий
                    await response.write(b": keep-alive\n\n")
                    continue
                    
        except asyncio.CancelledError:
            logger.info("SSE соединение закрыто клиентом")
        except Exception as e:
            err_msg = str(e).lower()
            # При завершении сервера/клиента транспорт закрывается — не логируем как ошибку
            if "closing transport" in err_msg or "connection reset" in err_msg or "connection closed" in err_msg:
                logger.debug(f"SSE соединение закрыто: {e}")
            else:
                logger.error(f"Ошибка в SSE обработчике: {e}")
        finally:
            await self.event_bus.unsubscribe(queue)
            if transport is not None:
                self._active_sse_transports.discard(transport)
            if handler_task is not None:
                self._active_sse_tasks.discard(handler_task)

            transport_is_open = bool(transport) and not transport.is_closing()
            if not self._stopping and transport_is_open:
                try:
                    await response.write_eof()
                except Exception as eof_err:
                    if "closing" not in str(eof_err).lower() and "closed" not in str(eof_err).lower():
                        logger.warning(f"SSE write_eof: {eof_err}")
            logger.info("SSE соединение завершено")
        
        return response
    
    async def _handle_long_poll(self, request: Request) -> Response:
        """
        Обработчик long-poll.
        
        Ждет одно событие до 30 секунд и возвращает JSON.
        Если событие не получено за это время, возвращает пустой ответ.
        """
        timeout = 30.0
        
        # Подписываемся на события
        queue = self.event_bus.subscribe()
        
        try:
            # Ждем событие с таймаутом
            event = await asyncio.wait_for(queue.get(), timeout=timeout)
            if event and event.get("_shutdown"):
                return web.json_response({"status": "shutdown"}, status=503, headers={
                    "Access-Control-Allow-Origin": "*"
                })
            # Возвращаем событие как JSON
            return web.json_response(event, headers={
                "Access-Control-Allow-Origin": "*"
            })
            
        except asyncio.TimeoutError:
            # Таймаут - возвращаем пустой ответ
            return web.json_response({
                "status": "timeout",
                "message": "No events received within timeout"
            }, headers={
                "Access-Control-Allow-Origin": "*"
            })
        except Exception as e:
            logger.error(f"Ошибка в long-poll обработчике: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500, headers={
                "Access-Control-Allow-Origin": "*"
            })
        finally:
            await self.event_bus.unsubscribe(queue)
    
    async def handle_consent_decision(self, request: Request) -> Response:
        """
        Обработчик POST /ui/consent_decision.
        
        Принимает JSON:
        {
            "job_id": "...",
            "consent_token": "...",
            "approved": true,
            "reason": ""
        }
        
        Вызывает callback on_consent_decision если он установлен.
        """
        try:
            # Парсим JSON тело запроса
            data = await request.json()
            
            # Валидируем обязательные поля
            required_fields = ["job_id", "consent_token", "approved"]
            for field in required_fields:
                if field not in data:
                    return web.json_response({
                        "status": "error",
                        "error": f"Missing required field: {field}"
                    }, status=400, headers={
                        "Access-Control-Allow-Origin": "*"
                    })
            
            # Создаем объект ConsentDecision
            decision = ConsentDecision(
                job_id=data["job_id"],
                consent_token=data["consent_token"],
                approved=bool(data["approved"]),
                reason=data.get("reason"),
                session_key=data.get("session_key") or data["job_id"]
            )
            
            logger.info(f"Получено решение о согласии: job_id={decision.job_id}, approved={decision.approved}")
            
            # Вызываем callback если он установлен
            if self.on_consent_decision:
                if inspect.iscoroutinefunction(self.on_consent_decision):
                    await self.on_consent_decision(decision)
                else:
                    self.on_consent_decision(decision)
            else:
                logger.warning("Callback on_consent_decision не установлен, решение не обработано")
            
            # Возвращаем успешный ответ
            return web.json_response({
                "status": "success",
                "message": "Consent decision processed"
            }, headers={
                "Access-Control-Allow-Origin": "*"
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            return web.json_response({
                "status": "error",
                "error": f"Invalid JSON: {str(e)}"
            }, status=400, headers={
                "Access-Control-Allow-Origin": "*"
            })
        except Exception as e:
            logger.error(f"Ошибка обработки consent_decision: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500, headers={
                "Access-Control-Allow-Origin": "*"
            })
    
    async def handle_chat_send(self, request: Request) -> Response:
        """
        Обработчик POST /ui/chat_send.
        
        Принимает JSON:
        {
            "ticket_id": "...",   // обязательно
            "text": "...",        // обязательно
            "from_role": "user",  // опционально, по умолчанию "user"
            "attachment_refs": [], // опционально
            "metadata": {}        // опционально
        }
        Вызывает on_chat_send и возвращает результат отправки на сервер (Ticket API).
        """
        try:
            data = await request.json()
        except json.JSONDecodeError as e:
            return web.json_response({
                "status": "error",
                "error": f"Invalid JSON: {str(e)}"
            }, status=400, headers={"Access-Control-Allow-Origin": "*"})

        ticket_id = data.get("ticket_id")
        text = data.get("text")
        if not ticket_id:
            return web.json_response({
                "status": "error",
                "error": "Missing required field: ticket_id"
            }, status=400, headers={"Access-Control-Allow-Origin": "*"})
        if text is None:
            return web.json_response({
                "status": "error",
                "error": "Missing required field: text"
            }, status=400, headers={"Access-Control-Allow-Origin": "*"})

        from_role = data.get("from_role", "user")
        attachment_refs: Optional[List[str]] = data.get("attachment_refs")
        metadata: Optional[Dict[str, Any]] = data.get("metadata")

        if not self.on_chat_send:
            return web.json_response({
                "status": "error",
                "error": "chat_send not configured"
            }, status=501, headers={"Access-Control-Allow-Origin": "*"})

        try:
            result = await self._invoke_maybe_async(
                self.on_chat_send,
                ticket_id,
                text,
                from_role,
                attachment_refs,
                metadata,
            )
            if result is None:
                result = {}
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            err_msg = str(e)
            if "Тикет не найден" in err_msg or "404" in err_msg:
                return web.json_response({
                    "status": "error",
                    "error": err_msg
                }, status=404, headers={"Access-Control-Allow-Origin": "*"})
            if "Тикет закрыт" in err_msg or "ticket_closed" in err_msg or "409" in err_msg:
                return web.json_response({
                    "status": "error",
                    "error": err_msg
                }, status=409, headers={"Access-Control-Allow-Origin": "*"})
            logger.exception(e)
            return web.json_response({
                "status": "error",
                "error": err_msg
            }, status=500, headers={"Access-Control-Allow-Origin": "*"})
    
    async def handle_stop_recording(self, request: Request) -> Response:
        """
        Обработчик POST /ui/stop_recording (этап 4: STOP-кнопка при записи экрана).
        
        Принимает JSON: {"operation_id": "..."}.
        Вызывает signal_stop(operation_id) в RecordingController.
        """
        try:
            data = await request.json()
            operation_id = data.get("operation_id")
            if not operation_id:
                return web.json_response({
                    "status": "error",
                    "error": "Missing required field: operation_id"
                }, status=400, headers={"Access-Control-Allow-Origin": "*"})
            from core.recording_controller import get_recording_controller
            controller = get_recording_controller()
            if controller.signal_stop(operation_id):
                return web.json_response({
                    "status": "success",
                    "message": "Stop signal sent"
                }, headers={"Access-Control-Allow-Origin": "*"})
            return web.json_response({
                "status": "error",
                "error": "Unknown operation_id or recording already finished"
            }, status=404, headers={"Access-Control-Allow-Origin": "*"})
        except json.JSONDecodeError as e:
            logger.error(f"stop_recording: invalid JSON: {e}")
            return web.json_response({
                "status": "error",
                "error": "Invalid JSON"
            }, status=400, headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            logger.exception(e)
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500, headers={"Access-Control-Allow-Origin": "*"})
    
    async def handle_request_support(self, request: Request) -> Response:
        """
        Обработчик POST /ui/request_support.
        
        Принимает JSON с опциональными полями: title, reason, severity, context.
        Вызывает callback on_request_support если он установлен.
        """
        try:
            data = await request.json()
        except Exception:
            data = {}

        if not self.on_request_support:
            return web.json_response({"status": "error", "error": "request_support not configured"}, status=501)

        try:
            res = await self.on_request_support(data)
            return web.json_response({"status": "ok", "result": res})
        except Exception as e:
            logger.exception(e)
            return web.json_response({"status": "error", "error": str(e)}, status=500)

    async def _invoke_maybe_async(self, func, *args):
        """Вызывает callback, поддерживая sync/async варианты."""
        if func is None:
            return None
        if inspect.iscoroutinefunction(func):
            return await func(*args)
        result = func(*args)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def handle_get_settings(self, request: Request) -> Response:
        """Обработчик GET /ui/settings."""
        if not self.on_get_settings:
            return web.json_response(
                {"status": "error", "error": "settings provider not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            settings = await self._invoke_maybe_async(self.on_get_settings)
            return web.json_response(
                {"status": "ok", "settings": settings},
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_update_settings(self, request: Request) -> Response:
        """Обработчик PATCH и POST /ui/settings."""
        if not self.on_update_settings:
            return web.json_response(
                {"status": "error", "error": "settings updater not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            result = await self._invoke_maybe_async(self.on_update_settings, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_test_connection(self, request: Request) -> Response:
        """Обработчик POST /ui/settings/test_connection."""
        if not self.on_test_connection:
            return web.json_response(
                {"status": "error", "error": "test_connection provider not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            result = await self._invoke_maybe_async(self.on_test_connection, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_restart_agent(self, request: Request) -> Response:
        """Обработчик POST /ui/agent/restart."""
        if not self.on_restart_agent:
            return web.json_response(
                {"status": "error", "error": "restart handler not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            result = await self._invoke_maybe_async(self.on_restart_agent, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_shutdown_agent(self, request: Request) -> Response:
        """Обработчик POST /ui/agent/shutdown."""
        if not self.on_shutdown_agent:
            return web.json_response(
                {"status": "error", "error": "shutdown handler not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        try:
            result = await self._invoke_maybe_async(self.on_shutdown_agent, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_runtime_status(self, request: Request) -> Response:
        """Обработчик GET /ui/agent/status."""
        if not self.on_get_runtime_status:
            return web.json_response(
                {"status": "error", "error": "runtime status provider not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            result = await self._invoke_maybe_async(self.on_get_runtime_status)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_trigger_update(self, request: Request) -> Response:
        """Обработчик POST /ui/agent/update."""
        if not self.on_trigger_update:
            return web.json_response(
                {"status": "error", "error": "update trigger not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        try:
            payload = {}
            if request.can_read_body:
                try:
                    payload = await request.json()
                except Exception:
                    payload = {}
            result = await self._invoke_maybe_async(self.on_trigger_update, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )

    async def handle_runtime_logs(self, request: Request) -> Response:
        """Обработчик GET /ui/agent/logs."""
        if not self.on_get_runtime_logs:
            return web.json_response(
                {"status": "error", "error": "runtime logs provider not configured"},
                status=501,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        payload = {
            "source": request.query.get("source", "agent"),
            "lines": request.query.get("lines", "120"),
        }
        try:
            result = await self._invoke_maybe_async(self.on_get_runtime_logs, payload)
            if not isinstance(result, dict):
                result = {"result": result}
            result.setdefault("status", "ok")
            return web.json_response(result, headers={"Access-Control-Allow-Origin": "*"})
        except ValueError as e:
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=400,
                headers={"Access-Control-Allow-Origin": "*"},
            )
        except Exception as e:
            logger.exception(e)
            return web.json_response(
                {"status": "error", "error": str(e)},
                status=500,
                headers={"Access-Control-Allow-Origin": "*"},
            )
    
    async def _abort_start(self) -> None:
        """Откат после неудачного bind (иначе runner течёт и повторный start снова падает)."""
        self.site = None
        if self.runner is not None:
            try:
                await self.runner.cleanup()
            except Exception as exc:
                logger.debug(f"UiApiServer cleanup после ошибки bind: {exc}")
            self.runner = None

    async def start(self) -> bool:
        """Запускает HTTP сервер. Идемпотентен: повторный вызов безопасен.

        Returns:
            True если слушаем порт, False если порт занят (другой процесс / гонка).
        """
        if self._listening:
            logger.debug("UiApiServer.start: уже слушаем, пропуск")
            return True

        try:
            self._stopping = False
            self.runner = web.AppRunner(self.app, shutdown_timeout=self._shutdown_timeout)
            await self.runner.setup()

            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            self._listening = True

            logger.success(f"✅ UI API сервер запущен на http://{self.host}:{self.port}")
            logger.info(f"   Эндпоинты:")
            logger.info(f"   - GET  /ui/events (SSE или long-poll)")
            logger.info(f"   - POST /ui/consent_decision")
            logger.info(f"   - POST /ui/chat_send")
            logger.info(f"   - POST /ui/stop_recording")
            logger.info(f"   - POST /ui/request_support")
            logger.info(f"   - GET  /ui/settings")
            logger.info(f"   - PATCH /ui/settings")
            logger.info(f"   - POST /ui/settings (как PATCH)")
            logger.info(f"   - POST /ui/settings/test_connection")
            logger.info(f"   - POST /ui/agent/restart")
            logger.info(f"   - POST /ui/agent/shutdown")
            logger.info(f"   - GET  /ui/agent/status")
            logger.info(f"   - GET  /ui/agent/logs")
            logger.info(f"   - GET  /health")
            return True

        except OSError as e:
            if _is_address_in_use(e):
                logger.warning(
                    f"⚠️  Порт {self.port} уже занят ({self.host}). "
                    f"Повторный запуск UI API в этом процессе пропущен; "
                    f"закройте другой экземпляр агента или смените ui.port в конфиге."
                )
                await self._abort_start()
                return False
            logger.error(f"❌ Ошибка запуска UI API сервера: {e}")
            await self._abort_start()
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка запуска UI API сервера: {e}")
            await self._abort_start()
            raise
    
    async def stop(self):
        """Останавливает HTTP сервер."""
        self._stopping = True
        try:
            # Разблокируем SSE/long-poll обработчики (иначе они ждут до 30 сек по таймауту)
            await self.event_bus.notify_shutdown()
            await self._close_active_sse_connections()
            if self.site:
                await asyncio.wait_for(self.site.stop(), timeout=self._shutdown_timeout)
                logger.info("🛑 UI API сервер остановлен")
            
            if self.runner:
                await asyncio.wait_for(self.runner.cleanup(), timeout=self._shutdown_timeout)
                logger.info("🧹 UI API сервер очищен")
        except asyncio.TimeoutError:
            logger.warning("⚠️ Остановка UI API сервера превысила таймаут")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки UI API сервера: {e}")
        finally:
            self.site = None
            self.runner = None
            self._listening = False

    async def _close_active_sse_connections(self) -> None:
        """Прерывает активные SSE stream'ы до cleanup aiohttp, чтобы shutdown не зависал."""
        transports = list(self._active_sse_transports)
        for transport in transports:
            try:
                if transport is not None and not transport.is_closing():
                    transport.close()
            except Exception as e:
                logger.debug(f"Ошибка закрытия SSE transport: {e}")

        pending_tasks = [task for task in self._active_sse_tasks if not task.done()]
        for task in pending_tasks:
            task.cancel()

        if pending_tasks:
            done, still_pending = await asyncio.wait(pending_tasks, timeout=self._shutdown_timeout)
            for task in done:
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.debug(f"SSE handler завершился с ошибкой: {e}")
            if still_pending:
                logger.debug(f"Остались активные SSE handler'ы при shutdown: {len(still_pending)}")
