"""
Бизнес-логика для работы с чат-сессиями.
"""

import time
from typing import List, Optional, Dict
from loguru import logger


class ChatService:
    """Сервис для работы с чат-сессиями."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def create_session(self, chat_job_id: str, device_id: str, created_by: str = "unknown") -> Dict:
        """
        Создаёт новую чат-сессию.
        
        Args:
            chat_job_id: ID чат-сессии
            device_id: ID устройства агента
            created_by: Кто создал сессию ("agent", "support", "admin")
        
        Returns:
            dict: Созданная сессия
        """
        # owner_uuid: при наличии device_id в connected_agents можно взять из metadata (docs/BOTTLENECKS_AND_RISKS.md Phase 3)
        owner_uuid = None
        if getattr(self.state, "connected_agents", None) and device_id in self.state.connected_agents:
            meta = self.state.connected_agents[device_id].get("metadata", {})
            owner_uuid = meta.get("device_id") or meta.get("owner_uuid")
        session_data = {
            "chat_job_id": chat_job_id,
            "device_id": device_id,
            "owner_uuid": owner_uuid,
            "created_by": created_by,
            "status": "active",
            "created_at": time.time(),
            "subscribers": set(),
            "events": []
        }
        
        self.state.create_chat_session(chat_job_id, session_data)
        
        # Инициализируем job_events для chat_job_id
        if chat_job_id not in self.state.job_events:
            self.state.job_events[chat_job_id] = []
        
        logger.info(f"[ChatService] Created chat session: job_id={chat_job_id} device_id={device_id} created_by={created_by}")
        
        return session_data
    
    def get_session(self, chat_job_id: str) -> Optional[Dict]:
        """Возвращает чат-сессию по ID."""
        return self.state.get_chat_session(chat_job_id)
    
    def update_session_status(self, chat_job_id: str, status: str) -> None:
        """Обновляет статус чат-сессии."""
        self.state.update_chat_session(chat_job_id, status=status)
        logger.info(f"[ChatService] Updated session status: job_id={chat_job_id} status={status}")
    
    def get_active_chats(self) -> List[Dict]:
        """
        Возвращает список всех активных чат-сессий.
        
        Returns:
            list: Список активных чатов с информацией о них
        """
        active_chats = []
        
        for chat_job_id, session in self.state.chat_sessions.items():
            if session.get("status") != "active":
                continue
            
            device_id = session.get("device_id", "unknown")
            agent_info = self.state.get_agent(device_id)
            
            if agent_info:
                agent_metadata = agent_info.get("metadata", {})
                agent_status = agent_metadata.get("status", "offline")
                agent_version = agent_metadata.get("agent_version", "unknown")
            else:
                agent_status = "offline"
                agent_version = "unknown"
            
            active_chats.append({
                "job_id": chat_job_id,
                "device_id": device_id,
                "created_by": session.get("created_by", "unknown"),
                "created_at": session.get("created_at", 0),
                "subscribers_count": len(session.get("subscribers", set())),
                "agent_status": agent_status,
                "agent_version": agent_version
            })
        
        # Сортируем по времени создания (новые сверху)
        active_chats.sort(key=lambda x: x["created_at"], reverse=True)
        
        return active_chats
    
    def add_subscriber(self, chat_job_id: str, ws) -> None:
        """Добавляет подписчика в чат-сессию."""
        session = self.state.get_chat_session(chat_job_id)
        if session:
            session["subscribers"].add(ws)
            logger.debug(f"[ChatService] Added subscriber to chat: job_id={chat_job_id}")
    
    def remove_subscriber(self, chat_job_id: str, ws) -> None:
        """Удаляет подписчика из чат-сессии."""
        session = self.state.get_chat_session(chat_job_id)
        if session:
            session["subscribers"].discard(ws)
            logger.debug(f"[ChatService] Removed subscriber from chat: job_id={chat_job_id}")
    
    def close_session(self, chat_job_id: str) -> None:
        """Закрывает чат-сессию."""
        self.update_session_status(chat_job_id, "closed")
    
    def delete_session(self, chat_job_id: str) -> None:
        """Удаляет чат-сессию."""
        self.state.delete_chat_session(chat_job_id)
        logger.info(f"[ChatService] Deleted chat session: job_id={chat_job_id}")


