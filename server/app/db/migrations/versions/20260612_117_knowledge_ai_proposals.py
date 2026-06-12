"""Knowledge AI proposal review queue.

Revision ID: 117
Revises: 116
Create Date: 2026-06-12 16:25:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "117"
down_revision: Union[str, None] = "116"
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
    if not _has_table("knowledge_ai_proposals"):
        op.create_table(
            "knowledge_ai_proposals",
            sa.Column("proposal_id", sa.String(length=36), nullable=False),
            sa.Column("proposal_type", sa.String(length=40), nullable=False),
            sa.Column("target_kind", sa.String(length=40), nullable=False),
            sa.Column("target_ref", sa.Text(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("proposed_payload_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
            sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
            sa.Column("visibility", sa.String(length=40), server_default="support_internal", nullable=False),
            sa.Column("source_kind", sa.String(length=60), nullable=True),
            sa.Column("source_ref", sa.Text(), nullable=True),
            sa.Column("applied_refs_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.CheckConstraint("proposal_type IN ('summary', 'tags', 'glossary_term', 'graph_node', 'graph_edge', 'duplicate')", name="ck_knowledge_ai_proposals_type"),
            sa.CheckConstraint("target_kind IN ('item', 'version', 'graph', 'space', 'import_job')", name="ck_knowledge_ai_proposals_target_kind"),
            sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'archived')", name="ck_knowledge_ai_proposals_status"),
            sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_ai_proposals_visibility"),
            sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_ai_proposals_confidence"),
            sa.PrimaryKeyConstraint("proposal_id"),
        )
    if not _has_index("knowledge_ai_proposals", "ix_knowledge_ai_proposals_status_target"):
        op.create_index("ix_knowledge_ai_proposals_status_target", "knowledge_ai_proposals", ["status", "target_kind"])
    if not _has_index("knowledge_ai_proposals", "ix_knowledge_ai_proposals_type_status"):
        op.create_index("ix_knowledge_ai_proposals_type_status", "knowledge_ai_proposals", ["proposal_type", "status"])
    if not _has_index("knowledge_ai_proposals", "ix_knowledge_ai_proposals_created"):
        op.create_index("ix_knowledge_ai_proposals_created", "knowledge_ai_proposals", ["created_at"])


def downgrade() -> None:
    if _has_table("knowledge_ai_proposals"):
        for index_name in (
            "ix_knowledge_ai_proposals_created",
            "ix_knowledge_ai_proposals_type_status",
            "ix_knowledge_ai_proposals_status_target",
        ):
            if _has_index("knowledge_ai_proposals", index_name):
                op.drop_index(index_name, table_name="knowledge_ai_proposals")
        op.drop_table("knowledge_ai_proposals")
