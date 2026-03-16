"""
Управление событиями чатов.
"""

import time
from typing import Dict, List
from loguru import logger


class ChatEventsManager:
    """Менеджер для работы с событиями чатов."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def append_event(self, job_id: str, event: dict) -> None:
        """
        Добавляет событие в журнал чата.
        
        Args:
            job_id: ID чата
            event: Событие для добавления
        """
        # Добавляем timestamp если отсутствует
        if "ts" not in event:
            event["ts"] = time.time()
        
        self.state.append_job_event(job_id, event)
        
        logger.debug(f"[ChatEventsManager] Event added to chat: job_id={job_id} event_type={event.get('event', 'unknown')}")
    
    def get_events(self, job_id: str, since_ts: float = None, limit: int = None) -> List[dict]:
        """
        Возвращает события чата.
        
        Args:
            job_id: ID чата
            since_ts: Фильтр по времени (события после указанного timestamp)
            limit: Максимальное количество событий
        
        Returns:
            list: Список событий
        """
        events = self.state.get_job_events(job_id)
        
        # Фильтрация по времени
        if since_ts is not None:
            events = [e for e in events if e.get("ts", 0) > since_ts]
        
        # Применение лимита
        if limit is not None and limit > 0:
            events = events[-limit:]
        
        return events
    
    def clear_events(self, job_id: str) -> None:
        """Очищает события чата."""
        self.state.clear_job_events(job_id)
        logger.info(f"[ChatEventsManager] Cleared events for chat: job_id={job_id}")
    
    def create_chat_message_event(self, job_id: str, message_id: str, from_: str, text: str) -> dict:
        """
        Создаёт событие chat_message.
        
        Args:
            job_id: ID чата
            message_id: ID сообщения
            from_: Отправитель сообщения
            text: Текст сообщения
        
        Returns:
            dict: Событие chat_message
        """
        event = {
            "event": "chat_message",
            "job_id": job_id,
            "message_id": message_id,
            "from": from_,
            "text": text,
            "ts": time.time()
        }
        
        self.append_event(job_id, event)
        
        return event
    
    def create_chat_invite_event(self, job_id: str, device_id: str, from_: str, title: str = None) -> dict:
        """
        Создаёт событие chat_invite.
        
        Args:
            job_id: ID чата
            device_id: ID устройства
            from_: Инициатор приглашения
            title: Заголовок чата
        
        Returns:
            dict: Событие chat_invite
        """
        event = {
            "event": "chat_invite",
            "job_id": job_id,
            "device_id": device_id,
            "from": from_,
            "title": title or "Chat Invite",
            "ts": time.time()
        }
        
        self.append_event(job_id, event)
        
        return event
    
    def create_chat_ended_event(self, job_id: str, reason: str = "normal") -> dict:
        """
        Создаёт событие chat_ended.
        
        Args:
            job_id: ID чата
            reason: Причина завершения чата
        
        Returns:
            dict: Событие chat_ended
        """
        event = {
            "event": "chat_ended",
            "job_id": job_id,
            "reason": reason,
            "ts": time.time()
        }
        
        self.append_event(job_id, event)
        
        return event


