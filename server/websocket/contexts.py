from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from aiohttp import web


@dataclass
class AgentConnectionContext:
    """Runtime context for one agent WS connection."""

    ws: web.WebSocketResponse
    request: web.Request
    state: Any
    agent_id: Optional[str] = None
    device_id: Optional[str] = None
    authenticated: bool = False
    capabilities: list[str] = field(default_factory=list)
    session_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvelopeContext:
    """Envelope metadata passed to message handlers."""

    message_type: Optional[str]
    trace_id: Optional[str]
    received_at: datetime
    raw_envelope: dict[str, Any]

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> "EnvelopeContext":
        return cls(
            message_type=message.get("type"),
            trace_id=message.get("trace_id"),
            received_at=datetime.now(timezone.utc),
            raw_envelope=message,
        )
