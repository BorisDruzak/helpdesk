"""ticket auto-close: index (status, resolved_at) for watchdog scan

Revision ID: 019
Revises: 018
Create Date: 2026-02-16 12:00:00.000000

Stage 3: индекс для get_tickets_auto_close_candidates (status=Resolved, resolved_at <= cutoff).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_tickets_status_resolved_at",
        "tickets",
        ["status", "resolved_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_status_resolved_at", table_name="tickets")
