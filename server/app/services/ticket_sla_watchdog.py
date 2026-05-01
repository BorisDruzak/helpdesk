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
from sqlalchemy import and_, select

from app.db import get_session
from app.db.models import Ticket
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.sla_service import (
    _duration_to_minutes,
    _sla_policy_metadata,
    _standalone_sla_policy_config,
)

SLA_REMINDER_INTERVAL_SEC = 60 * 60  # 60 минут
SLA_LAST_REMINDER_AT_KEY = "sla_last_reminder_at"
SLA_LAST_WARNING_AT_KEY = "sla_last_warning_at"


def _sla_breach_actions(policy: dict | None) -> dict:
    if not isinstance(policy, dict):
        return {}
    actions = policy.get("breach_actions") or {}
    return dict(actions) if isinstance(actions, dict) else {}


def _warning_before_minutes(policy: dict | None, warning_type: str) -> int | None:
    if not isinstance(policy, dict):
        return None
    warnings = policy.get("warnings") or {}
    if not isinstance(warnings, dict):
        warnings = {}
    warning_before = (
        warnings.get("warning_before")
        or policy.get("warning_before")
        or _sla_breach_actions(policy).get("warning_before")
        or {}
    )
    if isinstance(warning_before, dict):
        return _duration_to_minutes(warning_before.get(warning_type))
    return _duration_to_minutes(warning_before)


def _last_warning_map(ticket: Ticket) -> dict[str, str]:
    custom_fields = ticket.custom_fields if isinstance(ticket.custom_fields, dict) else {}
    raw = custom_fields.get(SLA_LAST_WARNING_AT_KEY)
    return dict(raw) if isinstance(raw, dict) else {}


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
                            policy = _standalone_sla_policy_config(ticket)
                            payload = {
                                "ticket_id": ticket.ticket_id,
                                "breach_types": list(updates.keys()),
                                "ts": now.isoformat(),
                                "sla_policy": _sla_policy_metadata(policy),
                                "breach_actions": _sla_breach_actions(policy),
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

    async def _check_warnings(self) -> None:
        """Emit one pre-breach warning per configured SLA timer."""
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                stmt = (
                    select(Ticket)
                    .where(
                        and_(
                            Ticket.status.notin_(["resolved", "closed", "canceled"]),
                            Ticket.sla_paused_at.is_(None),
                            (
                                (Ticket.first_response_due_at.isnot(None) & Ticket.first_response_at.is_(None))
                                | (Ticket.resolution_due_at.isnot(None) & Ticket.resolution_at.is_(None))
                            ),
                        )
                    )
                    .limit(100)
                )
                rows = await session.execute(stmt)
                tickets = list(rows.scalars().all())
                if not tickets:
                    return
                now = datetime.now(timezone.utc)
                for ticket in tickets:
                    try:
                        policy = _standalone_sla_policy_config(ticket)
                        if not policy:
                            continue
                        last_warnings = _last_warning_map(ticket)
                        for warning_type, due_at, completed_at in (
                            ("first_response", ticket.first_response_due_at, ticket.first_response_at),
                            ("resolution", ticket.resolution_due_at, ticket.resolution_at),
                        ):
                            if not due_at or completed_at is not None or last_warnings.get(warning_type):
                                continue
                            minutes = _warning_before_minutes(policy, warning_type)
                            if minutes is None:
                                continue
                            effective_due = due_at + timedelta(seconds=ticket.sla_paused_seconds or 0)
                            warning_at = effective_due - timedelta(minutes=minutes)
                            if not (warning_at <= now < effective_due):
                                continue
                            cf = dict(ticket.custom_fields or {})
                            warning_map = dict(last_warnings)
                            warning_map[warning_type] = now.isoformat()
                            cf[SLA_LAST_WARNING_AT_KEY] = warning_map
                            await repo.update_ticket(ticket.ticket_id, custom_fields=cf)
                            payload = {
                                "ticket_id": ticket.ticket_id,
                                "warning_type": warning_type,
                                "due_at": effective_due.isoformat(),
                                "ts": now.isoformat(),
                                "sla_policy": _sla_policy_metadata(policy),
                                "breach_actions": _sla_breach_actions(policy),
                            }
                            ev_result = await repo.add_event(
                                ticket_id=ticket.ticket_id,
                                device_id=ticket.device_id,
                                agent_seq=None,
                                event_type="sla_warning",
                                payload=payload,
                                trace_id=str(uuid.uuid4()),
                            )
                            if ev_result and self._state and self._state.subscription_registry:
                                from websocket.ui_handler import push_ticket_event_committed

                                await push_ticket_event_committed(
                                    self._state,
                                    ticket_id=ticket.ticket_id,
                                    event_id=ev_result[0],
                                    event_type="sla_warning",
                                    operation_id=None,
                                    agent_seq=None,
                                    created_at=ev_result[1],
                                    payload=payload,
                                )
                            last_warnings = warning_map
                    except Exception as e:
                        logger.error(
                            f"[TicketSlaWatchdog] Error warning ticket {ticket.ticket_id}: {e}",
                            exc_info=True,
                        )
                await session.commit()
        except Exception as e:
            logger.error(f"[TicketSlaWatchdog] Error in _check_warnings: {e}", exc_info=True)

    async def _check_reminders(self) -> None:
        """Отправка напоминаний раз в 60 минут по тикетам в breach."""
        try:
            async with get_session() as session:
                repo = TicketEventsRepo(session)
                # Тикеты с breach и не resolved/closed
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
                await self._check_warnings()
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
        await self._check_warnings()
        await self._check_breaches()
        await self._check_reminders()


_ticket_sla_watchdog_instance: Optional[TicketSlaWatchdog] = None


def get_ticket_sla_watchdog(state=None) -> TicketSlaWatchdog:
    global _ticket_sla_watchdog_instance
    if _ticket_sla_watchdog_instance is None:
        _ticket_sla_watchdog_instance = TicketSlaWatchdog(state=state)
    return _ticket_sla_watchdog_instance
