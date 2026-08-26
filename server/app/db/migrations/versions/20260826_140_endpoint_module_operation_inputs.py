"""Persist safe module invocation inputs and caller idempotency scope.

Revision ID: 140
Revises: 139
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "140"
down_revision = "139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "endpoint_module_operation_links",
        sa.Column("inputs_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "endpoint_module_operation_links",
        sa.Column("caller_actor_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "endpoint_module_operation_links",
        sa.Column("caller_idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_endpoint_module_operation_links_caller_key",
        "endpoint_module_operation_links",
        ["caller_actor_id", "caller_idempotency_key"],
        unique=True,
        postgresql_where=sa.text(
            "caller_actor_id IS NOT NULL AND caller_idempotency_key IS NOT NULL"
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Revision 140 is forward-only; roll back the application release instead.")
