"""Bounded Web Push worker. Database locks prevent competing dispatchers."""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger
from sqlalchemy import exists, select, update

from app.db import get_session
from app.db.models import TicketNotification
from app.db.web_push_models import WebPushDelivery, WebPushSubscription
from tickets.web_push import send_wakeup


class WebPushDispatcher:
    def __init__(self, config, *, session_factory=get_session):
        self.config = config
        self.session_factory = session_factory
        self.task = None

    def start(self):
        self.task = asyncio.create_task(self._run(), name="helpdesk-web-push")

    async def stop(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
            self.task = None

    async def dispatch_one(self, client) -> bool:
        now = datetime.now(timezone.utc)
        eligible = select(WebPushDelivery.notification_id).join(TicketNotification, TicketNotification.id == WebPushDelivery.notification_id).where(
            WebPushDelivery.endpoint_hash == WebPushSubscription.endpoint_hash,
            WebPushDelivery.shown_at.is_(None), TicketNotification.is_read.is_(False),
            TicketNotification.created_at > now - timedelta(days=1),
            (WebPushDelivery.sent_at.is_(None) | (WebPushDelivery.sent_at < now - timedelta(minutes=5))),
        ).correlate(WebPushSubscription)
        async with self.session_factory() as session:
            subscription = await session.scalar(select(WebPushSubscription).where(
                WebPushSubscription.next_attempt_at <= now,
                WebPushSubscription.vapid_public_key == self.config.public_key,
                exists(eligible),
            ).order_by(WebPushSubscription.next_attempt_at).with_for_update(skip_locked=True).limit(1))
            if subscription is None:
                return False
            batch_ids = list((await session.scalars(select(WebPushDelivery.notification_id).where(
                WebPushDelivery.endpoint_hash == subscription.endpoint_hash, WebPushDelivery.shown_at.is_(None),
            ))).all())
            try:
                status = await send_wakeup(client, self.config, subscription.endpoint)
            except (httpx.HTTPError, ValueError):
                status = 0  # Never log exception strings: they can contain endpoints.
            if status in (404, 410):
                await session.delete(subscription)
            elif 200 <= status < 300:
                await session.execute(update(WebPushDelivery).where(
                    WebPushDelivery.endpoint_hash == subscription.endpoint_hash,
                    WebPushDelivery.notification_id.in_(batch_ids),
                    WebPushDelivery.shown_at.is_(None),
                ).values(sent_at=now))
                subscription.failures = 0
                # sent_at governs retries; fresh events must not inherit a cooldown.
                subscription.next_attempt_at = now
            else:
                subscription.failures = min(subscription.failures + 1, 12)
                subscription.next_attempt_at = now + timedelta(seconds=min(3600, 15 * 2 ** subscription.failures))
                logger.warning("Web Push provider failed; HTTP status={}", status)
            await session.commit()
        return True

    async def _run(self):
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
            while True:
                try:
                    for _ in range(20):
                        if not await self.dispatch_one(client):
                            break
                except Exception:
                    logger.warning("Web Push queue unavailable; retrying")
                await asyncio.sleep(5)
