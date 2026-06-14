"""Add knowledge audience rules.

Revision ID: 121
Revises: 120
Create Date: 2026-06-14 22:00:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "121"
down_revision: Union[str, None] = "120"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(table_name):
        return False
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("knowledge_audience_rules"):
        op.create_table(
            "knowledge_audience_rules",
            sa.Column("rule_id", sa.String(length=36), nullable=False),
            sa.Column("subject_type", sa.String(length=20), nullable=False),
            sa.Column("subject_id", sa.String(length=36), nullable=False),
            sa.Column("target_type", sa.String(length=40), nullable=False),
            sa.Column("target_id", sa.Text(), nullable=False),
            sa.Column("effect", sa.String(length=20), server_default="allow", nullable=False),
            sa.Column("include_children", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
            sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("rule_id"),
            sa.CheckConstraint("subject_type IN ('space', 'item')", name="ck_knowledge_audience_rules_subject_type"),
            sa.CheckConstraint(
                "target_type IN ('person', 'department', 'department_tree', 'location', 'access_group', 'audience_group', 'role', 'service')",
                name="ck_knowledge_audience_rules_target_type",
            ),
            sa.CheckConstraint("effect IN ('allow')", name="ck_knowledge_audience_rules_effect"),
            sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name="ck_knowledge_audience_rules_status"),
        )
    if not _has_index("knowledge_audience_rules", "ix_knowledge_audience_rules_subject"):
        op.create_index(
            "ix_knowledge_audience_rules_subject",
            "knowledge_audience_rules",
            ["subject_type", "subject_id", "status", "priority"],
        )
    if not _has_index("knowledge_audience_rules", "ix_knowledge_audience_rules_target"):
        op.create_index(
            "ix_knowledge_audience_rules_target",
            "knowledge_audience_rules",
            ["target_type", "target_id", "status"],
        )
    if not _has_index("knowledge_audience_rules", "ix_knowledge_audience_rules_status"):
        op.create_index("ix_knowledge_audience_rules_status", "knowledge_audience_rules", ["status"])


def downgrade() -> None:
    if _has_table("knowledge_audience_rules"):
        for index_name in (
            "ix_knowledge_audience_rules_status",
            "ix_knowledge_audience_rules_target",
            "ix_knowledge_audience_rules_subject",
        ):
            if _has_index("knowledge_audience_rules", index_name):
                op.drop_index(index_name, table_name="knowledge_audience_rules")
        op.drop_table("knowledge_audience_rules")
