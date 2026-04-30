"""
Сервис SLA тикетов (Этап 2).

- При create: старт FRT и Resolution по policy + priority (24x7).
- FRT закрывается первым public support/agent comment.
- В статусах Waiting on User/Vendor — пауза/возобновление с накоплением sla_paused_seconds.
- При reopen: сброс resolution timer, reopen_count++.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from app.db.models import Ticket, TicketBusinessCalendar, TicketSlaPolicy
from tickets.calendar_engine import add_business_minutes
from tickets.statuses import PRIORITY_CLASS_TO_LEGACY_PRIORITY, WAITING_STATUSES, TERMINAL_STATUSES, extract_priority_class


class TicketSlaService:
    """Управление SLA-таймерами тикетов (24x7 на этапе 2)."""

    def __init__(self, session, ticket_repo):
        self.session = session
        self.ticket_repo = ticket_repo

    async def _get_policy_and_targets(self, ticket: Ticket):
        """Политика SLA и цели по приоритету для тикета."""
        policy_id = ticket.sla_policy_id
        if not policy_id:
            policy = await self.ticket_repo.get_default_sla_policy()
            if not policy:
                return None, []
        else:
            policy = await self.session.get(TicketSlaPolicy, policy_id)
            if not policy or not getattr(policy, "is_active", True):
                return None, []
        targets = await self.ticket_repo.get_sla_targets(policy.id)
        return policy, targets

    async def _calendar_for_policy(self, policy: TicketSlaPolicy | None) -> dict | None:
        if not policy:
            return None
        if getattr(policy, "calendar_id", None):
            calendar = await self.session.get(TicketBusinessCalendar, policy.calendar_id)
            if calendar and getattr(calendar, "is_active", True):
                return {
                    "timezone": calendar.timezone,
                    "weekly_hours_json": calendar.weekly_hours_json or [],
                    "holidays_json": calendar.holidays_json or [],
                }
        business_hours = getattr(policy, "business_hours_json", None)
        if isinstance(business_hours, dict):
            return {
                "timezone": business_hours.get("timezone") or getattr(policy, "timezone", None) or "UTC",
                "weekly_hours_json": business_hours.get("weekly_hours_json")
                or business_hours.get("weekly_hours")
                or [],
                "holidays_json": business_hours.get("holidays_json") or business_hours.get("holidays") or [],
            }
        if isinstance(business_hours, list):
            return {
                "timezone": getattr(policy, "timezone", None) or "UTC",
                "weekly_hours_json": business_hours,
                "holidays_json": [],
            }
        return None

    def _due_at(self, start: datetime, minutes: int, calendar: dict | None) -> datetime:
        return add_business_minutes(start, minutes, calendar)

    def _target_for_priority(self, targets: list, priority: Optional[str]):
        """Цель SLA по приоритету (first_response_min, resolution_min)."""
        if not priority:
            priority = "P3"
        for t in targets:
            if t.priority == priority:
                return t
        legacy_priority = PRIORITY_CLASS_TO_LEGACY_PRIORITY.get(priority)
        if legacy_priority:
            for t in targets:
                if t.priority == legacy_priority:
                    return t
        for t in targets:
            if t.priority == "P3":
                return t
        return targets[0] if targets else None

    async def start_sla(self, ticket: Ticket) -> bool:
        """
        Запустить SLA для тикета: установить first_response_due_at и resolution_due_at.
        Используется при создании тикета. Календарь 24x7 — просто добавляем минуты к now().
        """
        policy, targets = await self._get_policy_and_targets(ticket)
        if not policy or not targets:
            return False
        target = self._target_for_priority(targets, extract_priority_class(ticket))
        if not target:
            return False
        now = datetime.now(timezone.utc)
        calendar = await self._calendar_for_policy(policy)
        fr_due = self._due_at(now, target.first_response_min, calendar)
        res_due = self._due_at(now, target.resolution_min, calendar)
        await self.ticket_repo.update_ticket(
            ticket.ticket_id,
            sla_policy_id=policy.id,
            first_response_due_at=fr_due,
            resolution_due_at=res_due,
        )
        logger.debug(
            f"[SLA] Started for ticket_id={ticket.ticket_id} "
            f"FRT due {fr_due.isoformat()} resolution due {res_due.isoformat()}"
        )
        return True

    async def close_frt(self, ticket_id: str) -> bool:
        """Закрыть FRT: зафиксировать first_response_at (при первом public support/agent comment)."""
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket or ticket.first_response_at is not None:
            return False
        now = datetime.now(timezone.utc)
        await self.ticket_repo.update_ticket(ticket_id, first_response_at=now)
        logger.debug(f"[SLA] FRT closed for ticket_id={ticket_id}")
        return True

    async def pause_sla(self, ticket_id: str) -> bool:
        """Поставить SLA на паузу (Waiting on User/Vendor): записать sla_paused_at."""
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket:
            return False
        if ticket.sla_paused_at is not None:
            return True  # уже на паузе
        now = datetime.now(timezone.utc)
        await self.ticket_repo.update_ticket(ticket_id, sla_paused_at=now)
        logger.debug(f"[SLA] Paused for ticket_id={ticket_id}")
        return True

    async def resume_sla(self, ticket_id: str) -> bool:
        """Снять паузу: накопить sla_paused_seconds и очистить sla_paused_at."""
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket:
            return False
        if ticket.sla_paused_at is None:
            return True
        now = datetime.now(timezone.utc)
        delta_sec = int((now - ticket.sla_paused_at).total_seconds())
        prev_paused = ticket.sla_paused_seconds or 0
        await self.ticket_repo.update_ticket(
            ticket_id,
            sla_paused_seconds=prev_paused + delta_sec,
            sla_paused_at=None,
        )
        logger.debug(f"[SLA] Resumed for ticket_id={ticket_id} added_pause_sec={delta_sec}")
        return True

    async def on_reopen(self, ticket_id: str) -> bool:
        """После reopen: сброс resolution SLA (новый due_at) и reopen_count++."""
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket:
            return False
        policy, targets = await self._get_policy_and_targets(ticket)
        target = self._target_for_priority(targets, extract_priority_class(ticket))
        if not target:
            return False
        now = datetime.now(timezone.utc)
        calendar = await self._calendar_for_policy(policy)
        new_res_due = self._due_at(now, target.resolution_min, calendar)
        new_count = (ticket.reopen_count or 0) + 1
        await self.ticket_repo.update_ticket(
            ticket_id,
            resolution_due_at=new_res_due,
            first_response_breached_at=None,
            resolution_breached_at=None,
            reopen_count=new_count,
        )
        logger.debug(f"[SLA] Reopen ticket_id={ticket_id} new resolution_due_at={new_res_due} reopen_count={new_count}")
        return True

    async def recalc_due_for_priority(self, ticket_id: str, new_priority: str) -> bool:
        """Пересчитать first_response_due_at и resolution_due_at при смене приоритета (Stage 10.3)."""
        ticket = await self.ticket_repo.get_ticket(ticket_id)
        if not ticket:
            return False
        policy, targets = await self._get_policy_and_targets(ticket)
        target = self._target_for_priority(targets, new_priority)
        if not target:
            return False
        now = datetime.now(timezone.utc)
        calendar = await self._calendar_for_policy(policy)
        fr_due = self._due_at(now, target.first_response_min, calendar)
        res_due = self._due_at(now, target.resolution_min, calendar)
        update_kw = {
            "resolution_due_at": res_due,
            "first_response_breached_at": None,
            "resolution_breached_at": None,
        }
        if ticket.first_response_at is None:
            update_kw["first_response_due_at"] = fr_due
        await self.ticket_repo.update_ticket(ticket_id, **update_kw)
        logger.debug(
            f"[SLA] Recalc for ticket_id={ticket_id} priority={new_priority} "
            f"FRT due {update_kw.get('first_response_due_at', 'unchanged')} resolution due {res_due.isoformat()}"
        )
        return True
