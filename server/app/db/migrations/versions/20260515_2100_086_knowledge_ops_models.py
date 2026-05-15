"""knowledge operations first-class models

Revision ID: 086
Revises: 085
Create Date: 2026-05-15 21:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "086"
down_revision: Union[str, None] = "085"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_review_tasks",
        sa.Column("task_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("assigned_to_actor_id", sa.Text(), nullable=True),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("due_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("source_kind", sa.String(length=60), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("task_type IN ('draft_review', 'scheduled_review', 'stale_content', 'negative_feedback', 'gap_candidate', 'passport_draft', 'ingestion_review', 'unsafe_visibility')", name="ck_knowledge_review_tasks_type"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info')", name="ck_knowledge_review_tasks_severity"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_progress', 'done', 'dismissed')", name="ck_knowledge_review_tasks_status"),
        sa.UniqueConstraint("item_id", "task_type", "source_kind", "source_ref", "status", name="uq_knowledge_review_tasks_open_source"),
    )
    op.create_index("ix_knowledge_review_tasks_status_due", "knowledge_review_tasks", ["status", "due_at"])
    op.create_index("ix_knowledge_review_tasks_item", "knowledge_review_tasks", ["item_id"])
    op.create_index("ix_knowledge_review_tasks_assignee", "knowledge_review_tasks", ["assigned_to_actor_id", "status"])

    op.create_table(
        "knowledge_review_comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("knowledge_review_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
    )
    op.create_index("ix_knowledge_review_comments_task", "knowledge_review_comments", ["task_id", "created_at"])

    op.create_table(
        "knowledge_quality_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(length=2), nullable=False),
        sa.Column("dimensions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("issues_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("computed_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_knowledge_quality_snapshots_score"),
    )
    op.create_index("ix_knowledge_quality_snapshots_item", "knowledge_quality_snapshots", ["item_id", "computed_at"])

    op.create_table(
        "knowledge_gap_findings",
        sa.Column("finding_id", sa.String(length=36), primary_key=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_template_key", sa.String(length=100), nullable=True),
        sa.Column("gap_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("gap_type IN ('no_requester_article', 'no_support_runbook', 'high_volume_no_kb', 'high_not_helpful', 'zero_result_search', 'unresolved_passport_drafts', 'repeated_issue_without_known_error')", name="ck_knowledge_gap_findings_type"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info', 'high', 'medium', 'low')", name="ck_knowledge_gap_findings_severity"),
        sa.CheckConstraint("status IN ('open', 'accepted', 'dismissed', 'resolved')", name="ck_knowledge_gap_findings_status"),
        sa.UniqueConstraint("service_code", "offering_code", "request_template_key", "gap_type", "evidence_hash", name="uq_knowledge_gap_findings_evidence"),
    )
    op.create_index("ix_knowledge_gap_findings_status", "knowledge_gap_findings", ["status", "severity"])
    op.create_index("ix_knowledge_gap_findings_scope", "knowledge_gap_findings", ["service_code", "offering_code"])

    op.create_table(
        "knowledge_search_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("surface", sa.String(length=40), nullable=False, server_default="search"),
        sa.Column("query_text_hash", sa.String(length=64), nullable=False),
        sa.Column("query_text_redacted", sa.Text(), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicked_item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_ticket_after_search", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')", name="ck_knowledge_search_events_surface"),
    )
    op.create_index("ix_knowledge_search_events_scope", "knowledge_search_events", ["service_code", "offering_code", "created_at"])
    op.create_index("ix_knowledge_search_events_zero", "knowledge_search_events", ["result_count", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_search_events_zero", table_name="knowledge_search_events")
    op.drop_index("ix_knowledge_search_events_scope", table_name="knowledge_search_events")
    op.drop_table("knowledge_search_events")
    op.drop_index("ix_knowledge_gap_findings_scope", table_name="knowledge_gap_findings")
    op.drop_index("ix_knowledge_gap_findings_status", table_name="knowledge_gap_findings")
    op.drop_table("knowledge_gap_findings")
    op.drop_index("ix_knowledge_quality_snapshots_item", table_name="knowledge_quality_snapshots")
    op.drop_table("knowledge_quality_snapshots")
    op.drop_index("ix_knowledge_review_comments_task", table_name="knowledge_review_comments")
    op.drop_table("knowledge_review_comments")
    op.drop_index("ix_knowledge_review_tasks_assignee", table_name="knowledge_review_tasks")
    op.drop_index("ix_knowledge_review_tasks_item", table_name="knowledge_review_tasks")
    op.drop_index("ix_knowledge_review_tasks_status_due", table_name="knowledge_review_tasks")
    op.drop_table("knowledge_review_tasks")
