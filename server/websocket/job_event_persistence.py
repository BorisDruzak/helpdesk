"""Job-event persistence helper for websocket command flow."""

"""
WebSocket обработчик для агентов.
"""

import asyncio
import time
import uuid
import json
from datetime import datetime, timezone
from aiohttp import web, WSMsgType
from loguru import logger
from typing import Optional, Tuple, Any
from utils import now_iso
from websocket.protocol import (
    send_ws_command,
    push_chat_event_to_ui,
    send_outbox_ack,
    send_outbox_nack
)
from websocket.batch_ack_manager import BatchAckManager, NackInfo
from websocket.validator import EventValidator
from websocket.command_result_parser import normalize_command_result_payload
from config import ENABLE_DB_PERSISTENCE
from auth.service import AuthService
from auth.context import AuthContext, AuthType
from websocket.contexts import AgentConnectionContext, EnvelopeContext
from websocket.agent_services import (
    AgentLoopSafetyService,
    AgentCommandService,
    AgentMessageRouter,
    CommandAckService,
    CommandResultService,
    HandshakeService,
    OutboxIngestService,
)

# Import database components (lazy import to handle missing dependencies)
try:
    from app.db import get_session
    from app.repos import JobEventsRepo, TicketEventsRepo, DeviceEventsRepo
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False

async def persist_job_event(job_id: str, event: dict) -> None:
    """
    Persist job event to database (best-effort, non-blocking).
    
    This function attempts to save events to PostgreSQL for persistence
    and replay functionality. If the database is unavailable or disabled,
    it silently continues without raising errors.
    
    Args:
        job_id: Job identifier
        event: Event payload dictionary containing event data
    """
    # Skip if database persistence is disabled
    if not ENABLE_DB_PERSISTENCE:
        return
    
    # Skip if database components are not available
    if not DB_AVAILABLE:
        logger.debug(f"[persist_job_event] DB not available, skipping persistence for job_id={job_id}")
        return
    
    try:
        event_type = event.get("event", "unknown")
        
        # Create database session and persist event
        async with get_session() as session:
            repo = JobEventsRepo(session)
            await repo.add_event(
                job_id=job_id,
                event_type=event_type,
                payload=event
            )
            
        logger.debug(
            f"[persist_job_event] Successfully persisted event: "
            f"job_id={job_id} event_type={event_type}"
        )
    except Exception as e:
        # Log warning but don't raise - best effort persistence
        # Server should continue working even if DB persistence fails
        event_type = event.get("event", "unknown")
        logger.warning(
            f"[persist_job_event] Failed to persist event to DB "
            f"(job_id={job_id}, event_type={event_type}): {e}"
        )


