"""ticket status lifecycle backfill

Revision ID: 057
Revises: 056
Create Date: 2026-04-26 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "057"
down_revision: Union[str, None] = "056"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE tickets
        SET status = CASE
                WHEN status = 'triaged' AND assignee_id IS NOT NULL THEN 'assigned'
                WHEN status = 'triaged' THEN 'queued'
                ELSE status
            END
        WHERE status = 'triaged'
        """
    )
    op.execute(
        """
        UPDATE tickets
        SET next_action_owner = CASE
                WHEN status = 'waiting_on_user' THEN 'requester'
                WHEN status = 'waiting_on_internal_team' THEN 'internal_team'
                WHEN status = 'waiting_on_vendor' THEN 'vendor'
                WHEN status = 'waiting_on_approval' THEN 'approver'
                WHEN status = 'resolved' THEN 'requester'
                WHEN status IN ('closed', 'canceled') THEN 'system'
                ELSE 'support'
            END,
            requester_status = CASE
                WHEN status IN ('new', 'queued', 'assigned') THEN 'accepted'
                WHEN status = 'waiting_on_user' THEN 'needs_requester'
                WHEN status = 'resolved' THEN 'review_solution'
                WHEN status = 'closed' THEN 'closed'
                WHEN status = 'canceled' THEN 'canceled'
                ELSE 'in_work'
            END
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tickets
        SET status = 'triaged'
        WHERE status IN ('queued', 'assigned')
        """
    )
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
