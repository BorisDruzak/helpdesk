"""Add last_request_at to connection_requests for heartbeat / active-only display.

Revision ID: 045
Revises: 044
Create Date: 2026-03-18 10:00:00

- connection_requests.last_request_at: обновляется при каждом POST от агента;
  в списке для админки показываются только запросы с last_request_at за последние 30 сек.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "045"
down_revision: Union[str, None] = "044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "connection_requests",
        sa.Column("last_request_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.execute(
        "UPDATE connection_requests SET last_request_at = created_at WHERE last_request_at IS NULL"
    )
    op.alter_column(
        "connection_requests",
        "last_request_at",
        existing_type=sa.TIMESTAMP(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("connection_requests", "last_request_at")
