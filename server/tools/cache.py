"""
Кеширование tools.
"""

import time
from typing import Optional, Any
from config import TOOLS_CACHE_TTL


class ToolsCache:
    """Менеджер кеша инструментов."""
    
    def __init__(self, state_manager):
        self.state = state_manager
    
    def get(self) -> Optional[Any]:
        """Возвращает закешированные tools если они актуальны."""
        return self.state.get_tools_cache()
    
    def set(self, data: Any, ttl_sec: Optional[float] = None) -> None:
        """Сохраняет tools в кеш."""
        if ttl_sec is None:
            ttl_sec = TOOLS_CACHE_TTL
        self.state.set_tools_cache(data, ttl_sec)
    
    def clear(self) -> None:
        """Очищает кеш tools."""
        self.state.clear_tools_cache()
    
    def is_valid(self) -> bool:
        """Проверяет, актуален ли кеш."""
        return self.get() is not None

