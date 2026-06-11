"""
EventBus для публикации и подписки на UI-события.

Позволяет core компонентам публиковать события,
а UI компонентам (Qt или HTTP клиентам) подписываться на них.
"""

import asyncio
import copy
from datetime import datetime, timezone
from typing import Dict, Any, Set, List
from loguru import logger


class EventBus:
    """
    Шина событий для публикации и подписки на UI-события.
    
    Использует asyncio.Queue для каждого подписчика,
    что позволяет безопасно работать в async контексте.
    """
    
    def __init__(self):
        """Инициализация EventBus."""
        self._subscribers: Set[asyncio.Queue] = set()
        self._sticky_events: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        # Не логируем инициализацию, чтобы избежать бесконечного цикла логов
    
    async def publish(self, event: Dict[str, Any]) -> None:
        """
        Публикует событие всем подписчикам.
        
        Args:
            event: Словарь с данными события. Должен содержать ключи:
                   - event_type: тип события
                   - data: данные события
                   - timestamp: временная метка (опционально)
        
        Пример:
            await event_bus.publish({
                "event_type": "job_started",
                "data": {"job_id": "123", "module": "screen"},
                "timestamp": "2025-01-01T12:00:00Z"
            })
        """
        async with self._lock:
            self._remember_sticky_event(event)
            if not self._subscribers:
                # Не логируем отсутствие подписчиков, чтобы избежать бесконечного цикла логов
                return
            
            # Отправляем событие всем подписчикам
            dead_queues = set()
            for queue in self._subscribers:
                try:
                    await queue.put(event)
                except Exception as e:
                    # Не логируем ошибки публикации, чтобы избежать бесконечного цикла логов
                    dead_queues.add(queue)
            
            # Удаляем мертвые очереди
            if dead_queues:
                self._subscribers -= dead_queues
                # Не логируем удаление подписчиков, чтобы избежать бесконечного цикла логов
            
            # Не логируем публикацию событий, чтобы избежать бесконечного цикла логов

    def _remember_sticky_event(self, event: Dict[str, Any]) -> None:
        """Запоминает последнее критичное UI-состояние для поздних подписчиков."""
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type == "connection_state":
            self._sticky_events[event_type] = copy.deepcopy(event)
            return
        if event_type == "remote_assist_request":
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            session_id = str(data.get("session_id") or "").strip()
            if session_id:
                self._sticky_events[f"{event_type}:{session_id}"] = copy.deepcopy(event)

    def subscribe(self) -> asyncio.Queue[Dict[str, Any]]:
        """
        Создает новую подписку на события.
        
        Returns:
            asyncio.Queue, из которой можно читать события.
        
        Пример:
            queue = event_bus.subscribe()
            while True:
                event = await queue.get()
                print(f"Получено событие: {event}")
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        # Не логируем добавление подписчиков, чтобы избежать бесконечного цикла логов
        return queue

    def get_replay_events(self) -> List[Dict[str, Any]]:
        """
        Возвращает события-снимки для новых подписчиков.

        Сейчас sticky-реплей нужен прежде всего для connection_state, чтобы GUI,
        подписавшийся уже после handshake_ack, сразу увидел актуальный статус.
        """
        replay: List[Dict[str, Any]] = []
        snapshot = self._sticky_events.get("connection_state")
        if snapshot:
            replay.append(copy.deepcopy(snapshot))

        expired_keys: list[str] = []
        for key, event in self._sticky_events.items():
            if not key.startswith("remote_assist_request:"):
                continue
            if self._is_remote_assist_event_expired(event):
                expired_keys.append(key)
                continue
            replay.append(copy.deepcopy(event))
        for key in expired_keys:
            self._sticky_events.pop(key, None)
        return replay

    @staticmethod
    def _is_remote_assist_event_expired(event: Dict[str, Any]) -> bool:
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        expires_at = str(data.get("expires_at") or "").strip()
        if not expires_at:
            return False
        try:
            parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
    
    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        """
        Отменяет подписку на события.
        
        Args:
            queue: Очередь, которую нужно удалить из подписчиков.
        
        Пример:
            queue = event_bus.subscribe()
            # ... работа с событиями ...
            await event_bus.unsubscribe(queue)
        """
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
                # Не логируем удаление подписчиков, чтобы избежать бесконечного цикла логов
            else:
                # Не логируем предупреждения, чтобы избежать бесконечного цикла логов
                pass
    
    def get_subscriber_count(self) -> int:
        """
        Возвращает количество активных подписчиков.

        Returns:
            Количество активных подписчиков.
        """
        return len(self._subscribers)

    async def notify_shutdown(self) -> None:
        """
        Отправляет сигнал завершения всем подписчикам (очередь разблокируется).
        Вызывать перед остановкой UI API сервера, чтобы SSE/long-poll обработчики
        не ждали таймаут 30 сек.
        """
        async with self._lock:
            for queue in self._subscribers:
                try:
                    await queue.put({"_shutdown": True})
                except Exception:
                    pass
