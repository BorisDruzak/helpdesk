"""Allow endpoint facade operations without a legacy Helpdesk device.

Revision ID: 138
Revises: 137
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "138"
down_revision = "137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("operations", "device_id", existing_type=sa.String(length=36), nullable=True)
    op.create_check_constraint(
        "ck_operations_device_id_required_except_endpoint_operation",
        "operations",
        "kind = 'endpoint_operation' OR device_id IS NOT NULL",
    )


def downgrade() -> None:
    raise RuntimeError("Revision 138 is forward-only; roll back the application release instead.")
