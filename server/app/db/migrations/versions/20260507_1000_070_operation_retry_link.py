"""operation retry link

Revision ID: 070
Revises: 069
Create Date: 2026-05-07 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations", sa.Column("retry_of_operation_id", sa.String(length=36), nullable=True))
    op.create_index("ix_operations_retry_of", "operations", ["retry_of_operation_id"])


def downgrade() -> None:
    op.drop_index("ix_operations_retry_of", table_name="operations")
    op.drop_column("operations", "retry_of_operation_id")
