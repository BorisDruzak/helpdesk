"""
Workflow тикетов (Stage 3): FSM переходов статусов + side effects (SLA, resolved_at, reopen).

- Нормализация статусов через statuses.normalize_status.
- Разрешённые переходы: support/admin — полная матрица; requester — только Resolved -> New.
- Side effects: вход в Resolved (resolved_at), в Closed (closed_at), reopen (очистка, SLA on_reopen),
  Waiting — pause SLA, выход из Waiting — resume SLA.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any

from loguru import logger

from app.repos.auth_tokens_repo import AuthTokensRepo
from tickets.statuses import CANONICAL_STATUSES, WAITING_STATUSES
from tickets.sla_service import TicketSlaService

# Матрица разрешённых переходов для support/admin: from_status -> [to_statuses]
SUPPORT_TRANSITIONS = {
    "new": ["triaged", "in_progress"],
    "triaged": ["in_progress", "waiting_on_user", "waiting_on_vendor"],
    "in_progress": ["triaged", "waiting_on_user", "waiting_on_vendor", "resolved"],
    "waiting_on_user": ["triaged", "in_progress", "resolved"],
    "waiting_on_vendor": ["triaged", "in_progress", "resolved"],
    "resolved": ["new"],
    "closed": ["new"],
}

# Requester: может переоткрыть тикет или подтвердить решение.
REQUESTER_TRANSITIONS = {
    "resolved": ["new", "closed"],
}


def _allowed_transitions(from_status: str, is_support_or_admin: bool) -> List[str]:
    if is_support_or_admin:
        return list(SUPPORT_TRANSITIONS.get(from_status, []))
    return list(REQUESTER_TRANSITIONS.get(from_status, []))


def validate_transition(
    from_status: str,
    to_status_canonical: str,
    is_support_or_admin: bool,
) -> bool:
    """
    Проверяет, разрешён ли переход из from_status в to_status_canonical для данной роли.
    Статусы должны быть уже в каноническом виде.
    """
    allowed = _allowed_transitions(from_status, is_support_or_admin)
    return to_status_canonical in allowed


class TicketWorkflowService:
    """
    Применение перехода статуса с side effects (SLA pause/resume, resolved_at, reopen).
    """

    def __init__(self, session, ticket_repo):
        self.session = session
        self.ticket_repo = ticket_repo
        self.sla_service = TicketSlaService(session, ticket_repo)

    async def apply_status_transition(
        self,
        ticket_id: str,
        from_status: str,
        to_status: str,
        actor_id: str,
        actor_role: str,
        reason: Optional[str] = None,
        resolution_code: Optional[str] = None,
        root_cause: Optional[str] = None,
        source: str = "api",
    ) -> dict:
        """
        Применяет переход статуса: обновляет тикет, вызывает SLA side effects, пишет событие.

        Args:
            ticket_id: ID тикета
            from_status: текущий канонический статус
            to_status: целевой канонический статус (уже нормализован)
            actor_id: ID актора (из AuthContext)
            actor_role: роль актора (admin, support, user, agent, system)
            reason, resolution_code, root_cause: опциональные поля для события
            source: "api" | "auto_close" | "system"

        Returns:
            dict с ключами: applied (bool), no_op (bool), updates (dict полей тикета),
            event_payload (для status_changed).
        """
        now = datetime.now(timezone.utc)
        updates = {}
        event_payload = {
            "from_status": from_status,
            "to_status": to_status,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "reason": reason or "",
            "source": source,
            "normalized": True,
        }
        if resolution_code is not None:
            event_payload["resolution_code"] = resolution_code
            updates["resolution_code"] = resolution_code
        if root_cause is not None:
            event_payload["root_cause"] = root_cause
            updates["root_cause"] = root_cause

        # Вход в Resolved: проставить resolved_at если пусто
        if to_status == "resolved":
            ticket = await self.ticket_repo.get_ticket(ticket_id)
            if ticket and getattr(ticket, "resolved_at", None) is None:
                updates["resolved_at"] = now

        # Вход в Closed: closed_at, resolution_at
        if to_status == "closed":
            updates["closed_at"] = now
            updates["resolution_at"] = now

        # Reopen (Resolved/Closed -> New): очистить resolved_at, closed_at
        if from_status in ("resolved", "closed") and to_status == "new":
            updates["resolved_at"] = None
            updates["closed_at"] = None
            updates["resolution_at"] = None
            updates["resolution_code"] = None
            updates["root_cause"] = None

        # Вход в Waiting: pause SLA (до update_ticket, чтобы sla_paused_at был корректен)
        if to_status in WAITING_STATUSES:
            await self.sla_service.pause_sla(ticket_id)

        # Выход из Waiting: resume SLA
        if from_status in WAITING_STATUSES and to_status not in WAITING_STATUSES:
            await self.sla_service.resume_sla(ticket_id)

        # Применяем обновление тикета
        await self.ticket_repo.update_ticket(
            ticket_id,
            status=to_status,
            **updates,
        )

        # Stage 11: при переходе в Resolved/Closed — закрыть OLA processing
        if to_status in ("resolved", "closed"):
            try:
                from tickets.ola_service import close_ola_processing
                await close_ola_processing(self.session, ticket_id)
            except Exception:
                pass  # не ломаем workflow при отключённом OLA
        if to_status == "closed":
            try:
                auth_repo = AuthTokensRepo(self.session)
                revoked = await auth_repo.revoke_ticket_public_sessions(ticket_id, commit=False)
                if revoked:
                    logger.info(
                        f"[Workflow] revoked public ticket sessions: ticket_id={ticket_id} count={revoked}"
                    )
            except Exception as revoke_err:
                logger.warning(
                    f"[Workflow] failed to revoke public ticket sessions: "
                    f"ticket_id={ticket_id} err={revoke_err}"
                )

        # После перехода в New при reopen — SLA on_reopen (сброс resolution, reopen_count++)
        if from_status in ("resolved", "closed") and to_status == "new":
            await self.sla_service.on_reopen(ticket_id)

        ticket = await self.ticket_repo.get_ticket(ticket_id)
        event_result = await self.ticket_repo.add_event(
            ticket_id=ticket_id,
            device_id=ticket.device_id,
            agent_seq=None,
            event_type="status_changed",
            payload=event_payload,
            trace_id=str(uuid.uuid4()),
        )
        logger.info(
            f"[Workflow] status_changed ticket_id={ticket_id} "
            f"{from_status} -> {to_status} actor_role={actor_role} source={source}"
        )
        return {
            "applied": True,
            "no_op": False,
            "updates": {"status": to_status, **updates},
            "event_payload": event_payload,
            "event_result": event_result,
        }
