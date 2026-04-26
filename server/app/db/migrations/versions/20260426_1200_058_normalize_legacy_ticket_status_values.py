"""normalize legacy ticket status values

Revision ID: 058
Revises: 057
Create Date: 2026-04-26 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "058"
down_revision: Union[str, None] = "057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE tickets
        SET status = CASE
                WHEN lower(trim(status)) IN ('in progress', 'in-progress', 'in_progress', 'open') THEN 'in_progress'
                WHEN lower(trim(status)) IN ('waiting on user', 'waiting-for-user', 'waiting_user', 'waiting_on_user') THEN 'waiting_on_user'
                WHEN lower(trim(status)) IN ('waiting on internal team', 'waiting_internal', 'waiting_on_internal_team') THEN 'waiting_on_internal_team'
                WHEN lower(trim(status)) IN ('waiting on vendor', 'waiting_vendor', 'waiting_on_vendor') THEN 'waiting_on_vendor'
                WHEN lower(trim(status)) IN ('waiting on approval', 'waiting_approval', 'waiting_on_approval') THEN 'waiting_on_approval'
                WHEN lower(trim(status)) IN ('cancelled', 'canceled') THEN 'canceled'
                WHEN lower(trim(status)) IN ('solved', 'resolved') THEN 'resolved'
                WHEN lower(trim(status)) = 'closed' THEN 'closed'
                WHEN lower(trim(status)) = 'scheduled' THEN 'scheduled'
                WHEN lower(trim(status)) = 'assigned' THEN 'assigned'
                WHEN lower(trim(status)) IN ('queue', 'queued') THEN 'queued'
                WHEN lower(trim(status)) IN ('new ticket', 'new_request', 'newrequest', 'new') THEN 'new'
                ELSE status
            END
        WHERE status IS NOT NULL
          AND status <> CASE
                WHEN lower(trim(status)) IN ('in progress', 'in-progress', 'in_progress', 'open') THEN 'in_progress'
                WHEN lower(trim(status)) IN ('waiting on user', 'waiting-for-user', 'waiting_user', 'waiting_on_user') THEN 'waiting_on_user'
                WHEN lower(trim(status)) IN ('waiting on internal team', 'waiting_internal', 'waiting_on_internal_team') THEN 'waiting_on_internal_team'
                WHEN lower(trim(status)) IN ('waiting on vendor', 'waiting_vendor', 'waiting_on_vendor') THEN 'waiting_on_vendor'
                WHEN lower(trim(status)) IN ('waiting on approval', 'waiting_approval', 'waiting_on_approval') THEN 'waiting_on_approval'
                WHEN lower(trim(status)) IN ('cancelled', 'canceled') THEN 'canceled'
                WHEN lower(trim(status)) IN ('solved', 'resolved') THEN 'resolved'
                WHEN lower(trim(status)) = 'closed' THEN 'closed'
                WHEN lower(trim(status)) = 'scheduled' THEN 'scheduled'
                WHEN lower(trim(status)) = 'assigned' THEN 'assigned'
                WHEN lower(trim(status)) IN ('queue', 'queued') THEN 'queued'
                WHEN lower(trim(status)) IN ('new ticket', 'new_request', 'newrequest', 'new') THEN 'new'
                ELSE status
            END
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
    pass
