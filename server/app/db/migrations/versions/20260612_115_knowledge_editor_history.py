"""Knowledge authoring editor history and diff cache.

Revision ID: 115
Revises: 114
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "115"
down_revision: Union[str, None] = "114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _has_unique(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_unique_constraints(table)}


def upgrade() -> None:
    if not _has_table("knowledge_article_editor_events"):
        op.create_table(
            "knowledge_article_editor_events",
            sa.Column("event_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("source_surface", sa.String(40), nullable=False, server_default="authoring_studio"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("payload_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
                name="ck_knowledge_editor_events_actor_role",
            ),
            sa.CheckConstraint(
                "event_type IN ('draft_created', 'version_created', 'published', 'rollback_published', 'review_submitted', "
                "'changes_requested', 'approved', 'commented', 'archived', 'retired', 'metadata_changed', 'review_action')",
                name="ck_knowledge_editor_events_type",
            ),
        )
    if not _has_index("knowledge_article_editor_events", "ix_knowledge_editor_events_item_created"):
        op.create_index("ix_knowledge_editor_events_item_created", "knowledge_article_editor_events", ["item_id", "created_at"])
    if not _has_index("knowledge_article_editor_events", "ix_knowledge_editor_events_version"):
        op.create_index("ix_knowledge_editor_events_version", "knowledge_article_editor_events", ["version_id", "created_at"])

    if not _has_table("knowledge_version_diff_cache"):
        op.create_table(
            "knowledge_version_diff_cache",
            sa.Column("diff_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("from_version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
            sa.Column("to_version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("added_lines", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("removed_lines", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("changed_lines", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("summary_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("content_hash", sa.String(64), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    if not _has_unique("knowledge_version_diff_cache", "uq_knowledge_version_diff_cache_to_version"):
        op.create_unique_constraint("uq_knowledge_version_diff_cache_to_version", "knowledge_version_diff_cache", ["to_version_id"])
    if not _has_index("knowledge_version_diff_cache", "ix_knowledge_version_diff_cache_item_created"):
        op.create_index("ix_knowledge_version_diff_cache_item_created", "knowledge_version_diff_cache", ["item_id", "created_at"])
    if not _has_index("knowledge_version_diff_cache", "ix_knowledge_version_diff_cache_to_version"):
        op.create_index("ix_knowledge_version_diff_cache_to_version", "knowledge_version_diff_cache", ["to_version_id"])


def downgrade() -> None:
    for table, indexes in (
        (
            "knowledge_version_diff_cache",
            ["ix_knowledge_version_diff_cache_to_version", "ix_knowledge_version_diff_cache_item_created"],
        ),
        (
            "knowledge_article_editor_events",
            ["ix_knowledge_editor_events_version", "ix_knowledge_editor_events_item_created"],
        ),
    ):
        for index in indexes:
            if _has_index(table, index):
                op.drop_index(index, table_name=table)
        if table == "knowledge_version_diff_cache" and _has_unique(table, "uq_knowledge_version_diff_cache_to_version"):
            op.drop_constraint("uq_knowledge_version_diff_cache_to_version", table, type_="unique")
        if _has_table(table):
            op.drop_table(table)
