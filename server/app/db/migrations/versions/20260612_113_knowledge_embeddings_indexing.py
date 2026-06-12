"""Knowledge embeddings and index jobs.

Revision ID: 113
Revises: 112
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "113"
down_revision: Union[str, None] = "112"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("knowledge_chunk_embeddings"):
        op.create_table(
            "knowledge_chunk_embeddings",
            sa.Column("embedding_id", sa.String(36), primary_key=True),
            sa.Column("chunk_id", sa.String(36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="CASCADE"), nullable=False),
            sa.Column("segment_id", sa.String(36), nullable=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("model_profile_id", sa.String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True),
            sa.Column("embedding_model", sa.Text(), nullable=True),
            sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
            sa.Column("embedding_vector", JSONB, nullable=True),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("embedding_input_hash", sa.String(64), nullable=True),
            sa.Column("visibility", sa.String(40), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("indexed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("error_redacted", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "status IN ('pending', 'indexed', 'failed', 'stale', 'disabled')",
                name="ck_knowledge_chunk_embeddings_status",
            ),
            sa.CheckConstraint(
                "visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')",
                name="ck_knowledge_chunk_embeddings_visibility",
            ),
        )

    if not _has_table("knowledge_index_jobs"):
        op.create_table(
            "knowledge_index_jobs",
            sa.Column("job_id", sa.String(36), primary_key=True),
            sa.Column("scope_type", sa.String(30), nullable=False),
            sa.Column("scope_ref", sa.Text(), nullable=True),
            sa.Column("model_profile_id", sa.String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
            sa.Column("requested_by", sa.Text(), nullable=True),
            sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("stats_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("error_redacted", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint(
                "scope_type IN ('item', 'version', 'space', 'all', 'segment')",
                name="ck_knowledge_index_jobs_scope_type",
            ),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'completed', 'failed', 'canceled')",
                name="ck_knowledge_index_jobs_status",
            ),
        )

    if not _has_index("knowledge_chunk_embeddings", "ix_knowledge_chunk_embeddings_chunk_status"):
        op.create_index("ix_knowledge_chunk_embeddings_chunk_status", "knowledge_chunk_embeddings", ["chunk_id", "status"])
    if not _has_index("knowledge_chunk_embeddings", "ix_knowledge_chunk_embeddings_item_version"):
        op.create_index("ix_knowledge_chunk_embeddings_item_version", "knowledge_chunk_embeddings", ["item_id", "version_id", "status"])
    if not _has_index("knowledge_chunk_embeddings", "ix_knowledge_chunk_embeddings_segment"):
        op.create_index("ix_knowledge_chunk_embeddings_segment", "knowledge_chunk_embeddings", ["segment_id"])
    if not _has_index("knowledge_index_jobs", "ix_knowledge_index_jobs_scope_status"):
        op.create_index("ix_knowledge_index_jobs_scope_status", "knowledge_index_jobs", ["scope_type", "scope_ref", "status"])


def downgrade() -> None:
    if _has_table("knowledge_index_jobs"):
        if _has_index("knowledge_index_jobs", "ix_knowledge_index_jobs_scope_status"):
            op.drop_index("ix_knowledge_index_jobs_scope_status", table_name="knowledge_index_jobs")
        op.drop_table("knowledge_index_jobs")
    if _has_table("knowledge_chunk_embeddings"):
        for name in (
            "ix_knowledge_chunk_embeddings_segment",
            "ix_knowledge_chunk_embeddings_item_version",
            "ix_knowledge_chunk_embeddings_chunk_status",
        ):
            if _has_index("knowledge_chunk_embeddings", name):
                op.drop_index(name, table_name="knowledge_chunk_embeddings")
        op.drop_table("knowledge_chunk_embeddings")
