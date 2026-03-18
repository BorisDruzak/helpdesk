"""
DB-backed token verification service for agent/UI auth paths.
"""

from __future__ import annotations

from typing import Optional

from app.db import get_session
from app.repos.auth_tokens_repo import AuthTokensRepo


class AgentTokenService:
    """Source-of-truth token verification via PostgreSQL."""

    async def verify_agent_token(self, token: str) -> Optional[dict]:
        async with get_session() as session:
            repo = AuthTokensRepo(session)
            token_record = await repo.verify_agent_token(token)
            if not token_record:
                return None
            return {
                "device_id": token_record.device_id,
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
