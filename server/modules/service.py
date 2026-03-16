"""
Бизнес-логика для работы с динамическими модулями.
Примечание: Основная логика на стороне агента, этот сервис просто хелпер.
"""

from typing import Optional, Dict
from loguru import logger


class ModulesService:
    """Сервис для работы с динамическими модулями."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def validate_module_name(self, name: str) -> bool:
        """
        Проверяет валидность имени модуля.
        
        Args:
            name: Имя модуля
        
        Returns:
            bool: True если имя валидно
        """
        if not name:
            return False
        
        # Простая валидация: только буквы, цифры, _ и -
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return False
        
        return True
    
    def validate_version(self, version: str) -> bool:
        """
        Проверяет валидность версии модуля.
        
        Args:
            version: Версия модуля (например, "0.1.0")
        
        Returns:
            bool: True если версия валидна
        """
        if not version:
            return False
        
        # Простая валидация: формат X.Y.Z
        import re
        if not re.match(r'^\d+\.\d+\.\d+$', version):
            return False
        
        return True
    
    def check_agent_online(self, device_id: str) -> bool:
        """
        Проверяет, подключён ли агент.
        
        Args:
            device_id: ID устройства
        
        Returns:
            bool: True если агент онлайн
        """
        return self.state.is_agent_online(device_id)


