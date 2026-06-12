"""
SQLAlchemy database models.
"""
from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import (
    BigInteger,
    Boolean,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
import sqlalchemy as sa
from app.db.base import Base


class Ticket(Base):
    """
    Ticket model for Protocol V3 (расширенная тикетная система).
    
    Represents a support ticket bound to a specific device.
    Статусы: canonical ticket status contract from tickets.statuses.CANONICAL_STATUSES.
    Совместимость: legacy aliases normalize only at input boundaries and are not stored.
    """
    __tablename__ = "tickets"
    
    ticket_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_code: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True,
        server_default=sa.text("'T-' || lpad(nextval('ticket_code_seq')::text, 6, '0')"),
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    # Расширенная модель (миграция 018)
    ticket_type: Mapped[str] = mapped_column(String(64), nullable=False, server_default="request")
    priority: Mapped[str] = mapped_column(String(5), nullable=False, server_default="P3")
    impact: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    urgency: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    importance: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    urgency_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    importance_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    requester_id: Mapped[str] = mapped_column(Text, nullable=False)
    requester_person_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    requester_binding_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    requester_registration_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    requester_account_session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    requester_account_mode: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    requester_account_warning: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    assignee_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    service_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    subcategory_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    catalog_service_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("helpdesk_services.service_id", ondelete="SET NULL"),
        nullable=True,
    )
    catalog_offering_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("helpdesk_service_offerings.offering_id", ondelete="SET NULL"),
        nullable=True,
    )
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    business_criticality: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    service_owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    support_group_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_action_owner: Mapped[str] = mapped_column(String(30), nullable=False, server_default="support", index=True)
    next_action_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    status_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requester_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="accepted", index=True)
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requester_resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    evidence_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closure_feedback: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    canceled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_policy_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    first_response_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    first_response_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_paused_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    sla_paused_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Stage 11: OLA (queue-level)
    ola_queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ola_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_ack_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_processing_breached_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_paused_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ola_paused_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    observer_root_trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolution_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    parent_ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # Stage 10.2: ручной порядок в очереди (отдельно от priority/SLA)
    manual_rank: Mapped[Optional[int]] = mapped_column(sa.BigInteger, nullable=True)
    manual_rank_updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    manual_rank_updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Скрытие из веб-очереди (только для закрытых): в БД остаётся, в список не попадает
    archived_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('new', 'queued', 'assigned', 'in_progress', "
            "'waiting_on_user', 'waiting_on_internal_team', 'waiting_on_vendor', "
            "'waiting_on_approval', 'scheduled', 'resolved', 'closed', 'canceled')",
            name="ck_tickets_status_canonical",
        ),
        sa.CheckConstraint("btrim(requester_id) <> ''", name="ck_tickets_requester_id_non_empty"),
        sa.CheckConstraint("sla_policy_id IS NULL OR priority IS NOT NULL", name="ck_tickets_sla_priority_present"),
        Index("ix_tickets_device_id_status", "device_id", "status"),
        Index("ix_tickets_queue_status_priority", "queue_id", "status", "priority"),
        Index("ix_tickets_assignee_status", "assignee_id", "status"),
        Index("ix_tickets_requester_created", "requester_id", "created_at"),
        Index("ix_tickets_requester_person_created", "requester_person_id", "created_at"),
        Index("ix_tickets_requester_binding", "requester_binding_id"),
        Index("ix_tickets_requester_registration_status", "requester_registration_status"),
        Index("ix_tickets_requester_account_session_id", "requester_account_session_id"),
        Index("ix_tickets_device_account_session", "device_id", "requester_account_session_id"),
        Index("ix_tickets_requester_account_mode", "requester_account_mode"),
        Index("ix_tickets_requester_account_warning", "requester_account_warning"),
        Index("ix_tickets_service_offering_created", "service_code", "offering_code", "created_at"),
        Index("ix_tickets_catalog_service_created", "catalog_service_id", "created_at"),
        Index("ix_tickets_catalog_offering_created", "catalog_offering_id", "created_at"),
        Index("ix_tickets_reporting_category_created", "reporting_category", "created_at"),
        Index("ix_tickets_status_updated", "status", "updated_at"),
        Index("ix_tickets_first_response_due", "first_response_due_at"),
        Index("ix_tickets_resolution_due", "resolution_due_at"),
        Index("ix_tickets_ola_queue_id", "ola_queue_id"),
        Index("ix_tickets_ola_ack_due_at", "ola_ack_due_at"),
        Index("ix_tickets_ola_ack_breached_at", "ola_ack_breached_at"),
        Index("ix_tickets_ola_processing_due_at", "ola_processing_due_at"),
        Index("ix_tickets_ola_processing_breached_at", "ola_processing_breached_at"),
        Index("ix_tickets_queue_manual_rank", "queue_id", "manual_rank"),
        Index("ix_tickets_queue_open_sort", "queue_id", "status", "priority", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Ticket(ticket_id={self.ticket_id!r}, device_id={self.device_id!r}, "
            f"status={self.status!r})>"
        )


class TicketFeedback(Base):
    """Structured requester satisfaction feedback for resolved/closed tickets."""

    __tablename__ = "ticket_feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    requester_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    public_access_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    resolution_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    problem_resolved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    response_time_satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    communication_satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    quality_satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason_codes: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="requester_visible")
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))

    __table_args__ = (
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_ticket_feedback_rating"),
        sa.CheckConstraint("response_time_satisfaction IS NULL OR response_time_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_response_time_rating"),
        sa.CheckConstraint("communication_satisfaction IS NULL OR communication_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_communication_rating"),
        sa.CheckConstraint("quality_satisfaction IS NULL OR quality_satisfaction BETWEEN 1 AND 5", name="ck_ticket_feedback_quality_rating"),
        sa.CheckConstraint("sentiment IN ('positive', 'neutral', 'negative')", name="ck_ticket_feedback_sentiment"),
        sa.CheckConstraint("visibility IN ('support_internal', 'manager_aggregate', 'requester_visible')", name="ck_ticket_feedback_visibility"),
        sa.CheckConstraint("source_surface IN ('requester_portal', 'public_ticket_page', 'agent_gui', 'email_link', 'support_entered', 'api')", name="ck_ticket_feedback_source_surface"),
        sa.CheckConstraint("comment IS NULL OR char_length(comment) <= 2000", name="ck_ticket_feedback_comment_length"),
        Index("ix_ticket_feedback_ticket_latest", "ticket_id", "is_latest"),
        Index("uq_ticket_feedback_latest_per_ticket", "ticket_id", unique=True, postgresql_where=sa.text("is_latest IS TRUE")),
        Index("ix_ticket_feedback_service_offering_submitted", "service_code", "offering_code", "submitted_at"),
    )


class TicketReopenEvent(Base):
    """Structured reopen reason event for quality analytics."""

    __tablename__ = "ticket_reopen_events"

    reopen_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    reopened_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopened_by_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    previous_status: Mapped[str] = mapped_column(String(40), nullable=False)
    new_status: Mapped[str] = mapped_column(String(40), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(60), nullable=False)
    reason_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_feedback_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ticket_feedback.feedback_id", ondelete="SET NULL"), nullable=True)
    linked_knowledge_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("reason_code IN ('not_resolved', 'problem_returned', 'incomplete_work', 'wrong_resolution', 'unclear_instruction', 'requester_disagreed', 'closed_too_early', 'new_information', 'wrong_category_or_queue', 'dependency_failed', 'knowledge_article_failed', 'other')", name="ck_ticket_reopen_reason_code"),
        sa.CheckConstraint("reason_code <> 'other' OR btrim(coalesce(reason_comment, '')) <> ''", name="ck_ticket_reopen_other_comment"),
        sa.CheckConstraint("previous_status IN ('resolved', 'closed')", name="ck_ticket_reopen_previous_status"),
        Index("ix_ticket_reopen_service_offering_created", "service_code", "offering_code", "created_at"),
    )


class TicketQualityReview(Base):
    """Internal QA review queue item."""

    __tablename__ = "ticket_quality_reviews"

    review_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    review_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    assigned_to_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trigger_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    findings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewer_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("review_type IN ('low_csat', 'reopened', 'sla_breached', 'high_priority', 'missing_evidence', 'closure_policy_exception', 'negative_kb_feedback', 'random_sample', 'manager_request', 'quality_audit')", name="ck_ticket_quality_reviews_type"),
        sa.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low', 'info')", name="ck_ticket_quality_reviews_severity"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_review', 'passed', 'failed', 'action_required', 'dismissed')", name="ck_ticket_quality_reviews_status"),
        sa.CheckConstraint("score IS NULL OR score BETWEEN 0 AND 100", name="ck_ticket_quality_reviews_score"),
        Index("ix_ticket_quality_reviews_status_due", "status", "due_at"),
        Index("ix_ticket_quality_reviews_type_status", "review_type", "status"),
        Index("ix_ticket_quality_reviews_service_offering", "service_code", "offering_code"),
    )


class TicketQualityReviewComment(Base):
    """Internal comments on quality reviews."""

    __tablename__ = "ticket_quality_review_comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("ticket_quality_reviews.review_id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="internal")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint("visibility IN ('internal', 'manager', 'audit')", name="ck_ticket_quality_review_comments_visibility"),
        sa.CheckConstraint("btrim(body) <> '' AND char_length(body) <= 4000", name="ck_ticket_quality_review_comments_body"),
    )


class ContinuousImprovementAction(Base):
    """Process improvement action created from quality signals."""

    __tablename__ = "continuous_improvement_actions"

    action_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True, index=True)
    review_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ticket_quality_reviews.review_id", ondelete="SET NULL"), nullable=True)
    feedback_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ticket_feedback.feedback_id", ondelete="SET NULL"), nullable=True)
    problem_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True)
    problem_candidate_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problem_candidates.candidate_id", ondelete="SET NULL"), nullable=True)
    change_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="SET NULL"), nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    outcome_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("source_kind IN ('csat', 'reopen', 'qa_review', 'knowledge_gap', 'service_quality', 'sla_breach', 'problem_candidate', 'problem', 'change', 'manual')", name="ck_continuous_improvement_source_kind"),
        sa.CheckConstraint("action_type IN ('update_kb_article', 'create_kb_article', 'create_known_error', 'improve_request_form', 'update_routing_policy', 'adjust_sla_policy', 'add_diagnostic_playbook', 'train_support', 'open_problem_candidate', 'create_change_candidate', 'contact_requester', 'process_review', 'perform_rca', 'implement_permanent_fix', 'validate_workaround', 'update_known_error', 'other')", name="ck_continuous_improvement_action_type"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_progress', 'blocked', 'done', 'dismissed')", name="ck_continuous_improvement_status"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_continuous_improvement_priority"),
        sa.CheckConstraint("btrim(title) <> ''", name="ck_continuous_improvement_title"),
        Index("ix_continuous_improvement_status_priority", "status", "priority"),
        Index("ix_continuous_improvement_service_offering", "service_code", "offering_code"),
    )


class ServiceQualitySnapshot(Base):
    """Aggregate service/offering quality metrics for dashboards."""

    __tablename__ = "service_quality_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    period_start: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    bucket: Mapped[str] = mapped_column(String(20), nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    ticket_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avg_csat: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    negative_csat_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reopen_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    sla_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sla_breach_rate: Mapped[Optional[float]] = mapped_column(Numeric(8, 4), nullable=True)
    first_response_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    resolution_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    knowledge_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ticket_after_failed_knowledge_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    deflection_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    qa_review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    qa_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    improvement_action_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("bucket IN ('day', 'week', 'month')", name="ck_service_quality_snapshots_bucket"),
        Index("ix_service_quality_snapshots_service_period", "service_code", "offering_code", "period_start", "period_end"),
        Index("ix_service_quality_snapshots_queue_period", "queue_id", "period_start", "period_end"),
    )


class QualityPolicy(Base):
    """Configurable quality trigger policy."""

    __tablename__ = "quality_policies"

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="global")
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    low_csat_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    reopen_review_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    sla_breach_review_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    high_priority_review_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    missing_evidence_review_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    random_sample_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, server_default="0")
    qa_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="72")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("scope_type IN ('global', 'service', 'offering', 'queue')", name="ck_quality_policies_scope_type"),
        sa.CheckConstraint("low_csat_threshold BETWEEN 1 AND 5", name="ck_quality_policies_low_csat_threshold"),
        sa.CheckConstraint("random_sample_percent >= 0 AND random_sample_percent <= 100", name="ck_quality_policies_random_sample_percent"),
        sa.CheckConstraint("qa_due_hours > 0", name="ck_quality_policies_due_hours"),
        Index("ix_quality_policies_scope", "scope_type", "service_code", "offering_code", "queue_id"),
    )


def _ensure_ticket_requester_id(_mapper, _connection, target: Ticket) -> None:
    """Application-boundary fallback matching migration 081 for legacy direct inserts."""
    requester_id = getattr(target, "requester_id", None)
    if isinstance(requester_id, str) and requester_id.strip():
        return
    device_id = getattr(target, "device_id", None)
    if isinstance(device_id, str) and device_id.strip():
        target.requester_id = f"device:{device_id.strip()}"
        return
    ticket_id = getattr(target, "ticket_id", None)
    if isinstance(ticket_id, str) and ticket_id.strip():
        target.requester_id = f"legacy:{ticket_id.strip()}"
        return
    target.requester_id = "legacy:unknown"


sa.event.listen(Ticket, "before_insert", _ensure_ticket_requester_id)
sa.event.listen(Ticket, "before_update", _ensure_ticket_requester_id)


class TicketEvent(Base):
    """
    Ticket event model for Protocol V3.
    
    Stores all events for tickets with deduplication support.
    Ordered by agent_seq per-ticket.
    """
    __tablename__ = "ticket_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # КРИТИЧНО: agent_seq nullable для server-originated событий (support/user messages)
    # Agent-originated события имеют agent_seq (монотонный, от агента)
    # Server-originated события имеют agent_seq = NULL
    agent_seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        # КРИТИЧНО: Частичный UNIQUE constraint создается в миграции 005 через raw SQL
        # (SQLAlchemy не поддерживает postgresql_where для UniqueConstraint в моделях)
        # Constraint: uq_ticket_events_device_ticket_seq UNIQUE (device_id, ticket_id, agent_seq) WHERE agent_seq IS NOT NULL
        # Server events (agent_seq = NULL) дедуплицируются через логику по message_id в TicketEventsRepo
        # Composite index для эффективного получения событий с сортировкой
        Index("ix_ticket_events_ticket_id_agent_seq", "ticket_id", "agent_seq"),
        Index("ix_ticket_events_ticket_created_id", "ticket_id", "created_at", "id"),
        # Index для фильтрации по типу событий
        Index("ix_ticket_events_ticket_type_seq", "ticket_id", "event_type", "agent_seq"),
        Index("ix_ticket_events_ticket_type_created_id", "ticket_id", "event_type", "created_at", "id"),
        Index("ix_ticket_events_trace_id", "trace_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<TicketEvent(id={self.id}, ticket_id={self.ticket_id!r}, "
            f"event_type={self.event_type!r}, agent_seq={self.agent_seq})>"
        )


class TicketWait(Base):
    """Wait ledger entry for requester, vendor, internal team and approval pauses."""

    __tablename__ = "ticket_waits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    wait_type: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_party: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_waits_ticket_active", "ticket_id", "ended_at"),
        Index("ix_ticket_waits_type_active", "wait_type", "ended_at"),
    )


class TicketResolutionPassport(Base):
    """Versioned generated resolution passport for a ticket."""

    __tablename__ = "ticket_resolution_passports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    summary_source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="deterministic")
    requester_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    affected_object_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    automated_checks_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_checks_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes_made_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approvals_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repeat_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_event_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    source_operation_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    generated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("ticket_id", "version", name="uq_ticket_resolution_passports_ticket_version"),
        Index("ix_ticket_resolution_passports_ticket_generated", "ticket_id", "generated_at"),
    )


class TicketEvidenceItem(Base):
    """Evidence attached to a ticket passport or directly to a ticket."""

    __tablename__ = "ticket_evidence_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    passport_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required_fact: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    section_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    artifact_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("artifacts.artifact_id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="internal")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="unverified")
    verified_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    captured_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    public_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    export_visibility: Mapped[str] = mapped_column(String(30), nullable=False, server_default="internal")
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_evidence_items_ticket_created", "ticket_id", "created_at"),
        Index("ix_ticket_evidence_items_passport", "passport_id"),
        Index("ix_ticket_evidence_items_source", "source_kind", "source_id"),
        Index("ix_ticket_evidence_items_required_fact", "ticket_id", "required_fact"),
        Index("ix_ticket_evidence_items_artifact", "artifact_id"),
        Index(
            "uq_ticket_evidence_items_source_fact",
            "ticket_id",
            "evidence_type",
            "source_kind",
            "source_id",
            "required_fact",
            unique=True,
            postgresql_where=sa.text("source_kind IS NOT NULL AND source_id IS NOT NULL"),
        ),
    )


class TicketActionLog(Base):
    """Action row used by the resolution passport."""

    __tablename__ = "ticket_action_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    passport_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_event_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_action_log_ticket_created", "ticket_id", "created_at"),
        Index("ix_ticket_action_log_operation", "operation_id"),
    )


class TicketApproval(Base):
    """Approval record for governed ticket work."""

    __tablename__ = "ticket_approvals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    passport_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"),
        nullable=True,
    )
    approval_type: Mapped[str] = mapped_column(String(40), nullable=False)
    approver_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="requested")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ticket_approvals_ticket_status", "ticket_id", "status"),
        Index("ix_ticket_approvals_approver_status", "approver_id", "status"),
    )


class TicketRelatedObject(Base):
    """Object relation captured for the resolution passport."""

    __tablename__ = "ticket_related_objects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
    )
    passport_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"),
        nullable=True,
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_ref: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="snapshot")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "ticket_id",
            "object_type",
            "object_ref",
            "relation_type",
            name="uq_ticket_related_objects_unique_relation",
        ),
        Index("ix_ticket_related_objects_ticket", "ticket_id"),
        Index("ix_ticket_related_objects_passport", "passport_id"),
    )


class TicketQueue(Base):
    """Очередь тикетов (ServiceDesk L1, SysAdmins, Network, 1C, Security и т.д.)."""
    __tablename__ = "ticket_queues"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_triage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    auto_assign_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))


class TicketCategory(Base):
    """Иерархия категорий (level 1=category, 2=service, 3=subcategory)."""
    __tablename__ = "ticket_categories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class TicketBusinessCalendar(Base):
    """Stage 11: Бизнес-календарь (рабочие часы, праздники) для SLA."""
    __tablename__ = "ticket_business_calendars"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="UTC")
    weekly_hours_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    holidays_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class TicketSlaPolicy(Base):
    """Политика SLA (24x7 или business hours). Stage 9: is_active. Stage 11: calendar_id."""
    __tablename__ = "ticket_sla_policies"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    business_hours_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    calendar_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_business_calendars.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))


class TicketSlaTarget(Base):
    """Цели SLA по приоритету (FRT и Resolution в минутах)."""
    __tablename__ = "ticket_sla_targets"
    policy_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_sla_policies.id", ondelete="CASCADE"), primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), primary_key=True)
    first_response_min: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_min: Mapped[int] = mapped_column(Integer, nullable=False)


class TicketPriorityMatrix(Base):
    """Матрица impact × urgency -> priority для политики."""
    __tablename__ = "ticket_priority_matrix"
    policy_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_sla_policies.id", ondelete="CASCADE"), primary_key=True)
    impact: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    urgency: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), nullable=False)


class TicketRoutingRule(Base):
    """Правило маршрутизации тикетов в очередь."""
    __tablename__ = "ticket_routing_rules"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    target_queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), nullable=False)


class TicketQueueMember(Base):
    """Участник очереди (actor_id + роль в очереди)."""
    __tablename__ = "ticket_queue_members"
    queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    role_in_queue: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class TicketQueueOlaTarget(Base):
    """Stage 11: OLA-цели по очереди и приоритету (ack_min, processing_min)."""
    __tablename__ = "ticket_queue_ola_targets"
    queue_id: Mapped[int] = mapped_column(BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True)
    priority: Mapped[str] = mapped_column(String(5), primary_key=True)
    ack_min: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_min: Mapped[int] = mapped_column(Integer, nullable=False)


class TicketWatcher(Base):
    """Наблюдатель тикета."""
    __tablename__ = "ticket_watchers"
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)


class TicketLink(Base):
    """Связь тикетов (duplicate, related, parent-child)."""
    __tablename__ = "ticket_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    src_ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    dst_ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketResolutionCode(Base):
    """Справочник кодов резолюции (Stage 5)."""
    __tablename__ = "ticket_resolution_codes"
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))


class TicketKbLink(Base):
    """Ссылка на статью базы знаний по тикету (Stage 5)."""
    __tablename__ = "ticket_kb_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    article_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class KnowledgeSpace(Base):
    """Universal knowledge space such as IT Support, HR, or Security."""

    __tablename__ = "knowledge_spaces"

    space_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_reviewer_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_review_period_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allowed_item_types: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    allow_publication: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    allow_ingestion: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    allow_rag: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_spaces_code_safe"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_spaces_visibility"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'active', 'archived')", name="ck_knowledge_spaces_lifecycle"),
        Index("ix_knowledge_spaces_status_visibility", "lifecycle_status", "visibility"),
    )


class KnowledgeItem(Base):
    """Universal knowledge item. Article is one item type, not the whole model."""

    __tablename__ = "knowledge_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_spaces.space_id", ondelete="RESTRICT"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    item_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    language: Mapped[str] = mapped_column(String(12), nullable=False, server_default="ru")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_ticket_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True)
    source_passport_id: Mapped[Optional[int]] = mapped_column(BigInteger, sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    review_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_items_slug_safe"),
        sa.CheckConstraint("item_type IN ('article', 'faq', 'runbook', 'policy', 'document', 'known_error', 'workaround', 'troubleshooting_tree', 'glossary_term', 'service_description', 'external_source', 'resolution_draft')", name="ck_knowledge_items_type"),
        sa.CheckConstraint("status IN ('draft', 'in_review', 'published', 'needs_review', 'archived')", name="ck_knowledge_items_status"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_items_visibility"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_items_confidence"),
        Index("ix_knowledge_items_space_status", "space_id", "status"),
        Index("ix_knowledge_items_type_status", "item_type", "status"),
        Index("ix_knowledge_items_visibility_status", "visibility", "status"),
        Index("ix_knowledge_items_source_ticket", "source_ticket_id"),
    )


class KnowledgeItemVersion(Base):
    """Versioned knowledge content."""

    __tablename__ = "knowledge_item_versions"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_format: Mapped[str] = mapped_column(String(30), nullable=False, server_default="markdown")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("item_id", "version_number", name="uq_knowledge_item_versions_item_number"),
        sa.CheckConstraint("body_format IN ('markdown', 'html', 'plain_text', 'json', 'structured_steps')", name="ck_knowledge_item_versions_body_format"),
        Index("ix_knowledge_item_versions_item_created", "item_id", "created_at"),
    )


class KnowledgeChunk(Base):
    """Search/retrieval chunk for a knowledge item version."""

    __tablename__ = "knowledge_chunks"

    chunk_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("version_id", "chunk_index", name="uq_knowledge_chunks_version_index"),
        Index("ix_knowledge_chunks_item_version", "item_id", "version_id"),
        Index("ix_knowledge_chunks_hash", "content_hash"),
        Index("ix_knowledge_chunks_visibility", "visibility"),
    )


class KnowledgeBinding(Base):
    """Operational context binding for search/suggestions."""

    __tablename__ = "knowledge_bindings"

    binding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ticket_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    device_class: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    os_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    symptom_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    queue_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    weight: Mapped[float] = mapped_column(sa.Numeric(6, 3), nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_knowledge_bindings_item", "item_id"),
        Index("ix_knowledge_bindings_service_offering", "service_code", "offering_code"),
        Index("ix_knowledge_bindings_template", "request_template_key"),
        Index("ix_knowledge_bindings_symptom_error", "symptom_code", "error_code"),
    )


class KnowledgeNode(Base):
    """Knowledge graph node."""

    __tablename__ = "knowledge_nodes"

    node_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(40), nullable=False)
    stable_key: Mapped[str] = mapped_column(String(240), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    linked_item_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="confirmed")
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("node_type IN ('knowledge_item', 'article', 'known_error', 'workaround', 'glossary_term', 'service', 'offering', 'ticket', 'asset', 'registry_service', 'diagnostic_playbook', 'external_entity', 'concept', 'document')", name="ck_knowledge_nodes_node_type"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_nodes_visibility"),
        sa.CheckConstraint("status IN ('proposed', 'confirmed', 'rejected', 'archived')", name="ck_knowledge_nodes_status"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_nodes_confidence"),
        Index("ix_knowledge_nodes_type_status", "node_type", "status"),
        Index("ix_knowledge_nodes_item", "linked_item_id"),
        Index("ix_knowledge_nodes_service_offering", "service_code", "offering_code"),
    )


class KnowledgeEdge(Base):
    """Knowledge graph relation."""

    __tablename__ = "knowledge_edges"

    edge_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"), nullable=False)
    target_node_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    weight: Mapped[float] = mapped_column(sa.Numeric(6, 3), nullable=False, server_default="1")
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="confirmed")
    source_kind: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    valid_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("relation_type IN ('explains', 'causes', 'caused_by', 'depends_on', 'affects', 'affected_by', 'has_workaround', 'has_permanent_fix', 'requires', 'replaces', 'duplicates', 'similar_to', 'belongs_to_service', 'belongs_to_offering', 'suggested_for', 'tried_in_ticket', 'resolved_by', 'source_of', 'mentions', 'synonym_of', 'contradicts', 'supersedes')", name="ck_knowledge_edges_relation_type"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_edges_visibility"),
        sa.CheckConstraint("status IN ('proposed', 'confirmed', 'rejected', 'archived')", name="ck_knowledge_edges_status"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_edges_confidence"),
        sa.CheckConstraint("weight >= 0", name="ck_knowledge_edges_weight_nonnegative"),
        sa.CheckConstraint("source_node_id <> target_node_id", name="ck_knowledge_edges_no_self_relation"),
        UniqueConstraint("source_node_id", "target_node_id", "relation_type", "source_ref", name="uq_knowledge_edges_exact"),
        Index("ix_knowledge_edges_source", "source_node_id", "relation_type"),
        Index("ix_knowledge_edges_target", "target_node_id", "relation_type"),
    )


class KnowledgeGraphLayout(Base):
    """Persisted canvas layout for a knowledge graph scope."""

    __tablename__ = "knowledge_graph_layouts"

    layout_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="graph")
    scope_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    layout_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("scope_type IN ('graph', 'space', 'item')", name="ck_knowledge_graph_layouts_scope_type"),
        UniqueConstraint("scope_type", "scope_ref", name="uq_knowledge_graph_layouts_scope"),
        Index("ix_knowledge_graph_layouts_scope", "scope_type", "scope_ref"),
    )


class KnowledgeAiProposal(Base):
    """Governed AI proposal awaiting human review before applying changes."""

    __tablename__ = "knowledge_ai_proposals"

    proposal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    target_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    source_kind: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_refs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("proposal_type IN ('summary', 'tags', 'glossary_term', 'graph_node', 'graph_edge', 'duplicate')", name="ck_knowledge_ai_proposals_type"),
        sa.CheckConstraint("target_kind IN ('item', 'version', 'graph', 'space', 'import_job')", name="ck_knowledge_ai_proposals_target_kind"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'archived')", name="ck_knowledge_ai_proposals_status"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_knowledge_ai_proposals_visibility"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_ai_proposals_confidence"),
        Index("ix_knowledge_ai_proposals_status_target", "status", "target_kind"),
        Index("ix_knowledge_ai_proposals_type_status", "proposal_type", "status"),
        Index("ix_knowledge_ai_proposals_created", "created_at"),
    )


class KnowledgeEntityMention(Base):
    """Entity mention inside a knowledge version/chunk."""

    __tablename__ = "knowledge_entity_mentions"

    mention_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="SET NULL"), nullable=True)
    node_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    start_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    confidence_score: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("extraction_method IN ('manual', 'rule', 'model', 'import')", name="ck_knowledge_mentions_extraction_method"),
        sa.CheckConstraint("status IN ('proposed', 'confirmed', 'rejected')", name="ck_knowledge_mentions_status"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_mentions_confidence"),
        Index("ix_knowledge_mentions_item_version", "item_id", "version_id"),
        Index("ix_knowledge_mentions_node", "node_id"),
    )


class KnowledgeFeedbackEvent(Base):
    """Knowledge usage, helpfulness and deflection event."""

    __tablename__ = "knowledge_feedback_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    chunk_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="SET NULL"), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="api")
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("source_surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')", name="ck_knowledge_feedback_source_surface"),
        sa.CheckConstraint("event_type IN ('suggested', 'viewed', 'helpful', 'not_helpful', 'deflected', 'ticket_created_after_view', 'support_linked', 'support_used', 'draft_created', 'published', 'archived')", name="ck_knowledge_feedback_event_type"),
        sa.CheckConstraint("actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')", name="ck_knowledge_feedback_actor_role"),
        Index("ix_knowledge_feedback_item_event_created", "item_id", "event_type", "created_at"),
        Index("ix_knowledge_feedback_service_offering_created", "service_code", "offering_code", "created_at"),
        Index("ix_knowledge_feedback_ticket", "ticket_id"),
    )


class KnowledgeArticleView(Base):
    """Persisted requester portal article view."""

    __tablename__ = "knowledge_article_views"

    view_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="requester_portal")
    viewed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
            name="ck_knowledge_article_views_actor_role",
        ),
        Index("ix_knowledge_article_views_item_viewed", "item_id", "viewed_at"),
        Index("ix_knowledge_article_views_actor", "actor_id", "session_id", "viewed_at"),
    )


class KnowledgeUserBookmark(Base):
    """Per-actor/session requester portal bookmark state."""

    __tablename__ = "knowledge_user_bookmarks"

    bookmark_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    bookmark_key: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bookmark_state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="requester_portal")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("bookmark_state IN ('active', 'removed')", name="ck_knowledge_user_bookmarks_state"),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
            name="ck_knowledge_user_bookmarks_actor_role",
        ),
        sa.UniqueConstraint("bookmark_key", "item_id", name="uq_knowledge_user_bookmarks_key_item"),
        Index("ix_knowledge_user_bookmarks_item_state", "item_id", "bookmark_state", "updated_at"),
    )


class KnowledgeCorrectionRequest(Base):
    """Requester correction request tied to an article version."""

    __tablename__ = "knowledge_correction_requests"

    correction_request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    feedback_event_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_feedback_events.event_id", ondelete="SET NULL"), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="requester_portal")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("status IN ('open', 'triaged', 'accepted', 'rejected', 'closed')", name="ck_knowledge_correction_requests_status"),
        sa.CheckConstraint("length(trim(comment)) > 0", name="ck_knowledge_correction_requests_comment"),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
            name="ck_knowledge_correction_requests_actor_role",
        ),
        Index("ix_knowledge_correction_requests_item_status", "item_id", "status", "created_at"),
    )


class KnowledgeArticleSubscription(Base):
    """Future portal subscription state for article update notifications."""

    __tablename__ = "knowledge_article_subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    subscription_key: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subscription_state: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("subscription_state IN ('active', 'paused', 'removed')", name="ck_knowledge_article_subscriptions_state"),
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
            name="ck_knowledge_article_subscriptions_actor_role",
        ),
        sa.UniqueConstraint("subscription_key", "item_id", name="uq_knowledge_article_subscriptions_key_item"),
        Index("ix_knowledge_article_subscriptions_item_state", "item_id", "subscription_state", "updated_at"),
    )


class KnowledgeArticleEditorEvent(Base):
    """Audit-grade workflow event emitted by the authoring studio."""

    __tablename__ = "knowledge_article_editor_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="authoring_studio")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint(
            "actor_role IS NULL OR actor_role IN ('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')",
            name="ck_knowledge_editor_events_actor_role",
        ),
        sa.CheckConstraint(
            "event_type IN ('draft_created', 'version_created', 'published', 'rollback_published', 'review_submitted', "
            "'changes_requested', 'approved', 'commented', 'archived', 'retired', 'metadata_changed', 'review_action')",
            name="ck_knowledge_editor_events_type",
        ),
        Index("ix_knowledge_editor_events_item_created", "item_id", "created_at"),
        Index("ix_knowledge_editor_events_version", "version_id", "created_at"),
    )


class KnowledgeVersionDiffCache(Base):
    """Cached line-level diff summary for immutable knowledge versions."""

    __tablename__ = "knowledge_version_diff_cache"

    diff_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    from_version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    to_version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    added_lines: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    removed_lines: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    changed_lines: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("to_version_id", name="uq_knowledge_version_diff_cache_to_version"),
        Index("ix_knowledge_version_diff_cache_item_created", "item_id", "created_at"),
        Index("ix_knowledge_version_diff_cache_to_version", "to_version_id"),
    )


class KnowledgeIngestionJob(Base):
    """Document/source ingestion job. P2 creates drafts and never auto-publishes."""

    __tablename__ = "knowledge_ingestion_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    space_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_spaces.space_id", ondelete="RESTRICT"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    created_item_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True)
    created_version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    error_message_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("source_kind IN ('manual_upload', 'text', 'markdown', 'html', 'pdf', 'docx', 'external_url', 'ticket_passport', 'git_repo', 'api')", name="ck_knowledge_ingestion_source_kind"),
        sa.CheckConstraint("status IN ('queued', 'parsing', 'chunking', 'indexing', 'review_required', 'completed', 'failed', 'canceled')", name="ck_knowledge_ingestion_status"),
        Index("ix_knowledge_ingestion_jobs_space_status", "space_id", "status"),
        Index("ix_knowledge_ingestion_jobs_created", "created_at"),
    )


class TicketKnowledgeLink(Base):
    """Normalized ticket-to-knowledge link while ticket_kb_links remains compatible."""

    __tablename__ = "ticket_knowledge_links"

    link_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_linked")
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("link_type IN ('suggested', 'user_tried', 'support_linked', 'used_for_resolution', 'generated_from_ticket')", name="ck_ticket_knowledge_links_link_type"),
        sa.CheckConstraint("visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')", name="ck_ticket_knowledge_links_visibility"),
        UniqueConstraint("ticket_id", "item_id", "link_type", name="uq_ticket_knowledge_links_ticket_item_type"),
        Index("ix_ticket_knowledge_links_ticket", "ticket_id", "created_at"),
        Index("ix_ticket_knowledge_links_item", "item_id"),
    )


class KnowledgeContentPack(Base):
    """Idempotent operational content pack install state."""

    __tablename__ = "knowledge_content_packs"

    pack_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    installed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    installed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="installed")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_knowledge_content_packs_code_version"),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_content_packs_code_safe"),
        sa.CheckConstraint("status IN ('installed', 'partially_installed', 'failed', 'retired')", name="ck_knowledge_content_packs_status"),
        Index("ix_knowledge_content_packs_code_status", "code", "status"),
    )


class KnowledgeContentPackItem(Base):
    """Per-item audit row for knowledge content pack application."""

    __tablename__ = "knowledge_content_pack_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pack_code: Mapped[str] = mapped_column(String(120), nullable=False)
    pack_version: Mapped[int] = mapped_column(Integer, nullable=False)
    item_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    item_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    install_status: Mapped[str] = mapped_column(String(40), nullable=False)
    last_error_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    installed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("install_status IN ('created', 'skipped', 'updated', 'conflict', 'failed', 'retired', 'bindings_repaired')", name="ck_knowledge_content_pack_items_status"),
        Index("ix_knowledge_content_pack_items_pack", "pack_code", "pack_version"),
        Index("ix_knowledge_content_pack_items_slug", "item_slug"),
    )


class KnowledgeRolloutPolicy(Base):
    """Rollout gate for requester/agent self-service deflection."""

    __tablename__ = "knowledge_rollout_policies"

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="requester_portal")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    rollout_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="global")
    show_before_form: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    show_after_form: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    require_suggestions_before_submit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    allow_skip: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    urgency_bypass: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    impact_bypass: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    min_suggestions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_suggestions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    deflection_prompt_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    feedback_required_on_article_view: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    show_known_errors: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    show_quality_badge: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    show_review_freshness: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    no_suggestions_behavior: Mapped[str] = mapped_column(String(30), nullable=False, server_default="allow_submit")
    api_unavailable_behavior: Mapped[str] = mapped_column(String(30), nullable=False, server_default="allow_submit")
    bypass_roles: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    effective_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("service_code", "offering_code", "request_template_key", "surface", name="uq_knowledge_rollout_policy_scope"),
        sa.CheckConstraint("surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'api', 'all')", name="ck_knowledge_rollout_policies_surface"),
        sa.CheckConstraint("rollout_percent >= 0 AND rollout_percent <= 100", name="ck_knowledge_rollout_policies_percent"),
        sa.CheckConstraint("scope_type IN ('global', 'service', 'offering', 'template')", name="ck_knowledge_rollout_scope_type"),
        sa.CheckConstraint("min_suggestions >= 0 AND max_suggestions >= min_suggestions", name="ck_knowledge_rollout_suggestion_bounds"),
        sa.CheckConstraint("no_suggestions_behavior IN ('allow_submit', 'show_message', 'block_submit')", name="ck_knowledge_rollout_no_suggestions_behavior"),
        sa.CheckConstraint("api_unavailable_behavior IN ('allow_submit', 'show_warning', 'block_submit')", name="ck_knowledge_rollout_api_unavailable_behavior"),
        sa.CheckConstraint(
            "((scope_type = 'global' AND service_code IS NULL AND offering_code IS NULL AND request_template_key IS NULL) "
            "OR (scope_type = 'service' AND service_code IS NOT NULL AND offering_code IS NULL AND request_template_key IS NULL) "
            "OR (scope_type = 'offering' AND service_code IS NOT NULL AND offering_code IS NOT NULL) "
            "OR (scope_type = 'template' AND request_template_key IS NOT NULL))",
            name="ck_knowledge_rollout_scope_fields",
        ),
        Index("ix_knowledge_rollout_policies_scope", "service_code", "offering_code", "request_template_key", "surface"),
    )


class KnowledgeReviewTask(Base):
    """Operational review/curation task for knowledge lifecycle work."""

    __tablename__ = "knowledge_review_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="warning")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    assigned_to_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    source_kind: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("task_type IN ('draft_review', 'scheduled_review', 'stale_content', 'negative_feedback', 'gap_candidate', 'passport_draft', 'ingestion_review', 'unsafe_visibility')", name="ck_knowledge_review_tasks_type"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info')", name="ck_knowledge_review_tasks_severity"),
        sa.CheckConstraint("status IN ('open', 'assigned', 'in_progress', 'done', 'dismissed')", name="ck_knowledge_review_tasks_status"),
        UniqueConstraint("item_id", "task_type", "source_kind", "source_ref", "status", name="uq_knowledge_review_tasks_open_source"),
        Index("ix_knowledge_review_tasks_status_due", "status", "due_at"),
        Index("ix_knowledge_review_tasks_item", "item_id"),
        Index("ix_knowledge_review_tasks_assignee", "assigned_to_actor_id", "status"),
    )


class KnowledgeReviewComment(Base):
    """Comment/audit entry on a knowledge review task."""

    __tablename__ = "knowledge_review_comments"

    comment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_review_tasks.task_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_knowledge_review_comments_task", "task_id", "created_at"),)


class KnowledgeQualitySnapshot(Base):
    """Optional cached explainable quality score for a knowledge item/version."""

    __tablename__ = "knowledge_quality_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    grade: Mapped[str] = mapped_column(String(2), nullable=False)
    dimensions_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    issues_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    computed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_knowledge_quality_snapshots_score"),
        Index("ix_knowledge_quality_snapshots_item", "item_id", "computed_at"),
    )


class KnowledgeGapFinding(Base):
    """Persistent knowledge coverage/usefulness finding."""

    __tablename__ = "knowledge_gap_findings"

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gap_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="warning")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("gap_type IN ('no_requester_article', 'no_support_runbook', 'high_volume_no_kb', 'high_not_helpful', 'zero_result_search', 'unresolved_passport_drafts', 'repeated_issue_without_known_error')", name="ck_knowledge_gap_findings_type"),
        sa.CheckConstraint("severity IN ('critical', 'error', 'warning', 'info', 'high', 'medium', 'low')", name="ck_knowledge_gap_findings_severity"),
        sa.CheckConstraint("status IN ('open', 'accepted', 'dismissed', 'resolved')", name="ck_knowledge_gap_findings_status"),
        UniqueConstraint("service_code", "offering_code", "request_template_key", "gap_type", "evidence_hash", name="uq_knowledge_gap_findings_evidence"),
        Index("ix_knowledge_gap_findings_status", "status", "severity"),
        Index("ix_knowledge_gap_findings_scope", "service_code", "offering_code"),
    )


class KnowledgeSearchEvent(Base):
    """Privacy-preserving search analytics event."""

    __tablename__ = "knowledge_search_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    surface: Mapped[str] = mapped_column(String(40), nullable=False, server_default="search")
    query_text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    query_text_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    clicked_item_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True)
    created_ticket_after_search: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')", name="ck_knowledge_search_events_surface"),
        Index("ix_knowledge_search_events_scope", "service_code", "offering_code", "created_at"),
        Index("ix_knowledge_search_events_zero", "result_count", "created_at"),
    )


class TicketWorklog(Base):
    """Трудозатраты по тикету (минуты + заметка)."""
    __tablename__ = "ticket_worklogs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    spent_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class TicketNotification(Base):
    """In-app уведомление по тикету (Stage 6). Доставка через WS/API."""
    __tablename__ = "ticket_notifications"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ticket_notifications_actor_read_created", "actor_id", "is_read", "created_at"),
        Index("ix_ticket_notifications_ticket_created", "ticket_id", "created_at"),
    )


class TicketNotificationPref(Base):
    """Stage 8: Настройки уведомлений пользователя (mute_internal, muted_event_types, suppress_self)."""
    __tablename__ = "ticket_notification_prefs"
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mute_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    muted_event_types: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    suppress_self: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Problem(Base):
    """Stage 7: ITSM Problem. FSM: New -> Investigating -> Mitigated -> Resolved -> Closed."""
    __tablename__ = "problems"
    problem_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    problem_key: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, default=lambda: f"PRB-{uuid.uuid4().hex[:8].upper()}")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="new")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    impact: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, server_default="manual")
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    detected_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    investigation_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    known_error_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    workaround_available_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    permanent_fix_planned_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    permanent_fix_in_progress_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    target_resolution_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    investigation_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    known_error_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    workaround_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rca_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolution_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closure_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    breached_milestones: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    workaround: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    workaround_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permanent_fix_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kb_article_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_problems_status_priority_updated", "status", "priority", "updated_at"),
        Index("ix_problems_owner_status", "owner_id", "status"),
        Index("ix_problems_service_offering", "service_code", "offering_code"),
        Index("ix_problems_slo_due", "investigation_due_at", "known_error_due_at", "workaround_due_at", "rca_due_at", "resolution_due_at", "closure_due_at"),
    )


class ProblemTicketLink(Base):
    """Stage 7: Связь problem <-> ticket."""
    __tablename__ = "problem_ticket_links"
    link_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False
    )
    ticket_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False
    )
    link_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="suspected")
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    linked_by: Mapped[str] = mapped_column(Text, nullable=False)
    unlinked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_problem_ticket_links_ticket_id", "ticket_id"),
        Index("ix_problem_ticket_links_problem_ticket", "problem_id", "ticket_id"),
    )


class ProblemRCARecord(Base):
    """Versioned human-reviewed root cause analysis."""

    __tablename__ = "problem_rca_records"

    rca_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    methodology: Mapped[str] = mapped_column(String(40), nullable=False, server_default="narrative")
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    impact_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeline_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    contributing_factors_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    evidence_refs_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    corrective_actions_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    preventive_actions_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    reviewer_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("problem_id", "version_number", name="uq_problem_rca_problem_version"),
        Index("ix_problem_rca_problem_status", "problem_id", "status"),
    )


class ProblemKnownErrorLink(Base):
    """Problem to Knowledge known-error/workaround link."""

    __tablename__ = "problem_known_error_links"

    link_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(40), nullable=False)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False, server_default="support_internal")
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))


class ProblemAffectedObject(Base):
    """Affected service, offering, registry object or asset."""

    __tablename__ = "problem_affected_objects"

    affected_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_ref: Mapped[str] = mapped_column(Text, nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))


class ProblemDetectionRule(Base):
    """Configurable candidate scanner rule."""

    __tablename__ = "problem_detection_rules"

    rule_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="global")
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="168")
    min_ticket_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    min_reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    min_low_csat_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    min_sla_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    min_failed_kb_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    min_failed_qa_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    min_knowledge_gap_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    signal_types: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    breach_types: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    similarity_mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="service_offering")
    auto_create_candidate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    severity: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ProblemCandidate(Base):
    """Detected candidate before conversion to a problem."""

    __tablename__ = "problem_candidates"

    candidate_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problem_detection_rules.rule_id", ondelete="SET NULL"), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    fingerprint_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    evidence_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="open")
    signal_type: Mapped[str] = mapped_column(String(60), nullable=False, server_default="manual")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    ticket_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    low_csat_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    sla_breach_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_kb_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    confidence_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    suggested_problem_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True)
    converted_problem_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    dismissed_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    merged_into_candidate_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problem_candidates.candidate_id", ondelete="SET NULL"), nullable=True)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    reviewed_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    dismissal_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_problem_candidates_status_service", "status", "service_code", "offering_code"),
        Index("ix_problem_candidates_seen", "first_seen_at", "last_seen_at"),
    )


class ProblemScannerRun(Base):
    """Audit record for manual/API/scheduled problem candidate scanner runs."""

    __tablename__ = "problem_scanner_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="running")
    triggered_by: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    lookback_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="168")
    rules_run: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    candidates_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    candidates_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    candidates_skipped: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    errors_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("status IN ('running', 'completed', 'failed', 'canceled', 'skipped_overlap')", name="ck_problem_scanner_runs_status"),
        sa.CheckConstraint("triggered_by IN ('scheduler', 'manual', 'api')", name="ck_problem_scanner_runs_triggered_by"),
        Index("ix_problem_scanner_runs_started", "started_at"),
        Index("ix_problem_scanner_runs_status_started", "status", "started_at"),
    )


class ProblemSLOPolicy(Base):
    """Operational SLO policy for problem management milestones."""

    __tablename__ = "problem_slo_policies"

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="global")
    severity: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    investigation_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="24")
    known_error_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="72")
    workaround_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="96")
    rca_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="120")
    resolution_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="336")
    closure_due_hours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="504")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("scope_type IN ('global', 'severity', 'service', 'offering')", name="ck_problem_slo_policies_scope"),
        sa.CheckConstraint("severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')", name="ck_problem_slo_policies_severity"),
        sa.CheckConstraint("investigation_due_hours > 0 AND known_error_due_hours > 0 AND workaround_due_hours > 0 AND rca_due_hours > 0 AND resolution_due_hours > 0 AND closure_due_hours > 0", name="ck_problem_slo_policies_positive_hours"),
        Index("ix_problem_slo_policies_scope", "scope_type", "severity", "service_code", "offering_code"),
    )


class ProblemActivityEvent(Base):
    """Append-only problem activity timeline."""

    __tablename__ = "problem_activity_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=True, index=True)
    candidate_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problem_candidates.candidate_id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Change(Base):
    """First-class Change Enablement record."""

    __tablename__ = "changes"

    change_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_key: Mapped[str] = mapped_column(String(24), nullable=False, unique=True, default=lambda: f"CHG-{uuid.uuid4().hex[:8].upper()}")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="normal")
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="draft")
    category: Mapped[str] = mapped_column(String(40), nullable=False, server_default="other")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    impact_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    source_kind: Mapped[str] = mapped_column(String(40), nullable=False, server_default="manual")
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True, index=True)
    improvement_action_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("continuous_improvement_actions.action_id", ondelete="SET NULL"), nullable=True, index=True)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True, index=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    requested_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    assessed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    implementation_started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    implemented_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    planned_start_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    planned_end_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    actual_start_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    actual_end_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    blackout_override: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    emergency_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rollback_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    communication_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    closure_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint("change_type IN ('standard', 'normal', 'emergency')", name="ck_changes_type"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'assessing', 'awaiting_approval', 'approved', 'scheduled', 'implementation_in_progress', 'implemented', 'pir_required', 'closed', 'rejected', 'canceled', 'failed', 'rolled_back')", name="ck_changes_status"),
        sa.CheckConstraint("category IN ('infrastructure', 'application', 'network', 'security', 'access', 'service_catalog', 'knowledge', 'process', 'other')", name="ck_changes_category"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_changes_priority"),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name="ck_changes_risk_level"),
        sa.CheckConstraint("impact_level IN ('low', 'medium', 'high', 'critical')", name="ck_changes_impact_level"),
        sa.CheckConstraint("urgency IN ('low', 'medium', 'high', 'critical')", name="ck_changes_urgency"),
        sa.CheckConstraint("planned_end_at IS NULL OR planned_start_at IS NULL OR planned_end_at > planned_start_at", name="ck_changes_planned_window"),
        sa.CheckConstraint("actual_end_at IS NULL OR actual_start_at IS NULL OR actual_end_at >= actual_start_at", name="ck_changes_actual_window"),
        Index("ix_changes_status_type", "status", "change_type"),
        Index("ix_changes_service_offering", "service_code", "offering_code"),
        Index("ix_changes_planned_window", "planned_start_at", "planned_end_at"),
    )


class ChangeRiskAssessment(Base):
    __tablename__ = "change_risk_assessments"

    assessment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    impact_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    suggested_risk_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    risk_factors_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    mitigation_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    test_plan_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessed_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("change_id", "version_number", name="uq_change_risk_change_version"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'archived')", name="ck_change_risk_status"),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name="ck_change_risk_level"),
        sa.CheckConstraint("impact_level IN ('low', 'medium', 'high', 'critical')", name="ck_change_risk_impact"),
    )


class ChangePlan(Base):
    __tablename__ = "change_plans"

    plan_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    implementation_steps_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    rollback_steps_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    validation_steps_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    communication_steps_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    pre_checks_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    post_checks_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    downtime_expected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    downtime_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("change_id", "version_number", name="uq_change_plans_change_version"),
        sa.CheckConstraint("status IN ('draft', 'in_review', 'approved', 'archived')", name="ck_change_plans_status"),
    )


class ChangeApproval(Base):
    __tablename__ = "change_approvals"

    approval_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    approval_stage: Mapped[str] = mapped_column(String(40), nullable=False, server_default="cab")
    approver_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approver_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    approver_group: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    decision_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'skipped', 'expired')", name="ck_change_approvals_status"),
        sa.CheckConstraint("approval_stage IN ('risk_assessment', 'technical_review', 'business_approval', 'cab', 'emergency_approval', 'implementation_authorization')", name="ck_change_approvals_stage"),
        Index("ix_change_approvals_status", "change_id", "status"),
    )


class ChangeWindow(Base):
    __tablename__ = "change_windows"

    window_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    window_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="maintenance")
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    object_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    object_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    timezone_name: Mapped[Optional[str]] = mapped_column("timezone", Text, nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("window_type IN ('standard', 'maintenance', 'blackout', 'emergency_allowed')", name="ck_change_windows_type"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_change_windows_range"),
        Index("ix_change_windows_range", "starts_at", "ends_at"),
    )


class ChangeAffectedObject(Base):
    __tablename__ = "change_affected_objects"

    affected_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_ref: Mapped[str] = mapped_column(Text, nullable=False)
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    impact: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    planned_downtime: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("impact IN ('low', 'medium', 'high', 'critical')", name="ck_change_affected_impact"),
        Index("ix_change_affected_type", "change_id", "object_type"),
    )


class ChangeTask(Base):
    __tablename__ = "change_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="implementation")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    result_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_refs_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint("task_type IN ('pre_check', 'implementation', 'validation', 'rollback', 'communication', 'documentation', 'post_check')", name="ck_change_tasks_type"),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'done', 'skipped', 'failed', 'blocked')", name="ck_change_tasks_status"),
        Index("ix_change_tasks_status", "change_id", "status"),
    )


class ChangePIRRecord(Base):
    __tablename__ = "change_pir_records"

    pir_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    implementation_successful: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    rollback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    caused_incident: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    met_objectives: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    downtime_actual_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    issues_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    follow_up_actions_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    reviewed_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'archived')", name="ck_change_pir_status"),)


class ChangeActivityEvent(Base):
    __tablename__ = "change_activity_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    change_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_change_activity_change_created", "change_id", "created_at"),)


class ChangePolicy(Base):
    __tablename__ = "change_policies"

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="global")
    service_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    offering_code: Mapped[Optional[str]] = mapped_column(String(220), nullable=True)
    change_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    require_risk_assessment: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    require_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    require_rollback_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    require_pir: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    standard_preapproved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    approval_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="single")
    approver_roles_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    approver_actor_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    cab_group: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_lead_time_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_emergency_retro_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blackout_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint("scope_type IN ('global', 'service', 'offering', 'category', 'change_type', 'risk_level')", name="ck_change_policies_scope"),
        sa.CheckConstraint("approval_mode IN ('none', 'single', 'all', 'cab')", name="ck_change_policies_approval_mode"),
        Index("ix_change_policies_scope", "scope_type", "service_code", "offering_code", "change_type", "risk_level"),
    )


class TicketAdminAudit(Base):
    """Stage 9: Аудит изменений admin-config (очереди, routing rules, SLA policies)."""
    __tablename__ = "ticket_admin_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_admin_audit_entity_type_entity_id_created_at", "entity_type", "entity_id", "created_at"),
        Index("ix_ticket_admin_audit_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_ticket_admin_audit_created_at", "created_at"),
    )


class TicketChangeLink(Base):
    """Stage 7: Связь тикета с Change (внешняя система)."""
    __tablename__ = "ticket_change_links"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False
    )
    change_ref: Mapped[str] = mapped_column(Text, nullable=False)
    change_system: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ticket_change_links_ticket_id", "ticket_id"),
        sa.UniqueConstraint("ticket_id", "change_ref", "change_system", name="uq_ticket_change_links_ticket_ref_system"),
    )


class DeviceEvent(Base):
    """
    Device event model for Protocol V3.
    
    Stores events for devices without ticket binding.
    Ordered by device_seq per-device.
    """
    __tablename__ = "device_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        # КРИТИЧНО: dedupe по (device_id, device_seq)
        sa.UniqueConstraint(
            "device_id", "device_seq",
            name="uq_device_events_device_seq"
        ),
        Index("ix_device_events_device_id_device_seq", "device_id", "device_seq"),
        Index("ix_device_events_trace_id", "trace_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceEvent(id={self.id}, device_id={self.device_id!r}, "
            f"event_type={self.event_type!r}, device_seq={self.device_seq})>"
        )


class JobEvent(Base):
    """
    Job event model for persistent storage of chat/job events.
    
    Stores all events from agents with deduplication support.
    """
    
    __tablename__ = "job_events"
    
    # Primary key
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    
    # Job identification
    job_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    
    # Sequence number (nullable for lifecycle events)
    seq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamp (event time from payload or current time)
    ts: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    
    # Event type (chat_message, chat_started, tool_call_started, etc.)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Message ID (for deduplication of chat_message events)
    message_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Full event payload as JSONB
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Table constraints and indexes
    __table_args__ = (
        # Composite index for efficient seq-based queries
        Index("ix_job_events_job_id_seq", "job_id", "seq"),
        # Index for timestamp-based queries
        Index("ix_job_events_job_id_ts", "job_id", "ts"),
        # Unique constraint for message deduplication
        sa.Index(
            "uq_job_events_job_id_message_id_not_null",
            "job_id",
            "message_id",
            unique=True,
            postgresql_where=sa.text("message_id IS NOT NULL"),
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<JobEvent(id={self.id}, job_id={self.job_id!r}, "
            f"event_type={self.event_type!r}, seq={self.seq}, "
            f"message_id={self.message_id!r})>"
        )


class Device(Base):
    """
    Device registry model.
    
    Tracks all devices that have connected to the server with metadata,
    toolset information, and last activity timestamps.
    """
    __tablename__ = "devices"
    
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    
    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_handshake_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    last_toolset_refresh_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    last_tools_changed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delete_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Agent metadata
    protocol_version: Mapped[str] = mapped_column(Text, nullable=False)
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    os: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Capabilities and tools
    capabilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    tools_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Toolset tracking
    current_toolset_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_toolset_snapshot_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True
    )
    
    # Additional metadata (modules, etc.)
    # Note: named 'device_metadata' to avoid conflict with SQLAlchemy's reserved 'metadata' attribute
    device_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    
    __table_args__ = (
        Index("ix_devices_last_seen_at", "last_seen_at"),
        Index("ix_devices_agent_version", "agent_version"),
        Index("ix_devices_last_toolset_refresh_at", "last_toolset_refresh_at"),
        Index("ix_devices_deleted_at", "deleted_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Device(device_id={self.device_id!r}, agent_version={self.agent_version!r}, "
            f"toolset_hash={self.current_toolset_hash!r})>"
        )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class RegistryDepartment(Base):
    """Lightweight registry department used by people, assets and routing context."""
    __tablename__ = "registry_departments"

    department_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_department_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_departments.department_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_registry_departments_name", "name"),
        Index("ix_registry_departments_status", "status"),
    )


class RegistryLocation(Base):
    """Building/room registry. The project term is buildings, not corps."""
    __tablename__ = "registry_locations"

    location_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    building: Mapped[str] = mapped_column(Text, nullable=False)
    floor: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("building", "floor", "room", name="uq_registry_locations_building_floor_room"),
        Index("ix_registry_locations_building_room", "building", "room"),
        Index("ix_registry_locations_status", "status"),
    )


class RegistryAdminPolicy(Base):
    """Persisted admin-editable registry policy bundle."""
    __tablename__ = "registry_admin_policies"

    policy_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RegistryAdminEvent(Base):
    """Generic audit timeline for registry admin operations not tied to a single device registration event."""
    __tablename__ = "registry_admin_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    related_device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    related_person_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_registry_admin_events_object_event_at", "object_type", "object_id", "event_at"),
        Index("ix_registry_admin_events_device_event_at", "related_device_id", "event_at"),
        Index("ix_registry_admin_events_person_event_at", "related_person_id", "event_at"),
        Index("ix_registry_admin_events_type_event_at", "event_type", "event_at"),
    )


class RegistryQualityIssueOverride(Base):
    """Admin state for generated registry data-quality issues."""
    __tablename__ = "registry_quality_issue_overrides"

    issue_key: Mapped[str] = mapped_column(String(300), primary_key=True)
    issue_kind: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[str] = mapped_column(String(120), nullable=False)
    related_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_registry_quality_overrides_status_until", "status", "snoozed_until"),
        Index("ix_registry_quality_overrides_object", "object_type", "object_id"),
    )


class RegistryVendor(Base):
    """External vendor/contractor registry."""
    __tablename__ = "registry_vendors"

    vendor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    contact_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RegistryService(Base):
    """Business/IT system registry entry."""
    __tablename__ = "registry_services"

    service_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_queue_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_vendors.vendor_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_registry_services_status", "status"),
        Index("ix_registry_services_owner_queue", "owner_queue_id"),
    )


class RegistryPerson(Base):
    """Person registry entry populated manually, from AD, or from an agent profile."""
    __tablename__ = "registry_people"

    person_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    department_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_departments.department_id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_locations.location_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    profile_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("source", "profile_key", name="uq_registry_people_source_profile_key"),
        Index("ix_registry_people_department", "department_id"),
        Index("ix_registry_people_location", "location_id"),
        Index("ix_registry_people_status", "status"),
    )


class RegistryAsset(Base):
    """Asset registry entry for PCs, printers and related objects."""
    __tablename__ = "registry_assets"

    asset_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    hostname: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, unique=True)
    inventory_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_locations.location_id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_person_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"),
        nullable=True,
    )
    department_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_departments.department_id", ondelete="SET NULL"),
        nullable=True,
    )
    service_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_services.service_id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_vendors.vendor_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False, server_default="manual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    discovery_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_registry_assets_type_status", "asset_type", "status"),
        Index("ix_registry_assets_hostname", "hostname"),
        Index("ix_registry_assets_location", "location_id"),
        Index("ix_registry_assets_assigned_person", "assigned_person_id"),
        Index("ix_registry_assets_department", "department_id"),
    )


class RegistryPersonIdentity(Base):
    """Normalized identity alias for a registry person."""
    __tablename__ = "registry_person_identities"

    identity_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    identifier: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="manual")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("provider", "normalized_identifier", name="uq_registry_person_identities_provider_identifier"),
        Index("ix_registry_person_identities_person", "person_id"),
        Index("ix_registry_person_identities_provider_identifier", "provider", "normalized_identifier"),
    )


class DeviceRegistrationClaim(Base):
    """Self-reported or admin-created claim that a person is related to a device."""
    __tablename__ = "device_registration_claims"

    claim_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"),
        nullable=True,
    )
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="primary_user")
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    device_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="agent_profile")
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    user_confirmed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    conflict_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "claim_type IN ('self_reported', 'agent_detected', 'admin_created', 'presence_inferred', 'import', 'sso')",
            name="ck_device_registration_claims_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'self_reported', 'pending_user_confirmation', 'user_confirmed', "
            "'pending_admin_review', 'approved', 'rejected', 'superseded', 'expired', 'conflict')",
            name="ck_device_registration_claims_status",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('primary_user', 'responsible', 'owner', 'shared_user', 'temporary_user')",
            name="ck_device_registration_claims_relationship",
        ),
        Index("ix_device_registration_claims_device_status", "device_id", "status"),
        Index("ix_device_registration_claims_person_status", "person_id", "status"),
        Index("ix_device_registration_claims_status_submitted", "status", "submitted_at"),
        Index("ix_device_registration_claims_source_ref", "source", "source_ref"),
        Index("ix_device_registration_claims_device_submitted", "device_id", "submitted_at"),
    )


class DeviceUserBinding(Base):
    """Authoritative device-to-person binding derived from an approved registration claim."""
    __tablename__ = "device_user_bindings"

    binding_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_assets.asset_id", ondelete="SET NULL"),
        nullable=True,
    )
    person_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="primary_user")
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="active")
    source_claim_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_registration_claims.claim_id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(40), nullable=False, server_default="registration_claim")
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by_user_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by_admin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "relationship_type IN ('primary_user', 'responsible', 'owner', 'shared_user', 'temporary_user')",
            name="ck_device_user_bindings_relationship",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'stale', 'revoked', 'transferred')",
            name="ck_device_user_bindings_status",
        ),
        Index("ix_device_user_bindings_device_status", "device_id", "status"),
        Index("ix_device_user_bindings_person_status", "person_id", "status"),
        Index("ix_device_user_bindings_asset_status", "asset_id", "status"),
        Index("ix_device_user_bindings_source_claim", "source_claim_id"),
        Index("ix_device_user_bindings_relationship_status", "relationship_type", "status"),
        Index(
            "uq_device_user_bindings_active_primary_device",
            "device_id",
            unique=True,
            postgresql_where=sa.text("status = 'active' AND relationship_type = 'primary_user'"),
        ),
    )


class DeviceRegistrationEvent(Base):
    """Audit event for registration claims and active bindings."""
    __tablename__ = "device_registration_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_registration_claims.claim_id", ondelete="SET NULL"),
        nullable=True,
    )
    binding_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"),
        nullable=True,
    )
    device_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("devices.device_id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    event_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_device_registration_events_device_event_at", "device_id", "event_at"),
        Index("ix_device_registration_events_person_event_at", "person_id", "event_at"),
        Index("ix_device_registration_events_claim", "claim_id"),
        Index("ix_device_registration_events_binding", "binding_id"),
        Index("ix_device_registration_events_type_event_at", "event_type", "event_at"),
    )


class DeviceAccountSession(Base):
    """Server-issued requester account session for an authenticated device agent."""
    __tablename__ = "device_account_sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    account_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_method: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    person_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True)
    binding_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"), nullable=True)
    claim_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_registration_claims.claim_id", ondelete="SET NULL"), nullable=True)
    base_binding_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"), nullable=True)
    base_person_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True)
    declared_account: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    warning_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    verified_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint(
            "account_mode IN ('confirmed_binding', 'registration_pending', 'verified_other_account', 'unverified_other_account')",
            name="ck_device_account_sessions_mode",
        ),
        sa.CheckConstraint(
            "verification_status IN ('verified', 'pending_verification', 'rejected', 'expired', 'revoked')",
            name="ck_device_account_sessions_verification_status",
        ),
        sa.CheckConstraint(
            "verification_method IS NULL OR verification_method IN ('device_binding', 'registration_claim', 'admin_approval', 'email_otp', 'sso', 'break_glass')",
            name="ck_device_account_sessions_verification_method",
        ),
        Index("ix_device_account_sessions_device_status", "device_id", "verification_status"),
        Index("ix_device_account_sessions_person_status", "person_id", "verification_status"),
        Index("ix_device_account_sessions_binding", "binding_id"),
        Index("ix_device_account_sessions_base_binding", "base_binding_id"),
        Index("ix_device_account_sessions_token_hash", "session_token_hash"),
        Index("ix_device_account_sessions_mode_status", "account_mode", "verification_status"),
    )


class DeviceAccountLoginRequest(Base):
    """Admin-reviewed request to use another requester account on a registered device."""
    __tablename__ = "device_account_login_requests"

    request_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    requested_account: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    matched_person_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True)
    base_binding_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"), nullable=True)
    base_person_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_method: Mapped[str] = mapped_column(String(40), nullable=False, server_default="admin_approval")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resulting_session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_account_sessions.session_id", ondelete="SET NULL"), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending_verification', 'approved', 'rejected', 'expired', 'canceled')",
            name="ck_device_account_login_requests_status",
        ),
        Index("ix_device_account_login_requests_device_status", "device_id", "status"),
        Index("ix_device_account_login_requests_matched_person_status", "matched_person_id", "status"),
        Index("ix_device_account_login_requests_base_binding_status", "base_binding_id", "status"),
        Index("ix_device_account_login_requests_status_requested", "status", "requested_at"),
    )


class DeviceBrowserPairing(Base):
    """Persisted browser-to-agent pairing state for account session handoff."""
    __tablename__ = "device_browser_pairings"

    pairing_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    pairing_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    pairing_code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    resulting_account_session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_account_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed_person_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"),
        nullable=True,
    )
    binding_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"),
        nullable=True,
    )
    claim_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_registration_claims.claim_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    confirmed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint(
            "purpose IN ('login', 'registration')",
            name="ck_device_browser_pairings_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'consumed', 'expired', 'canceled', 'superseded', 'failed')",
            name="ck_device_browser_pairings_status",
        ),
        Index("ix_device_browser_pairings_device_status", "device_id", "status"),
        Index("ix_device_browser_pairings_device_purpose_status", "device_id", "purpose", "status"),
        Index("ix_device_browser_pairings_code_hash", "pairing_code_hash"),
        Index("ix_device_browser_pairings_token_hash", "pairing_token_hash"),
        Index("ix_device_browser_pairings_session", "resulting_account_session_id"),
    )


class DeviceAccountEvent(Base):
    """Audit event for requester account session lifecycle and ticket use."""
    __tablename__ = "device_account_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_account_sessions.session_id", ondelete="SET NULL"), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_account_login_requests.request_id", ondelete="SET NULL"), nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    event_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_device_account_events_device_event_at", "device_id", "event_at"),
        Index("ix_device_account_events_session_event_at", "session_id", "event_at"),
        Index("ix_device_account_events_request_event_at", "request_id", "event_at"),
        Index("ix_device_account_events_ticket_event_at", "ticket_id", "event_at"),
        Index("ix_device_account_events_type_event_at", "event_type", "event_at"),
    )


class DeviceConfig(Base):
    """
    Device configuration model.
    
    Stores desired and applied configurations for devices using revision-based tracking.
    """
    __tablename__ = "device_config"
    
    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    
    # Desired configuration
    desired_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    desired_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    # Applied configuration
    applied_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    last_apply_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_apply_error: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    
    # Metadata
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceConfig(device_id={self.device_id!r}, "
            f"desired_revision={self.desired_revision}, "
            f"applied_revision={self.applied_revision})>"
        )


class DeviceToolsetSnapshot(Base):
    """
    Device toolset snapshot model.
    
    Stores snapshots of tool lists from devices for tracking changes over time.
    UNIQUE constraint on (device_id, toolset_hash) prevents duplicates.
    """
    __tablename__ = "device_toolset_snapshots"
    
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    
    # Snapshot metadata
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    agent_version: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Toolset data
    toolset_hash: Mapped[str] = mapped_column(Text, nullable=False)
    toolset_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    __table_args__ = (
        # КРИТИЧНО: UNIQUE constraint для предотвращения дубликатов
        sa.UniqueConstraint(
            "device_id", "toolset_hash",
            name="uq_device_toolset_snapshots_device_hash"
        ),
        Index("ix_toolset_snapshots_device_captured", "device_id", "captured_at"),
        Index("ix_toolset_snapshots_device_hash", "device_id", "toolset_hash"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceToolsetSnapshot(snapshot_id={self.snapshot_id}, "
            f"device_id={self.device_id!r}, toolset_hash={self.toolset_hash!r}, "
            f"tool_count={self.tool_count})>"
        )


class DeviceInventorySnapshot(Base):
    """Raw endpoint inventory snapshots collected by inventory.collect."""
    __tablename__ = "device_inventory_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_tool: Mapped[str] = mapped_column(Text, nullable=False, default="inventory.collect")
    source_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    normalized: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    snapshot_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_snapshots_device_collected", "device_id", "collected_at"),
        Index("ix_device_inventory_snapshots_source_tool", "source_tool"),
        Index("ix_device_inventory_snapshots_status", "status"),
        Index("ix_device_inventory_snapshots_hash", "snapshot_hash"),
    )


class DeviceInventoryBinding(Base):
    """Lightweight workplace binding metadata for an endpoint inventory card."""
    __tablename__ = "device_inventory_bindings"

    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    person_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    asset_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    source_binding_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    registration_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    building: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    floor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    room: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    responsible_user: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    responsible_user_login: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    inventory_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_bindings_person", "person_id"),
        Index("ix_device_inventory_bindings_asset", "asset_id"),
        Index("ix_device_inventory_bindings_source_binding", "source_binding_id"),
        Index("ix_device_inventory_bindings_registration_status", "registration_status"),
    )


class DeviceInventoryBindingHistory(Base):
    """Audit trail for lightweight inventory binding changes."""
    __tablename__ = "device_inventory_binding_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    changed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    old_binding: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_binding: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    changed_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_binding_history_device_changed", "device_id", "changed_at"),
    )


class DeviceInventoryRefreshPolicy(Base):
    """Periodic inventory.collect refresh policy."""
    __tablename__ = "device_inventory_refresh_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global")
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    jitter_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    last_requested_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    next_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_refresh_policies_scope", "scope"),
        Index("ix_device_inventory_refresh_policies_device", "device_id"),
        Index("ix_device_inventory_refresh_policies_enabled_due", "enabled", "next_due_at"),
    )


class DeviceInventoryRefreshRun(Base):
    """Visibility record for manual/scheduled inventory refresh attempts."""
    __tablename__ = "device_inventory_refresh_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    policy_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    bulk_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    requested_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="requested")
    job_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_refresh_runs_device_requested", "device_id", "requested_at"),
        Index("ix_device_inventory_refresh_runs_policy_requested", "policy_id", "requested_at"),
        Index("ix_device_inventory_refresh_runs_bulk_operation", "bulk_operation_id"),
        Index("ix_device_inventory_refresh_runs_status", "status"),
    )


class DeviceInventoryBulkOperation(Base):
    """Tracked fleet operation for batched inventory refresh."""
    __tablename__ = "device_inventory_bulk_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False, default="inventory_refresh")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    requested_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    wave: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispatched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_bulk_operations_requested", "requested_at"),
        Index("ix_device_inventory_bulk_operations_status", "status"),
    )


class DeviceInventoryBulkOperationItem(Base):
    """Per-device item in a batched inventory refresh operation."""
    __tablename__ = "device_inventory_bulk_operation_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    wave_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    job_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_device_inventory_bulk_items_operation", "operation_id"),
        Index("ix_device_inventory_bulk_items_device", "device_id"),
        UniqueConstraint("operation_id", "device_id", name="uq_device_inventory_bulk_item_operation_device"),
    )


class DeviceBindingSuggestion(Base):
    """Pending or reviewed workplace binding suggestion from an agent profile."""
    __tablename__ = "device_binding_suggestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="agent_profile")
    source_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_binding: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    profile_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    confidence: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    reviewed_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_device_binding_suggestions_device_status", "device_id", "status"),
        Index("ix_device_binding_suggestions_source_ref", "source", "source_ref"),
    )


class DevicePresenceSnapshot(Base):
    """Privacy-safe presence snapshot for a workplace device."""
    __tablename__ = "device_presence_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    session_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    current_user: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idle_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    locked: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    __table_args__ = (
        Index("ix_device_presence_snapshots_device_collected", "device_id", "collected_at"),
        Index("ix_device_presence_snapshots_state", "session_state"),
    )


class DevicePresenceDailySummary(Base):
    """Daily aggregate derived from presence snapshots."""
    __tablename__ = "device_presence_daily_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    summary_date: Mapped[str] = mapped_column(String(10), nullable=False)
    active_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    offline_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unknown_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("device_id", "summary_date", name="uq_device_presence_daily_device_date"),
        Index("ix_device_presence_daily_device_date", "device_id", "summary_date"),
    )


class ServerRuntimeSnapshot(Base):
    """Persisted live-server runtime evidence for read-only diagnostics."""
    __tablename__ = "server_runtime_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    process_kind: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    git_revision: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    collected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_server_runtime_snapshots_kind_collected", "process_kind", "collected_at"),
        Index("ix_server_runtime_snapshots_kind_expires", "process_kind", "expires_at"),
    )


class DeviceOutbox(Base):
    """
    Device outbox model for Protocol V3.
    
    Server-side outbox for reliable command delivery to devices.
    Commands are persisted before sending and lifecycle-tracked.
    """
    __tablename__ = "device_outbox"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    command_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Lifecycle tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, sent, delivered, failed
    
    # Metadata
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    failed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    
    # Error tracking
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_device_outbox_device_id_status", "device_id", "status"),
        Index("ix_device_outbox_command_id_status", "command_id", "status"),
        Index("ix_device_outbox_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceOutbox(id={self.id}, device_id={self.device_id!r}, "
            f"command_id={self.command_id!r}, command={self.command!r}, "
            f"status={self.status!r})>"
        )


class RemoteAccessSession(Base):
    """Remote Assist session lifecycle bound to a ticket, device and operator."""

    __tablename__ = "remote_access_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    operator_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    requester_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consent_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    consent_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    denied_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    max_duration_sec: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("900"))
    signaling_token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator_token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agent_token_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ice_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recording_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
    )

    __table_args__ = (
        Index("ix_remote_access_sessions_expires_at", "expires_at"),
        Index("ix_remote_access_sessions_ticket_created", "ticket_id", "created_at"),
    )


class RemoteAccessEvent(Base):
    """Audit trail for Remote Assist sessions."""

    __tablename__ = "remote_access_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.text("now()"),
        index=True,
    )


class DispatchReadyDevice(Base):
    """
    Cross-instance coordination queue for device dispatch readiness.

    One row per device_id. Workers claim leases before drain to avoid
    parallel sends from multiple server instances.
    """

    __tablename__ = "dispatch_ready_devices"

    device_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    shard_key: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    next_attempt_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    lease_owner: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    lease_until: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_dispatch_ready_shard_next_attempt", "shard_key", "next_attempt_at"),
        Index("ix_dispatch_ready_lease_until", "lease_until"),
    )

    def __repr__(self) -> str:
        return (
            f"<DispatchReadyDevice(device_id={self.device_id!r}, shard_key={self.shard_key}, "
            f"lease_owner={self.lease_owner!r}, lease_until={self.lease_until})>"
        )


class Operation(Base):
    """
    Operation model for tracking end-to-end command/tool execution lifecycle.
    
    Operations materialize operation state from events for efficient querying.
    All operations updates are transactional with corresponding events.
    """
    __tablename__ = "operations"
    
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Для kind=command (list_tools и др.): имя команды для метрик (Этап 5)
    command_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    # Status: queued, sent, accepted, running, waiting_consent, succeeded, failed, denied, timed_out, cancel_requested, canceled
    # denied - терминальный статус для denied consent, отдельно от failed
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    phase: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    
    # SLA tracking
    deadline_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        index=True
    )
    # Переопределение таймаута для шага playbook (Этап 5)
    timeout_override_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Связь с playbook_run для наблюдаемости (Этап 5)
    playbook_run_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("playbook_run.id", ondelete="SET NULL"), nullable=True
    )
    
    # Lifecycle timestamps
    queued_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        # КРИТИЧНО: Не используем default=lambda, так как он может вычисляться при импорте модуля
        # В OperationsRepo.create_operation явно устанавливается queued_at=datetime.now(timezone.utc)
        # Это гарантирует правильное UTC время при создании операции
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    
    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_of_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    
    # Result tracking
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_event_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Cancel tracking
    status_before_cancel: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_target_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    active_cancel_operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_operations_status_queued_at", "status", "queued_at"),
        Index("ix_operations_device_id_status", "device_id", "status"),
        Index("ix_operations_phase", "phase"),
        Index("ix_operations_deadline_at", "deadline_at"),
        Index("ix_operations_cancel_target", "cancel_target_operation_id"),
        Index("ix_operations_active_cancel", "active_cancel_operation_id"),
        Index("ix_operations_retry_of", "retry_of_operation_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Operation(operation_id={self.operation_id!r}, device_id={self.device_id!r}, "
            f"kind={self.kind!r}, status={self.status!r})>"
        )


class OperationDependency(Base):
    """Runtime dependency linkage for operations that wait on a module, runner, or integration."""

    __tablename__ = "operation_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("operations.operation_id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_operation_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("operations.operation_id", ondelete="SET NULL"),
        nullable=True,
    )
    dependency_type: Mapped[str] = mapped_column(String(40), nullable=False)
    dependency_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version_constraint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    timeout_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resume_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_operation_dependencies_operation_id", "operation_id"),
        Index("ix_operation_dependencies_dependency_operation_id", "dependency_operation_id"),
        Index("ix_operation_dependencies_type", "dependency_type"),
        Index("ix_operation_dependencies_key", "dependency_key"),
        Index("ix_operation_dependencies_status", "status"),
        Index("ix_operation_dependencies_timeout_at", "timeout_at"),
    )


class RunnerRolloutPlan(Base):
    """Fleet rollout plan for the protected agent_recipe_runner managed module."""

    __tablename__ = "runner_rollout_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False, default="agent_recipe_runner")
    target_version: Mapped[str] = mapped_column(String(50), nullable=False)
    rollback_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="canary_waves")
    canary_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    wave_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_runner_rollout_plans_module_status", "module_name", "status"),
        Index("ix_runner_rollout_plans_target_status", "target_version", "status"),
    )


class RunnerRolloutWave(Base):
    """A canary or rollout wave inside a runner rollout plan."""

    __tablename__ = "runner_rollout_waves"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("runner_rollout_plans.id", ondelete="CASCADE"), nullable=False)
    wave_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("plan_id", "wave_index", name="uq_runner_rollout_waves_plan_index"),
        Index("ix_runner_rollout_waves_plan_status", "plan_id", "status"),
    )


class RunnerRolloutTarget(Base):
    """Per-device target state for a runner rollout plan."""

    __tablename__ = "runner_rollout_targets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("runner_rollout_plans.id", ondelete="CASCADE"), nullable=False)
    wave_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("runner_rollout_waves.id", ondelete="SET NULL"), nullable=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False, default="agent_recipe_runner")
    target_version: Mapped[str] = mapped_column(String(50), nullable=False)
    rollback_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    current_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    desired_set_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("plan_id", "device_id", name="uq_runner_rollout_targets_plan_device"),
        Index("ix_runner_rollout_targets_plan_status", "plan_id", "status"),
        Index("ix_runner_rollout_targets_wave_status", "wave_id", "status"),
        Index("ix_runner_rollout_targets_device", "device_id"),
    )


class RunnerRolloutEvent(Base):
    """Audit timeline for runner rollout plan/wave/target actions."""

    __tablename__ = "runner_rollout_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    plan_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("runner_rollout_plans.id", ondelete="CASCADE"), nullable=False)
    wave_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("runner_rollout_waves.id", ondelete="SET NULL"), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("runner_rollout_targets.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_runner_rollout_events_plan", "plan_id", "created_at"),
        Index("ix_runner_rollout_events_type", "event_type"),
    )


class Module(Base):
    """
    Server-side registry of module artifacts.
    
    Stores metadata about uploaded module ZIP files.
    """
    __tablename__ = "modules"
    
    module_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # Relative to MODULES_STORAGE_DIR
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    uploaded_by: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")  # actor_role
    manifest_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    validation_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    manifest_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # manifest summary (renamed from metadata to avoid conflict with SQLAlchemy Base.metadata)
    
    __table_args__ = (
        Index("ix_modules_sha256", "sha256"),
        Index("ix_modules_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Module(module_name={self.module_name!r}, version={self.version!r}, "
            f"sha256={self.sha256[:16]}..., size={self.size})>"
        )


class TicketFormPack(Base):
    """Versioned registry of structured ticket request forms."""
    __tablename__ = "ticket_form_packs"

    pack_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ticket_form_packs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<TicketFormPack(pack_key={self.pack_key!r}, version={self.version!r})>"
        )


class FormBuilderDraft(Base):
    """Draft request-form catalog that is not visible to requesters until published."""

    __tablename__ = "form_builder_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pack_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft", index=True)
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    validation_report_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    published_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_form_builder_drafts_pack_status", "pack_key", "status"),
        Index("ix_form_builder_drafts_updated_at", "updated_at"),
    )


class TicketType(Base):
    """Versioned top-level service desk process type defaults."""

    __tablename__ = "ticket_types"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_workflow_profile_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_priority_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_routing_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_sla_policy_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    default_sla_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_ola_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_approval_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_diagnostic_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_closure_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_visibility_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_notification_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_reporting_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sla_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    ola_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    approval_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    approval_required_by_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    diagnostics_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    remediation_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    portal_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    valid_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ticket_types_active", "code", "is_active"),
        Index("ix_ticket_types_published_at", "published_at"),
        Index("ix_ticket_types_portal_visible", "portal_visible", "is_active"),
    )


class FormSchema(Base):
    """Versioned first-class intake form schema linked by request templates."""

    __tablename__ = "form_schemas"

    schema_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    form_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    request_template_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    ticket_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    valid_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_form_schemas_active", "schema_id", "is_active"),
        Index("ix_form_schemas_template", "request_template_code", "is_active"),
        Index("ix_form_schemas_published_at", "published_at"),
    )


class FormField(Base):
    """Field definition materialized from a versioned form schema."""

    __tablename__ = "form_fields"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schema_id: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    options_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    validation_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    process_mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    visibility_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        sa.UniqueConstraint("schema_id", "schema_version", "key", name="uq_form_fields_schema_key"),
        Index("ix_form_fields_schema", "schema_id", "schema_version"),
    )


class FormCondition(Base):
    """Conditional visibility/requiredness rule for a versioned form schema."""

    __tablename__ = "form_conditions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schema_id: Mapped[str] = mapped_column(String(120), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    show_fields_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    require_fields_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_form_conditions_schema", "schema_id", "schema_version"),
    )


class RequestTemplate(Base):
    """Versioned request template assembled from form, workflow and policy references."""

    __tablename__ = "request_templates"

    template_code: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    public_title: Mapped[str] = mapped_column(Text, nullable=False)
    internal_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ticket_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    service_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    subcategory_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    form_schema_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    workflow_profile_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    priority_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    routing_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sla_policy_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    sla_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ola_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approval_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    diagnostic_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    closure_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    visibility_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notification_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reporting_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    overrides_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    valid_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_request_templates_active", "template_code", "is_active"),
        Index("ix_request_templates_type_category", "ticket_type", "category_id"),
        Index("ix_request_templates_published_at", "published_at"),
    )


class HelpdeskService(Base):
    """Requester-facing Service Catalog service."""

    __tablename__ = "helpdesk_services"

    service_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    public_title: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft")
    visibility: Mapped[str] = mapped_column(String(24), nullable=False, server_default="internal")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    business_criticality: Mapped[str] = mapped_column(String(20), nullable=False, server_default="medium")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_person_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_queue_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"),
        nullable=True,
    )
    support_group_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    registry_service_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("registry_services.service_id", ondelete="SET NULL"),
        nullable=True,
    )
    default_ticket_type_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    default_queue_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_priority_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_routing_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_sla_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_ola_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_approval_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_diagnostic_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_closure_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_visibility_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_notification_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_reporting_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_services_code_safe"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'published', 'retired')", name="ck_helpdesk_services_lifecycle"),
        sa.CheckConstraint("visibility IN ('public', 'internal', 'restricted')", name="ck_helpdesk_services_visibility"),
        sa.CheckConstraint("business_criticality IN ('low', 'medium', 'high', 'critical')", name="ck_helpdesk_services_criticality"),
        Index("ix_helpdesk_services_status_visibility", "lifecycle_status", "visibility"),
        Index("ix_helpdesk_services_registry_service", "registry_service_id"),
        Index("ix_helpdesk_services_sort", "sort_order", "code"),
    )


class HelpdeskServiceOffering(Base):
    """Requester-facing offering inside a Service Catalog service."""

    __tablename__ = "helpdesk_service_offerings"

    offering_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    service_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("helpdesk_services.service_id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    full_code: Mapped[str] = mapped_column(String(220), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    public_title: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lifecycle_status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft")
    visibility: Mapped[str] = mapped_column(String(24), nullable=False, server_default="internal")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ticket_type_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    request_template_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    request_template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    form_schema_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_queue_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"),
        nullable=True,
    )
    priority_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    routing_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sla_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ola_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approval_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    diagnostic_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    closure_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    visibility_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    notification_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reporting_policy_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reporting_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    kb_article_refs: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    availability_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    retired_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("service_id", "code", name="uq_helpdesk_service_offerings_service_code"),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_offerings_code_safe"),
        sa.CheckConstraint("full_code ~ '^[a-z0-9][a-z0-9_-]*[.][a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_offerings_full_code_safe"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'published', 'retired')", name="ck_helpdesk_offerings_lifecycle"),
        sa.CheckConstraint("visibility IN ('public', 'internal', 'restricted')", name="ck_helpdesk_offerings_visibility"),
        Index("ix_helpdesk_offerings_service_status_visibility", "service_id", "lifecycle_status", "visibility", "sort_order"),
        Index("ix_helpdesk_offerings_template", "request_template_key"),
        Index("ix_helpdesk_offerings_full_code", "full_code"),
    )


class HelpdeskServiceCatalogAudit(Base):
    """Audit trail for Service Catalog publication and governance actions."""

    __tablename__ = "helpdesk_service_catalog_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_code: Mapped[str] = mapped_column(String(220), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    issues_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_helpdesk_service_catalog_audit_object", "object_type", "object_code", "created_at"),
    )


class RequestStudioPublishToken(Base):
    """One-time confirmation tokens for guarded Request Studio publish."""

    __tablename__ = "request_studio_publish_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    draft_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(40), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    used_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preview_summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_request_studio_publish_tokens_hash", "token_hash"),
        Index("ix_request_studio_publish_tokens_nonce", "nonce_hash"),
        Index("ix_request_studio_publish_tokens_actor", "actor_id", "actor_role", "expires_at"),
        Index("ix_request_studio_publish_tokens_draft", "draft_hash", "scope"),
        Index("ix_request_studio_publish_tokens_unused", "expires_at", "used_at"),
    )


class _VersionedPolicyMixin:
    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_level: Mapped[str] = mapped_column(String(40), nullable=False, server_default="system")
    scope_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    valid_from: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PriorityPolicy(_VersionedPolicyMixin, Base):
    """Versioned priority calculation policy."""

    __tablename__ = "priority_policies"
    __table_args__ = (
        Index("ix_priority_policies_active", "code", "is_active"),
        Index("ix_priority_policies_scope", "scope_level", "scope_ref"),
        Index("ix_priority_policies_published_at", "published_at"),
    )


class SlaPolicy(_VersionedPolicyMixin, Base):
    """Versioned SLA policy profile for request templates."""

    __tablename__ = "sla_policies"
    __table_args__ = (
        Index("ix_sla_policies_active", "code", "is_active"),
        Index("ix_sla_policies_scope", "scope_level", "scope_ref"),
        Index("ix_sla_policies_published_at", "published_at"),
    )


class OlaPolicy(_VersionedPolicyMixin, Base):
    """Versioned OLA policy profile for internal queue deadlines."""

    __tablename__ = "ola_policies"
    __table_args__ = (
        Index("ix_ola_policies_active", "code", "is_active"),
        Index("ix_ola_policies_scope", "scope_level", "scope_ref"),
        Index("ix_ola_policies_published_at", "published_at"),
    )


class RoutingPolicy(_VersionedPolicyMixin, Base):
    """Versioned routing policy."""

    __tablename__ = "routing_policies"
    __table_args__ = (
        Index("ix_routing_policies_active", "code", "is_active"),
        Index("ix_routing_policies_scope", "scope_level", "scope_ref"),
        Index("ix_routing_policies_published_at", "published_at"),
    )


class ApprovalPolicy(_VersionedPolicyMixin, Base):
    """Versioned approval policy."""

    __tablename__ = "approval_policies"
    __table_args__ = (
        Index("ix_approval_policies_active", "code", "is_active"),
        Index("ix_approval_policies_scope", "scope_level", "scope_ref"),
        Index("ix_approval_policies_published_at", "published_at"),
    )


class ClosurePolicy(_VersionedPolicyMixin, Base):
    """Versioned closure policy."""

    __tablename__ = "closure_policies"
    __table_args__ = (
        Index("ix_closure_policies_active", "code", "is_active"),
        Index("ix_closure_policies_scope", "scope_level", "scope_ref"),
        Index("ix_closure_policies_published_at", "published_at"),
    )


class DiagnosticPolicy(_VersionedPolicyMixin, Base):
    """Versioned diagnostic policy."""

    __tablename__ = "diagnostic_policies"
    __table_args__ = (
        Index("ix_diagnostic_policies_active", "code", "is_active"),
        Index("ix_diagnostic_policies_scope", "scope_level", "scope_ref"),
        Index("ix_diagnostic_policies_published_at", "published_at"),
    )


class NotificationPolicy(_VersionedPolicyMixin, Base):
    """Versioned notification recipient/channel policy."""

    __tablename__ = "notification_policies"
    __table_args__ = (
        Index("ix_notification_policies_active", "code", "is_active"),
        Index("ix_notification_policies_scope", "scope_level", "scope_ref"),
        Index("ix_notification_policies_published_at", "published_at"),
    )


class VisibilityPolicy(_VersionedPolicyMixin, Base):
    """Versioned requester/support visibility policy."""

    __tablename__ = "visibility_policies"
    __table_args__ = (
        Index("ix_visibility_policies_active", "code", "is_active"),
        Index("ix_visibility_policies_scope", "scope_level", "scope_ref"),
        Index("ix_visibility_policies_published_at", "published_at"),
    )


class ReportingPolicy(_VersionedPolicyMixin, Base):
    """Versioned reporting and passport generation policy."""

    __tablename__ = "reporting_policies"
    __table_args__ = (
        Index("ix_reporting_policies_active", "code", "is_active"),
        Index("ix_reporting_policies_scope", "scope_level", "scope_ref"),
        Index("ix_reporting_policies_published_at", "published_at"),
    )


class SmartView(Base):
    """Versioned saved operational queue view."""

    __tablename__ = "smart_views"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope_level: Mapped[str] = mapped_column(String(40), nullable=False, server_default="system")
    scope_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    filter_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    sort_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    columns_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_smart_views_active", "code", "is_active"),
        Index("ix_smart_views_scope", "scope_level", "scope_ref"),
        Index("ix_smart_views_published_at", "published_at"),
    )


class SupportQueueSavedView(Base):
    """Operator/shared queue triage view for the support workspace."""

    __tablename__ = "support_queue_saved_views"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="personal")
    owner_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    queue_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"),
        nullable=True,
    )
    filters_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    columns_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    sort_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=sa.text("'[]'::jsonb"))
    is_favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_support_queue_saved_views_owner", "owner_actor_id", "updated_at"),
        Index("ix_support_queue_saved_views_scope", "scope", "queue_id"),
        Index("ix_support_queue_saved_views_default", "scope", "owner_actor_id", "queue_id", "is_default"),
    )


class HelpdeskPolicyAudit(Base):
    """Audit trail for request-template and policy publishing."""

    __tablename__ = "helpdesk_policy_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_code: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_helpdesk_policy_audit_entity", "entity_type", "entity_code", "created_at"),
        Index("ix_helpdesk_policy_audit_actor", "actor_id", "created_at"),
    )


class AgentBuild(Base):
    """
    Server-side registry of agent build artifacts (self-update packages).

    Stores metadata about uploaded agent ZIP packages.
    Composite PK: (target, channel, version).
    """
    __tablename__ = "agent_builds"

    target: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g. windows_amd64
    channel: Mapped[str] = mapped_column(String(20), primary_key=True, default="stable")  # stable|beta|dev
    version: Mapped[str] = mapped_column(String(50), primary_key=True)

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)  # Relative to AGENT_BUILDS_STORAGE_DIR
    artifact_filename: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # e.g. pc_agent-windows_amd64-3.1.0.zip
    archive_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # zip | tar.gz
    mime_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)  # application/zip | application/gzip

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    uploaded_by: Mapped[str] = mapped_column(String(20), nullable=False, default="admin")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agent_builds_sha256", "sha256"),
        Index("ix_agent_builds_created_at", "created_at"),
        Index("ix_agent_builds_target_channel_created_at", "target", "channel", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentBuild(target={self.target!r}, channel={self.channel!r}, "
            f"version={self.version!r}, sha256={self.sha256[:16]}..., size={self.size})>"
        )


class DeviceModule(Base):
    """
    Server-side registry of installed modules on devices (actual state).
    
    Tracks which modules are installed/active on each device.
    source: handshake|command_result|event
    last_seen_at: последнее подтверждение реального наличия от агента
    """
    __tablename__ = "device_modules"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    
    installed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    
    installed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    # Новые поля (миграция 037)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        comment="Время последнего подтверждения реального наличия модуля (от агента)"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Источник обновления: handshake|command_result|event"
    )
    
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="installed", index=True)  # installing|installed|activating|active|failed|missing|removed
    last_error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        UniqueConstraint("device_id", "module_name", "version", name="uq_device_modules_device_name_version"),
        Index("ix_device_modules_device_active", "device_id", "active"),
        Index("ix_device_modules_device_state", "device_id", "state"),
        Index("ix_device_modules_module_name", "module_name"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceModule(id={self.id}, device_id={self.device_id!r}, "
            f"module_name={self.module_name!r}, version={self.version!r}, "
            f"installed={self.installed}, active={self.active}, state={self.state!r})>"
        )


class DeviceDesiredModule(Base):
    """
    Желаемое состояние модулей на устройствах (desired state).
    
    Server-first источник истины для reconcile engine.
    state: installed | absent
    reason: manual | run_tool | policy | reconcile
    """
    __tablename__ = "device_desired_modules"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # desired_version: None означает "absent" (желаем удалить)
    desired_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    desired_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="installed",
        comment="Желаемое состояние: installed|absent"
    )
    reason: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        comment="Причина изменения: manual|run_tool|policy|reconcile"
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    updated_by: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Кто изменил (actor_role или имя пользователя)"
    )
    
    __table_args__ = (
        UniqueConstraint("device_id", "module_name", name="uq_device_desired_modules_device_module"),
        Index("ix_device_desired_modules_device_id", "device_id"),
        Index("ix_device_desired_modules_state", "state"),
        Index("ix_device_desired_modules_device_state", "device_id", "state"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DeviceDesiredModule(id={self.id}, device_id={self.device_id!r}, "
            f"module_name={self.module_name!r}, desired_version={self.desired_version!r}, "
            f"state={self.state!r}, reason={self.reason!r})>"
        )


class AgentToken(Base):
    """
    Agent token model for authentication.
    
    Stores SHA256 hashes of tokens (not raw tokens) for security.
    Supports token rotation with grace period.
    """
    __tablename__ = "agent_tokens"
    
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for logs
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Token rotation support
    replaced_by_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        # Foreign key to self for rotation tracking
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_agent_tokens_device_id", "device_id"),
        # Partial index for active tokens (not revoked)
        Index("ix_agent_tokens_active", "device_id", "revoked_at", postgresql_where=sa.text("revoked_at IS NULL")),
        Index("ix_agent_tokens_prefix", "token_prefix"),  # For log lookups
    )
    
    def __repr__(self) -> str:
        return (
            f"<AgentToken(token_hash={self.token_hash[:16]}..., "
            f"device_id={self.device_id!r}, revoked_at={self.revoked_at})>"
        )


class UiToken(Base):
    """
    UI token model for authentication.
    
    Stores SHA256 hashes of tokens (not raw tokens) for security.
    Supports token rotation with grace period.
    """
    __tablename__ = "ui_tokens"
    
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA256 hash
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)  # First 8 chars for logs
    user_login: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Token rotation support
    replaced_by_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        # Foreign key to self for rotation tracking
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    __table_args__ = (
        Index("ix_ui_tokens_user_login", "user_login"),
        # Partial index for active tokens (not revoked)
        Index("ix_ui_tokens_active", "user_login", "revoked_at", postgresql_where=sa.text("revoked_at IS NULL")),
        Index("ix_ui_tokens_prefix", "token_prefix"),  # For log lookups
    )
    
    def __repr__(self) -> str:
        return (
            f"<UiToken(token_hash={self.token_hash[:16]}..., "
            f"user_login={self.user_login!r}, actor_role={self.actor_role!r}, "
            f"revoked_at={self.revoked_at})>"
        )


class ConnectionRequest(Base):
    """
    Pending or resolved device connection request (agent requests token).
    status: pending | approved | rejected
    last_request_at: обновляется при каждом POST от агента; в списке для админки
    показываются только запросы с last_request_at за последние 30 сек.
    """
    __tablename__ = "connection_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_request_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    request_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    poll_secret_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_token_delivered_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ConnectionRequest(id={self.id}, device_id={self.device_id!r}, status={self.status!r})>"


class ServerConfig(Base):
    """Key-value server config (e.g. connection_policy)."""
    __tablename__ = "server_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UiUser(Base):
    """Stage 10: UI пользователь (логин, хеш пароля, роль). Управление из БД."""
    __tablename__ = "ui_users"
    user_login: Mapped[str] = mapped_column(String(100), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa.text("0"))
    locked_until: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_ticket_assigned_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        sa.CheckConstraint("actor_role IN ('admin', 'support', 'auditor', 'user')", name="ck_ui_users_actor_role"),
        Index("ix_ui_users_is_active", "is_active"),
        Index("ix_ui_users_actor_role", "actor_role"),
        Index("ix_ui_users_locked_until", "locked_until"),
    )


class UiUserAudit(Base):
    """Stage 10: Журнал действий по UI пользователям (создание, смена пароля, деактивация и т.д.)."""
    __tablename__ = "ui_user_audit"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_login: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_ui_user_audit_user_login_created_at", "user_login", "created_at"),
        Index("ix_ui_user_audit_created_at", "created_at"),
    )


class AccessGroup(Base):
    """Admin-defined RBAC access group."""
    __tablename__ = "access_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_access_groups_is_active", "is_active"),
        Index("ix_access_groups_code", "code"),
    )


class AccessGroupMember(Base):
    """User membership in an RBAC access group."""
    __tablename__ = "access_group_members"

    group_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True
    )
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)

    __table_args__ = (Index("ix_access_group_members_actor_id", "actor_id"),)


class AccessGroupPermission(Base):
    """Permission grant assigned to an RBAC access group."""
    __tablename__ = "access_group_permissions"

    group_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True
    )
    permission_code: Mapped[str] = mapped_column(String(120), primary_key=True)

    __table_args__ = (Index("ix_access_group_permissions_permission", "permission_code"),)


class AccessGroupQueueMember(Base):
    """Queue visibility grant assigned through an RBAC access group."""
    __tablename__ = "access_group_queue_members"

    group_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("access_groups.id", ondelete="CASCADE"), primary_key=True
    )
    queue_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True
    )
    role_in_queue: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class AccessAudit(Base):
    """Append-only RBAC audit trail for access groups and grants."""
    __tablename__ = "access_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_access_audit_entity_created", "entity_type", "entity_id", "created_at"),
        Index("ix_access_audit_actor_created", "actor_id", "created_at"),
        Index("ix_access_audit_created_at", "created_at"),
    )


class AgentRuntimeAudit(Base):
    """Append-only audit trail for agent auth/update/runtime lifecycle."""
    __tablename__ = "agent_runtime_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="info")
    source: Mapped[str] = mapped_column(String(64), nullable=False, server_default="server")
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_agent_runtime_audit_device_created", "device_id", "created_at"),
        Index("ix_agent_runtime_audit_event_created", "event_type", "created_at"),
        Index("ix_agent_runtime_audit_severity_created", "severity", "created_at"),
        Index("ix_agent_runtime_audit_created_at", "created_at"),
    )


class ObserverIntegrityEvent(Base):
    """Durable OBS1 integrity event with dedupe, resolution and suppression state."""

    __tablename__ = "observer_integrity_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active", index=True)
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    command_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    device_outbox_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    outbox_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    runbook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suppression_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_observer_integrity_status_severity", "status", "severity", "last_seen_at"),
        Index("ix_observer_integrity_device_status", "device_id", "status", "severity"),
        Index("ix_observer_integrity_operation", "operation_id", "status"),
        Index("ix_observer_integrity_ticket", "ticket_id", "status"),
    )


class ObserverKnownContamination(Base):
    """Narrow suppression registry for historical P0-P6 contamination."""

    __tablename__ = "observer_known_contamination"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_phase: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(160), nullable=False)
    suppression_scope: Mapped[str] = mapped_column(String(160), nullable=False, default="observer_integrity")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source_phase",
            "entity_type",
            "entity_id",
            "suppression_scope",
            name="uq_observer_known_contamination_entity",
        ),
        Index("ix_observer_known_contamination_entity", "entity_type", "entity_id"),
        Index("ix_observer_known_contamination_active", "active", "expires_at"),
    )


class AgentObserverEvent(Base):
    """Bounded agent-uploaded telemetry source for server-side observer projection."""
    __tablename__ = "agent_observer_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    install_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    machine_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    agent_seq: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    playbook_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    playbook_step_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    root_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="info")
    component: Mapped[str] = mapped_column(String(64), nullable=False, server_default="agent")
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    module_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    received_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_agent_observer_events_device_created", "device_id", "created_at"),
        Index("ix_agent_observer_events_trace_id", "trace_id"),
        Index("ix_agent_observer_events_operation_id", "operation_id"),
        Index("ix_agent_observer_events_event_created", "event_type", "created_at"),
        Index("ix_agent_observer_events_severity_created", "severity", "created_at"),
        Index("ix_agent_observer_events_root_created", "root_kind", "created_at"),
    )


class ObserverTrace(Base):
    """Materialized technical trace overlay built from existing runtime sources."""
    __tablename__ = "observer_traces"

    trace_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    root_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    root_kind: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="running")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    span_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_observer_traces_started_at", "started_at"),
        Index("ix_observer_traces_status_started_at", "status", "started_at"),
    )


class ObserverSpan(Base):
    """Individual segment of an observer trace."""
    __tablename__ = "observer_spans"

    span_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("observer_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, server_default="internal")
    component: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    module_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="ok")
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        UniqueConstraint("trace_id", "source_type", "source_ref", name="uq_observer_spans_trace_source"),
        Index("ix_observer_spans_trace_parent", "trace_id", "parent_span_id"),
        Index("ix_observer_spans_status_started_at", "status", "started_at"),
    )


class ObserverSpanLink(Base):
    """Causal links between spans when relationship is not a strict tree edge."""
    __tablename__ = "observer_span_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    span_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("observer_spans.span_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    linked_span_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "span_id",
            "linked_trace_id",
            "linked_span_id",
            "reason",
            name="uq_observer_span_links_target_reason",
        ),
    )


class ObserverErrorSignature(Base):
    """Aggregated fingerprint of similar observer failures."""
    __tablename__ = "observer_error_signatures"

    error_signature: Mapped[str] = mapped_column(String(160), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    module_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    exception_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message_sample: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    occurrences_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    affected_devices_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        Index("ix_observer_error_signatures_component_seen", "component", "last_seen_at"),
        Index("ix_observer_error_signatures_module_seen", "module_name", "last_seen_at"),
    )


class ObserverErrorOccurrence(Base):
    """Concrete failure occurrence inside a projected observer span/trace."""
    __tablename__ = "observer_error_occurrences"

    occurrence_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("observer_traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    span_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("observer_spans.span_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_signature: Mapped[str] = mapped_column(
        String(160),
        sa.ForeignKey("observer_error_signatures.error_signature", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    component: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    module_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tool_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_kind: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    exception_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, server_default="error")
    message_norm: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stack_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attrs_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    __table_args__ = (
        Index("ix_observer_error_occurrences_signature_created", "error_signature", "created_at"),
        Index("ix_observer_error_occurrences_trace_created", "trace_id", "created_at"),
    )


class AuthSession(Base):
    """
    Auth session model for Phase 2 (session-based authentication).
    
    Prepared for future implementation of session-based auth for UI.
    """
    __tablename__ = "auth_sessions"
    
    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_login: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    
    # Session metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_auth_sessions_user_login", "user_login"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
    )


class TicketPublicSession(Base):
    """Short-lived public web session for a specific ticket."""
    __tablename__ = "ticket_public_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    ticket_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ticket_public_sessions_ticket_id", "ticket_id"),
        Index("ix_ticket_public_sessions_expires_at", "expires_at"),
        Index(
            "ix_ticket_public_sessions_active",
            "ticket_id",
            "revoked_at",
            postgresql_where=sa.text("revoked_at IS NULL"),
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AuthSession(session_id={self.session_id[:16]}..., "
            f"user_login={self.user_login!r}, expires_at={self.expires_at})>"
        )


class ConsentDecision(Base):
    """
    Consent decision model for tracking approve/deny decisions.
    
    Stores decisions for operations that require consent (waiting_consent status).
    """
    __tablename__ = "consent_decisions"
    
    operation_id: Mapped[str] = mapped_column(
        String(36),
        sa.ForeignKey("operations.operation_id", ondelete="CASCADE"),
        primary_key=True
    )
    decision: Mapped[str] = mapped_column(String(10), nullable=False)  # 'approved' or 'denied'
    decided_by: Mapped[str] = mapped_column(String(100), nullable=False)  # actor_role or user_login
    decided_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        sa.CheckConstraint(
            "decision IN ('approved', 'denied')",
            name="ck_consent_decisions_decision"
        ),
        Index("ix_consent_decisions_decided_at", "decided_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<ConsentDecision(operation_id={self.operation_id!r}, "
            f"decision={self.decision!r}, decided_by={self.decided_by!r})>"
        )


class UserConsentRequest(Base):
    """Canonical requester consent request shared by browser and agent surfaces."""

    __tablename__ = "user_consent_requests"

    consent_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("devices.device_id", ondelete="SET NULL"), nullable=True)
    requester_person_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True)
    requester_binding_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("device_user_bindings.binding_id", ondelete="SET NULL"), nullable=True)
    requester_account_session_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        sa.ForeignKey("device_account_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    risk_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_action_payload_redacted: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    expires_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    decided_by_actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_by_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    decided_from_surface: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        sa.CheckConstraint(
            "subject_type IN ('operation', 'remote_assist', 'diagnostic', 'tool_run', 'file_transfer', 'clipboard', 'elevated')",
            name="ck_user_consent_requests_subject_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'denied', 'expired', 'superseded', 'canceled')",
            name="ck_user_consent_requests_status",
        ),
        sa.CheckConstraint(
            "decided_from_surface IS NULL OR decided_from_surface IN ('browser', 'agent_gui', 'api')",
            name="ck_user_consent_requests_surface",
        ),
        Index("ix_user_consent_requests_status_expires", "status", "expires_at"),
        Index("ix_user_consent_requests_person_status", "requester_person_id", "status"),
        Index("ix_user_consent_requests_device_status", "device_id", "status"),
        Index("ix_user_consent_requests_ticket", "ticket_id"),
        Index("ix_user_consent_requests_subject", "subject_type", "subject_id"),
        Index(
            "ux_user_consent_requests_pending_subject",
            "subject_type",
            "subject_id",
            unique=True,
            postgresql_where=sa.text("status = 'pending'"),
        ),
    )


class DownloadAudit(Base):
    """
    Download audit model for tracking module downloads.
    
    Stores audit logs for all module download requests with token information.
    КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token.
    """
    __tablename__ = "download_audit"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA256 hash
    token_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # First 8 chars for logs
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    __table_args__ = (
        Index("ix_download_audit_token_hash", "token_hash"),
        Index("ix_download_audit_module", "module_name", "version"),
        Index("ix_download_audit_downloaded_at", "downloaded_at"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<DownloadAudit(id={self.id}, module_name={self.module_name!r}, "
            f"version={self.version!r}, downloaded_at={self.downloaded_at})>"
        )


class AgentBuildDownloadAudit(Base):
    """
    Download audit model for tracking agent build downloads.

    КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token.
    """
    __tablename__ = "agent_build_download_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    target: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)

    downloaded_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_agent_build_dl_audit_token_hash", "token_hash"),
        Index("ix_agent_build_dl_audit_build", "target", "channel", "version"),
        Index("ix_agent_build_dl_audit_downloaded_at", "downloaded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentBuildDownloadAudit(id={self.id}, target={self.target!r}, "
            f"channel={self.channel!r}, version={self.version!r})>"
        )


class Artifact(Base):
    """
    Артефакт (файл), загруженный агентом: скриншоты, запись экрана.
    
    Метаданные хранятся в БД, файл — на диске (storage_path относительно UPLOAD_DIR).
    """
    __tablename__ = "artifacts"
    
    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        Index("ix_artifacts_sha256", "sha256"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Artifact(artifact_id={self.artifact_id!r}, kind={self.kind!r}, "
            f"device_id={self.device_id!r}, size_bytes={self.size_bytes})>"
        )


# --- Playbook Engine (см. docs/PLAYBOOK_ENGINE_DESIGN.md) ---


class DiagnosticSession(Base):
    """Ticket-scoped diagnostic session independent from ticket status."""

    __tablename__ = "diagnostic_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    profile_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", server_default="draft", index=True)
    trigger_source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    started_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"), index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_sessions_ticket_status", "ticket_id", "status"),
        Index("ix_diag_sessions_started_at", "started_at"),
    )


class DiagnosticStep(Base):
    """Single diagnostic step linked to an operation, playbook, observer, remote assist or manual check."""

    __tablename__ = "diagnostic_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    step_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("operations.operation_id", ondelete="SET NULL"), nullable=True, index=True)
    playbook_run_id: Mapped[Optional[int]] = mapped_column(BigInteger, sa.ForeignKey("playbook_run.id", ondelete="SET NULL"), nullable=True, index=True)
    playbook_step_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    remote_assist_session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("remote_access_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    observer_trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_steps_ticket_type", "ticket_id", "step_type"),
        Index("ix_diag_steps_session_status", "session_id", "status"),
    )


class DiagnosticSessionCapability(Base):
    """Session-scoped capability snapshot with readiness, params, result and evidence links."""

    __tablename__ = "diagnostic_session_capabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    capability_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    capability_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    execution_target: Mapped[str] = mapped_column(String(64), nullable=False)
    readiness_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    readiness_reason_code: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    readiness_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    readiness_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    params_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    result_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_evidence.id", ondelete="SET NULL"), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("operations.operation_id", ondelete="SET NULL"), nullable=True, index=True)
    session_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", server_default="planned")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_session_caps_session_capability", "session_id", "capability_id"),
    )


class DiagnosticEvidence(Base):
    """Normalized diagnostic fact that can later be selected for a passport."""

    __tablename__ = "diagnostic_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    step_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_steps.id", ondelete="SET NULL"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    perspective: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"), index=True)
    normalized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    raw_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifact_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    redaction_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    passport_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.text("false"))
    selected_for_passport: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.text("false"), index=True)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_ev_ticket_observed", "ticket_id", "observed_at"),
        Index("ix_diag_ev_source_identity", "ticket_id", "source_type", "source_id", "kind", unique=True),
        Index("ix_diag_ev_ticket_status", "ticket_id", "status"),
    )


class DiagnosticArtifactLink(Base):
    """Normalized link from diagnostic evidence/session steps to existing artifacts."""

    __tablename__ = "diagnostic_artifact_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    step_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    evidence_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_evidence.id", ondelete="CASCADE"), nullable=True, index=True)
    artifact_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("artifacts.artifact_id", ondelete="SET NULL"), nullable=True, index=True)
    artifact_kind: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capability_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        UniqueConstraint("ticket_id", "evidence_id", "artifact_id", "artifact_kind", name="uq_diag_artifact_link_identity"),
        Index("ix_diag_artifact_links_source", "source_type", "source_id"),
    )


class DiagnosticFinding(Base):
    """Rule-based or manual diagnostic conclusion linked to evidence ids."""

    __tablename__ = "diagnostic_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    root_cause_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="suspected", server_default="suspected", index=True)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    recommended_actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="system", server_default="system")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_find_ticket_code", "ticket_id", "root_cause_code"),
        Index("ix_diag_find_ticket_status", "ticket_id", "status"),
    )


class DiagnosticBundle(Base):
    """JSON diagnostic package that references selected evidence and existing artifacts."""

    __tablename__ = "diagnostic_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("diagnostic_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="building", server_default="building", index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    artifact_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    observer_trace_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    remote_assist_session_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_bundles_ticket_created", "ticket_id", "created_at"),
        Index("ix_diag_bundles_ticket_status", "ticket_id", "status"),
    )


class DiagnosticProvider(Base):
    """Persisted diagnostic provider snapshot/config boundary."""

    __tablename__ = "diagnostic_providers"

    provider_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="computed", server_default="computed")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available", server_default="available")
    config_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_providers_type_status", "provider_type", "status"),
    )


class DiagnosticCapability(Base):
    """Persisted capability descriptor snapshot for admin/config workflows."""

    __tablename__ = "diagnostic_capabilities"

    capability_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_id: Mapped[str] = mapped_column(Text, sa.ForeignKey("diagnostic_providers.provider_id", ondelete="CASCADE"), nullable=False)
    execution_target: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available", server_default="available")
    latest_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    descriptor_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_capabilities_provider", "provider_id"),
        Index("ix_diag_capabilities_target_status", "execution_target", "status"),
    )


class ToolPresentationOverride(Base):
    """Server-side override for declarative tool result rendering."""

    __tablename__ = "tool_presentation_overrides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tool_id: Mapped[str] = mapped_column(Text, nullable=False)
    tool_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="global", server_default="global")
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    presentation_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.text("true"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_tool_presentation_overrides_tool", "tool_id"),
        Index("ix_tool_presentation_overrides_enabled", "enabled"),
    )


class DiagnosticCapabilityVersion(Base):
    """Versioned persisted snapshot for a diagnostic capability descriptor."""

    __tablename__ = "diagnostic_capability_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capability_id: Mapped[str] = mapped_column(Text, sa.ForeignKey("diagnostic_capabilities.capability_id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published", server_default="published")
    descriptor_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    params_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    output_schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    output_contract_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    safety_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    evidence_mapping_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    deployment_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    readiness_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    contract_hash: Mapped[str] = mapped_column(String(128), nullable=False, default="", server_default="")
    source_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa.text("false"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_diag_capability_versions_capability", "capability_id", "is_current"),
        sa.UniqueConstraint("capability_id", "version", name="uq_diag_capability_versions_capability_version"),
    )


class AgentRecipeVersion(Base):
    """Concrete declarative recipe implementation for an agent_recipe capability version."""

    __tablename__ = "agent_recipe_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capability_version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("diagnostic_capability_versions.id", ondelete="CASCADE"), nullable=False)
    recipe_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    runner_provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="agent_recipe_runner", server_default="agent_recipe_runner")
    min_runner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    primitive_id: Mapped[str] = mapped_column(Text, nullable=False)
    primitive_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    platforms_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    platform_variants_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    recipe_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    parameter_bindings_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    resource_limits_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    redaction_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    validation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown", server_default="unknown")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_agent_recipe_versions_capability_version", "capability_version_id"),
        Index("ix_agent_recipe_versions_primitive", "primitive_id"),
        Index("ix_agent_recipe_versions_runner", "runner_provider_id"),
        Index("ix_agent_recipe_versions_validation", "validation_status"),
    )


class AgentRecipePrimitive(Base):
    """Primitive catalog advertised by protected agent_recipe_runner versions."""

    __tablename__ = "agent_recipe_primitives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    runner_provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="agent_recipe_runner", server_default="agent_recipe_runner")
    runner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    primitive_id: Mapped[str] = mapped_column(Text, nullable=False)
    primitive_version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platforms_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    params_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    output_contract: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    safety_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    evidence_defaults_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    resource_limits_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    redaction_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        sa.UniqueConstraint(
            "runner_provider_id",
            "runner_version",
            "primitive_id",
            "primitive_version",
            name="uq_agent_recipe_primitives_runner_primitive",
        ),
        Index("ix_agent_recipe_primitives_runner", "runner_provider_id", "runner_version"),
        Index("ix_agent_recipe_primitives_primitive", "primitive_id"),
    )


class AgentRecipeTestRun(Base):
    """Audit trail for recipe validation/live tests."""

    __tablename__ = "agent_recipe_test_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    recipe_version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("agent_recipe_versions.id", ondelete="CASCADE"), nullable=False)
    target_device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    runner_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    artifacts_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb"))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_agent_recipe_test_runs_recipe", "recipe_version_id"),
        Index("ix_agent_recipe_test_runs_status", "status"),
        Index("ix_agent_recipe_test_runs_platform", "platform"),
        Index("ix_agent_recipe_test_runs_device", "target_device_id"),
    )


class DiagnosticProviderConfig(Base):
    """Server-side provider integration config with redacted persisted config payloads."""

    __tablename__ = "diagnostic_provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=sa.text("true"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="configured", server_default="configured")
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    redaction_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    health_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_provider_configs_provider", "provider_id"),
        Index("ix_diag_provider_configs_integration_status", "integration_key", "status"),
    )


class DiagnosticProviderCredentialRef(Base):
    """Reference to a secret/config-store credential for a diagnostic provider."""

    __tablename__ = "diagnostic_provider_credential_refs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_config_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("diagnostic_provider_configs.id", ondelete="CASCADE"), nullable=False)
    credential_key: Mapped[str] = mapped_column(String(120), nullable=False)
    secret_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="missing", server_default="missing")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_provider_credential_refs_config", "provider_config_id"),
        Index("ix_diag_provider_credential_refs_status", "status"),
        sa.UniqueConstraint("provider_config_id", "credential_key", name="uq_diag_provider_credential_key"),
    )


class DiagnosticProviderAudit(Base):
    """Append-only audit trail for diagnostic provider config changes."""

    __tablename__ = "diagnostic_provider_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_config_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=sa.text("now()"))

    __table_args__ = (
        Index("ix_diag_provider_audit_provider_created", "provider_id", "created_at"),
        Index("ix_diag_provider_audit_actor_created", "actor_id", "created_at"),
    )


class Playbook(Base):
    """Плейбук: ключ, имя, домен, владелец, архивный флаг."""
    __tablename__ = "playbook"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PlaybookVersion(Base):
    """Версия плейбука: manifest, статус, даты публикации."""
    __tablename__ = "playbook_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    manifest_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("playbook_id", "version", name="uq_playbook_version_playbook_version"),)


class PlaybookStep(Base):
    """Шаг плейбука: tool, params template, if_expr, timeout, retry, parallel_group."""
    __tablename__ = "playbook_step"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_version_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_version.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, default="run_tool")
    tool: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    params_template_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    if_expr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeout_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    continue_on_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parallel_group: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_playbook_step_order", "playbook_version_id", "order_no"),)


class PlaybookRun(Base):
    """Запуск плейбука на устройстве: статус, scheduled/started/finished, trigger, context."""
    __tablename__ = "playbook_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_version_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_version.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Этап 6: идемпотентность при повторном POST (один ключ — один run)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True)

    __table_args__ = (
        Index("ix_playbook_run_scheduled_at", "scheduled_at"),
        Index("ix_playbook_run_status_scheduled_at", "status", "scheduled_at"),
    )


class PlaybookStepRun(Base):
    """Исполнение шага плейбука: attempt, status, operation_id, input/output/error, trace_id."""
    __tablename__ = "playbook_step_run"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playbook_run_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_run.id", ondelete="CASCADE"), nullable=False, index=True
    )
    playbook_step_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("playbook_step.id", ondelete="RESTRICT"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    operation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    input_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)


class AIProvider(Base):
    """Configurable AI provider. Secret refs are stored as references, not raw keys."""

    __tablename__ = "ai_providers"

    provider_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="api_key")
    api_key_secret_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_headers_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    data_policy: Mapped[str] = mapped_column(String(40), nullable=False, server_default="no_sensitive")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    health_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    last_health_check_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    last_error_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "provider_type IN ('openrouter', 'openai_compatible', 'ollama', 'local_custom')",
            name="ck_ai_providers_provider_type",
        ),
        sa.CheckConstraint(
            "auth_type IN ('api_key', 'bearer', 'none', 'custom_header')",
            name="ck_ai_providers_auth_type",
        ),
        sa.CheckConstraint(
            "data_policy IN ('local_only', 'cloud_allowed', 'no_sensitive', 'allow_public')",
            name="ck_ai_providers_data_policy",
        ),
        Index("ix_ai_providers_type_enabled", "provider_type", "enabled"),
        Index("ix_ai_providers_health", "health_status"),
    )


class AIModelProfile(Base):
    """Model profile for a specific AI task."""

    __tablename__ = "ai_model_profiles"

    profile_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("ai_providers.provider_id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    context_window: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30000")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    temperature: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    top_p: Mapped[Optional[float]] = mapped_column(sa.Float, nullable=True)
    structured_output_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    streaming_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    fallback_profile_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "task_type IN ('chat', 'embedding', 'rerank', 'rewrite', 'summarize', 'classify', 'extract', 'answer', 'markup', 'moderation')",
            name="ck_ai_model_profiles_task_type",
        ),
        Index("ix_ai_model_profiles_provider_task", "provider_id", "task_type"),
        Index("ix_ai_model_profiles_task_default", "task_type", "is_default"),
    )


class AIPolicyProfile(Base):
    """Policy profile controlling optional AI task usage."""

    __tablename__ = "ai_policy_profiles"

    policy_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False)
    space_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    visibility: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    ai_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    embedding_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    rerank_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    answer_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    rewrite_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    auto_markup_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    require_local_for_security_restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    allow_cloud_for_requester_safe: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    redact_before_send: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    store_prompts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    store_outputs: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    max_tokens_per_request: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_requests_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cost_per_day: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint(
            "scope_type IN ('global', 'space', 'visibility', 'task_type')",
            name="ck_ai_policy_profiles_scope_type",
        ),
        Index("ix_ai_policy_profiles_scope_task", "scope_type", "task_type"),
        Index("ix_ai_policy_profiles_visibility", "visibility"),
    )


class AIRequestAudit(Base):
    """Redacted audit row for AI requests."""

    __tablename__ = "ai_request_audit"

    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ai_providers.provider_id", ondelete="SET NULL"), nullable=True)
    model_profile_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True)
    task_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    error_message_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ai_request_audit_provider_created", "provider_id", "created_at"),
        Index("ix_ai_request_audit_task_status", "task_type", "status"),
    )


class KnowledgeSearchSettings(Base):
    """Global Knowledge search controls. AI/vector switches default to off."""

    __tablename__ = "knowledge_search_settings"

    settings_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, server_default="global")
    space_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    visibility: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    search_mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="keyword_only")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    keyword_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("true"))
    full_text_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    vector_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    rerank_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    ai_query_rewrite_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    rag_answer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sa.text("false"))
    keyword_weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="1.0")
    full_text_weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="1.0")
    vector_weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, server_default="1.0")
    max_results: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    snippet_length: Mapped[int] = mapped_column(Integer, nullable=False, server_default="180")
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        sa.CheckConstraint("scope_type IN ('global', 'space', 'visibility')", name="ck_knowledge_search_settings_scope_type"),
        sa.CheckConstraint(
            "search_mode IN ('keyword_only', 'full_text', 'hybrid_no_ai', 'hybrid_vector', 'hybrid_vector_rerank', 'rag_answer')",
            name="ck_knowledge_search_settings_search_mode",
        ),
        sa.CheckConstraint("max_results BETWEEN 1 AND 50", name="ck_knowledge_search_settings_max_results"),
        sa.CheckConstraint("snippet_length BETWEEN 80 AND 1000", name="ck_knowledge_search_settings_snippet_length"),
        Index("ix_knowledge_search_settings_scope", "scope_type", "space_id", "visibility"),
    )


class KnowledgeChunkEmbedding(Base):
    """Optional embedding/vector state for a Knowledge chunk."""

    __tablename__ = "knowledge_chunk_embeddings"

    embedding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    item_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[str] = mapped_column(String(36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False)
    model_profile_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True)
    embedding_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding_dimensions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    indexed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'indexed', 'failed', 'stale', 'disabled')",
            name="ck_knowledge_chunk_embeddings_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', 'admin_internal', 'security_restricted', 'auditor_read')",
            name="ck_knowledge_chunk_embeddings_visibility",
        ),
        Index("ix_knowledge_chunk_embeddings_chunk_status", "chunk_id", "status"),
        Index("ix_knowledge_chunk_embeddings_item_version", "item_id", "version_id", "status"),
        Index("ix_knowledge_chunk_embeddings_segment", "segment_id"),
    )


class KnowledgeIndexJob(Base):
    """Observable Knowledge indexing job."""

    __tablename__ = "knowledge_index_jobs"

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(30), nullable=False)
    scope_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_profile_id: Mapped[Optional[str]] = mapped_column(String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    requested_by: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))
    error_redacted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb"))

    __table_args__ = (
        sa.CheckConstraint(
            "scope_type IN ('item', 'version', 'space', 'all', 'segment')",
            name="ck_knowledge_index_jobs_scope_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'canceled')",
            name="ck_knowledge_index_jobs_status",
        ),
        Index("ix_knowledge_index_jobs_scope_status", "scope_type", "scope_ref", "status"),
    )
