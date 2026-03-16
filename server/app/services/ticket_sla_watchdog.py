"""
Ticket SLA Watchdog — периодическая проверка breach SLA и напоминания.

- Сканирует тикеты с истёкшим first_response_due_at или resolution_due_at.
- При первом breach: проставляет *_breached_at, событие sla_breached, push в UI.
- Reminders каждые 60 минут: sla_reminder_sent, push в UI.
- Остановка reminders при Resolved/Closed.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from loguru import logger

from app.db import get_session
from app.repos.ticket_events_repo import TicketEventsRepo

SLA_REMINDER_INTERVAL_SEC = 60 * 60  # 60 минут
SLA_LAST_REMINDER_AT_KEY = "sla_last_reminder_at"


class TicketSlaWatchdog:
    """
    Watchdog для SLA тикетов: breach и напоминания.
    """

    def __init__(self, interval: Optional[int] = None, state=None):
        self.interval = interval or 120  # проверка каждые 2 мин
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._state = state  # для push_ticket_event_committed

    async def _check_breaches(self) -> None:
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                candidates = await repo.get_tickets_sla_breach_candidates(limit=100)
                if not candidates:
                    return

                now = datetime.now(timezone.utc)
                for ticket in candidates:
                    try:
                        # Первый breach: проставить *_breached_at если ещё не проставлено
                        updates = {}
                        if (
                            ticket.first_response_due_at
                            and ticket.first_response_at is None
                            and ticket.first_response_breached_at is None
                        ):
                            effective_fr = ticket.first_response_due_at + timedelta(
                                seconds=ticket.sla_paused_seconds or 0
                            )
                            if now >= effective_fr:
                                updates["first_response_breached_at"] = now
                        if (
                            ticket.resolution_due_at
                            and ticket.resolution_at is None
                            and ticket.resolution_breached_at is None
                        ):
                            effective_res = ticket.resolution_due_at + timedelta(
                                seconds=ticket.sla_paused_seconds or 0
                            )
                            if now >= effective_res:
                                updates["resolution_breached_at"] = now

                        if updates:
                            await repo.update_ticket(ticket.ticket_id, **updates)
                            trace_id = str(uuid.uuid4())
                            payload = {
                                "ticket_id": ticket.ticket_id,
                                "breach_types": list(updates.keys()),
                                "ts": now.isoformat(),
                            }
                            ev_result = await repo.add_event(
                                ticket_id=ticket.ticket_id,
                                device_id=ticket.device_id,
                                agent_seq=None,
                                event_type="sla_breached",
                                payload=payload,
                                trace_id=trace_id,
                            )
                            if ev_result and self._state and self._state.subscription_registry:
                                from websocket.ui_handler import push_ticket_event_committed
                                await push_ticket_event_committed(
                                    self._state,
                                    ticket_id=ticket.ticket_id,
                                    event_id=ev_result[0],
                                    event_type="sla_breached",
                                    operation_id=None,
                                    agent_seq=None,
                                    created_at=ev_result[1],
                                    payload=payload,
                                )
                            try:
                                from app.repos.notification_repo import NotificationRepo
                                from app.repos.notification_prefs_repo import NotificationPrefsRepo
                                from tickets.notification_service import notify_ticket_event
                                notif_repo = NotificationRepo(session)
                                prefs_repo = NotificationPrefsRepo(session)
                                await notify_ticket_event(
                                    repo, notif_repo, ticket.ticket_id, "sla_breached", payload, visibility="internal",
                                    initiator_id="system", prefs_repo=prefs_repo,
                                )
                            except Exception as notif_err:
                                logger.warning(f"[TicketSlaWatchdog] notification sla_breached: {notif_err}")
                            logger.warning(
                                f"[TicketSlaWatchdog] Breach ticket_id={ticket.ticket_id} updates={updates}"
                            )
                    except Exception as e:
                        logger.error(
                            f"[TicketSlaWatchdog] Error processing ticket {ticket.ticket_id}: {e}",
                            exc_info=True,
                        )

                await session.commit()
        except Exception as e:
            logger.error(f"[TicketSlaWatchdog] Error in _check_breaches: {e}", exc_info=True)

    async def _check_reminders(self) -> None:
        """Отправка напоминаний раз в 60 минут по тикетам в breach."""
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                # Тикеты с breach и не resolved/closed
                from sqlalchemy import select, and_
                from app.db.models import Ticket

                stmt = select(Ticket).where(
                    and_(
                        Ticket.status.notin_(["resolved", "closed"]),
                        Ticket.resolution_breached_at.isnot(None),
                    )
                ).limit(100)
                result = await session.execute(stmt)
                tickets = list(result.scalars().all())
                now = datetime.now(timezone.utc)
                interval = timedelta(seconds=SLA_REMINDER_INTERVAL_SEC)

                for ticket in tickets:
                    try:
                        last_at = None
                        if ticket.custom_fields and isinstance(ticket.custom_fields, dict):
                            raw = ticket.custom_fields.get(SLA_LAST_REMINDER_AT_KEY)
                            if raw:
                                try:
                                    last_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                                except Exception:
                                    pass
                        if last_at and (now - last_at) < interval:
                            continue
                        cf = dict(ticket.custom_fields or {})
                        cf[SLA_LAST_REMINDER_AT_KEY] = now.isoformat()
                        await repo.update_ticket(ticket.ticket_id, custom_fields=cf)
                        trace_id = str(uuid.uuid4())
                        ev_result = await repo.add_event(
                            ticket_id=ticket.ticket_id,
                            device_id=ticket.device_id,
                            agent_seq=None,
                            event_type="sla_reminder_sent",
                            payload={
                                "ticket_id": ticket.ticket_id,
                                "ts": now.isoformat(),
                            },
                            trace_id=trace_id,
                        )
                        if ev_result and self._state and self._state.subscription_registry:
                            from websocket.ui_handler import push_ticket_event_committed
                            await push_ticket_event_committed(
                                self._state,
                                ticket_id=ticket.ticket_id,
                                event_id=ev_result[0],
                                event_type="sla_reminder_sent",
                                operation_id=None,
                                agent_seq=None,
                                created_at=ev_result[1],
                                payload={"ticket_id": ticket.ticket_id, "ts": now.isoformat()},
                            )
                        try:
                            from app.repos.notification_repo import NotificationRepo
                            from app.repos.notification_prefs_repo import NotificationPrefsRepo
                            from tickets.notification_service import notify_ticket_event
                            notif_repo = NotificationRepo(session)
                            prefs_repo = NotificationPrefsRepo(session)
                            await notify_ticket_event(
                                repo, notif_repo, ticket.ticket_id, "sla_reminder_sent",
                                {"ticket_id": ticket.ticket_id, "ts": now.isoformat()}, visibility="internal",
                                initiator_id="system", prefs_repo=prefs_repo,
                            )
                        except Exception as notif_err:
                            logger.warning(f"[TicketSlaWatchdog] notification sla_reminder_sent: {notif_err}")
                        logger.info(f"[TicketSlaWatchdog] Reminder sent ticket_id={ticket.ticket_id}")
                    except Exception as e:
                        logger.error(
                            f"[TicketSlaWatchdog] Error reminder ticket {ticket.ticket_id}: {e}",
                            exc_info=True,
                        )

                await session.commit()
        except Exception as e:
            logger.error(f"[TicketSlaWatchdog] Error in _check_reminders: {e}", exc_info=True)

    async def _run_loop(self) -> None:
        logger.info(f"[TicketSlaWatchdog] Started interval={self.interval}s")
        while self._running:
            try:
                await self._check_breaches()
                await self._check_reminders()
            except Exception as e:
                logger.error(f"[TicketSlaWatchdog] Loop error: {e}", exc_info=True)
            await asyncio.sleep(self.interval)
        logger.info("[TicketSlaWatchdog] Stopped")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[TicketSlaWatchdog] Starting...")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[TicketSlaWatchdog] Stopping...")

    async def force_check(self) -> None:
        await self._check_breaches()
        await self._check_reminders()


_ticket_sla_watchdog_instance: Optional[TicketSlaWatchdog] = None


def get_ticket_sla_watchdog(state=None) -> TicketSlaWatchdog:
    global _ticket_sla_watchdog_instance
    if _ticket_sla_watchdog_instance is None:
        _ticket_sla_watchdog_instance = TicketSlaWatchdog(state=state)
    return _ticket_sla_watchdog_instance
