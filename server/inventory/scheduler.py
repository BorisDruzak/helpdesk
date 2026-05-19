from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import uuid
from typing import Any, Callable

from loguru import logger

from app.db import get_session
from config import INVENTORY_REFRESH_SCHEDULER_ENABLED, INVENTORY_REFRESH_SCHEDULER_INTERVAL_SEC
from inventory.service import DeviceInventoryService, INVENTORY_TOOL_ID
from tools.service import ToolExecutionService


def _online_device_ids(state: Any) -> list[str]:
    connected = getattr(state, "connected_agents", None)
    if not isinstance(connected, dict):
        return []
    checker = getattr(state, "is_agent_online", None)
    result: list[str] = []
    for device_id in list(connected.keys()):
        if callable(checker):
            try:
                if not checker(device_id):
                    continue
            except Exception:
                continue
        result.append(str(device_id))
    return result


class InventoryRefreshRuntime:
    """Periodic dispatcher for inventory.collect using the existing tool path."""

    def __init__(
        self,
        *,
        state: Any,
        interval_sec: int = INVENTORY_REFRESH_SCHEDULER_INTERVAL_SEC,
        enabled: bool = INVENTORY_REFRESH_SCHEDULER_ENABLED,
        tool_service_factory: Callable[[Any], ToolExecutionService] = ToolExecutionService,
    ):
        self.state = state
        self.interval_sec = max(10, int(interval_sec or 60))
        self.enabled = bool(enabled)
        self.tool_service_factory = tool_service_factory
        self._task: asyncio.Task | None = None
        self._running = False
        self.last_run_at: datetime | None = None
        self.last_dispatch_count = 0

    async def start(self) -> None:
        if self._running or not self.enabled:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="inventory-refresh-runtime")
        logger.info("[inventory_refresh] runtime started")

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("[inventory_refresh] runtime stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.opt(exception=exc).warning("[inventory_refresh] loop failed")
            await asyncio.sleep(self.interval_sec)

    async def run_once(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        dispatched = 0
        skipped_offline = 0
        async with get_session() as session:
            service = DeviceInventoryService(session)
            due = await service.list_due_refresh_policies(now=now)
            tool_service = self.tool_service_factory(self.state)
            for policy in due:
                if getattr(policy, "scope", None) == "device":
                    device_ids = [str(policy.device_id)] if policy.device_id else []
                else:
                    device_ids = _online_device_ids(self.state)
                if not device_ids:
                    skipped_offline += 1
                    continue
                policy_dispatched = 0
                for device_id in device_ids:
                    checker = getattr(self.state, "is_agent_online", None)
                    if callable(checker) and not checker(device_id):
                        skipped_offline += 1
                        continue
                    operation_id = str(uuid.uuid4())
                    result = await tool_service.run_tool(
                        device_id=device_id,
                        ticket_id="",
                        tool_name=INVENTORY_TOOL_ID,
                        params={"_operation_id": operation_id, "source": "inventory_refresh_policy"},
                        call_id=str(uuid.uuid4()),
                        auth_context=None,
                        wait_for_result=False,
                    )
                    status = str(result.get("status") or "")
                    if status in {"accepted", "queued", "sent", "waiting_consent"}:
                        dispatched += 1
                        policy_dispatched += 1
                if policy_dispatched:
                    await service.mark_refresh_requested(policy, requested_at=now)
            await session.commit()
        self.last_run_at = now
        self.last_dispatch_count = dispatched
        return {"due": len(due), "dispatched": dispatched, "skipped_offline": skipped_offline}

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_sec": self.interval_sec,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_dispatch_count": self.last_dispatch_count,
        }
