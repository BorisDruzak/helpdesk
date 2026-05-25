"""registry quality issue overrides

Revision ID: 104
Revises: 103
Create Date: 2026-05-25 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "104"
down_revision: Union[str, None] = "103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("registry_quality_issue_overrides"):
        op.create_table(
            "registry_quality_issue_overrides",
            sa.Column("issue_key", sa.String(length=300), nullable=False),
            sa.Column("issue_kind", sa.String(length=80), nullable=False),
            sa.Column("object_type", sa.String(length=50), nullable=False),
            sa.Column("object_id", sa.String(length=120), nullable=False),
            sa.Column("related_id", sa.String(length=120), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("snoozed_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("issue_key"),
        )
    if not _has_index("registry_quality_issue_overrides", "ix_registry_quality_overrides_status_until"):
        op.create_index(
            "ix_registry_quality_overrides_status_until",
            "registry_quality_issue_overrides",
            ["status", "snoozed_until"],
        )
    if not _has_index("registry_quality_issue_overrides", "ix_registry_quality_overrides_object"):
        op.create_index(
            "ix_registry_quality_overrides_object",
            "registry_quality_issue_overrides",
            ["object_type", "object_id"],
        )


def downgrade() -> None:
    if _has_table("registry_quality_issue_overrides"):
        for name in (
            "ix_registry_quality_overrides_object",
            "ix_registry_quality_overrides_status_until",
        ):
            if _has_index("registry_quality_issue_overrides", name):
                op.drop_index(name, table_name="registry_quality_issue_overrides")
        op.drop_table("registry_quality_issue_overrides")
