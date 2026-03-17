"""
SSE клиент для подключения к EventBus через HTTP SSE endpoint.
"""

import asyncio
import json
import aiohttp
from typing import Callable, Optional
from loguru import logger


class SseClient:
    """
    Клиент для Server-Sent Events (SSE).
    
    Подключается к SSE endpoint и парсит события в формате:
    data: <json>\n\n
    """
    
    def __init__(self, base_url: str):
        """
        Инициализация SSE клиента.
        
        Args:
            base_url: Базовый URL (например, "http://127.0.0.1:8765")
        """
        self.base_url = base_url.rstrip("/")
        self.url = f"{self.base_url}/ui/events"
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._response: Optional[aiohttp.ClientResponse] = None

    async def _close_transport(self) -> None:
        """Жестко закрывает текущий SSE transport, чтобы shutdown не висел на stream reader."""
        response = self._response
        self._response = None
        if response is not None:
            try:
                response.close()
            except Exception as e:
                logger.debug(f"Ошибка закрытия SSE response: {e}")

        session = self._session
        self._session = None
        if session is not None and not session.closed:
            try:
                await session.close()
            except Exception as e:
                logger.debug(f"Ошибка закрытия SSE session: {e}")
    
    async def run(self, on_event_cb: Callable[[dict], None]):
        """
        Запускает вечный цикл подключения с авто-reconnect.
        
        Args:
            on_event_cb: Callback функция для обработки событий (sync)
        """
        self._running = True
        
        while self._running:
            try:
                # Создаем новую сессию для каждого подключения
                self._session = aiohttp.ClientSession()
                
                logger.info(f"Подключаюсь к SSE: {self.url}")
                
                async with self._session.get(
                    self.url,
                    headers={"Accept": "text/event-stream"},
                    timeout=aiohttp.ClientTimeout(total=None)  # Без таймаута
                ) as response:
                    self._response = response
                    if response.status != 200:
                        logger.error(f"Ошибка подключения к SSE: HTTP {response.status}")
                        await asyncio.sleep(5)
                        continue
                    
                    logger.success("SSE соединение установлено")
                    
                    # Буфер для накопления данных
                    buffer = b""
                    
                    async for chunk in response.content.iter_any():
                        if not self._running:
                            break
                        
                        buffer += chunk
                        
                        # Обрабатываем полные строки
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            
                            if not line:
                                continue
                            
                            # Пропускаем комментарии (keep-alive)
                            if line.startswith(b":"):
                                continue
                            
                            # Парсим строку data: <json>
                            if line.startswith(b"data: "):
                                json_str = line[6:].decode("utf-8", errors="ignore")
                                try:
                                    event = json.loads(json_str)
                                    on_event_cb(event)
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Ошибка парсинга JSON события: {e}, строка: {json_str[:100]}")
                                except Exception as e:
                                    logger.error(f"Ошибка обработки события: {e}")
                    
                    logger.warning("SSE соединение закрыто")
                    
            except asyncio.CancelledError:
                logger.info("SSE клиент получил сигнал отмены")
                break
            except aiohttp.ClientError as e:
                logger.error(f"Ошибка подключения к SSE: {e}")
            except Exception as e:
                logger.error(f"Неожиданная ошибка в SSE клиенте: {e}")
            finally:
                try:
                    await self._close_transport()
                except asyncio.CancelledError:
                    # При отмене всё равно планируем фактическое закрытие, чтобы transport не зависал.
                    asyncio.create_task(self._close_transport())
                    raise
            
            # Переподключение через 5 секунд
            if self._running:
                logger.info("Переподключение через 5 секунд...")
                await asyncio.sleep(5)
        
        logger.info("SSE клиент остановлен")
    
    def stop(self):
        """Останавливает SSE клиент."""
        self._running = False

    async def stop_async(self) -> None:
        """Останавливает SSE клиент и сразу рвёт текущее соединение."""
        self._running = False
        await self._close_transport()





















