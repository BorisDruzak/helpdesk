"""
HTTP API сервер для UI Bridge.

Предоставляет эндпоинты:
- GET /ui/events - SSE или long-poll для получения событий
- POST /ui/consent_decision - обработка решений о согласии
- POST /ui/chat_send - заготовка для отправки сообщений в чат
"""

import asyncio
import json
from typing import Callable, Optional, Dict, Any, Union, Awaitable
from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response, StreamResponse
from loguru import logger

from .event_bus import EventBus
from .models import ConsentDecision


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
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
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
        self.app.router.add_post("/ui/settings/test_connection", self.handle_test_connection)
        self.app.router.add_post("/ui/agent/restart", self.handle_restart_agent)
        
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
        response = StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        response.headers["Access-Control-Allow-Origin"] = "*"
        
        await response.prepare(request)
        
        # Подписываемся на события
        queue = self.event_bus.subscribe()
        
        try:
            logger.info("SSE соединение установлено")
            
            # Отправляем начальное сообщение
            await response.write(b": connected\n\n")
            
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
                if asyncio.iscoroutinefunction(self.on_consent_decision):
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
        Обработчик POST /ui/chat_send (заготовка).
        
        Пока не реализован, возвращает заглушку.
        """
        return web.json_response({
            "status": "not_implemented",
            "message": "Chat send endpoint is not implemented yet"
        }, status=501, headers={
            "Access-Control-Allow-Origin": "*"
        })
    
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
        if asyncio.iscoroutinefunction(func):
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
        """Обработчик PATCH /ui/settings."""
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
    
    async def start(self):
        """Запускает HTTP сервер."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.success(f"✅ UI API сервер запущен на http://{self.host}:{self.port}")
            logger.info(f"   Эндпоинты:")
            logger.info(f"   - GET  /ui/events (SSE или long-poll)")
            logger.info(f"   - POST /ui/consent_decision")
            logger.info(f"   - POST /ui/chat_send (заготовка)")
            logger.info(f"   - POST /ui/stop_recording")
            logger.info(f"   - POST /ui/request_support")
            logger.info(f"   - GET  /ui/settings")
            logger.info(f"   - PATCH /ui/settings")
            logger.info(f"   - POST /ui/settings/test_connection")
            logger.info(f"   - POST /ui/agent/restart")
            logger.info(f"   - GET  /health")
            
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.warning(
                    f"⚠️  Порт {self.port} уже занят. "
                    f"UI API сервер не запущен. "
                    f"Возможно, уже запущен другой экземпляр агента или GUI."
                )
                # Не падаем, просто продолжаем работу без UI API сервера
                return
            else:
                logger.error(f"❌ Ошибка запуска UI API сервера: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Ошибка запуска UI API сервера: {e}")
            raise
    
    async def stop(self):
        """Останавливает HTTP сервер."""
        try:
            # Разблокируем SSE/long-poll обработчики (иначе они ждут до 30 сек по таймауту)
            await self.event_bus.notify_shutdown()
            if self.site:
                await self.site.stop()
                logger.info("🛑 UI API сервер остановлен")
            
            if self.runner:
                await self.runner.cleanup()
                logger.info("🧹 UI API сервер очищен")
                
        except Exception as e:
            logger.error(f"❌ Ошибка остановки UI API сервера: {e}")
