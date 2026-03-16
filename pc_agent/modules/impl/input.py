"""
Модуль для мониторинга активности ввода (клавиатура и мышь).

Отслеживает факт активности пользователя без записи конкретных нажатий
для соблюдения приватности.
"""

from typing import Dict, Any
from loguru import logger

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class InputCollector(BaseCollector):
    """
    Коллектор активности ввода (клавиатура и мышь).
    
    Фиксирует только факт активности, не записывает конкретные нажатия.
    """
    
    def __init__(self):
        """Инициализация счетчиков активности."""
        super().__init__()
        self._keyboard_events = 0
        self._mouse_events = 0
    
    @property
    def name(self) -> str:
        """Возвращает уникальное имя модуля."""
        return "input"
    
    @exposed_tool(
        name="collect_input_activity",
        description="Сбор данных об активности ввода (клавиатура и мышь)",
        risk_level="safe_readonly",
        presets=[
            {
                "id": "quick_check",
                "name": "Быстрая проверка активности",
                "description": "Проверка текущей активности ввода пользователя",
                "params": {}
            }
        ],
        metadata_risk_level="safe_read",
        metadata_scopes=["input"],
        metadata_requires_consent=False
    )
    async def collect(self) -> Dict[str, Any]:
        """
        Асинхронный сбор данных об активности ввода.
        
        Returns:
            Dict[str, Any]: Словарь с наблюдениями об активности ввода (observations)
        
        Raises:
            Exception: В случае ошибок сбора данных
        """
        logger.debug(f"[{self.name}] Начинаю сбор данных об активности ввода")
        
        # TODO: Здесь будет реальная логика через pynput
        # from pynput import keyboard, mouse
        # Устанавливаем слушатели событий
        # Считаем количество событий за интервал
        
        # Пока возвращаем заглушку
        current_keyboard = self._keyboard_events
        current_mouse = self._mouse_events
        
        # Сбрасываем счетчики
        self._keyboard_events = 0
        self._mouse_events = 0
        
        import time
        return {
            "keyboard": current_keyboard,
            "mouse": current_mouse,
            "total_events": current_keyboard + current_mouse,
            "timestamp": time.time()
        }

