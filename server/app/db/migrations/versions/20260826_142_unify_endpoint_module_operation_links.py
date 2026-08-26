"""Unify module operations with the established Endpoint facade link lifecycle.

Revision ID: 142
Revises: 141
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "142"
down_revision = "141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("endpoint_operation_links", sa.Column("module_key", sa.String(length=128), nullable=True))
    op.add_column("endpoint_operation_links", sa.Column("module_version", sa.String(length=64), nullable=True))
    op.add_column("endpoint_operation_links", sa.Column("module_spec_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "endpoint_operation_links",
        sa.Column("module_inputs_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "endpoint_operation_links",
        sa.Column("safe_module_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_constraint("ck_endpoint_operation_links_capability_code", "endpoint_operation_links", type_="check")
    op.create_check_constraint(
        "ck_endpoint_operation_links_capability_code",
        "endpoint_operation_links",
        "(capability_code = 'context.diagnostic.collect' AND module_key IS NULL AND module_version IS NULL) "
        "OR (capability_code = 'endpoint.module.recipe' AND module_key IS NOT NULL AND module_version IS NOT NULL)",
    )
    # Revisions 139-140 were never a production contract; remove their empty
    # staging table so every Endpoint facade operation has one local lifecycle.
    op.drop_table("endpoint_module_operation_links")


def downgrade() -> None:
    raise RuntimeError("Revision 142 is forward-only; roll back the application release instead.")
