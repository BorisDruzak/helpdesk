"""
DB-backed token verification service for agent/UI auth paths.
"""

from __future__ import annotations

from typing import Optional

from app.db import get_session
from app.repos.auth_tokens_repo import AuthTokensRepo
from app.repos.devices_repo import DevicesRepo


class AgentTokenService:
    """Source-of-truth token verification via PostgreSQL."""

    async def verify_agent_token(self, token: str) -> Optional[dict]:
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            devices_repo = DevicesRepo(session)
            token_record = await repo.verify_agent_token(token)
            if not token_record:
                return None
            device = await devices_repo.get_by_device_id(
                token_record.device_id,
                include_deleted=True,
            )
            if device and device.deleted_at is not None:
                return None
            return {
                "device_id": token_record.device_id,
                "token_hash": token_record.token_hash,
                "token_prefix": token_record.token_prefix,
                "created_at": token_record.created_at.isoformat(),
                "type": "agent",
            }

    async def verify_ui_token(self, token: str) -> Optional[dict]:
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token_record = await repo.verify_ui_token(token)
            if not token_record:
                return None
            return {
                "user_login": token_record.user_login,
                "actor_role": token_record.actor_role,
                "created_at": token_record.created_at.isoformat(),
                "type": "ui",
            }
