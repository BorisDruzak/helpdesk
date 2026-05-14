"""
Клиент для работы с API сервера чата.
"""

from pathlib import Path
from typing import Any, Optional
import json
import uuid
import aiohttp
from aiohttp import ClientSession, ClientTimeout
from loguru import logger

from pc_agent.core.action_trace import ActionTraceContext, get_action_trace_recorder


class ServerApiClient:
    """
    DEPRECATED: Используйте TicketApiClient вместо этого класса.
    
    Клиент для взаимодействия с API сервера чата (старая модель).
    
    Использование (deprecated):
        client = ServerApiClient(base_url="http://localhost:8666/api", device_id="test_pc_01")
        try:
            result = await client.chat_start()
            job_id = result.get("job_id")
            await client.chat_send(job_id, "Hello")
            events = await client.chat_events(job_id)
        finally:
            await client.close()
    
    Новый способ (рекомендуется):
        client = TicketApiClient(base_url="http://localhost:8666/api", device_id="test_pc_01")
        try:
            result = await client.create_ticket(description="Problem description")
            ticket_id = result.get("ticket_id")
            await client.send_message(ticket_id, "Hello", from_role="user")
            ticket = await client.get_ticket(ticket_id)
        finally:
            await client.close()
    """
    
    def __init__(self, base_url: str, device_id: str, actor_role: str = "support"):
        """
        Инициализирует клиент API.
        
        Args:
            base_url: Базовый URL API сервера (например, "http://localhost:8666/api")
            device_id: Идентификатор устройства
            actor_role: Роль актора (по умолчанию "support")
        """
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.actor_role = actor_role
        self._session: Optional[ClientSession] = None
        self._timeout = ClientTimeout(total=30)
        
        logger.debug(f"Инициализирован ServerApiClient: base_url={base_url}, device_id={device_id}, actor_role={actor_role}")
    
    def _trace_context(
        self,
        *,
        action: str,
        category: str,
        parent_action_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> ActionTraceContext:
        return get_action_trace_recorder().context(
            source="ticket_api",
            action=action,
            category=category,
            parent_action_id=parent_action_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            message_id=message_id,
            tool_name=tool_name,
        )

    @staticmethod
    def _trace_payload_preview(payload: dict) -> dict:
        preview = dict(payload or {})
        text = str(preview.get("text") or "")
        if text:
            preview["text"] = text[:160]
            preview["text_length"] = len(text)
        return preview

    def _trace_context(
        self,
        *,
        action: str,
        category: str,
        parent_action_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> ActionTraceContext:
        return get_action_trace_recorder().context(
            source="ticket_api",
            action=action,
            category=category,
            parent_action_id=parent_action_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            message_id=message_id,
            tool_name=tool_name,
        )

    @staticmethod
    def _trace_payload_preview(payload: dict) -> dict:
        preview = dict(payload or {})
        text = str(preview.get("text") or "")
        if text:
            preview["text"] = text[:160]
            preview["text_length"] = len(text)
        return preview

    async def _get_session(self) -> ClientSession:
        """
        Получает или создает aiohttp ClientSession (ленивая инициализация).
        
        Returns:
            ClientSession: Сессия aiohttp
        """
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
            logger.debug("Создана новая aiohttp ClientSession")
        return self._session
    
    async def close(self):
        """
        Закрывает aiohttp ClientSession.
        """
        if self._session is not None and not self._session.closed:
            await self._session.close()
            logger.debug("Закрыта aiohttp ClientSession")
    
    async def chat_start(self) -> dict:
        """
        DEPRECATED: Используйте TicketApiClient.create_ticket() вместо этого метода.
        
        Начинает новый чат сессию.
        
        Returns:
            dict: JSON ответ от сервера (обычно содержит job_id)
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        logger.warning("[DEPRECATED] chat_start используется. Рекомендуется использовать TicketApiClient.create_ticket()")
        url = f"{self.base_url}/chat_start"
        payload = {
            "device_id": self.device_id,
            "actor_role": self.actor_role
        }
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка chat_start: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                logger.debug(f"chat_start успешно: {result}")
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при chat_start: {e}")
            raise Exception(f"Network error: {e}")
    
    async def chat_send(self, job_id: str, text: str, from_: str = "user") -> dict:
        """
        DEPRECATED: Используйте TicketApiClient.send_message() вместо этого метода.
        
        Отправляет сообщение в чат.
        
        Args:
            job_id: Идентификатор задачи/чата
            text: Текст сообщения
            from_: Отправитель сообщения (по умолчанию "user")
            
        Returns:
            dict: JSON ответ от сервера
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        logger.warning("[DEPRECATED] chat_send используется. Рекомендуется использовать TicketApiClient.send_message()")
        url = f"{self.base_url}/chat_send"
        payload = {
            "device_id": self.device_id,
            "job_id": job_id,
            "text": text,
            "from": from_,
            "actor_role": self.actor_role
        }
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка chat_send: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                logger.debug(f"chat_send успешно: {result}")
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при chat_send: {e}")
            raise Exception(f"Network error: {e}")
    
    async def chat_events(
        self, 
        job_id: str, 
        since_ts: Optional[float] = None, 
        limit: int = 200, 
        format: str = "raw",
        wait: Optional[int] = None,
        timeout_ms: Optional[int] = None
    ) -> dict:
        """
        DEPRECATED: Используйте TicketApiClient.get_ticket() вместо этого метода.
        
        Получает события чата.
        
        Args:
            job_id: Идентификатор задачи/чата
            since_ts: Временная метка для получения событий после этого времени (опционально)
            limit: Максимальное количество событий (по умолчанию 200)
            format: Формат ответа - "raw" (по умолчанию) или "normalized"
            wait: Включить long-polling, ждать до появления событий (опционально, например 1)
            timeout_ms: Таймаут для long-polling в миллисекундах (опционально, например 25000)
            
        Returns:
            dict: JSON ответ от сервера со списком событий
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        logger.warning("[DEPRECATED] chat_events используется. Рекомендуется использовать TicketApiClient.get_ticket()")
        url = f"{self.base_url}/chat_events"
        params = {
            "job_id": job_id,
            "limit": limit,
            "format": format
        }
        if since_ts is not None:
            params["since_ts"] = since_ts
        if wait is not None:
            params["wait"] = wait
        if timeout_ms is not None:
            params["timeout_ms"] = timeout_ms
        
        logger.debug(f"GET {url} с params: {params}")
        
        session = await self._get_session()
        try:
            headers = self._get_headers()
            async with session.get(url, params=params, headers=headers) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка chat_events: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                logger.debug(f"chat_events успешно: получено {len(result.get('events', []))} событий")
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при chat_events: {e}")
            raise Exception(f"Network error: {e}")
    
    async def request_support_local(
        self,
        title: str = "Support needed",
        reason: str = "user_requested",
        severity: str = "warning",
        context: dict | None = None,
    ) -> dict:
        """
        Отправляет запрос на поддержку в локальный UI API сервер.
        
        Args:
            title: Заголовок запроса поддержки (по умолчанию "Support needed")
            reason: Причина запроса (по умолчанию "user_requested")
            severity: Уровень серьезности (по умолчанию "warning")
            context: Дополнительный контекст (опционально)
            
        Returns:
            dict: JSON ответ от сервера
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        # Локальный UiApiServer (тот же host/port, что в ui.* конфига и run_gui)
        try:
            from pc_agent.config.config_loader import get_config

            ui = get_config().ui
            _host = ui.host if ui else "127.0.0.1"
            _port = ui.port if ui else 8765
        except Exception:
            _host, _port = "127.0.0.1", 8765
        url = f"http://{_host}:{_port}/ui/request_support"
        payload = {"title": title, "reason": reason, "severity": severity, "context": context or {}}
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                text = await response.text()
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {text}"
                    logger.error(f"Ошибка request_support_local: {error_msg}")
                    raise Exception(error_msg)
                result = await response.json()
                logger.debug(f"request_support_local успешно: {result}")
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при request_support_local: {e}")
            raise Exception(f"Network error: {e}")


class TicketApiClient:
    """
    Клиент для работы с Ticket API сервера.
    
    Предоставляет методы для работы с новой моделью обращений:
    - Создание обращения
    - Получение списка обращений
    - Получение конкретного обращения
    - Отправка сообщения в обращение
    - Закрытие обращения
    
    Использование:
        client = TicketApiClient(base_url="http://localhost:8666/api", device_id="test_pc_01")
        try:
            result = await client.create_ticket(description="Problem description")
            ticket_id = result.get("ticket_id")
            await client.send_message(ticket_id, "Hello", from_role="user")
            tickets = await client.list_tickets()
            await client.close_ticket(ticket_id, reason="resolved")
        finally:
            await client.close()
    """
    
    def __init__(self, base_url: str, device_id: str, user_display_name: str = "User", auth_token: Optional[str] = None):
        """
        Инициализирует клиент Ticket API.
        
        Args:
            base_url: Базовый URL API сервера (например, "http://localhost:8666/api")
            device_id: Идентификатор устройства
            user_display_name: Отображаемое имя пользователя (по умолчанию "User")
            auth_token: Токен авторизации (опционально, если не указан, загружается из identity.json)
        """
        self.base_url = base_url.rstrip("/")
        self.device_id = device_id
        self.user_display_name = user_display_name
        self._session: Optional[ClientSession] = None
        self._timeout = ClientTimeout(total=30)
        
        # Используем переданный токен (не загружаем из identity.json - legacy удален)
        self.auth_token = auth_token
        
        logger.debug(f"Инициализирован TicketApiClient: base_url={base_url}, device_id={device_id}, user_display_name={user_display_name}, has_token={bool(self.auth_token)}")

    def _trace_context(
        self,
        *,
        action: str,
        category: str,
        parent_action_id: Optional[str] = None,
        ticket_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> ActionTraceContext:
        return get_action_trace_recorder().context(
            source="ticket_api",
            action=action,
            category=category,
            parent_action_id=parent_action_id,
            ticket_id=ticket_id,
            operation_id=operation_id,
            message_id=message_id,
            tool_name=tool_name,
        )

    @staticmethod
    def _trace_payload_preview(payload: dict) -> dict:
        preview = dict(payload or {})
        text = str(preview.get("text") or "")
        if text:
            preview["text"] = text[:160]
            preview["text_length"] = len(text)
        return preview

    async def _get_session(self) -> ClientSession:
        """
        Получает или создает aiohttp ClientSession (ленивая инициализация).
        
        Returns:
            ClientSession: Сессия aiohttp
        """
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self._timeout)
            logger.debug("Создана новая aiohttp ClientSession для TicketApiClient")
        return self._session
    
    def _get_headers(self) -> dict:
        """
        Получает заголовки для HTTP запросов, включая Authorization если есть токен.
        
        Returns:
            dict: Словарь с заголовками
        """
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    async def close(self):
        """
        Закрывает aiohttp ClientSession.
        """
        if self._session is not None and not self._session.closed:
            await self._session.close()
            logger.debug("Закрыта aiohttp ClientSession для TicketApiClient")
    
    async def sync_registry_profile(
        self,
        *,
        requester_id: str,
        display_name: str,
        profile: dict,
    ) -> dict:
        """Отправляет профиль инициатора в серверный реестр людей и локаций."""
        url = f"{self.base_url}/registry/profile"
        payload = {
            "device_id": self.device_id,
            "requester_id": requester_id,
            "display_name": display_name,
            "profile": profile or {},
        }
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                if response.status != 200:
                    logger.info("Registry profile sync skipped: HTTP %s", response.status)
                    return {"status": "error", "http_status": response.status, "body": response_text}
                return json.loads(response_text)
        except aiohttp.ClientError as exc:
            logger.info("Registry profile sync network error: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def get_registry_options(self) -> dict:
        """Получает справочники для picker-полей формы обращения."""
        url = f"{self.base_url}/registry/options"
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.get(url, headers=headers) as response:
                response_text = await response.text()
                if response.status != 200:
                    logger.info("Registry options sync skipped: HTTP %s", response.status)
                    return {}
                payload = json.loads(response_text) if response_text else await response.json()
                data = payload.get("data") if isinstance(payload, dict) else {}
                return data if isinstance(data, dict) else {}
        except (aiohttp.ClientError, json.JSONDecodeError) as exc:
            logger.info("Registry options sync error: %s", exc)
            return {}

    async def create_ticket(
        self,
        description: str,
        title: str = "Untitled",
        tags: list = None,
        requester_profile: Optional[dict] = None,
        user_display_name: Optional[str] = None,
        urgency: Optional[bool] = None,
        importance: Optional[bool] = None,
        urgency_reason: Optional[str] = None,
        importance_reason: Optional[str] = None,
        form_key: Optional[str] = None,
        request_template_key: Optional[str] = None,
        form_pack_key: Optional[str] = None,
        form_pack_version: Optional[str] = None,
        form_payload: Optional[dict] = None,
        diagnostic_consent: Optional[dict] = None,
        ticket_type: Optional[str] = None,
        service_code: Optional[str] = None,
        offering_code: Optional[str] = None,
        offering_full_code: Optional[str] = None,
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Создает новое обращение.
        
        Args:
            description: Описание проблемы (обязательно)
            title: Заголовок обращения (по умолчанию "Untitled")
            tags: Список тегов (опционально)
            
        Returns:
            dict: JSON ответ от сервера с ticket и session
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        url = f"{self.base_url}/tickets/create"
        payload = {
            "title": title,
            "description": description,
            "user_display_name": user_display_name or self.user_display_name,
            "device_id": self.device_id,
            "tags": tags or []
        }
        if requester_profile is not None:
            payload["requester_profile"] = requester_profile
        if urgency is not None:
            payload["urgency"] = urgency
        if importance is not None:
            payload["importance"] = importance
        if urgency_reason is not None:
            payload["urgency_reason"] = urgency_reason
        if importance_reason is not None:
            payload["importance_reason"] = importance_reason
        if form_key is not None:
            payload["form_key"] = form_key
        if request_template_key is not None:
            payload["request_template_key"] = request_template_key
        if form_pack_key is not None:
            payload["form_pack_key"] = form_pack_key
        if form_pack_version is not None:
            payload["form_pack_version"] = form_pack_version
        if form_payload is not None:
            payload["form_payload"] = form_payload
        if diagnostic_consent is not None:
            payload["diagnostic_consent"] = diagnostic_consent
        if ticket_type is not None:
            payload["ticket_type"] = ticket_type
        if service_code is not None:
            payload["service_code"] = service_code
        if offering_code is not None:
            payload["offering_code"] = offering_code
        if offering_full_code is not None:
            payload["offering_full_code"] = offering_full_code
        trace = self._trace_context(
            action="ticket.create",
            category="ticket",
            parent_action_id=trace_parent_action_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="POST /tickets/create",
            details={"payload": self._trace_payload_preview(payload)},
        )
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка create_ticket: {error_msg}")
                    raise Exception(error_msg)
                
                result = json.loads(response_text)
                ticket_data = result.get('ticket', {})
                ticket_id = ticket_data.get('ticket_id', 'N/A')
                trace.ticket_id = str(ticket_id or "") or trace.ticket_id
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="ticket created",
                    details={
                        "http_status": response.status,
                        "ticket_id": ticket_id,
                        "public_access_code": result.get("public_access_code"),
                    },
                )
                logger.debug(f"create_ticket успешно: ticket_id={ticket_id}")
                return result
                
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при create_ticket: {e}")
            raise Exception(f"Network error: {e}")

    async def preview_ticket_create(
        self,
        *,
        form_key: Optional[str] = None,
        request_template_key: Optional[str] = None,
        form_pack_key: Optional[str] = None,
        form_pack_version: Optional[str] = None,
        form_payload: Optional[dict] = None,
        ticket_type: Optional[str] = None,
        service_code: Optional[str] = None,
        offering_code: Optional[str] = None,
        offering_full_code: Optional[str] = None,
    ) -> dict:
        """Возвращает серверный предпросмотр маршрута, приоритета и сроков перед созданием обращения."""
        url = f"{self.base_url}/tickets/create/preview"
        payload: dict[str, Any] = {"device_id": self.device_id}
        if form_key is not None:
            payload["form_key"] = form_key
        if request_template_key is not None:
            payload["request_template_key"] = request_template_key
        if form_pack_key is not None:
            payload["form_pack_key"] = form_pack_key
        if form_pack_version is not None:
            payload["form_pack_version"] = form_pack_version
        if form_payload is not None:
            payload["form_payload"] = form_payload
        if ticket_type is not None:
            payload["ticket_type"] = ticket_type
        if service_code is not None:
            payload["service_code"] = service_code
        if offering_code is not None:
            payload["offering_code"] = offering_code
        if offering_full_code is not None:
            payload["offering_full_code"] = offering_full_code

        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response_text}")
                return json.loads(response_text)
        except aiohttp.ClientError as exc:
            logger.info(f"Предпросмотр создания обращения недоступен: {exc}")
            raise Exception(f"Network error: {exc}")
    
    async def get_service_catalog_current(self) -> dict:
        """Fetch requester-safe Service Catalog for the local agent wizard."""
        url = f"{self.base_url}/service-catalog/current"
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.get(url, headers=headers) as response:
                response_text = await response.text()
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response_text}")
                return json.loads(response_text)
        except aiohttp.ClientError as exc:
            logger.info("Service catalog sync unavailable: %s", exc)
            raise Exception(f"Network error: {exc}")

    async def get_ticket_form_pack_current(
        self,
        pack_key: str = "request_forms",
        current_version: Optional[str] = None,
    ) -> dict:
        """Получает текущий каталог форм заявок для агента."""
        url = f"{self.base_url}/ticket_forms/current"
        params = {"pack_key": pack_key}
        if current_version:
            params["current_version"] = current_version

        logger.debug(f"GET {url} pack_key={pack_key} current_version={current_version}")

        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response_text = await response.text()
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка get_ticket_form_pack_current: {error_msg}")
                    raise Exception(error_msg)
                result = await response.json()
                logger.debug(
                    "get_ticket_form_pack_current успешно: "
                    f"pack_key={pack_key}, version={(result.get('pack') or {}).get('version')}"
                )
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при get_ticket_form_pack_current: {e}")
            raise Exception(f"Network error: {e}")

    async def list_tickets(self, *, trace_parent_action_id: Optional[str] = None) -> dict:
        """
        Получает список обращений. Для агента передаётся device_id — сервер возвращает только обращения этого устройства.
        
        Returns:
            dict: JSON ответ от сервера со списком обращений
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        url = f"{self.base_url}/tickets"
        params = {"device_id": self.device_id}
        trace = self._trace_context(
            action="ticket.list",
            category="ticket",
            parent_action_id=trace_parent_action_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="GET /tickets",
            details={"device_id": self.device_id},
        )
        logger.debug(f"GET {url} device_id={self.device_id[:8]}...")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response_text = await response.text()

                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка list_tickets: {error_msg}")
                    raise Exception(error_msg)

                result = await response.json()
                tickets = result.get("tickets", [])
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="ticket list loaded",
                    details={"http_status": response.status, "ticket_count": len(tickets)},
                )
                logger.debug(f"list_tickets успешно: получено {len(tickets)} обращений (device_id={self.device_id[:8]}...)")
                return result
                
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при list_tickets: {e}")
            raise Exception(f"Network error: {e}")
    
    async def get_ticket(
        self,
        ticket_id: str,
        *,
        since_event_id: Optional[int] = None,
        before_event_id: Optional[int] = None,
        limit: Optional[int] = None,
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Получает информацию об обращении, включая сообщения и события.
        
        Args:
            ticket_id: Идентификатор обращения
            since_event_id: Если указан, вернуть только события с id больше этого значения
            before_event_id: Если указан, вернуть страницу событий с id меньше этого значения
            limit: Размер страницы истории
            
        Returns:
            dict: JSON ответ от сервера с ticket, session, messages, events
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        url = f"{self.base_url}/tickets/{ticket_id}"
        params = None
        if since_event_id is not None and before_event_id is not None:
            raise ValueError("since_event_id and before_event_id are mutually exclusive")
        if since_event_id is not None or before_event_id is not None or limit is not None:
            params = {}
            if since_event_id is not None:
                params["since_event_id"] = int(since_event_id)
            if before_event_id is not None:
                params["before_event_id"] = int(before_event_id)
            if limit is not None:
                params["limit"] = int(limit)
        trace = self._trace_context(
            action="ticket.get",
            category="ticket",
            parent_action_id=trace_parent_action_id,
            ticket_id=ticket_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="GET /tickets/{ticket_id}",
            details={"params": params or {}},
        )
        
        logger.debug(f"GET {url}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response_text = await response.text()
                
                if response.status == 404:
                    error_msg = f"Обращение не найдено: {ticket_id}"
                    logger.error(f"Ошибка get_ticket: {error_msg}")
                    raise Exception(error_msg)
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка get_ticket: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                messages_count = len(result.get('messages', []))
                events_count = len(result.get('events', []))
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="ticket detail loaded",
                    details={
                        "http_status": response.status,
                        "messages_count": messages_count,
                        "events_count": events_count,
                    },
                )
                logger.debug(f"get_ticket успешно: ticket_id={ticket_id}, messages={messages_count}, events={events_count}")
                return result
                
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при get_ticket: {e}")
            raise Exception(f"Network error: {e}")
    
    async def send_message(
        self,
        ticket_id: str,
        text: str,
        from_role: str = "user",
        message_id: Optional[str] = None,
        attachment_refs: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        reply_to: Optional[dict] = None,
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Отправляет сообщение в обращение.
        
        Args:
            ticket_id: Идентификатор обращения
            text: Текст сообщения
            from_role: Роль отправителя (по умолчанию "user")
            message_id: Идентификатор сообщения (если None, будет сгенерирован)
            attachment_refs: Список artifact_id для вложений (optional)
            
        Returns:
            dict: JSON ответ от сервера
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
                       Если статус 409 - обращение закрыто (ticket_closed)
        """
        url = f"{self.base_url}/tickets/{ticket_id}/message"
        
        # Генерируем message_id если не передан
        if message_id is None:
            message_id = str(uuid.uuid4())
        
        payload = {
            "message_id": message_id,
            "from_role": from_role,
            "text": text
        }
        if attachment_refs:
            payload["attachment_refs"] = attachment_refs
        if metadata:
            payload["metadata"] = metadata
        if reply_to:
            payload["reply_to"] = reply_to
        trace = self._trace_context(
            action="ticket.message.send",
            category="message",
            parent_action_id=trace_parent_action_id,
            ticket_id=ticket_id,
            message_id=message_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="POST /tickets/{ticket_id}/message",
            details={"payload": self._trace_payload_preview(payload)},
        )
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status == 404:
                    error_msg = f"Обращение не найдено: {ticket_id}"
                    logger.error(f"Ошибка send_message: {error_msg}")
                    raise Exception(error_msg)
                
                if response.status == 409:
                    error_msg = "Обращение закрыто (ticket_closed)"
                    logger.warning(f"Ошибка send_message: {error_msg}")
                    raise Exception(error_msg)
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка send_message: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="message sent",
                    details={"http_status": response.status, "message_id": message_id},
                )
                logger.debug(f"send_message успешно: ticket_id={ticket_id}, message_id={message_id}")
                return result
                
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при send_message: {e}")
            raise Exception(f"Network error: {e}")

    async def mark_ticket_read(self, ticket_id: str, last_read_event_id: int) -> dict:
        """
        Отмечает последнее входящее сообщение как прочитанное пользователем.

        Args:
            ticket_id: Идентификатор обращения
            last_read_event_id: ID последнего прочитанного события chat_message

        Returns:
            dict: JSON ответ сервера

        Raises:
            Exception: При HTTP ошибке или сетевой ошибке
        """
        url = f"{self.base_url}/tickets/{ticket_id}/read"
        payload = {"last_read_event_id": int(last_read_event_id)}

        logger.debug(f"POST {url} с payload: {payload}")

        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()

                if response.status == 404:
                    error_msg = f"Обращение не найдено: {ticket_id}"
                    logger.error(f"Ошибка mark_ticket_read: {error_msg}")
                    raise Exception(error_msg)

                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка mark_ticket_read: {error_msg}")
                    raise Exception(error_msg)

                result = await response.json()
                logger.debug(
                    "mark_ticket_read успешно: ticket_id={}, last_read_event_id={}, no_op={}",
                    ticket_id,
                    last_read_event_id,
                    result.get("no_op"),
                )
                return result
        except aiohttp.ClientError as e:
            logger.error(f"Ошибка сети при mark_ticket_read: {e}")
            raise Exception(f"Network error: {e}")

    async def upload_attachment(
        self,
        ticket_id: str,
        file_path: str,
        kind: str = "file",
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Загружает вложение в artifacts через multipart: POST /api/upload.

        Args:
            ticket_id: Идентификатор обращения
            file_path: Локальный путь до файла
            kind: Тип артефакта (для GUI вложений — "file")

        Returns:
            dict: artifact metadata (artifact_id, url, mime_type, size, kind)

        Raises:
            Exception: При HTTP ошибке или сетевой ошибке
        """
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise Exception(f"File not found: {file_path}")

        url = f"{self.base_url}/upload"
        session = await self._get_session()
        headers = self._get_headers()

        form = aiohttp.FormData()
        trace = self._trace_context(
            action="ticket.attachment.upload",
            category="attachment",
            parent_action_id=trace_parent_action_id,
            ticket_id=ticket_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="POST /upload",
            details={"file_path": str(path), "kind": kind},
        )
        with path.open("rb") as f:
            form.add_field(
                "file",
                f,
                filename=path.name,
                content_type="application/octet-stream",
            )
            form.add_field("ticket_id", ticket_id)
            form.add_field("kind", kind)

            logger.debug(f"POST {url} multipart: file={path.name}, ticket_id={ticket_id}, kind={kind}")

            try:
                async with session.post(url, data=form, headers=headers) as response:
                    response_text = await response.text()
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: {response_text}"
                        logger.error(f"Ошибка upload_attachment: {error_msg}")
                        raise Exception(error_msg)

                    result = await response.json()
                    get_action_trace_recorder().record(
                        trace,
                        stage="response",
                        status="ok",
                        summary="attachment uploaded",
                        details={
                            "http_status": response.status,
                            "artifact_id": result.get("artifact_id"),
                            "size": result.get("size"),
                            "kind": result.get("kind"),
                        },
                    )
                    logger.debug(
                        "upload_attachment успешно: artifact_id={}, size={}",
                        result.get("artifact_id"),
                        result.get("size"),
                    )
                    return {
                        "artifact_id": result.get("artifact_id"),
                        "url": result.get("url"),
                        "mime_type": result.get("mime_type"),
                        "size": result.get("size"),
                        "kind": result.get("kind"),
                    }
            except aiohttp.ClientError as e:
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="error",
                    summary="network error",
                    details={"exception_type": type(e).__name__, "error": str(e)},
                )
                logger.error(f"Ошибка сети при upload_attachment: {e}")
                raise Exception(f"Network error: {e}")
    
    async def close_ticket(
        self,
        ticket_id: str,
        reason: str = "user_closed",
        closed_by_role: str = "user",
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Закрывает обращение.
        
        Args:
            ticket_id: Идентификатор обращения
            reason: Причина закрытия (по умолчанию "user_closed")
            closed_by_role: Роль закрывающего (по умолчанию "user")
            
        Returns:
            dict: JSON ответ от сервера
            
        Raises:
            Exception: Если HTTP статус != 200, содержит текст ответа для дебага
        """
        url = f"{self.base_url}/tickets/{ticket_id}/close"
        payload = {
            "closed_by_role": closed_by_role,
            "reason": reason
        }
        trace = self._trace_context(
            action="ticket.close",
            category="ticket",
            parent_action_id=trace_parent_action_id,
            ticket_id=ticket_id,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="POST /tickets/{ticket_id}/close",
            details={"payload": payload},
        )
        
        logger.debug(f"POST {url} с payload: {payload}")
        
        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                
                if response.status == 404:
                    error_msg = f"Обращение не найдено: {ticket_id}"
                    logger.error(f"Ошибка close_ticket: {error_msg}")
                    raise Exception(error_msg)
                
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response_text}"
                    logger.error(f"Ошибка close_ticket: {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="ticket closed",
                    details={"http_status": response.status, "already_closed": result.get("already_closed", False)},
                )
                already_closed = result.get("already_closed", False)
                if already_closed:
                    logger.info(f"close_ticket: обращение {ticket_id} уже было закрыто")
                else:
                    logger.debug(f"close_ticket успешно: ticket_id={ticket_id}")
                return result
                
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при close_ticket: {e}")
            raise Exception(f"Network error: {e}")

    async def run_tool(
        self,
        device_id: str,
        ticket_id: str,
        tool_name: str,
        preset_id: Optional[str] = None,
        params: Optional[dict] = None,
        trace_parent_action_id: Optional[str] = None,
    ) -> dict:
        """
        Запускает инструмент в контексте обращения: POST /api/tools/run.

        Команда ставится в очередь и доставляется агенту через device_outbox → WebSocket.
        Результат появится в ленте событий обращения (command_result).        Args:
            device_id: Идентификатор устройства (агента)
            ticket_id: Идентификатор обращения
            tool_name: Имя инструмента (например "screen.collect", "screen.record")
            preset_id: Опциональный preset (например "primary_monitor")
            params: Опциональные параметры инструмента (например {"duration_sec": 300})        Returns:
            dict: Ответ сервера (operation_id, status и т.д.)

        Raises:
            Exception: При HTTP ошибке или ошибке валидации
        """
        url = f"{self.base_url}/tools/run"
        payload = {
            "device_id": device_id,
            "ticket_id": ticket_id,
            "tool_name": tool_name,
        }
        if preset_id is not None:
            payload["preset_id"] = preset_id
        if params is not None:
            payload["params"] = params
        trace = self._trace_context(
            action="ticket.tool.run",
            category="tool",
            parent_action_id=trace_parent_action_id,
            ticket_id=ticket_id,
            tool_name=tool_name,
        )
        get_action_trace_recorder().record(
            trace,
            stage="request",
            status="started",
            summary="POST /tools/run",
            details={"payload": payload},
        )

        logger.debug(f"POST {url} tool_name={tool_name}, ticket_id={ticket_id}")

        session = await self._get_session()
        headers = self._get_headers()
        try:
            async with session.post(url, json=payload, headers=headers) as response:
                response_text = await response.text()
                if response.status == 401:
                    raise Exception("Требуется авторизация (401)")
                if response.status == 400:
                    raise Exception(f"Ошибка запроса: {response_text}")
                # 200 = синхронный результат (wait=1), 202 = операция принята и поставлена в очередь (норма для async)
                if response.status not in (200, 202):
                    raise Exception(f"HTTP {response.status}: {response_text}")

                result = json.loads(response_text) if response_text.strip() else {}
                trace.operation_id = str(result.get("operation_id") or "") or trace.operation_id
                get_action_trace_recorder().record(
                    trace,
                    stage="response",
                    status="ok",
                    summary="tool run accepted",
                    details={
                        "http_status": response.status,
                        "operation_id": result.get("operation_id"),
                        "result_status": result.get("status"),
                    },
                )
                logger.debug(f"run_tool успешно: tool_name={tool_name}, status={response.status}, result={result}")
                return result
        except aiohttp.ClientError as e:
            get_action_trace_recorder().record(
                trace,
                stage="response",
                status="error",
                summary="network error",
                details={"exception_type": type(e).__name__, "error": str(e)},
            )
            logger.error(f"Ошибка сети при run_tool: {e}")
            raise Exception(f"Network error: {e}")
