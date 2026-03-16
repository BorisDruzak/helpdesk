"""Ticket public sessions for requester web access.

Revision ID: 042
Revises: 041
Create Date: 2026-03-16 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "042"
down_revision: Union[str, None] = "041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_public_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=8), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index(
        "ix_ticket_public_sessions_ticket_id",
        "ticket_public_sessions",
        ["ticket_id"],
        unique=False,
    )
    op.create_index(
        "ix_ticket_public_sessions_expires_at",
        "ticket_public_sessions",
        ["expires_at"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ticket_public_sessions_active "
        "ON ticket_public_sessions (ticket_id, revoked_at) "
        "WHERE revoked_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ticket_public_sessions_active")
    op.drop_index("ix_ticket_public_sessions_expires_at", table_name="ticket_public_sessions")
    op.drop_index("ix_ticket_public_sessions_ticket_id", table_name="ticket_public_sessions")
    op.drop_table("ticket_public_sessions")
