"""ticket worklogs: index (ticket_id, created_at) for list/total

Revision ID: 020
Revises: 019
Create Date: 2026-02-16 14:00:00.000000

Stage 4: индекс для list_worklogs и get_worklog_total по ticket_worklogs.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_ticket_worklogs_ticket_created_at",
        "ticket_worklogs",
        ["ticket_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_worklogs_ticket_created_at", table_name="ticket_worklogs")
