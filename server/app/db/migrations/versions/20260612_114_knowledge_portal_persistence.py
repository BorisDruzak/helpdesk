"""Knowledge portal persisted user signals.

Revision ID: 114
Revises: 113
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "114"
down_revision: Union[str, None] = "113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("knowledge_article_views"):
        op.create_table(
            "knowledge_article_views",
            sa.Column("view_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("session_id", sa.Text(), nullable=True),
            sa.Column("source_surface", sa.String(40), nullable=False, server_default="requester_portal"),
            sa.Column("viewed_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
                name="ck_knowledge_article_views_actor_role",
            ),
        )
    if not _has_index("knowledge_article_views", "ix_knowledge_article_views_item_viewed"):
        op.create_index("ix_knowledge_article_views_item_viewed", "knowledge_article_views", ["item_id", "viewed_at"])
    if not _has_index("knowledge_article_views", "ix_knowledge_article_views_actor"):
        op.create_index("ix_knowledge_article_views_actor", "knowledge_article_views", ["actor_id", "session_id", "viewed_at"])

    if not _has_table("knowledge_user_bookmarks"):
        op.create_table(
            "knowledge_user_bookmarks",
            sa.Column("bookmark_id", sa.String(36), primary_key=True),
            sa.Column("bookmark_key", sa.Text(), nullable=False),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("session_id", sa.Text(), nullable=True),
            sa.Column("bookmark_state", sa.String(20), nullable=False, server_default="active"),
            sa.Column("source_surface", sa.String(40), nullable=False, server_default="requester_portal"),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("bookmark_state IN ('active', 'removed')", name="ck_knowledge_user_bookmarks_state"),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
                name="ck_knowledge_user_bookmarks_actor_role",
            ),
            sa.UniqueConstraint("bookmark_key", "item_id", name="uq_knowledge_user_bookmarks_key_item"),
        )
    if not _has_index("knowledge_user_bookmarks", "ix_knowledge_user_bookmarks_item_state"):
        op.create_index("ix_knowledge_user_bookmarks_item_state", "knowledge_user_bookmarks", ["item_id", "bookmark_state", "updated_at"])

    if not _has_table("knowledge_correction_requests"):
        op.create_table(
            "knowledge_correction_requests",
            sa.Column("correction_request_id", sa.String(36), primary_key=True),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("version_id", sa.String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
            sa.Column("feedback_event_id", sa.String(36), sa.ForeignKey("knowledge_feedback_events.event_id", ondelete="SET NULL"), nullable=True),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("session_id", sa.Text(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="open"),
            sa.Column("source_surface", sa.String(40), nullable=False, server_default="requester_portal"),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("status IN ('open', 'triaged', 'accepted', 'rejected', 'closed')", name="ck_knowledge_correction_requests_status"),
            sa.CheckConstraint("length(trim(comment)) > 0", name="ck_knowledge_correction_requests_comment"),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
                name="ck_knowledge_correction_requests_actor_role",
            ),
        )
    if not _has_index("knowledge_correction_requests", "ix_knowledge_correction_requests_item_status"):
        op.create_index("ix_knowledge_correction_requests_item_status", "knowledge_correction_requests", ["item_id", "status", "created_at"])

    if not _has_table("knowledge_article_subscriptions"):
        op.create_table(
            "knowledge_article_subscriptions",
            sa.Column("subscription_id", sa.String(36), primary_key=True),
            sa.Column("subscription_key", sa.Text(), nullable=False),
            sa.Column("item_id", sa.String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("session_id", sa.Text(), nullable=True),
            sa.Column("subscription_state", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("subscription_state IN ('active', 'paused', 'removed')", name="ck_knowledge_article_subscriptions_state"),
            sa.CheckConstraint(
                "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
                name="ck_knowledge_article_subscriptions_actor_role",
            ),
            sa.UniqueConstraint("subscription_key", "item_id", name="uq_knowledge_article_subscriptions_key_item"),
        )
    if not _has_index("knowledge_article_subscriptions", "ix_knowledge_article_subscriptions_item_state"):
        op.create_index(
            "ix_knowledge_article_subscriptions_item_state",
            "knowledge_article_subscriptions",
            ["item_id", "subscription_state", "updated_at"],
        )


def downgrade() -> None:
    for table, indexes in (
        ("knowledge_article_subscriptions", ["ix_knowledge_article_subscriptions_item_state"]),
        ("knowledge_correction_requests", ["ix_knowledge_correction_requests_item_status"]),
        ("knowledge_user_bookmarks", ["ix_knowledge_user_bookmarks_item_state"]),
        ("knowledge_article_views", ["ix_knowledge_article_views_actor", "ix_knowledge_article_views_item_viewed"]),
    ):
        for index in indexes:
            if _has_index(table, index):
                op.drop_index(index, table_name=table)
        if _has_table(table):
            op.drop_table(table)
