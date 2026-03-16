"""Stage 10.2: manual_rank — ручной порядок в очереди (отдельно от priority)

Revision ID: 032
Revises: 031
Create Date: 2026-02-19 10:00:00.000000

- tickets.manual_rank BIGINT NULL
- tickets.manual_rank_updated_at TIMESTAMPTZ NULL
- tickets.manual_rank_updated_by TEXT NULL
- ix_tickets_queue_manual_rank (queue_id, manual_rank)
- ix_tickets_queue_open_sort (queue_id, status, priority, created_at)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("manual_rank", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("manual_rank_updated_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("manual_rank_updated_by", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_tickets_queue_manual_rank",
        "tickets",
        ["queue_id", "manual_rank"],
        unique=False,
    )
    op.create_index(
        "ix_tickets_queue_open_sort",
        "tickets",
        ["queue_id", "status", "priority", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_queue_open_sort", table_name="tickets")
    op.drop_index("ix_tickets_queue_manual_rank", table_name="tickets")
    op.drop_column("tickets", "manual_rank_updated_by")
    op.drop_column("tickets", "manual_rank_updated_at")
    op.drop_column("tickets", "manual_rank")
