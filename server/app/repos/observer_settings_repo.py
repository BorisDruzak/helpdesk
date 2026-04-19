"""Observer settings persisted in server_config."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ServerConfig


OBSERVER_SETTINGS_KEY = "observer_settings"
DEFAULT_OBSERVER_SETTINGS = {
    "success_trace_sample_rate": 0.35,
    "ok_trace_retention_hours": 24,
    "error_trace_retention_hours": 168,
    "historical_backfill_enabled": True,
    "action_sync_enabled": True,
    "action_sync_limit": 120,
    "always_keep_root_kinds": ["ticket", "agent_update", "module_install", "consent"],
}


class ObserverSettingsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _normalize_rate(value: Any, *, default: float) -> float:
        try:
            rate = float(value)
        except (TypeError, ValueError):
            return default
        if rate > 1:
            rate = rate / 100.0
        return min(max(rate, 0.0), 1.0)

    @staticmethod
    def _normalize_positive_int(value: Any, *, default: int, minimum: int = 1, maximum: int = 100000) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(parsed, maximum))

    @classmethod
    def _normalize_settings(cls, payload: Any) -> dict[str, Any]:
        if payload is None:
            return dict(DEFAULT_OBSERVER_SETTINGS)
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return dict(DEFAULT_OBSERVER_SETTINGS)
        if not isinstance(payload, dict):
            return dict(DEFAULT_OBSERVER_SETTINGS)

        current = dict(DEFAULT_OBSERVER_SETTINGS)
        current["success_trace_sample_rate"] = cls._normalize_rate(
            payload.get("success_trace_sample_rate"),
            default=DEFAULT_OBSERVER_SETTINGS["success_trace_sample_rate"],
        )
        current["ok_trace_retention_hours"] = cls._normalize_positive_int(
            payload.get("ok_trace_retention_hours"),
            default=DEFAULT_OBSERVER_SETTINGS["ok_trace_retention_hours"],
            maximum=24 * 365,
        )
        current["error_trace_retention_hours"] = cls._normalize_positive_int(
            payload.get("error_trace_retention_hours"),
            default=DEFAULT_OBSERVER_SETTINGS["error_trace_retention_hours"],
            maximum=24 * 365,
        )
        current["action_sync_limit"] = cls._normalize_positive_int(
            payload.get("action_sync_limit"),
            default=DEFAULT_OBSERVER_SETTINGS["action_sync_limit"],
            maximum=500,
        )
        historical_backfill_enabled = payload.get("historical_backfill_enabled")
        current["historical_backfill_enabled"] = (
            historical_backfill_enabled
            if isinstance(historical_backfill_enabled, bool)
            else DEFAULT_OBSERVER_SETTINGS["historical_backfill_enabled"]
        )
        action_sync_enabled = payload.get("action_sync_enabled")
        current["action_sync_enabled"] = (
            action_sync_enabled
            if isinstance(action_sync_enabled, bool)
            else DEFAULT_OBSERVER_SETTINGS["action_sync_enabled"]
        )

        raw_root_kinds = payload.get("always_keep_root_kinds")
        if isinstance(raw_root_kinds, str):
            raw_root_kinds = [part.strip() for part in raw_root_kinds.split(",")]
        if isinstance(raw_root_kinds, list):
            current["always_keep_root_kinds"] = [
                str(item).strip()
                for item in raw_root_kinds
                if str(item or "").strip()
            ] or list(DEFAULT_OBSERVER_SETTINGS["always_keep_root_kinds"])
        else:
            current["always_keep_root_kinds"] = list(DEFAULT_OBSERVER_SETTINGS["always_keep_root_kinds"])
        return current

    async def get_settings(self) -> dict[str, Any]:
        row = await self.session.execute(select(ServerConfig.value).where(ServerConfig.key == OBSERVER_SETTINGS_KEY))
        return self._normalize_settings(row.scalar_one_or_none())

    async def set_settings(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_settings()
        current.update(patch)
        normalized = self._normalize_settings(current)
        value = json.dumps(normalized, ensure_ascii=False)
        await self.session.execute(
            insert(ServerConfig)
            .values(key=OBSERVER_SETTINGS_KEY, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await self.session.flush()
        return normalized
