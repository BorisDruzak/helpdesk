"""quality loop tables

Revision ID: 088
Revises: 087
Create Date: 2026-05-17 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "088"
down_revision: Union[str, None] = "087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_table_if_missing(name: str, *columns, **kwargs) -> None:
    if name not in _tables():
        op.create_table(name, *columns, **kwargs)


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}
    if name not in indexes:
        op.create_index(name, table, columns)


def upgrade() -> None:
    _create_table_if_missing(
        "ticket_feedback",
        sa.Column("feedback_id", sa.String(length=36), primary_key=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("public_access_id", sa.Text(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("sentiment", sa.String(length=20), nullable=False),
        sa.Column("resolution_confirmed", sa.Boolean(), nullable=True),
        sa.Column("problem_resolved", sa.Boolean(), nullable=True),
        sa.Column("response_time_satisfaction", sa.Integer(), nullable=True),
        sa.Column("communication_satisfaction", sa.Integer(), nullable=True),
        sa.Column("quality_satisfaction", sa.Integer(), nullable=True),
        sa.Column("reason_codes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=30), nullable=False, server_default="requester_visible"),
        sa.Column("source_surface", sa.String(length=40), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("submitted_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_ticket_feedback_rating"),
        sa.CheckConstraint("response_time_satisfaction IS NULL OR response_time_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_response_time_rating"),
        sa.CheckConstraint("communication_satisfaction IS NULL OR communication_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_communication_rating"),
        sa.CheckConstraint("quality_satisfaction IS NULL OR quality_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_quality_rating"),
        sa.CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name="ck_ticket_feedback_sentiment"),
        sa.CheckConstraint("visibility IN ('support_internal', 'manager_aggregate', 'requester_visible')", name="ck_ticket_feedback_visibility"),
        sa.CheckConstraint("source_surface IN ('requester_portal', 'public_ticket_page', 'agent_gui', 'email_link', 'support_entered', 'api')", name="ck_ticket_feedback_source_surface"),
        sa.CheckConstraint("comment IS NULL OR char_length(comment) <= 2000", name="ck_ticket_feedback_comment_length"),
    )
    _create_index_if_missing("ix_ticket_feedback_ticket_id", "ticket_feedback", ["ticket_id"])
    _create_index_if_missing("ix_ticket_feedback_ticket_latest", "ticket_feedback", ["ticket_id", "is_latest"])
    _create_index_if_missing("ix_ticket_feedback_service_offering_submitted", "ticket_feedback", ["service_code", "offering_code", "submitted_at"])

    _create_table_if_missing(
        "ticket_reopen_events",
        sa.Column("reopen_id", sa.String(length=36), primary_key=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("reopened_by_actor_id", sa.Text(), nullable=True),
        sa.Column("reopened_by_role", sa.String(length=40), nullable=True),
        sa.Column("previous_status", sa.String(length=40), nullable=False),
        sa.Column("new_status", sa.String(length=40), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("reason_comment", sa.Text(), nullable=True),
        sa.Column("linked_feedback_id", sa.String(length=36), sa.ForeignKey("ticket_feedback.feedback_id", ondelete="SET NULL"), nullable=True),
        sa.Column("linked_knowledge_item_id", sa.String(length=36), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("reason_code IN ('not_resolved', 'problem_returned', 'incomplete_work', 'wrong_resolution', 'unclear_instruction', 'requester_disagreed', 'closed_too_early', 'new_information', 'wrong_category_or_queue', 'dependency_failed', 'knowledge_article_failed', 'other')", name="ck_ticket_reopen_reason_code"),
        sa.CheckConstraint("reason_code <> 'other' OR btrim(coalesce(reason_comment, '')) <> ''", name="ck_ticket_reopen_other_comment"),
        sa.CheckConstraint("previous_status IN ('resolved', 'closed')", name="ck_ticket_reopen_previous_status"),
    )
    _create_index_if_missing("ix_ticket_reopen_events_ticket_id", "ticket_reopen_events", ["ticket_id"])
    _create_index_if_missing("ix_ticket_reopen_service_offering_created", "ticket_reopen_events", ["service_code", "offering_code", "created_at"])

    _create_table_if_missing(
        "ticket_quality_reviews",
        sa.Column("review_id", sa.String(length=36), primary_key=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("assigned_to_actor_id", sa.Text(), nullable=True),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("queue_id", sa.BigInteger(), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("due_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trigger_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("findings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("reviewer_actor_id", sa.Text(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("review_type IN ('low_csat', 'reopened', 'sla_breached', 'high_priority', 'missing_evidence', 'closure_policy_exception', 'negative_kb_feedback', 'random_sample', 'manager_request', 'quality_audit')", name="ck_ticket_quality_reviews_type"),
        sa.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low', 'info')", name="ck_ticket_quality_reviews_severity"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_review', 'passed', 'failed', 'action_required', 'dismissed')", name="ck_ticket_quality_reviews_status"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_ticket_quality_reviews_score"),
    )
    _create_index_if_missing("ix_ticket_quality_reviews_ticket_id", "ticket_quality_reviews", ["ticket_id"])
    _create_index_if_missing("ix_ticket_quality_reviews_status_due", "ticket_quality_reviews", ["status", "due_at"])
    _create_index_if_missing("ix_ticket_quality_reviews_type_status", "ticket_quality_reviews", ["review_type", "status"])
    _create_index_if_missing("ix_ticket_quality_reviews_service_offering", "ticket_quality_reviews", ["service_code", "offering_code"])
    _create_index_if_missing("ix_ticket_quality_reviews_queue_id", "ticket_quality_reviews", ["queue_id"])

    _create_table_if_missing(
        "ticket_quality_review_comments",
        sa.Column("comment_id", sa.String(length=36), primary_key=True),
        sa.Column("review_id", sa.String(length=36), sa.ForeignKey("ticket_quality_reviews.review_id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("visibility IN ('internal', 'manager', 'audit')", name="ck_ticket_quality_review_comments_visibility"),
        sa.CheckConstraint("btrim(body) <> '' AND char_length(body) <= 4000", name="ck_ticket_quality_review_comments_body"),
    )
    _create_index_if_missing("ix_ticket_quality_review_comments_review_id", "ticket_quality_review_comments", ["review_id"])

    _create_table_if_missing(
        "continuous_improvement_actions",
        sa.Column("action_id", sa.String(length=36), primary_key=True),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_id", sa.String(length=36), sa.ForeignKey("ticket_quality_reviews.review_id", ondelete="SET NULL"), nullable=True),
        sa.Column("feedback_id", sa.String(length=36), sa.ForeignKey("ticket_feedback.feedback_id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("action_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("due_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("outcome_notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("source_kind IN ('csat', 'reopen', 'qa_review', 'knowledge_gap', 'service_quality', 'sla_breach', 'problem_candidate', 'manual')", name="ck_continuous_improvement_source_kind"),
        sa.CheckConstraint("action_type IN ('update_kb_article', 'create_kb_article', 'create_known_error', 'improve_request_form', 'update_routing_policy', 'adjust_sla_policy', 'add_diagnostic_playbook', 'train_support', 'open_problem_candidate', 'create_change_candidate', 'contact_requester', 'process_review', 'other')", name="ck_continuous_improvement_action_type"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_progress', 'blocked', 'done', 'dismissed')", name="ck_continuous_improvement_status"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_continuous_improvement_priority"),
        sa.CheckConstraint("btrim(title) <> ''", name="ck_continuous_improvement_title"),
    )
    _create_index_if_missing("ix_continuous_improvement_actions_ticket_id", "continuous_improvement_actions", ["ticket_id"])
    _create_index_if_missing("ix_continuous_improvement_actions_owner_actor_id", "continuous_improvement_actions", ["owner_actor_id"])
    _create_index_if_missing("ix_continuous_improvement_status_priority", "continuous_improvement_actions", ["status", "priority"])
    _create_index_if_missing("ix_continuous_improvement_service_offering", "continuous_improvement_actions", ["service_code", "offering_code"])

    _create_table_if_missing(
        "service_quality_snapshots",
        sa.Column("snapshot_id", sa.String(length=36), primary_key=True),
        sa.Column("period_start", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("period_end", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("bucket", sa.String(length=20), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_type", sa.String(length=64), nullable=True),
        sa.Column("queue_id", sa.BigInteger(), nullable=True),
        sa.Column("ticket_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("closed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feedback_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_csat", sa.Numeric(5, 2), nullable=True),
        sa.Column("negative_csat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reopen_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("sla_breach_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_breach_rate", sa.Numeric(8, 4), nullable=True),
        sa.Column("first_response_breach_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolution_breach_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("knowledge_attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ticket_after_failed_knowledge_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deflection_count", sa.Integer(), nullable=True),
        sa.Column("qa_review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qa_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("improvement_action_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("computed_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("bucket IN ('day', 'week', 'month')", name="ck_service_quality_snapshots_bucket"),
    )
    _create_index_if_missing("ix_service_quality_snapshots_service_period", "service_quality_snapshots", ["service_code", "offering_code", "period_start", "period_end"])
    _create_index_if_missing("ix_service_quality_snapshots_queue_period", "service_quality_snapshots", ["queue_id", "period_start", "period_end"])

    _create_table_if_missing(
        "quality_policies",
        sa.Column("policy_id", sa.String(length=36), primary_key=True),
        sa.Column("scope_type", sa.String(length=20), nullable=False, server_default="global"),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("queue_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("low_csat_threshold", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("reopen_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sla_breach_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("high_priority_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("missing_evidence_review_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("random_sample_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("qa_due_hours", sa.Integer(), nullable=False, server_default="72"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("scope_type IN ('global', 'service', 'offering', 'queue')", name="ck_quality_policies_scope_type"),
        sa.CheckConstraint("low_csat_threshold BETWEEN 1 AND 5", name="ck_quality_policies_low_csat_threshold"),
        sa.CheckConstraint("random_sample_percent >= 0 AND random_sample_percent <= 100", name="ck_quality_policies_random_sample_percent"),
        sa.CheckConstraint("qa_due_hours > 0", name="ck_quality_policies_due_hours"),
    )
    _create_index_if_missing("ix_quality_policies_scope", "quality_policies", ["scope_type", "service_code", "offering_code", "queue_id"])


def downgrade() -> None:
    for table in (
        "quality_policies",
        "service_quality_snapshots",
        "continuous_improvement_actions",
        "ticket_quality_review_comments",
        "ticket_quality_reviews",
        "ticket_reopen_events",
        "ticket_feedback",
    ):
        if table in _tables():
            op.drop_table(table)
