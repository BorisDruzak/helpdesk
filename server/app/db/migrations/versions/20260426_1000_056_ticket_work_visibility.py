"""ticket work visibility

Revision ID: 056
Revises: 055
Create Date: 2026-04-26 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "056"
down_revision: Union[str, None] = "055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tickets",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=40),
        existing_nullable=False,
    )
    op.add_column("tickets", sa.Column("next_action_owner", sa.String(length=30), nullable=False, server_default="support"))
    op.add_column("tickets", sa.Column("next_action_due_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("status_reason", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("requester_status", sa.String(length=30), nullable=False, server_default="accepted"))
    op.add_column("tickets", sa.Column("resolution_summary", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("requester_resolution_summary", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("evidence_required", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("tickets", sa.Column("evidence_ref", sa.Text(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column(
            "closure_feedback",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("tickets", sa.Column("canceled_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.create_index("ix_tickets_next_action_owner", "tickets", ["next_action_owner"])
    op.create_index("ix_tickets_next_action_due_at", "tickets", ["next_action_due_at"])
    op.create_index("ix_tickets_requester_status", "tickets", ["requester_status"])

    op.execute(
        """
        UPDATE tickets
        SET next_action_owner = CASE
                WHEN status = 'waiting_on_user' THEN 'requester'
                WHEN status = 'waiting_on_vendor' THEN 'vendor'
                WHEN status = 'resolved' THEN 'requester'
                WHEN status = 'closed' THEN 'system'
                ELSE 'support'
            END,
            requester_status = CASE
                WHEN status = 'waiting_on_user' THEN 'needs_requester'
                WHEN status = 'resolved' THEN 'review_solution'
                WHEN status = 'closed' THEN 'closed'
                WHEN status IN ('new', 'triaged') THEN 'accepted'
                ELSE 'in_work'
            END
        """
    )

    op.create_table(
        "ticket_waits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("wait_type", sa.String(length=30), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("related_party", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_waits_ticket_active", "ticket_waits", ["ticket_id", "ended_at"])
    op.create_index("ix_ticket_waits_type_active", "ticket_waits", ["wait_type", "ended_at"])


def downgrade() -> None:
    op.drop_index("ix_ticket_waits_type_active", table_name="ticket_waits")
    op.drop_index("ix_ticket_waits_ticket_active", table_name="ticket_waits")
    op.drop_table("ticket_waits")

    op.drop_index("ix_tickets_requester_status", table_name="tickets")
    op.drop_index("ix_tickets_next_action_due_at", table_name="tickets")
    op.drop_index("ix_tickets_next_action_owner", table_name="tickets")
    op.drop_column("tickets", "canceled_at")
    op.drop_column("tickets", "closure_feedback")
    op.drop_column("tickets", "evidence_ref")
    op.drop_column("tickets", "evidence_required")
    op.drop_column("tickets", "requester_resolution_summary")
    op.drop_column("tickets", "resolution_summary")
    op.drop_column("tickets", "requester_status")
    op.drop_column("tickets", "status_reason")
    op.drop_column("tickets", "next_action_due_at")
    op.drop_column("tickets", "next_action_owner")
    op.alter_column(
        "tickets",
        "status",
        existing_type=sa.String(length=40),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
