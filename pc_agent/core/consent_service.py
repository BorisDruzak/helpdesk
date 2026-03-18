"""
Consent lifecycle service extracted from AgentOrchestrator.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from loguru import logger


class ConsentState(str, Enum):
    NEW = "NEW"
    WAITING_USER = "WAITING_USER"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RESOLVED = "RESOLVED"


@dataclass
class ConsentRecord:
    consent_token: str
    state: ConsentState
    pending: Optional[dict[str, Any]]


class ConsentService:
    """
    Handles persistent consent lifecycle via DatabaseManager pending_consents table.
    """

    def __init__(self, db_manager: Any, *, device_id_getter):
        self._db_manager = db_manager
        self._device_id_getter = device_id_getter

    async def create_pending(
        self,
        *,
        tool_name: str,
        params: dict[str, Any],
        payload_hash: str,
        request_id: str,
        session_key: str,
        actor_role: str,
        ticket_id: Optional[str],
        job_id: Optional[str],
        expires_in_sec: int = 1800,
    ) -> ConsentRecord:
        consent_token = str(uuid.uuid4())
        if self._db_manager:
            await self._db_manager.add_pending_consent(
                operation_id=consent_token,
                device_id=self._device_id_getter(),
                tool_name=tool_name,
                params=params,
                payload_hash=payload_hash,
                request_id=request_id,
                session_key=session_key,
                actor_role=actor_role,
                ticket_id=ticket_id,
                job_id=job_id,
                expires_at=int(time.time()) + expires_in_sec,
            )
            logger.info(f"[ConsentService] pending consent persisted: token={consent_token}")
        else:
            logger.warning("[ConsentService] db_manager unavailable, pending consent not persisted")
        return ConsentRecord(consent_token=consent_token, state=ConsentState.WAITING_USER, pending=None)

    async def apply_decision(self, *, consent_token: str, approved: bool) -> ConsentRecord:
        if not self._db_manager:
            return ConsentRecord(consent_token=consent_token, state=ConsentState.EXPIRED, pending=None)

        pending = await self._db_manager.get_pending_consent(consent_token)
        if not pending:
            return ConsentRecord(consent_token=consent_token, state=ConsentState.EXPIRED, pending=None)

        if pending.get("expires_at") and pending["expires_at"] < int(time.time()):
            await self._db_manager.remove_pending_consent(consent_token)
            return ConsentRecord(consent_token=consent_token, state=ConsentState.EXPIRED, pending=pending)

        await self._db_manager.remove_pending_consent(consent_token)
        return ConsentRecord(
            consent_token=consent_token,
            state=ConsentState.APPROVED if approved else ConsentState.REJECTED,
            pending=pending,
        )

    async def cleanup_expired(self) -> int:
        if not self._db_manager:
            return 0
        return await self._db_manager.cleanup_expired_consents()
