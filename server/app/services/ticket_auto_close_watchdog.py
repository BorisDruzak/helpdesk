"""Close expired requester confirmations."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger
from app.db import get_session
from app.repos.ticket_events_repo import TicketEventsRepo
from config import TICKET_AUTO_CLOSE_HOURS
from tickets.workflow_service import TicketWorkflowService

AUTO_CLOSE_INTERVAL_SEC = 60


class TicketAutoCloseWatchdog:
    """Background watchdog for policy-controlled requester-confirmation expiry."""

    def __init__(self, interval: Optional[int] = None, state=None, session_factory=None):
        self.interval = interval or AUTO_CLOSE_INTERVAL_SEC
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._state = state
        self._session_factory = session_factory

    async def process_once(self, *, now: datetime | None = None, limit: int = 100) -> int:
        """Close only unresolved confirmations that reached the configured deadline."""
        effective_now = now or datetime.now(timezone.utc)
        resolved_before = effective_now - timedelta(hours=TICKET_AUTO_CLOSE_HOURS)
        session_factory = self._session_factory or get_session
        closed_count = 0
        async with session_factory() as session:
            repo = TicketEventsRepo(session)
            workflow = TicketWorkflowService(session, repo)
            for ticket in await repo.get_tickets_auto_close_candidates(resolved_before, limit=limit):
                ticket_id = ticket.ticket_id
                try:
                    async with session.begin_nested():
                        await workflow.apply_status_transition(
                            ticket_id=ticket_id,
                            from_status="resolved",
                            to_status="closed",
                            actor_id="system",
                            actor_role="system",
                            reason="requester_confirmation_auto_close",
                            source="closure_policy_auto_close",
                        )
                        custom_fields = dict(ticket.custom_fields or {})
                        confirmation = dict(custom_fields["resolution_confirmation"])
                        confirmation.update(pending=False, responded_option_id="auto_close",
                                            auto_closed_at=effective_now.isoformat())
                        custom_fields["resolution_confirmation"] = confirmation
                        custom_fields["resolution_confirmation_pending"] = False
                        await repo.update_ticket(ticket_id, custom_fields=custom_fields)
                except ValueError:
                    logger.warning(f"[TicketAutoCloseWatchdog] transition rejected ticket_id={ticket_id}")
                    continue
                closed_count += 1
            await session.commit()
        if closed_count:
            logger.info(f"[TicketAutoCloseWatchdog] auto-closed tickets count={closed_count}")
        return closed_count

    async def _run_cycle(self) -> None:
        closed_count = await self.process_once()
        logger.debug(f"[TicketAutoCloseWatchdog] cycle complete closed_count={closed_count}")

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
