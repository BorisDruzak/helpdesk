"""Ticket auto-close watchdog driven by closure policy metadata."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import select

from app.db import get_session
from app.db.models import Ticket
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.workflow_service import TicketWorkflowService

AUTO_CLOSE_INTERVAL_SEC = 3600  # hourly heartbeat


class TicketAutoCloseWatchdog:
    """Background watchdog for policy-controlled requester-confirmation expiry."""

    def __init__(self, interval: Optional[int] = None, state=None, session_factory=None):
        self.interval = interval or AUTO_CLOSE_INTERVAL_SEC
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._state = state
        self._session_factory = session_factory

    @staticmethod
    def _confirmation_policy(ticket: Ticket) -> dict:
        custom_fields = getattr(ticket, "custom_fields", None) or {}
        if not isinstance(custom_fields, dict):
            return {}
        policy = custom_fields.get("resolution_confirmation_policy")
        return dict(policy) if isinstance(policy, dict) else {}

    @staticmethod
    def _confirmation_pending(ticket: Ticket) -> bool:
        custom_fields = getattr(ticket, "custom_fields", None) or {}
        if not isinstance(custom_fields, dict):
            return False
        state = custom_fields.get("resolution_confirmation")
        return bool(isinstance(state, dict) and state.get("pending"))

    @staticmethod
    def _auto_close_days(policy: dict) -> int | None:
        raw = policy.get("auto_close_after_days")
        if raw in (None, ""):
            return None
        try:
            days = int(raw)
        except (TypeError, ValueError):
            return None
        return days if days > 0 else None

    async def process_once(self, *, now: datetime | None = None, limit: int = 100) -> int:
        """Close resolved tickets whose closure policy auto-close deadline passed."""
        effective_now = now or datetime.now(timezone.utc)
        session_factory = self._session_factory or get_session
        closed_count = 0
        async with session_factory() as session:
            result = await session.execute(
                select(Ticket)
                .where(
                    Ticket.status == "resolved",
                    Ticket.resolved_at.isnot(None),
                )
                .order_by(Ticket.resolved_at.asc())
                .limit(limit)
            )
            repo = TicketEventsRepo(session)
            workflow = TicketWorkflowService(session, repo)
            for ticket in result.scalars().all():
                policy = self._confirmation_policy(ticket)
                if not policy or not bool(policy.get("required")):
                    continue
                auto_close_days = self._auto_close_days(policy)
                if auto_close_days is None or not self._confirmation_pending(ticket):
                    continue
                resolved_at = ticket.resolved_at
                if resolved_at is None:
                    continue
                if resolved_at.tzinfo is None:
                    resolved_at = resolved_at.replace(tzinfo=timezone.utc)
                if resolved_at + timedelta(days=auto_close_days) > effective_now:
                    continue
                await workflow.apply_status_transition(
                    ticket_id=ticket.ticket_id,
                    from_status=ticket.status,
                    to_status="closed",
                    actor_id="system",
                    actor_role="system",
                    reason="requester_confirmation_auto_close",
                    source="closure_policy_auto_close",
                )
                refreshed = await repo.get_ticket(ticket.ticket_id)
                custom_fields = dict(getattr(refreshed, "custom_fields", None) or {})
                confirmation = dict(custom_fields.get("resolution_confirmation") or {})
                confirmation["pending"] = False
                confirmation["responded_option_id"] = "auto_close"
                confirmation["auto_closed_at"] = effective_now.isoformat()
                custom_fields["resolution_confirmation"] = confirmation
                custom_fields["resolution_confirmation_pending"] = False
                await repo.update_ticket(ticket.ticket_id, custom_fields=custom_fields)
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
