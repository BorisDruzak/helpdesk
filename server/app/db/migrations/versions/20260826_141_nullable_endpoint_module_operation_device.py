"""Allow module facade operations without a legacy Helpdesk device.

Revision ID: 141
Revises: 140
"""
from __future__ import annotations

from alembic import op


revision = "141"
down_revision = "140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_operations_device_id_required_except_endpoint_operation",
        "operations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_operations_device_id_required_except_endpoint_facade_operation",
        "operations",
        "kind IN ('endpoint_operation', 'endpoint_module_operation') OR device_id IS NOT NULL",
    )


def downgrade() -> None:
    raise RuntimeError("Revision 141 is forward-only; roll back the application release instead.")
