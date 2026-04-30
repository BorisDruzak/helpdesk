"""Ticket notification recipient resolution and delivery."""

from __future__ import annotations

from typing import Any, Optional, Set, TYPE_CHECKING

from loguru import logger

from app.repos.notification_prefs_repo import DEFAULT_SUPPRESS_SELF
from app.repos.notification_repo import NotificationRepo
from app.repos.ticket_events_repo import TicketEventsRepo

if TYPE_CHECKING:
    from app.repos.notification_prefs_repo import NotificationPrefsRepo


PUBLIC_EVENT_TYPES: Set[str] = {
    "status_changed",
}


def get_template_notification_policy(ticket: Any) -> dict[str, Any]:
    custom_fields = getattr(ticket, "custom_fields", None) or {}
    if not isinstance(custom_fields, dict):
        return {}
    request_template = custom_fields.get("request_template") or {}
    if not isinstance(request_template, dict):
        return {}
    policy = request_template.get("notification_policy") or request_template.get("notifications") or {}
    return policy if isinstance(policy, dict) else {}


def _event_policy(policy: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    event_key = str(event_type or "").strip()
    candidates = [f"on_{event_key}", event_key]
    if event_key.endswith("ed"):
        candidates.append(f"on_{event_key[:-2]}")
    if event_key.endswith("_sent"):
        candidates.append(f"on_{event_key[:-5]}")
    for key in candidates:
        value = policy.get(key)
        if isinstance(value, dict):
            return value
    return None


def _recipient_enabled(event_policy: dict[str, Any] | None, key: str, *, legacy_default: bool) -> bool:
    if event_policy is None:
        return legacy_default
    return bool(event_policy.get(key, False))


async def get_recipients(
    ticket_repo: TicketEventsRepo,
    ticket_id: str,
    event_type: str,
    visibility: str = "internal",
) -> list[str]:
    """
    Resolve in-app notification recipients for a ticket event.

    Without a template policy this preserves the legacy behavior:
    queue members, assignee, public requester events and watchers.
    If request_template.notification_policy has an event block, that block
    explicitly controls requester/assignee/queue/watchers recipient groups.
    """
    ticket = await ticket_repo.get_ticket(ticket_id)
    if not ticket:
        return []

    recipient_ids: list[str] = []
    seen: set[str] = set()
    is_public_event = event_type in PUBLIC_EVENT_TYPES or visibility == "public"
    event_policy = _event_policy(get_template_notification_policy(ticket), event_type)

    def add(aid: str | None) -> None:
        if aid and str(aid) not in seen:
            seen.add(str(aid))
            recipient_ids.append(str(aid))

    if _recipient_enabled(event_policy, "queue", legacy_default=True) and getattr(ticket, "queue_id", None) is not None:
        for aid in await ticket_repo.list_queue_member_actor_ids(ticket.queue_id):
            add(aid)

    assignee = getattr(ticket, "assignee_id", None)
    if _recipient_enabled(event_policy, "assignee", legacy_default=True) and assignee:
        add(assignee)

    requester = getattr(ticket, "requester_id", None)
    if _recipient_enabled(event_policy, "requester", legacy_default=is_public_event) and is_public_event and requester:
        add(requester)

    if _recipient_enabled(event_policy, "watchers", legacy_default=True):
        watchers = await ticket_repo.list_watchers(ticket_id)
        for watcher in watchers:
            if watcher.actor_id == requester and not is_public_event:
                continue
            add(watcher.actor_id)

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
    Create notification rows for resolved recipients.

    User preferences remain the final per-recipient filter:
    mute_internal, muted_event_types and suppress_self are applied after
    request_template.notification_policy recipient selection.
    """
    recipients = await get_recipients(ticket_repo, ticket_id, event_type, visibility)
    for actor_id in recipients:
        if initiator_id and str(actor_id) == str(initiator_id):
            suppress = DEFAULT_SUPPRESS_SELF
            if prefs_repo:
                _, _, suppress = await prefs_repo.get_or_default(actor_id)
            if suppress:
                continue
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
        except Exception as exc:
            logger.warning(
                f"[NotificationService] create failed actor_id={actor_id} ticket_id={ticket_id}: {exc}"
            )
