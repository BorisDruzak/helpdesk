"""SQL equivalent of can_read_ui_ticket for notification reads/counts.

Keep queue-null, direct-assignee, membership aliases and unified-queue behavior
aligned with tickets.handlers.can_read_ui_ticket / TicketEventsRepo.is_actor_in_queue.
"""
from sqlalchemy import and_, false, or_, select, true

from app.db.models import Ticket, TicketNotification, TicketQueueMember, UiUser
from app.repos import ticket_events_repo as ticket_repo_module
from tickets.queue_mode import unified_queue_enabled


async def ui_actor_membership_ids(session, actor_id):
    # The accepted staging release predates alias membership support. Follow
    # whichever canonical ticket implementation is installed, without granting
    # new aliases or shipping an unrelated account-management change.
    resolver = getattr(ticket_repo_module, "ui_actor_membership_ids", None)
    return await resolver(session, actor_id) if resolver is not None else (actor_id,)


async def notification_scope_clause(session, auth):
    if getattr(auth, "ticket_scope", None):
        return false()  # A public ticket token is not a notification inbox session.
    role, actor = auth.actor_role, auth.actor_id
    if role in {"admin", "auditor"}:
        ticket_scope = true()
    elif role == "user":
        ticket_scope = Ticket.requester_id == actor
    elif role == "support":
        memberships = await ui_actor_membership_ids(session, actor)
        if unified_queue_enabled():
            queue_allowed = select(UiUser.user_login).where(UiUser.user_login.in_(memberships), UiUser.is_active.is_(True), UiUser.actor_role.in_(("admin", "support"))).exists()
        else:
            queue_allowed = select(TicketQueueMember.queue_id).where(TicketQueueMember.queue_id == Ticket.queue_id, TicketQueueMember.actor_id.in_(memberships)).exists()
        ticket_scope = or_(Ticket.queue_id.is_(None), Ticket.assignee_id == actor, queue_allowed)
    else:
        return false()
    allowed = select(Ticket.ticket_id).where(Ticket.ticket_id == TicketNotification.ticket_id, ticket_scope).exists()
    if role == "user":
        allowed = and_(allowed, or_(TicketNotification.event_type != "chat_message", TicketNotification.payload["visibility"].astext == "public"))
    return allowed
