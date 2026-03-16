"""Stage 6: ticket_notifications for in-app notifications

Revision ID: 023
Revises: 022
Create Date: 2026-02-16 18:00:00.000000

- ticket_notifications: id, actor_id, ticket_id, event_type, payload, is_read, created_at, read_at.
- Indexes: (actor_id, is_read, created_at), (ticket_id, created_at).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_notifications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_notifications_actor_id", "ticket_notifications", ["actor_id"], unique=False)
    op.create_index("ix_ticket_notifications_ticket_id", "ticket_notifications", ["ticket_id"], unique=False)
    op.create_index(
        "ix_ticket_notifications_actor_read_created",
        "ticket_notifications",
        ["actor_id", "is_read", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ticket_notifications_ticket_created",
        "ticket_notifications",
        ["ticket_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_notifications_ticket_created", table_name="ticket_notifications")
    op.drop_index("ix_ticket_notifications_actor_read_created", table_name="ticket_notifications")
    op.drop_index("ix_ticket_notifications_ticket_id", table_name="ticket_notifications")
    op.drop_index("ix_ticket_notifications_actor_id", table_name="ticket_notifications")
    op.drop_table("ticket_notifications")
