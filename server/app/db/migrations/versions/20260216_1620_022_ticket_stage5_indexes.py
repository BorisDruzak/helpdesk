"""Stage 5: indexes for metrics and performance

Revision ID: 022
Revises: 021
Create Date: 2026-02-16 16:20:00.000000

- ix_tickets_status_queue_priority_created on tickets(status, queue_id, priority, created_at).
- ix_ticket_events_ticket_type_created on ticket_events(ticket_id, event_type, created_at).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_tickets_status_queue_priority_created",
        "tickets",
        ["status", "queue_id", "priority", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ticket_events_ticket_type_created",
        "ticket_events",
        ["ticket_id", "event_type", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_events_ticket_type_created", table_name="ticket_events")
    op.drop_index("ix_tickets_status_queue_priority_created", table_name="tickets")
