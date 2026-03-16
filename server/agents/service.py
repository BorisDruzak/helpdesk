"""
Сервис управления агентами.
"""

import time
from typing import List, Dict, Optional
from loguru import logger


class AgentService:
    """Сервис для работы с агентами."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def get_agents_list(self) -> List[Dict]:
        """
        Возвращает список агентов, которые реально онлайн (WebSocket открыт, статус online).
        Использует единую точку проверки state.is_agent_online() для корректного отображения в веб-морде.
        
        Returns:
            Список агентов с информацией о device_id, версии, модулях, статусе и времени
        """
        agents_list = []
        current_time = time.time()
        # Итерация по копии ключей: is_agent_online() может вызывать unregister_agent()
        for device_id in list(self.state.connected_agents.keys()):
            if not self.state.is_agent_online(device_id):
                continue
            agent_info = self.state.connected_agents.get(device_id)
            if not agent_info:
                continue
            metadata = agent_info.get("metadata", {})
            connected_at = agent_info.get("connected_at", current_time)
            last_seen = metadata.get("last_seen", connected_at)
            
            uptime = current_time - connected_at
            last_seen_delta = current_time - last_seen
            
            agents_list.append({
                "device_id": device_id,
                "agent_version": metadata.get("agent_version", "unknown"),
                "modules": metadata.get("modules", []),
                "status": metadata.get("status", "online"),
                "user_display_name": metadata.get("user_display_name", "Unknown"),
                "os_type": metadata.get("os_type", "Unknown"),
                "os_version": metadata.get("os_version", "Unknown"),
                "uptime": round(uptime, 2),
                "last_seen": round(last_seen_delta, 2),
                "connected_at": connected_at,
                "online": True,
            })
        
        return agents_list
    
    def get_devices_list(self) -> List[str]:
        """
        Возвращает простой список device_id для использования в UI.
        
        Returns:
            Отсортированный список device_id
        """
        devices = set()
        for device_id in self.state.connected_agents.keys():
            devices.add(device_id)
        
        return sorted(list(devices))
    
    def get_agent_metadata(self, device_id: str) -> Optional[Dict]:
        """
        Возвращает метаданные агента.
        
        Args:
            device_id: ID устройства
        
        Returns:
            Метаданные агента или None
        """
        agent_info = self.state.get_agent(device_id)
        if agent_info:
            return agent_info.get("metadata", {})
        return None
    
    def update_agent_last_seen(self, device_id: str) -> None:
        """
        Обновляет время последней активности агента.
        
        Args:
            device_id: ID устройства
        """
        agent_info = self.state.get_agent(device_id)
        if agent_info and "metadata" in agent_info:
            agent_info["metadata"]["last_seen"] = time.time()
    
    def is_agent_online(self, device_id: str) -> bool:
        """
        Проверяет, подключён ли агент.
        
        Args:
            device_id: ID устройства
        
        Returns:
            True если агент подключён, иначе False
        """
        return self.state.is_agent_online(device_id)

