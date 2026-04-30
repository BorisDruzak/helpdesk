"""reporting policy registry

Revision ID: 065
Revises: 064
Create Date: 2026-04-30 20:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "065"
down_revision: Union[str, None] = "064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("reporting_policies"):
        return
    op.execute(sa.text("DROP TYPE IF EXISTS reporting_policies CASCADE"))
    op.create_table(
        "reporting_policies",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope_level", sa.String(length=40), server_default="system", nullable=False),
        sa.Column("scope_ref", sa.String(length=120), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code", "version"),
    )
    op.create_index("ix_reporting_policies_active", "reporting_policies", ["code", "is_active"])
    op.create_index("ix_reporting_policies_scope", "reporting_policies", ["scope_level", "scope_ref"])
    op.create_index("ix_reporting_policies_published_at", "reporting_policies", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_reporting_policies_published_at", table_name="reporting_policies")
    op.drop_index("ix_reporting_policies_scope", table_name="reporting_policies")
    op.drop_index("ix_reporting_policies_active", table_name="reporting_policies")
    op.drop_table("reporting_policies")
