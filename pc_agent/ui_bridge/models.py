"""
Модели данных для UI Bridge.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class UIEvent:
    """
    Модель UI-события.
    
    Attributes:
        event_type: Тип события (например, "job_started", "consent_required", "data_collected")
        data: Данные события (dict)
        timestamp: Временная метка события (ISO format)
    """
    event_type: str
    data: Dict[str, Any]
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        """Автоматически устанавливает timestamp если не указан."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует событие в словарь для JSON сериализации."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp
        }


@dataclass
class ConsentDecision:
    """
    Модель решения о согласии.
    
    Attributes:
        job_id: Идентификатор задачи
        consent_token: Токен согласия
        approved: Одобрено ли действие
        reason: Причина решения (опционально)
        session_key: Ключ сессии (опционально)
    """
    job_id: str
    consent_token: str
    approved: bool
    reason: Optional[str] = None
    session_key: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразует решение в словарь для JSON сериализации."""
        return {
            "job_id": self.job_id,
            "consent_token": self.consent_token,
            "approved": self.approved,
            "reason": self.reason,
            "session_key": self.session_key
        }

