"""Add soft-delete fields to devices.

Revision ID: 049
Revises: 048
Create Date: 2026-03-26 10:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "049"
down_revision: Union[str, None] = "048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("devices", sa.Column("deleted_by", sa.Text(), nullable=True))
    op.add_column("devices", sa.Column("delete_reason", sa.Text(), nullable=True))
    op.create_index("ix_devices_deleted_at", "devices", ["deleted_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_devices_deleted_at", table_name="devices")
    op.drop_column("devices", "delete_reason")
    op.drop_column("devices", "deleted_by")
    op.drop_column("devices", "deleted_at")
