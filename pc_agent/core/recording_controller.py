"""
Контроллер записи экрана: хранение asyncio.Event по operation_id для досрочной остановки.

Используется этапом 4 (STOP-кнопка): GUI при нажатии STOP вызывает signal_stop(operation_id),
модуль screen.record получает event через get(operation_id) и проверяет is_set() в цикле.
"""

import asyncio
from typing import Dict, Optional

# Глобальный экземпляр (оркестратор и UI API используют один и тот же)
_controller: Optional["RecordingController"] = None


def get_recording_controller() -> "RecordingController":
    """Возвращает глобальный экземпляр RecordingController."""
    global _controller
    if _controller is None:
        _controller = RecordingController()
    return _controller


class RecordingController:
    """
    Хранит по operation_id asyncio.Event для сигнала «остановить запись».
    Orchestrator при старте screen.record вызывает register(operation_id),
    при завершении (успех/ошибка) — unregister(operation_id).
    GUI при нажатии STOP вызывает signal_stop(operation_id).
    """

    def __init__(self) -> None:
        self._events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def register(self, operation_id: str) -> asyncio.Event:
        """Регистрирует event для operation_id, возвращает этот event (для передачи в модуль при необходимости)."""
        event = asyncio.Event()
        self._events[operation_id] = event
        return event

    def get(self, operation_id: str) -> Optional[asyncio.Event]:
        """Возвращает event для operation_id или None."""
        return self._events.get(operation_id)

    def signal_stop(self, operation_id: str) -> bool:
        """Устанавливает флаг остановки для operation_id. Возвращает True, если operation_id был зарегистрирован."""
        event = self._events.get(operation_id)
        if event is None:
            return False
        event.set()
        return True

    def unregister(self, operation_id: str) -> None:
        """Удаляет event для operation_id после завершения записи."""
        self._events.pop(operation_id, None)
