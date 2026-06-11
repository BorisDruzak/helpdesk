"""Knowledge article segments.

Revision ID: 112
Revises: 111
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "112"
down_revision: Union[str, None] = "111"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("knowledge_segmentation_profiles"):
        op.create_table(
            "knowledge_segmentation_profiles",
            sa.Column("profile_id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False, unique=True),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("mode", sa.String(30), nullable=False, server_default="auto"),
            sa.Column("split_by_headings", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("split_by_paragraphs", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("target_tokens", sa.Integer(), nullable=False, server_default="350"),
            sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="700"),
            sa.Column("min_tokens", sa.Integer(), nullable=False, server_default="40"),
            sa.Column("overlap_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("preserve_tables", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("preserve_code_blocks", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("default_segment_boost", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("ai_profile_id", sa.String(36), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint("mode IN ('auto', 'manual_default', 'ai')", name="ck_knowledge_segmentation_profiles_mode"),
            sa.CheckConstraint("target_tokens BETWEEN 1 AND 20000", name="ck_knowledge_segmentation_profiles_target_tokens"),
            sa.CheckConstraint("max_tokens BETWEEN 1 AND 50000", name="ck_knowledge_segmentation_profiles_max_tokens"),
        )

    if not _has_table("knowledge_article_segments"):
        op.create_table(
            "knowledge_article_segments",
            sa.Column("segment_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("segment_index", sa.Integer(), nullable=False),
            sa.Column("segment_type", sa.String(30), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("start_offset", sa.Integer(), nullable=True),
            sa.Column("end_offset", sa.Integer(), nullable=True),
            sa.Column("heading_path_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("keywords_json", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("boost", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("visibility", sa.String(40), nullable=False),
            sa.Column("embedding_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("full_text_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("source", sa.String(40), nullable=False, server_default="editor_selection"),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("segment_type IN ('manual', 'auto', 'ai_proposed', 'ai_approved')", name="ck_knowledge_article_segments_type"),
            sa.CheckConstraint("status IN ('draft', 'active', 'stale', 'archived', 'rejected')", name="ck_knowledge_article_segments_status"),
            sa.CheckConstraint("source IN ('editor_selection', 'paragraph_split', 'length_split', 'heading_split', 'ai_markup')", name="ck_knowledge_article_segments_source"),
            sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_article_segments_visibility"),
            sa.CheckConstraint("boost >= 0 AND boost <= 10", name="ck_knowledge_article_segments_boost"),
            sa.CheckConstraint("start_offset IS NULL OR start_offset >= 0", name="ck_knowledge_article_segments_start_offset"),
            sa.CheckConstraint("end_offset IS NULL OR end_offset >= 0", name="ck_knowledge_article_segments_end_offset"),
            sa.UniqueConstraint("version_id", "segment_index", name="uq_knowledge_article_segments_version_index"),
        )

    if not _has_table("knowledge_segmentation_jobs"):
        op.create_table(
            "knowledge_segmentation_jobs",
            sa.Column("job_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("profile_id", sa.String(36), nullable=True),
            sa.Column("mode", sa.String(30), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("stats_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("error_redacted", sa.Text(), nullable=True),
            sa.CheckConstraint("mode IN ('manual', 'auto', 'ai')", name="ck_knowledge_segmentation_jobs_mode"),
            sa.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'canceled')", name="ck_knowledge_segmentation_jobs_status"),
        )

    if not _has_index("knowledge_article_segments", "ix_knowledge_article_segments_item_version"):
        op.create_index("ix_knowledge_article_segments_item_version", "knowledge_article_segments", ["item_id", "version_id"])
    if not _has_index("knowledge_article_segments", "ix_knowledge_article_segments_status_visibility"):
        op.create_index("ix_knowledge_article_segments_status_visibility", "knowledge_article_segments", ["status", "visibility"])
    if not _has_index("knowledge_article_segments", "ix_knowledge_article_segments_hash"):
        op.create_index("ix_knowledge_article_segments_hash", "knowledge_article_segments", ["content_hash"])
    if not _has_index("knowledge_segmentation_jobs", "ix_knowledge_segmentation_jobs_item_version"):
        op.create_index("ix_knowledge_segmentation_jobs_item_version", "knowledge_segmentation_jobs", ["item_id", "version_id", "status"])


def downgrade() -> None:
    if _has_table("knowledge_segmentation_jobs"):
        if _has_index("knowledge_segmentation_jobs", "ix_knowledge_segmentation_jobs_item_version"):
            op.drop_index("ix_knowledge_segmentation_jobs_item_version", table_name="knowledge_segmentation_jobs")
        op.drop_table("knowledge_segmentation_jobs")
    if _has_table("knowledge_article_segments"):
        for name in (
            "ix_knowledge_article_segments_hash",
            "ix_knowledge_article_segments_status_visibility",
            "ix_knowledge_article_segments_item_version",
        ):
            if _has_index("knowledge_article_segments", name):
                op.drop_index(name, table_name="knowledge_article_segments")
        op.drop_table("knowledge_article_segments")
    if _has_table("knowledge_segmentation_profiles"):
        op.drop_table("knowledge_segmentation_profiles")
