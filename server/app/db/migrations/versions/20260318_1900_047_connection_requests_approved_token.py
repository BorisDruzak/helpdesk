"""Persist one-time approved token for connection requests.

Revision ID: 047
Revises: 046
Create Date: 2026-03-18 19:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "connection_requests",
        sa.Column("approved_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "connection_requests",
        sa.Column("approved_token_delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connection_requests", "approved_token_delivered_at")
    op.drop_column("connection_requests", "approved_token")
