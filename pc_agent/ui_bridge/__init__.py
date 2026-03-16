"""
UI Bridge модуль для публикации UI-событий и HTTP API.

Предоставляет:
- EventBus для публикации и подписки на события
- UiApiServer для HTTP API (SSE/long-poll для событий, consent_decision и др.)
"""

from .event_bus import EventBus
from .api_server import UiApiServer
from .models import UIEvent, ConsentDecision

__all__ = ["EventBus", "UiApiServer", "UIEvent", "ConsentDecision"]








