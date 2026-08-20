"""Add actor-scoped caller idempotency for Endpoint facade operations.

Revision ID: 137
Revises: 136
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "137"
down_revision = "136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("endpoint_operation_links", sa.Column("caller_actor_id", sa.String(length=128), nullable=True))
    op.add_column("endpoint_operation_links", sa.Column("caller_idempotency_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_endpoint_operation_links_caller_key",
        "endpoint_operation_links",
        ["caller_actor_id", "caller_idempotency_key"],
        unique=True,
        postgresql_where=sa.text("caller_actor_id IS NOT NULL AND caller_idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    raise RuntimeError("Revision 137 is forward-only; roll back the application release instead.")
