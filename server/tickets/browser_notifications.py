"""One safe projection and transactional producer for bell/browser events."""
from urllib.parse import quote

from app.repos.notification_repo import NotificationRepo
from app.repos.notification_prefs_repo import NotificationPrefsRepo
from tickets.notification_service import notify_ticket_event
from tickets.statuses import requester_status_label_for_internal, status_label_ru

BROWSER_EVENT_TYPES = ("chat_message", "status_changed")


def notification_to_dict(row, *, requester: bool = False) -> dict:
    payload = row.payload if isinstance(row.payload, dict) else {}
    code = str(payload.get("ticket_code") or "").strip()
    suffix = f" по обращению {code}" if code else " по обращению"
    title = "Новое сообщение" + suffix if row.event_type == "chat_message" else "Новое событие" + suffix
    body = "Откройте обращение, чтобы посмотреть подробности."
    if row.event_type == "status_changed":
        title = "Изменён статус обращения" + (f" {code}" if code else "")
        status = str(payload.get("to_status") or payload.get("new_status") or "")
        if status:
            body = requester_status_label_for_internal(status) if requester else status_label_ru(status)
    prefix = "/app/requester/tickets/" if requester else "/app/tickets/"
    return {
        "id": row.id, "ticket_id": row.ticket_id, "event_type": row.event_type,
        "title": title, "body": body, "url": prefix + quote(str(row.ticket_id), safe=""),
        "is_read": bool(row.is_read),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "read_at": row.read_at.isoformat() if row.read_at else None,
    }


async def enqueue_event_notifications(repo, ticket_id: str, event_id: int, event_type: str, payload: dict) -> None:
    if event_type not in BROWSER_EVENT_TYPES:
        return
    ticket = await repo.get_ticket(ticket_id)
    if ticket is None:
        return
    initiator = payload.get("sender_actor_id") or payload.get("actor_id")
    if not initiator and payload.get("sender_role") == "user":
        initiator = getattr(ticket, "requester_id", None)
    await notify_ticket_event(
        ticket_repo=repo, notification_repo=NotificationRepo(repo.session),
        prefs_repo=NotificationPrefsRepo(repo.session), ticket_id=ticket_id,
        event_type=event_type,
        payload={**payload, "source_event_id": event_id, "ticket_code": getattr(ticket, "ticket_code", None)},
        visibility="public" if event_type == "status_changed" else str(payload.get("visibility") or "internal"),
        initiator_id=str(initiator) if initiator else None,
        raise_on_error=True,
    )
