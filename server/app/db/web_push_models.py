"""Browser opt-in and durable, transactionally produced push deliveries."""
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebPushSubscription(Base):
    __tablename__ = "web_push_subscriptions"
    endpoint_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(sa.Text, nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(sa.Text, nullable=False)
    vapid_public_key: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    failures: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


class WebPushDelivery(Base):
    __tablename__ = "web_push_deliveries"
    endpoint_hash: Mapped[str] = mapped_column(sa.String(64), sa.ForeignKey("web_push_subscriptions.endpoint_hash", ondelete="CASCADE"), primary_key=True)
    notification_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey("ticket_notifications.id", ondelete="CASCADE"), primary_key=True)
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    shown_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
