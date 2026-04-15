"""Repository for preferred module versions stored in server_config."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig


MODULE_PREFERRED_KEY_PREFIX = "module_preferred:"


class ModuleRolloutRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _config_key(module_name: str) -> str:
        return f"{MODULE_PREFERRED_KEY_PREFIX}{module_name}"

    @staticmethod
    def _normalize_payload(module_name: str, payload: object) -> Optional[dict]:
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
        if not version:
            return None
        return {
            "module_name": module_name,
            "version": version,
            "updated_at": payload.get("updated_at"),
            "updated_by": payload.get("updated_by"),
        }

    async def get_assignment(self, module_name: str) -> Optional[dict]:
        row = await self.session.execute(
            select(ServerConfig.value).where(ServerConfig.key == self._config_key(module_name))
        )
        value = row.scalar_one_or_none()
        return self._normalize_payload(module_name, value)

    async def list_assignments(self) -> list[dict]:
        rows = await self.session.execute(
            select(ServerConfig.key, ServerConfig.value).where(ServerConfig.key.like(f"{MODULE_PREFERRED_KEY_PREFIX}%"))
        )
        result: list[dict] = []
        for key, value in rows.all():
            module_name = str(key)[len(MODULE_PREFERRED_KEY_PREFIX) :]
            normalized = self._normalize_payload(module_name, value)
            if normalized:
                result.append(normalized)
        result.sort(key=lambda item: item["module_name"])
        return result

    async def set_assignment(
        self,
        *,
        module_name: str,
        version: str,
        updated_by: Optional[str] = None,
    ) -> dict:
        payload = {
            "module_name": module_name,
            "version": version,
            "updated_by": updated_by,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        value = json.dumps(payload, ensure_ascii=False)
        await self.session.execute(
            insert(ServerConfig)
            .values(key=self._config_key(module_name), value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self.session.flush()
        return payload

    async def clear_assignment(self, module_name: str) -> None:
        await self.session.execute(delete(ServerConfig).where(ServerConfig.key == self._config_key(module_name)))
        await self.session.flush()
