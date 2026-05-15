"""knowledge operations content packs

Revision ID: 085
Revises: 084
Create Date: 2026-05-15 16:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "085"
down_revision: Union[str, None] = "084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_content_packs",
        sa.Column("pack_id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("installed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("installed_by", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="installed"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("code", "version", name="uq_knowledge_content_packs_code_version"),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_content_packs_code_safe"),
        sa.CheckConstraint("status IN ('installed', 'partially_installed', 'failed', 'retired')", name="ck_knowledge_content_packs_status"),
    )
    op.create_index("ix_knowledge_content_packs_code_status", "knowledge_content_packs", ["code", "status"])

    op.create_table(
        "knowledge_content_pack_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("pack_code", sa.String(length=120), nullable=False),
        sa.Column("pack_version", sa.Integer(), nullable=False),
        sa.Column("item_slug", sa.String(length=120), nullable=False),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("install_status", sa.String(length=40), nullable=False),
        sa.Column("last_error_redacted", sa.Text(), nullable=True),
        sa.Column("installed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("install_status IN ('created', 'skipped', 'updated', 'conflict', 'failed', 'retired')", name="ck_knowledge_content_pack_items_status"),
    )
    op.create_index("ix_knowledge_content_pack_items_pack", "knowledge_content_pack_items", ["pack_code", "pack_version"])
    op.create_index("ix_knowledge_content_pack_items_slug", "knowledge_content_pack_items", ["item_slug"])

    op.create_table(
        "knowledge_rollout_policies",
        sa.Column("policy_id", sa.String(length=36), primary_key=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_template_key", sa.String(length=100), nullable=True),
        sa.Column("surface", sa.String(length=40), nullable=False, server_default="requester_portal"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rollout_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.UniqueConstraint("service_code", "offering_code", "request_template_key", "surface", name="uq_knowledge_rollout_policy_scope"),
        sa.CheckConstraint("surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')", name="ck_knowledge_rollout_policies_surface"),
        sa.CheckConstraint("rollout_percent >= 0 AND rollout_percent <= 100", name="ck_knowledge_rollout_policies_percent"),
    )
    op.create_index(
        "ix_knowledge_rollout_policies_scope",
        "knowledge_rollout_policies",
        ["service_code", "offering_code", "request_template_key", "surface"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_rollout_policies_scope", table_name="knowledge_rollout_policies")
    op.drop_table("knowledge_rollout_policies")
    op.drop_index("ix_knowledge_content_pack_items_slug", table_name="knowledge_content_pack_items")
    op.drop_index("ix_knowledge_content_pack_items_pack", table_name="knowledge_content_pack_items")
    op.drop_table("knowledge_content_pack_items")
    op.drop_index("ix_knowledge_content_packs_code_status", table_name="knowledge_content_packs")
    op.drop_table("knowledge_content_packs")
