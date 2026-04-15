"""Repository for preferred module versions and rollout settings stored in server_config."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig


MODULE_PREFERRED_KEY_PREFIX = "module_preferred:"
MODULE_ROLLOUT_SETTINGS_KEY = "module_rollout_settings"
DEFAULT_MODULE_ROLLOUT_SETTINGS = {
    "preferred_version_rollout_mode": "manual",
    "sync_after_preferred_change": True,
}
ALLOWED_PREFERRED_VERSION_ROLLOUT_MODES = {"manual", "installed_devices"}


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

    @staticmethod
    def _normalize_settings(payload: object) -> dict:
        if payload is None:
            return dict(DEFAULT_MODULE_ROLLOUT_SETTINGS)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return dict(DEFAULT_MODULE_ROLLOUT_SETTINGS)
        if not isinstance(payload, dict):
            return dict(DEFAULT_MODULE_ROLLOUT_SETTINGS)

        mode = str(payload.get("preferred_version_rollout_mode") or "").strip().lower()
        if mode not in ALLOWED_PREFERRED_VERSION_ROLLOUT_MODES:
            mode = DEFAULT_MODULE_ROLLOUT_SETTINGS["preferred_version_rollout_mode"]

        sync_after_preferred_change = payload.get("sync_after_preferred_change")
        if not isinstance(sync_after_preferred_change, bool):
            sync_after_preferred_change = DEFAULT_MODULE_ROLLOUT_SETTINGS["sync_after_preferred_change"]

        return {
            "preferred_version_rollout_mode": mode,
            "sync_after_preferred_change": sync_after_preferred_change,
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

    async def get_settings(self) -> dict:
        row = await self.session.execute(
            select(ServerConfig.value).where(ServerConfig.key == MODULE_ROLLOUT_SETTINGS_KEY)
        )
        value = row.scalar_one_or_none()
        return self._normalize_settings(value)

    async def set_settings(
        self,
        *,
        preferred_version_rollout_mode: Optional[str] = None,
        sync_after_preferred_change: Optional[bool] = None,
    ) -> dict:
        current = await self.get_settings()
        payload = {
            "preferred_version_rollout_mode": (
                preferred_version_rollout_mode
                if preferred_version_rollout_mode is not None
                else current["preferred_version_rollout_mode"]
            ),
            "sync_after_preferred_change": (
                sync_after_preferred_change
                if sync_after_preferred_change is not None
                else current["sync_after_preferred_change"]
            ),
        }
        normalized = self._normalize_settings(payload)
        value = json.dumps(normalized, ensure_ascii=False)
        await self.session.execute(
            insert(ServerConfig)
            .values(key=MODULE_ROLLOUT_SETTINGS_KEY, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self.session.flush()
        return normalized
