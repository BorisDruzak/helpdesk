"""Keep durable actor-scoped requester create keys.

Revision ID: 144
Revises: 143
"""
from alembic import op
import sqlalchemy as sa

revision = "144"
down_revision = "143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requester_ticket_create_requests",
        sa.Column("actor_hash", sa.String(64), primary_key=True),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_requester_ticket_create_requests_ticket_id", "requester_ticket_create_requests", ["ticket_id"])


def downgrade() -> None:
    raise RuntimeError("Revision 144 is forward-only; roll back the application release instead.")
