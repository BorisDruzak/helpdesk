"""Thin compatibility wrapper for outbox_item handling."""

from __future__ import annotations

from typing import Any, Optional

from aiohttp import web
from loguru import logger

from websocket.agent_services import OutboxIngestService
from websocket.contexts import AgentConnectionContext


async def handle_outbox_item(
    ws: web.WebSocketResponse,
    data: dict[str, Any],
    state: Any,
    agent_id: Optional[str],
    batch_ack_manager: Any,
    event_validator: Any,
) -> bool:
    """
    Deprecated internal adapter.

    Kept for one compatibility cycle; production pipeline uses
    `OutboxIngestService` directly from `agent_handler.py`.
    """
    logger.debug("[agent_outbox_ingest] deprecated wrapper invoked")
    service = OutboxIngestService(
        legacy_handler=None,
        batch_ack_manager=batch_ack_manager,
        event_validator=event_validator,
    )
    ctx = AgentConnectionContext(ws=ws, request=None, state=state, agent_id=agent_id)
    return await service.handle(data, ctx)
