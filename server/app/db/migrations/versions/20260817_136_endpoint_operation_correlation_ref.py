"""Persist opaque Endpoint operation correlation references.

Revision ID: 136
Revises: 135
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "136"
down_revision = "135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("endpoint_operation_links", sa.Column("correlation_ref", sa.String(length=128), nullable=True))


def downgrade() -> None:
    raise RuntimeError("Revision 136 is forward-only; roll back the application release instead.")
