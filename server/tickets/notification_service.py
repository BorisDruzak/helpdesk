"""
Stage 6: Сервис уведомлений по событиям тикетов.
Stage 8: Фильтрация по notification preferences (mute_internal, muted_event_types, suppress_self).
Получатели: support/admin по queue membership + assignee; requester — только public-события; watchers — по тикету.
"""
from typing import Optional, Set, TYPE_CHECKING

from loguru import logger

from app.repos.ticket_events_repo import TicketEventsRepo
from app.repos.notification_repo import NotificationRepo
from app.repos.notification_prefs_repo import DEFAULT_SUPPRESS_SELF

if TYPE_CHECKING:
    from app.repos.notification_prefs_repo import NotificationPrefsRepo

# События, которые видны requester (остальные — только support/admin и watchers).
PUBLIC_EVENT_TYPES: Set[str] = {
    "status_changed",
}


async def get_recipients(
    ticket_repo: TicketEventsRepo,
    ticket_id: str,
    event_type: str,
    visibility: str = "internal",
) -> list[str]:
    """
    Определить список actor_id получателей уведомления.
    - support/admin: участники очереди тикета + assignee.
    - requester: только если событие public и у тикета есть requester_id.
    - watchers: наблюдатели тикета.
    Дубликаты убираются, порядок: queue+assignee, requester, watchers.
    """
    ticket = await ticket_repo.get_ticket(ticket_id)
    if not ticket:
        return []

    recipient_ids: list[str] = []
    seen: set[str] = set()

    def add(aid: str | None) -> None:
        if aid and str(aid) not in seen:
            seen.add(str(aid))
            recipient_ids.append(str(aid))

    # Участники очереди + assignee (support/admin по сути)
    if getattr(ticket, "queue_id", None) is not None:
        for aid in await ticket_repo.list_queue_member_actor_ids(ticket.queue_id):
            add(aid)
    assignee = getattr(ticket, "assignee_id", None)
    if assignee:
        add(assignee)

    # Requester — только для public-событий (Stage 7: утечка internal requester закрыта)
    requester = getattr(ticket, "requester_id", None)
    is_public_event = event_type in PUBLIC_EVENT_TYPES or visibility == "public"
    if is_public_event and requester:
        add(requester)

    # Watchers — Stage 7: requester как watcher получает ТОЛЬКО public-события
    watchers = await ticket_repo.list_watchers(ticket_id)
    for w in watchers:
        if w.actor_id == requester and not is_public_event:
            continue  # requester в роли watcher не получает internal
        add(w.actor_id)

    return recipient_ids


async def notify_ticket_event(
    ticket_repo: TicketEventsRepo,
    notification_repo: NotificationRepo,
    ticket_id: str,
    event_type: str,
    payload: dict,
    visibility: str = "internal",
    initiator_id: Optional[str] = None,
    prefs_repo: Optional["NotificationPrefsRepo"] = None,
) -> None:
    """
    Создать записи уведомлений для всех получателей по событию тикета.
    Вызывать после add_event в том же session/транзакции.

    Stage 8: если prefs_repo передан, фильтрация по preferences:
    - mute_internal=true блокирует visibility=internal
    - event_type in muted_event_types блокирует событие
    - suppress_self=true блокирует уведомление инициатору (initiator_id)
    """
    recipients = await get_recipients(ticket_repo, ticket_id, event_type, visibility)
    for actor_id in recipients:
        # Stage 8: suppress_self — не слать инициатору (default true)
        if initiator_id and str(actor_id) == str(initiator_id):
            suppress = DEFAULT_SUPPRESS_SELF
            if prefs_repo:
                _, _, suppress = await prefs_repo.get_or_default(actor_id)
            if suppress:
                continue
        # Stage 8: prefs фильтрация по mute_internal и muted_event_types
        if prefs_repo:
            mute_internal, muted_types, _ = await prefs_repo.get_or_default(actor_id)
            if mute_internal and visibility == "internal":
                continue
            if event_type in muted_types:
                continue
        try:
            await notification_repo.create(
                actor_id=actor_id,
                ticket_id=ticket_id,
                event_type=event_type,
                payload=payload,
            )
        except Exception as e:
            logger.warning(f"[NotificationService] create failed actor_id={actor_id} ticket_id={ticket_id}: {e}")
