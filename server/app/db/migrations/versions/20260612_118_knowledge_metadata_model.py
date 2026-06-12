"""Knowledge taxonomy, properties, applicability and quality model.

Revision ID: 118
Revises: 117
Create Date: 2026-06-12 23:30:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "118"
down_revision: Union[str, None] = "117"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("knowledge_taxonomy_terms"):
        op.create_table(
            "knowledge_taxonomy_terms",
            sa.Column("term_id", sa.String(length=36), nullable=False),
            sa.Column("space_id", sa.String(length=36), nullable=False),
            sa.Column("term_type", sa.String(length=40), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("parent_term_id", sa.String(length=36), nullable=True),
            sa.Column("visibility", sa.String(length=40), server_default="support_internal", nullable=False),
            sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.space_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["parent_term_id"], ["knowledge_taxonomy_terms.term_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("term_id"),
            sa.UniqueConstraint("space_id", "term_type", "code", name="uq_knowledge_taxonomy_terms_space_type_code"),
            sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_taxonomy_terms_code_safe"),
            sa.CheckConstraint("term_type IN ('category', 'product', 'audience', 'topic', 'tag')", name="ck_knowledge_taxonomy_terms_type"),
            sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_taxonomy_terms_visibility"),
            sa.CheckConstraint("status IN ('active', 'draft', 'archived')", name="ck_knowledge_taxonomy_terms_status"),
        )
    if not _has_index("knowledge_taxonomy_terms", "ix_knowledge_taxonomy_terms_space_type"):
        op.create_index("ix_knowledge_taxonomy_terms_space_type", "knowledge_taxonomy_terms", ["space_id", "term_type", "status"])

    if not _has_table("knowledge_property_definitions"):
        op.create_table(
            "knowledge_property_definitions",
            sa.Column("property_id", sa.String(length=36), nullable=False),
            sa.Column("space_id", sa.String(length=36), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("value_type", sa.String(length=30), server_default="text", nullable=False),
            sa.Column("required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("allowed_values_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("applies_to_item_types_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("quality_weight", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.space_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("property_id"),
            sa.UniqueConstraint("space_id", "code", name="uq_knowledge_property_definitions_space_code"),
            sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_property_definitions_code_safe"),
            sa.CheckConstraint("value_type IN ('text', 'number', 'boolean', 'date', 'select', 'multi_select', 'url')", name="ck_knowledge_property_definitions_value_type"),
            sa.CheckConstraint("status IN ('active', 'draft', 'archived')", name="ck_knowledge_property_definitions_status"),
            sa.CheckConstraint("quality_weight >= 0", name="ck_knowledge_property_definitions_weight"),
        )
    if not _has_index("knowledge_property_definitions", "ix_knowledge_property_definitions_space_status"):
        op.create_index("ix_knowledge_property_definitions_space_status", "knowledge_property_definitions", ["space_id", "status"])

    if not _has_table("knowledge_item_properties"):
        op.create_table(
            "knowledge_item_properties",
            sa.Column("item_property_id", sa.String(length=36), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("property_id", sa.String(length=36), nullable=False),
            sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.item_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["property_id"], ["knowledge_property_definitions.property_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("item_property_id"),
            sa.UniqueConstraint("item_id", "property_id", name="uq_knowledge_item_properties_item_property"),
        )
    if not _has_index("knowledge_item_properties", "ix_knowledge_item_properties_item"):
        op.create_index("ix_knowledge_item_properties_item", "knowledge_item_properties", ["item_id"])
    if not _has_index("knowledge_item_properties", "ix_knowledge_item_properties_property"):
        op.create_index("ix_knowledge_item_properties_property", "knowledge_item_properties", ["property_id"])

    if not _has_table("knowledge_item_taxonomy_terms"):
        op.create_table(
            "knowledge_item_taxonomy_terms",
            sa.Column("item_term_id", sa.String(length=36), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("term_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.item_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["term_id"], ["knowledge_taxonomy_terms.term_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("item_term_id"),
            sa.UniqueConstraint("item_id", "term_id", name="uq_knowledge_item_taxonomy_terms_item_term"),
        )
    if not _has_index("knowledge_item_taxonomy_terms", "ix_knowledge_item_taxonomy_terms_item"):
        op.create_index("ix_knowledge_item_taxonomy_terms_item", "knowledge_item_taxonomy_terms", ["item_id"])
    if not _has_index("knowledge_item_taxonomy_terms", "ix_knowledge_item_taxonomy_terms_term"):
        op.create_index("ix_knowledge_item_taxonomy_terms_term", "knowledge_item_taxonomy_terms", ["term_id"])

    if not _has_table("knowledge_applicability_rules"):
        op.create_table(
            "knowledge_applicability_rules",
            sa.Column("rule_id", sa.String(length=36), nullable=False),
            sa.Column("item_id", sa.String(length=36), nullable=False),
            sa.Column("scope_type", sa.String(length=40), nullable=False),
            sa.Column("scope_ref", sa.Text(), nullable=False),
            sa.Column("include_mode", sa.String(length=20), server_default="include", nullable=False),
            sa.Column("priority", sa.Integer(), server_default=sa.text("100"), nullable=False),
            sa.Column("conditions_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.ForeignKeyConstraint(["item_id"], ["knowledge_items.item_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("rule_id"),
            sa.CheckConstraint("scope_type IN ('service', 'offering', 'request_template', 'role', 'device_os', 'device_family', 'audience', 'taxonomy_term', 'custom')", name="ck_knowledge_applicability_rules_scope_type"),
            sa.CheckConstraint("include_mode IN ('include', 'exclude')", name="ck_knowledge_applicability_rules_include_mode"),
        )
    if not _has_index("knowledge_applicability_rules", "ix_knowledge_applicability_rules_item"):
        op.create_index("ix_knowledge_applicability_rules_item", "knowledge_applicability_rules", ["item_id", "priority"])
    if not _has_index("knowledge_applicability_rules", "ix_knowledge_applicability_rules_scope"):
        op.create_index("ix_knowledge_applicability_rules_scope", "knowledge_applicability_rules", ["scope_type", "scope_ref"])

    if not _has_table("knowledge_quality_models"):
        op.create_table(
            "knowledge_quality_models",
            sa.Column("model_id", sa.String(length=36), nullable=False),
            sa.Column("space_id", sa.String(length=36), nullable=True),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("weights_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("thresholds_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
            sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.space_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("model_id"),
            sa.UniqueConstraint("space_id", "code", name="uq_knowledge_quality_models_space_code"),
            sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_quality_models_code_safe"),
            sa.CheckConstraint("status IN ('active', 'draft', 'archived')", name="ck_knowledge_quality_models_status"),
        )
    if not _has_index("knowledge_quality_models", "ix_knowledge_quality_models_space_default"):
        op.create_index("ix_knowledge_quality_models_space_default", "knowledge_quality_models", ["space_id", "is_default", "status"])


def downgrade() -> None:
    for table_name, indexes in (
        ("knowledge_quality_models", ("ix_knowledge_quality_models_space_default",)),
        ("knowledge_applicability_rules", ("ix_knowledge_applicability_rules_scope", "ix_knowledge_applicability_rules_item")),
        ("knowledge_item_taxonomy_terms", ("ix_knowledge_item_taxonomy_terms_term", "ix_knowledge_item_taxonomy_terms_item")),
        ("knowledge_item_properties", ("ix_knowledge_item_properties_property", "ix_knowledge_item_properties_item")),
        ("knowledge_property_definitions", ("ix_knowledge_property_definitions_space_status",)),
        ("knowledge_taxonomy_terms", ("ix_knowledge_taxonomy_terms_space_type",)),
    ):
        if _has_table(table_name):
            for index_name in indexes:
                if _has_index(table_name, index_name):
                    op.drop_index(index_name, table_name=table_name)
            op.drop_table(table_name)
