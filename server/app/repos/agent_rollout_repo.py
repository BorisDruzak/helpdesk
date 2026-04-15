"""Repository for global agent rollout assignments stored in server_config."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig


ROLLOUT_KEY_PREFIX = "agent_rollout:"


class AgentRolloutRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _config_key(target: str) -> str:
        return f"{ROLLOUT_KEY_PREFIX}{target}"

    @staticmethod
    def _normalize_payload(target: str, payload: object) -> Optional[dict]:
        if payload is None:
            return None
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return None
        if not isinstance(payload, dict):
            return None
        version = str(payload.get("version") or "").strip()
        channel = str(payload.get("channel") or "").strip().lower()
        if not version or not channel:
            return None
        return {
            "target": target,
            "channel": channel,
            "version": version,
            "updated_at": payload.get("updated_at"),
            "updated_by": payload.get("updated_by"),
        }

    async def get_assignment(self, target: str) -> Optional[dict]:
        row = await self.session.execute(
            select(ServerConfig.value).where(ServerConfig.key == self._config_key(target))
        )
        value = row.scalar_one_or_none()
        return self._normalize_payload(target, value)

    async def list_assignments(self) -> list[dict]:
        rows = await self.session.execute(
            select(ServerConfig.key, ServerConfig.value).where(ServerConfig.key.like(f"{ROLLOUT_KEY_PREFIX}%"))
        )
        result: list[dict] = []
        for key, value in rows.all():
            target = str(key)[len(ROLLOUT_KEY_PREFIX) :]
            normalized = self._normalize_payload(target, value)
            if normalized:
                result.append(normalized)
        result.sort(key=lambda item: item["target"])
        return result

    async def set_assignment(
        self,
        *,
        target: str,
        channel: str,
        version: str,
        updated_by: Optional[str] = None,
    ) -> dict:
        payload = {
            "target": target,
            "channel": channel,
            "version": version,
            "updated_by": updated_by,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        value = json.dumps(payload, ensure_ascii=False)
        await self.session.execute(
            insert(ServerConfig)
            .values(key=self._config_key(target), value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self.session.flush()
        return payload

    async def clear_assignment(self, target: str) -> None:
        await self.session.execute(delete(ServerConfig).where(ServerConfig.key == self._config_key(target)))
        await self.session.flush()
