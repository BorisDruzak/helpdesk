"""Safe input-activity collector.

The production goal is to expose only privacy-preserving activity signals.
No raw key presses or pointer coordinates are stored.
"""

from __future__ import annotations

import platform
import time
from ctypes import Structure, byref, c_uint, sizeof
from typing import Any, Dict

from loguru import logger

from modules.base_module import BaseCollector
from core.registry import exposed_tool


class _LastInputInfo(Structure):
    _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]


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

        current_keyboard = self._keyboard_events
        current_mouse = self._mouse_events
        self._keyboard_events = 0
        self._mouse_events = 0

        idle_seconds, source = self._detect_idle_seconds()
        active_recently = idle_seconds is not None and idle_seconds < 60

        return {
            "keyboard": current_keyboard,
            "mouse": current_mouse,
            "total_events": current_keyboard + current_mouse,
            "timestamp": time.time(),
            "platform": platform.system().lower(),
            "idle_seconds": idle_seconds,
            "active_recently": active_recently,
            "activity_source": source,
        }

    def _detect_idle_seconds(self) -> tuple[float | None, str]:
        if platform.system() != "Windows":
            return None, "unsupported_platform"

        try:
            from ctypes import windll

            info = _LastInputInfo()
            info.cbSize = sizeof(_LastInputInfo)
            if not windll.user32.GetLastInputInfo(byref(info)):  # type: ignore[attr-defined]
                return None, "win32_get_last_input_failed"

            tick_count = windll.kernel32.GetTickCount64()  # type: ignore[attr-defined]
            idle_ms = max(int(tick_count) - int(info.dwTime), 0)
            return round(idle_ms / 1000.0, 3), "win32_last_input"
        except Exception as exc:
            logger.debug(f"[{self.name}] Не удалось определить idle_seconds: {exc}")
            return None, "unavailable"
