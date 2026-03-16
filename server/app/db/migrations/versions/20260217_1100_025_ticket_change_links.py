"""Stage 7: ticket_change_links — lightweight Change linkage to tickets

Revision ID: 025
Revises: 024
Create Date: 2026-02-17 11:00:00.000000

- ticket_change_links: id, ticket_id, change_ref, change_system, created_by, created_at
- UNIQUE (ticket_id, change_ref, change_system)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_change_links",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_ref", sa.Text(), nullable=False),
        sa.Column("change_system", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "change_ref", "change_system", name="uq_ticket_change_links_ticket_ref_system"),
    )
    op.create_index("ix_ticket_change_links_ticket_id", "ticket_change_links", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_change_links_ticket_id", table_name="ticket_change_links")
    op.drop_table("ticket_change_links")
