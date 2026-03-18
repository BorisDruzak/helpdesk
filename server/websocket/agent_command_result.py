"""Thin compatibility wrapper for command_result handling."""

from __future__ import annotations

from typing import Any, Optional

from aiohttp import web
from loguru import logger

from websocket.agent_services import CommandResultService
from websocket.contexts import AgentConnectionContext

_SERVICE = CommandResultService()


async def handle_command_result(
    ws: web.WebSocketResponse,
    data: dict[str, Any],
    state: Any,
    agent_id: Optional[str],
) -> None:
    """
    Deprecated internal adapter.

    Kept for one compatibility cycle; production pipeline uses
    `CommandResultService` directly from `agent_handler.py`.
    """
    logger.debug("[agent_command_result] deprecated wrapper invoked")
    ctx = AgentConnectionContext(ws=ws, request=None, state=state, agent_id=agent_id)
    await _SERVICE.handle(data, ctx)
