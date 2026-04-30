"""sla and ola policy registry

Revision ID: 064
Revises: 063
Create Date: 2026-04-30 19:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "064"
down_revision: Union[str, None] = "063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_TABLES = ["sla_policies", "ola_policies"]


def _create_versioned_policy_table(table_name: str) -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table(table_name):
        return
    op.execute(sa.text(f"DROP TYPE IF EXISTS {table_name} CASCADE"))
    op.create_table(
        table_name,
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
    op.create_index(f"ix_{table_name}_active", table_name, ["code", "is_active"])
    op.create_index(f"ix_{table_name}_scope", table_name, ["scope_level", "scope_ref"])
    op.create_index(f"ix_{table_name}_published_at", table_name, ["published_at"])


def _drop_versioned_policy_table(table_name: str) -> None:
    op.drop_index(f"ix_{table_name}_published_at", table_name=table_name)
    op.drop_index(f"ix_{table_name}_scope", table_name=table_name)
    op.drop_index(f"ix_{table_name}_active", table_name=table_name)
    op.drop_table(table_name)


def upgrade() -> None:
    for table_name in POLICY_TABLES:
        _create_versioned_policy_table(table_name)


def downgrade() -> None:
    for table_name in reversed(POLICY_TABLES):
        _drop_versioned_policy_table(table_name)
