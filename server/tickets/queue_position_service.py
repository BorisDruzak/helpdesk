"""
Stage 10.2: Position Engine — порядок тикетов в очереди.

- Ручной порядок (manual_rank) хранится отдельно от priority (SLA/бизнес).
- Позиция: per queue; manual mode (если есть manual_rank) или auto (priority → breach → due → created).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from loguru import logger

from app.db.models import Ticket
from tickets.statuses import compute_effective_priority, extract_priority_class, get_requester_display_name

def _effective_due_at(t: Ticket) -> Optional[datetime]:
    """Минимальный из FR/Resolution due (только не-NULL)."""
    vals = [t.first_response_due_at, t.resolution_due_at]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None


def _breach_flag(t: Ticket) -> int:
    """1 если нарушен SLA (FR или Resolution), иначе 0. Сначала breached."""
    if getattr(t, "first_response_breached_at", None) or getattr(t, "resolution_breached_at", None):
        return 1
    return 0


def _auto_sort_key(t: Ticket) -> Tuple[int, datetime, str]:
    """Ключ авто-сортировки: effective_priority DESC, created_at ASC, ticket_code ASC."""
    effective_priority = compute_effective_priority(
        extract_priority_class(t),
        t.status,
        t.created_at,
    )
    return (
        -effective_priority,
        t.created_at,
        t.ticket_code or "",
    )


def _build_ordered_list(tickets: List[Ticket]) -> List[Tuple[Ticket, int]]:
    """
    Строит упорядоченный список (ticket, 1-based position).
    Правило: если есть хотя бы один manual_rank — manual mode (manual_rank asc, затем auto key).
    Иначе — auto (priority, breach, due, created, ticket_code).
    """
    if not tickets:
        return []
    has_manual = any(getattr(t, "manual_rank", None) is not None for t in tickets)

    if has_manual:
        def sort_key(t: Ticket) -> Tuple[int, Tuple]:
            r = getattr(t, "manual_rank", None)
            return (r if r is not None else (1 << 62), _auto_sort_key(t))
        sorted_tickets = sorted(tickets, key=sort_key)
    else:
        sorted_tickets = sorted(tickets, key=_auto_sort_key)

    return [(t, i) for i, t in enumerate(sorted_tickets, 1)]


class QueuePositionService:
    """Сервис позиций тикетов в очереди (Stage 10.2)."""

    def __init__(self, ticket_repo: Any):
        self.ticket_repo = ticket_repo

    async def list_queue_positions(
        self,
        queue_id: int,
        include_terminal: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Упорядоченный список тикетов очереди с вычисленной позицией (1..N).
        include_terminal: включать ли тикеты в терминальных статусах (Resolved, Closed) — по умолчанию нет.
        """
        tickets = await self.ticket_repo.list_open_tickets_for_queue(queue_id)
        if include_terminal:
            # Сейчас list_open_tickets_for_queue уже только open — терминальные не включены
            pass
        ordered = _build_ordered_list(tickets)
        now = datetime.now(timezone.utc)
        out = []
        for ticket, position in ordered:
            wait_seconds = None
            if ticket.created_at:
                delta = now - ticket.created_at
                wait_seconds = int(delta.total_seconds())
            out.append({
                "ticket_id": ticket.ticket_id,
                "ticket_code": ticket.ticket_code,
                "status": ticket.status,
                "priority": ticket.priority,
                "urgency": getattr(ticket, "urgency", None),
                "importance": getattr(ticket, "importance", None),
                "requester_id": getattr(ticket, "requester_id", None),
                "requester_display_name": get_requester_display_name(ticket),
                "position": position,
                "wait_seconds": wait_seconds,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if getattr(ticket, "updated_at", None) else None,
                "manual_rank": getattr(ticket, "manual_rank", None),
            })
        return out

    async def has_manual_mode(self, queue_id: int) -> bool:
        """Есть ли в очереди хотя бы один тикет с manual_rank."""
        tickets = await self.ticket_repo.list_open_tickets_for_queue(queue_id)
        return any(getattr(t, "manual_rank", None) is not None for t in tickets)

    async def reorder_ticket(
        self,
        queue_id: int,
        ticket_id: str,
        direction: Literal["up", "down", "top", "bottom"],
        actor_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Переместить тикет в очереди. Транзакционно пересчитывает manual_rank (шаг 100).
        Возвращает {from_position, to_position} или None при ошибке.
        """
        tickets = await self.ticket_repo.list_open_tickets_for_queue(queue_id)
        ordered = _build_ordered_list(tickets)
        ticket_to_pos = {t.ticket_id: (t, pos) for t, pos in ordered}
        if ticket_id not in ticket_to_pos:
            return None
        ticket, from_position = ticket_to_pos[ticket_id]
        idx = from_position - 1
        new_idx = idx
        if direction == "up" and idx > 0:
            new_idx = idx - 1
        elif direction == "down" and idx < len(ordered) - 1:
            new_idx = idx + 1
        elif direction == "top":
            new_idx = 0
        elif direction == "bottom":
            new_idx = len(ordered) - 1
        if new_idx == idx:
            return {"from_position": from_position, "to_position": from_position}
        # Переставить в списке
        lst = [t for t, _ in ordered]
        t = lst.pop(idx)
        lst.insert(new_idx, t)
        to_position = new_idx + 1
        # Назначить manual_rank 100, 200, 300, ...
        now = datetime.now(timezone.utc)
        for i, t in enumerate(lst):
            rank = (i + 1) * 100
            await self.ticket_repo.update_ticket(
                t.ticket_id,
                manual_rank=rank,
                manual_rank_updated_at=now,
                manual_rank_updated_by=actor_id,
            )
        return {"from_position": from_position, "to_position": to_position}

    async def reset_manual_order(self, queue_id: int, actor_id: str) -> int:
        """
        Сбросить manual_rank у всех открытых тикетов очереди. Возвращает количество обновлённых.
        """
        tickets = await self.ticket_repo.list_open_tickets_for_queue(queue_id)
        count = 0
        for t in tickets:
            if getattr(t, "manual_rank", None) is not None:
                await self.ticket_repo.update_ticket(
                    t.ticket_id,
                    manual_rank=None,
                    manual_rank_updated_at=None,
                    manual_rank_updated_by=None,
                )
                count += 1
        logger.info(f"[QueuePosition] Reset manual order for queue_id={queue_id}, cleared {count} tickets")
        return count
