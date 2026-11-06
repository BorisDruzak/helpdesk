"""Actor-scoped subscription management and durable delivery fanout."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.models import TicketNotification
from app.db.web_push_models import WebPushDelivery, WebPushSubscription
from app.repos.ui_actor_memberships import ui_actor_membership_ids
from tickets.web_push import endpoint_hash


class WebPushRepo:
    def __init__(self, session):
        self.session = session

    async def enqueue(self, notification_id: int, actor_id: str) -> None:
        stmt = insert(WebPushDelivery).from_select(
            ["endpoint_hash", "notification_id"],
            select(WebPushSubscription.endpoint_hash, literal(notification_id)).where(
                WebPushSubscription.actor_id.in_(await ui_actor_membership_ids(self.session, actor_id))),
        ).on_conflict_do_nothing()
        await self.session.execute(stmt)

    async def get(self, endpoint: str, actor_id: str):
        return await self.session.scalar(select(WebPushSubscription).where(
            WebPushSubscription.endpoint_hash == endpoint_hash(endpoint),
            WebPushSubscription.actor_id.in_(await ui_actor_membership_ids(self.session, actor_id))))

    async def subscribe(self, endpoint: str, actor_id: str, public_key: str) -> None:
        digest = endpoint_hash(endpoint)
        actor_ids = await ui_actor_membership_ids(self.session, actor_id)
        if not actor_ids:
            raise ValueError("Ambiguous browser subscription owner")
        existing = await self.session.scalar(select(WebPushSubscription).where(WebPushSubscription.endpoint_hash == digest).with_for_update())
        if existing and existing.actor_id in actor_ids and existing.vapid_public_key == public_key:
            return  # Reopening a tab must retain unacknowledged deliveries.
        if existing:
            await self.session.delete(existing)
            await self.session.flush()
        count = await self.session.scalar(select(func.count()).select_from(WebPushSubscription).where(WebPushSubscription.actor_id.in_(actor_ids)))
        if count >= 20:
            raise ValueError("Too many browser subscriptions")
        self.session.add(WebPushSubscription(endpoint_hash=digest, actor_id=actor_id, endpoint=endpoint, vapid_public_key=public_key))
        await self.session.flush()

    async def unsubscribe(self, endpoint: str, actor_id: str) -> None:
        await self.session.execute(delete(WebPushSubscription).where(WebPushSubscription.endpoint_hash == endpoint_hash(endpoint),
            WebPushSubscription.actor_id.in_(await ui_actor_membership_ids(self.session, actor_id))))

    async def pending(self, endpoint: str, actor_id: str, *, auth_context=None) -> list:
        subscription = await self.get(endpoint, actor_id)
        if subscription is None:
            return []
        actor_ids = await ui_actor_membership_ids(self.session, actor_id)
        scope = None
        if auth_context is not None:
            from tickets.notification_scope import notification_scope_clause
            scope = await notification_scope_clause(self.session, auth_context)
            hidden_ids = select(TicketNotification.id).where(TicketNotification.actor_id.in_(actor_ids), ~scope)
            await self.session.execute(update(WebPushDelivery).where(
                WebPushDelivery.endpoint_hash == subscription.endpoint_hash,
                WebPushDelivery.shown_at.is_(None), WebPushDelivery.notification_id.in_(hidden_ids),
            ).values(shown_at=datetime.now(timezone.utc)))
        stmt = select(TicketNotification).join(WebPushDelivery, WebPushDelivery.notification_id == TicketNotification.id).where(
            WebPushDelivery.endpoint_hash == subscription.endpoint_hash, WebPushDelivery.shown_at.is_(None),
            TicketNotification.actor_id.in_(actor_ids), TicketNotification.is_read.is_(False),
            TicketNotification.created_at > datetime.now(timezone.utc) - timedelta(days=1),
        )
        if scope is not None:
            stmt = stmt.where(scope)
        stmt = stmt.order_by(TicketNotification.id).limit(50)
        return list((await self.session.scalars(stmt)).all())

    async def acknowledge(self, endpoint: str, actor_id: str, ids: list[int]) -> None:
        if await self.get(endpoint, actor_id) is None:
            return
        await self.session.execute(update(WebPushDelivery).where(
            WebPushDelivery.endpoint_hash == endpoint_hash(endpoint), WebPushDelivery.notification_id.in_(ids),
        ).values(shown_at=datetime.now(timezone.utc)))
