"""
Сервис назначения исполнителей по лимиту активной нагрузки.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from tickets.statuses import is_active_operator_status


MAX_ACTIVE_TICKETS_PER_OPERATOR = 3


class TicketAssignmentError(ValueError):
    """Ошибка назначения тикета."""


class TicketAssignmentService:
    def __init__(self, ticket_repo):
        self.ticket_repo = ticket_repo

    async def get_operator_loads(self) -> list[Dict[str, Any]]:
        return await self.ticket_repo.list_assignable_users_with_load()

    async def validate_manual_assignment(self, ticket: Any, assignee_id: Optional[str]) -> None:
        if not assignee_id:
            return
        if not is_active_operator_status(getattr(ticket, "status", None)):
            return
        if getattr(ticket, "assignee_id", None) == assignee_id:
            return
        active_count = await self.ticket_repo.count_active_tickets_for_assignee(assignee_id)
        if active_count >= MAX_ACTIVE_TICKETS_PER_OPERATOR:
            raise TicketAssignmentError(
                f"Оператор {assignee_id} уже достиг лимита {MAX_ACTIVE_TICKETS_PER_OPERATOR} активных тикетов"
            )

    async def resolve_assignee(
        self,
        ticket: Any,
        *,
        requested_assignee_id: Optional[str],
        auto_assign: bool,
    ) -> Dict[str, Any]:
        if auto_assign:
            user_login = await self.ticket_repo.select_assignee_for_update(MAX_ACTIVE_TICKETS_PER_OPERATOR)
            if not user_login:
                raise TicketAssignmentError("Нет доступных операторов для назначения")
            actual_count = await self.ticket_repo.count_active_tickets_for_assignee(user_login)
            return {
                "assignee_id": user_login,
                "active_count": actual_count,
                "auto_assigned": True,
            }
        await self.validate_manual_assignment(ticket, requested_assignee_id)
        return {
            "assignee_id": requested_assignee_id,
            "active_count": await self.ticket_repo.count_active_tickets_for_assignee(requested_assignee_id)
            if requested_assignee_id and is_active_operator_status(getattr(ticket, "status", None))
            else 0,
            "auto_assigned": False,
        }

    async def mark_assigned(self, assignee_id: Optional[str]) -> None:
        if not assignee_id:
            return
        await self.ticket_repo.touch_user_last_assignment(
            assignee_id,
            datetime.now(timezone.utc),
        )

    async def assign_ticket(
        self,
        ticket_id: str,
        ticket_device_id: str,
        assignee_id: Optional[str],
        *,
        actor_id: str,
        actor_role: str,
        reason: Optional[str],
        comment: Optional[str],
        old_assignee: Optional[str] = None,
        auto_assigned: bool = False,
        active_count: int = 0,
        limit: int = MAX_ACTIVE_TICKETS_PER_OPERATOR,
        db_session: Any,
        close_ola: bool = True,
    ) -> Tuple[Optional[Any], Optional[Any]]:
        """Единый поток назначения: update_ticket + событие + mark_assigned + OLA.

        Возвращает (ev_id, ev_created_at) для последующего push в WebSocket.
        """
        await self.ticket_repo.update_ticket(ticket_id, assignee_id=assignee_id)

        payload: Dict[str, Any] = {
            "field_name": "assignee_id",
            "old_value": old_assignee,
            "new_value": assignee_id,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": reason or "",
            "comment": comment or "",
            "assignee_id": assignee_id,
            "previous_assignee_id": old_assignee,
            "auto_assigned": auto_assigned,
            "target_active_count": active_count,
            "limit": limit,
        }

        ev_id, ev_created_at = await self.ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket_device_id,
            agent_seq=None,
            event_type="assignee_changed",
            payload=payload,
            trace_id=str(uuid.uuid4()),
        )

        await self.mark_assigned(assignee_id)

        if close_ola and assignee_id:
            try:
                from tickets.ola_service import close_ola_ack
                await close_ola_ack(db_session, ticket_id)
            except Exception as ola_err:
                logger.warning(f"[assign_ticket] OLA close_ola_ack failed: {ola_err}")

        return ev_id, ev_created_at
