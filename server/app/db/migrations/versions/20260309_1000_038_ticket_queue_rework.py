"""Ticket domain refresh: snake_case statuses, importance/reasons, operator load balancing

Revision ID: 038
Revises: 037
Create Date: 2026-03-09 10:00:00.000000

- tickets: importance, urgency_reason, importance_reason
- ui_users: last_ticket_assigned_at
- backfill ticket statuses to snake_case
- backfill custom_fields.priority_class from legacy priority values
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("importance", sa.SmallInteger(), nullable=True))
    op.add_column("tickets", sa.Column("urgency_reason", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("importance_reason", sa.Text(), nullable=True))

    op.add_column("ui_users", sa.Column("last_ticket_assigned_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.create_index("ix_ui_users_last_ticket_assigned_at", "ui_users", ["last_ticket_assigned_at"])

    op.execute(
        """
        UPDATE tickets
        SET status = CASE
            WHEN lower(status) = 'new' THEN 'new'
            WHEN lower(status) = 'triaged' THEN 'triaged'
            WHEN lower(status) IN ('in progress', 'in_progress', 'open') THEN 'in_progress'
            WHEN lower(status) IN ('waiting on user', 'waiting_on_user', 'waiting_user') THEN 'waiting_on_user'
            WHEN lower(status) IN ('waiting on vendor', 'waiting_on_vendor', 'waiting_vendor') THEN 'waiting_on_vendor'
            WHEN lower(status) = 'resolved' THEN 'resolved'
            WHEN lower(status) = 'closed' THEN 'closed'
            ELSE status
        END
        """
    )

    op.execute(
        """
        UPDATE tickets
        SET custom_fields = jsonb_set(
            COALESCE(custom_fields, '{}'::jsonb),
            '{priority_class}',
            to_jsonb(
                CASE
                    WHEN priority = 'P1' THEN 'P0'
                    WHEN priority = 'P2' THEN 'P1'
                    WHEN priority = 'P3' THEN 'P2'
                    ELSE 'P3'
                END
            ),
            true
        )
        WHERE custom_fields IS NULL
           OR NOT (COALESCE(custom_fields, '{}'::jsonb) ? 'priority_class')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tickets
        SET status = CASE
            WHEN status = 'new' THEN 'New'
            WHEN status = 'triaged' THEN 'Triaged'
            WHEN status = 'in_progress' THEN 'In Progress'
            WHEN status = 'waiting_on_user' THEN 'Waiting on User'
            WHEN status = 'waiting_on_vendor' THEN 'Waiting on Vendor'
            WHEN status = 'resolved' THEN 'Resolved'
            WHEN status = 'closed' THEN 'Closed'
            ELSE status
        END
        """
    )
    op.drop_index("ix_ui_users_last_ticket_assigned_at", table_name="ui_users")
    op.drop_column("ui_users", "last_ticket_assigned_at")
    op.drop_column("tickets", "importance_reason")
    op.drop_column("tickets", "urgency_reason")
    op.drop_column("tickets", "importance")
