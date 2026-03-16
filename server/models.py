"""
Модели данных для сервера.
"""

from dataclasses import dataclass


@dataclass
class Ticket:
    """Модель тикета поддержки."""
    ticket_id: str            # uuid
    title: str
    description: str
    user_display_name: str
    device_id: str
    created_at: str           # ISO timestamp
    updated_at: str           # ISO timestamp
    assigned_to: str | None   # "support" | "admin" | None
    tags: list[str]
    status: str               # "open" | "closed"
    
    def to_dict(self) -> dict:
        """Сериализует тикет в словарь для API ответов."""
        return {
            "ticket_id": self.ticket_id,
            "title": self.title,
            "description": self.description,
            "user_display_name": self.user_display_name,
            "device_id": self.device_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "assigned_to": self.assigned_to,
            "tags": self.tags,
            "status": self.status
        }


@dataclass
class Session:
    """Модель сессии поддержки."""
    session_id: str           # uuid
    ticket_id: str
    device_id: str
    job_id: str | None
    status: str               # "open" | "closed"
    created_at: str
    updated_at: str
    last_activity_at: str
    
    def to_dict(self) -> dict:
        """Сериализует сессию в словарь для API ответов."""
        return {
            "session_id": self.session_id,
            "ticket_id": self.ticket_id,
            "device_id": self.device_id,
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_activity_at": self.last_activity_at
        }

