"""helpdesk policy registry

Revision ID: 063
Revises: 062
Create Date: 2026-04-30 18:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "063"
down_revision: Union[str, None] = "062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_TABLES = [
    "priority_policies",
    "routing_policies",
    "approval_policies",
    "closure_policies",
    "diagnostic_policies",
    "notification_policies",
    "visibility_policies",
]


def _create_versioned_policy_table(table_name: str) -> None:
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
    op.create_table(
        "request_templates",
        sa.Column("template_code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("public_title", sa.Text(), nullable=False),
        sa.Column("internal_name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ticket_type", sa.String(length=64), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("service_id", sa.BigInteger(), nullable=True),
        sa.Column("subcategory_id", sa.BigInteger(), nullable=True),
        sa.Column("form_schema_id", sa.String(length=120), nullable=True),
        sa.Column("workflow_profile_id", sa.String(length=120), nullable=True),
        sa.Column("priority_policy_code", sa.String(length=100), nullable=True),
        sa.Column("routing_policy_code", sa.String(length=100), nullable=True),
        sa.Column("sla_policy_id", sa.BigInteger(), nullable=True),
        sa.Column("ola_policy_code", sa.String(length=100), nullable=True),
        sa.Column("approval_policy_code", sa.String(length=100), nullable=True),
        sa.Column("diagnostic_policy_code", sa.String(length=100), nullable=True),
        sa.Column("closure_policy_code", sa.String(length=100), nullable=True),
        sa.Column("visibility_policy_code", sa.String(length=100), nullable=True),
        sa.Column("notification_policy_code", sa.String(length=100), nullable=True),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("overrides_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("template_code", "version"),
    )
    op.create_index("ix_request_templates_active", "request_templates", ["template_code", "is_active"])
    op.create_index("ix_request_templates_type_category", "request_templates", ["ticket_type", "category_id"])
    op.create_index("ix_request_templates_published_at", "request_templates", ["published_at"])

    for table_name in POLICY_TABLES:
        _create_versioned_policy_table(table_name)

    op.create_table(
        "smart_views",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope_level", sa.String(length=40), server_default="system", nullable=False),
        sa.Column("scope_ref", sa.String(length=120), nullable=True),
        sa.Column("filter_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("sort_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("columns_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code", "version"),
    )
    op.create_index("ix_smart_views_active", "smart_views", ["code", "is_active"])
    op.create_index("ix_smart_views_scope", "smart_views", ["scope_level", "scope_ref"])
    op.create_index("ix_smart_views_published_at", "smart_views", ["published_at"])

    op.create_table(
        "helpdesk_policy_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_code", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_helpdesk_policy_audit_entity",
        "helpdesk_policy_audit",
        ["entity_type", "entity_code", "created_at"],
    )
    op.create_index(
        "ix_helpdesk_policy_audit_actor",
        "helpdesk_policy_audit",
        ["actor_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_helpdesk_policy_audit_actor", table_name="helpdesk_policy_audit")
    op.drop_index("ix_helpdesk_policy_audit_entity", table_name="helpdesk_policy_audit")
    op.drop_table("helpdesk_policy_audit")

    op.drop_index("ix_smart_views_published_at", table_name="smart_views")
    op.drop_index("ix_smart_views_scope", table_name="smart_views")
    op.drop_index("ix_smart_views_active", table_name="smart_views")
    op.drop_table("smart_views")

    for table_name in reversed(POLICY_TABLES):
        _drop_versioned_policy_table(table_name)

    op.drop_index("ix_request_templates_published_at", table_name="request_templates")
    op.drop_index("ix_request_templates_type_category", table_name="request_templates")
    op.drop_index("ix_request_templates_active", table_name="request_templates")
    op.drop_table("request_templates")
