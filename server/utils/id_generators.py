"""
Утилиты для генерации ID и временных меток.
"""
import uuid
from datetime import datetime


def now_iso() -> str:
    """Возвращает текущее время в формате ISO timestamp."""
    return datetime.utcnow().isoformat() + 'Z'


def new_ticket_id() -> str:
    """Генерирует новый UUID для тикета."""
    return str(uuid.uuid4())


def new_session_id() -> str:
    """Генерирует новый UUID для сессии."""
    return str(uuid.uuid4())


def new_message_id() -> str:
    """Генерирует новый UUID для сообщения."""
    return str(uuid.uuid4())


def new_call_id() -> str:
    """Генерирует новый UUID для вызова tool."""
    return str(uuid.uuid4())


def new_job_id() -> str:
    """Генерирует новый UUID для задания."""
    return str(uuid.uuid4())


def new_connection_id() -> str:
    """Генерирует новый UUID для UI подключения."""
    return str(uuid.uuid4())