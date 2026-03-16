"""Ticket auto-close watchdog.

Resolved tickets are no longer closed automatically. The watchdog stays in
place as a background hook, but only logs that requester confirmation is
required before moving a ticket to ``closed``.
"""

import asyncio
from typing import Optional

from loguru import logger

AUTO_CLOSE_INTERVAL_SEC = 3600  # hourly heartbeat


class TicketAutoCloseWatchdog:
    """Background watchdog that keeps the resolved-ticket policy explicit."""

    def __init__(self, interval: Optional[int] = None, state=None):
        self.interval = interval or AUTO_CLOSE_INTERVAL_SEC
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._state = state

    async def _run_cycle(self) -> None:
        logger.debug(
            "[TicketAutoCloseWatchdog] Auto-close disabled: resolved tickets "
            "must be confirmed by requester before closing"
        )

    async def _loop(self) -> None:
        logger.info(f"[TicketAutoCloseWatchdog] Started interval={self.interval}s")
        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"[TicketAutoCloseWatchdog] Loop error: {e}", exc_info=True)
            await asyncio.sleep(self.interval)
        logger.info("[TicketAutoCloseWatchdog] Stopped")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("[TicketAutoCloseWatchdog] Starting...")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[TicketAutoCloseWatchdog] Stopping...")


_auto_close_watchdog_instance: Optional[TicketAutoCloseWatchdog] = None


def get_ticket_auto_close_watchdog(state=None) -> TicketAutoCloseWatchdog:
    global _auto_close_watchdog_instance
    if _auto_close_watchdog_instance is None:
        _auto_close_watchdog_instance = TicketAutoCloseWatchdog(state=state)
    return _auto_close_watchdog_instance
