"""problem management RCA

Revision ID: 090
Revises: 089
Create Date: 2026-05-17 19:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "090"
down_revision: Union[str, None] = "089"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _drop_index(name: str, table_name: str) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name in indexes:
        op.drop_index(name, table_name=table_name)


def _create_index(name: str, table_name: str, columns: list[str], *, unique: bool = False, where: str | None = None) -> None:
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if name not in indexes:
        op.create_index(name, table_name, columns, unique=unique, postgresql_where=sa.text(where) if where else None)


def upgrade() -> None:
    bind = op.get_bind()
    _add_column("problems", sa.Column("problem_key", sa.String(length=24), nullable=True))
    _add_column("problems", sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"))
    _add_column("problems", sa.Column("impact", sa.String(length=20), nullable=False, server_default="medium"))
    _add_column("problems", sa.Column("urgency", sa.String(length=20), nullable=False, server_default="medium"))
    _add_column("problems", sa.Column("source_kind", sa.String(length=40), nullable=False, server_default="manual"))
    _add_column("problems", sa.Column("source_ref", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("service_code", sa.String(length=100), nullable=True))
    _add_column("problems", sa.Column("offering_code", sa.String(length=220), nullable=True))
    _add_column("problems", sa.Column("request_type", sa.String(length=64), nullable=True))
    _add_column("problems", sa.Column("reporting_category", sa.String(length=120), nullable=True))
    _add_column("problems", sa.Column("owner_actor_id", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("assignee_actor_id", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("queue_id", sa.BigInteger(), nullable=True))
    _add_column("problems", sa.Column("opened_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("detected_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("investigation_started_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("known_error_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("workaround_available_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("permanent_fix_planned_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("permanent_fix_in_progress_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("canceled_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("target_resolution_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("root_cause_summary", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("root_cause_category", sa.String(length=60), nullable=True))
    _add_column("problems", sa.Column("workaround_summary", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("permanent_fix_summary", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("closure_summary", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    _add_column("problems", sa.Column("created_by", sa.Text(), nullable=True))
    _add_column("problems", sa.Column("updated_by", sa.Text(), nullable=True))
    bind.execute(sa.text("""
        WITH numbered AS (
            SELECT problem_id, row_number() OVER (ORDER BY created_at, problem_id) AS rn
            FROM problems
            WHERE problem_key IS NULL
        )
        UPDATE problems
        SET problem_key = 'PRB-' || lpad(numbered.rn::text, 6, '0')
        FROM numbered
        WHERE problems.problem_id = numbered.problem_id
    """))
    bind.execute(sa.text("UPDATE problems SET opened_at = coalesce(created_at, now()) WHERE opened_at IS NULL"))
    bind.execute(sa.text("UPDATE problems SET status = lower(status) WHERE status IN ('New', 'Investigating', 'Mitigated', 'Resolved', 'Closed')"))
    bind.execute(sa.text("UPDATE problems SET status = 'workaround_available' WHERE status = 'mitigated'"))
    op.alter_column("problems", "problem_key", existing_type=sa.String(length=24), nullable=False)
    op.alter_column("problems", "opened_at", existing_type=TIMESTAMP(timezone=True), nullable=False)
    op.alter_column("problems", "status", existing_type=sa.String(length=30), type_=sa.String(length=40), existing_nullable=False, server_default="new")
    op.alter_column("problems", "priority", existing_type=sa.String(length=5), type_=sa.String(length=20), existing_nullable=False, server_default="medium")
    _create_index("uq_problems_problem_key", "problems", ["problem_key"], unique=True)
    _create_index("ix_problems_service_offering", "problems", ["service_code", "offering_code"])

    _add_column("problem_ticket_links", sa.Column("link_id", sa.String(length=36), nullable=True))
    _add_column("problem_ticket_links", sa.Column("link_type", sa.String(length=40), nullable=False, server_default="suspected"))
    _add_column("problem_ticket_links", sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True))
    _add_column("problem_ticket_links", sa.Column("evidence_summary", sa.Text(), nullable=True))
    _add_column("problem_ticket_links", sa.Column("linked_by_actor_id", sa.Text(), nullable=True))
    _add_column("problem_ticket_links", sa.Column("unlinked_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problem_ticket_links", sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
    bind.execute(sa.text("UPDATE problem_ticket_links SET link_id = md5(random()::text || clock_timestamp()::text) WHERE link_id IS NULL"))
    bind.execute(sa.text("UPDATE problem_ticket_links SET linked_by_actor_id = linked_by WHERE linked_by_actor_id IS NULL"))
    op.alter_column("problem_ticket_links", "link_id", existing_type=sa.String(length=36), nullable=False)
    try:
        op.drop_constraint("problem_ticket_links_pkey", "problem_ticket_links", type_="primary")
    except Exception:
        pass
    try:
        op.create_primary_key("problem_ticket_links_pkey", "problem_ticket_links", ["link_id"])
    except Exception:
        pass
    _create_index("ix_problem_ticket_links_problem_ticket", "problem_ticket_links", ["problem_id", "ticket_id"])
    _create_index(
        "uq_problem_ticket_links_active",
        "problem_ticket_links",
        ["problem_id", "ticket_id", "link_type"],
        unique=True,
        where="unlinked_at IS NULL",
    )

    op.create_table(
        "problem_rca_records",
        sa.Column("rca_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("methodology", sa.String(length=40), nullable=False, server_default="narrative"),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("impact_summary", sa.Text(), nullable=True),
        sa.Column("timeline_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("contributing_factors_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("root_cause_category", sa.String(length=60), nullable=True),
        sa.Column("evidence_refs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("corrective_actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("preventive_actions_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("reviewer_actor_id", sa.Text(), nullable=True),
        sa.Column("approved_by_actor_id", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("rca_id"),
        sa.UniqueConstraint("problem_id", "version_number", name="uq_problem_rca_problem_version"),
    )
    _create_index("ix_problem_rca_problem_status", "problem_rca_records", ["problem_id", "status"])

    op.create_table(
        "problem_known_error_links",
        sa.Column("link_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("link_type", sa.String(length=40), nullable=False),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("link_id"),
    )
    _create_index("ix_problem_known_error_links_problem", "problem_known_error_links", ["problem_id"])
    _create_index("ix_problem_known_error_links_item", "problem_known_error_links", ["knowledge_item_id"])

    op.create_table(
        "problem_affected_objects",
        sa.Column("affected_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_ref", sa.Text(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("impact", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("affected_id"),
    )
    _create_index("ix_problem_affected_problem_type", "problem_affected_objects", ["problem_id", "object_type"])

    op.create_table(
        "problem_detection_rules",
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scope_type", sa.String(length=30), nullable=False, server_default="global"),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("queue_id", sa.BigInteger(), nullable=True),
        sa.Column("request_type", sa.String(length=64), nullable=True),
        sa.Column("window_hours", sa.Integer(), nullable=False, server_default="168"),
        sa.Column("min_ticket_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("min_reopen_count", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("min_low_csat_count", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("min_sla_breach_count", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("min_failed_kb_count", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("similarity_mode", sa.String(length=40), nullable=False, server_default="service_offering"),
        sa.Column("auto_create_candidate", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("rule_id"),
        sa.UniqueConstraint("code", name="uq_problem_detection_rules_code"),
    )

    op.create_table(
        "problem_candidates",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), sa.ForeignKey("problem_detection_rules.rule_id", ondelete="SET NULL"), nullable=True),
        sa.Column("fingerprint", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("signal_type", sa.String(length=60), nullable=False, server_default="manual"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_type", sa.String(length=64), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ticket_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reopen_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_csat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sla_breach_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_kb_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("suggested_problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True),
        sa.Column("converted_problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_by_actor_id", sa.Text(), nullable=True),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dismissal_reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("candidate_id"),
        sa.UniqueConstraint("fingerprint", name="uq_problem_candidates_fingerprint"),
    )
    _create_index("ix_problem_candidates_status_service", "problem_candidates", ["status", "service_code", "offering_code"])

    op.create_table(
        "problem_activity_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=True),
        sa.Column("candidate_id", sa.String(length=36), sa.ForeignKey("problem_candidates.candidate_id", ondelete="CASCADE"), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("event_id"),
    )
    _create_index("ix_problem_activity_problem_created", "problem_activity_events", ["problem_id", "created_at"])

    _add_column("continuous_improvement_actions", sa.Column("problem_id", sa.String(length=36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True))
    _add_column("continuous_improvement_actions", sa.Column("problem_candidate_id", sa.String(length=36), sa.ForeignKey("problem_candidates.candidate_id", ondelete="SET NULL"), nullable=True))
    try:
        op.drop_constraint("ck_continuous_improvement_source_kind", "continuous_improvement_actions", type_="check")
        op.drop_constraint("ck_continuous_improvement_action_type", "continuous_improvement_actions", type_="check")
    except Exception:
        pass
    op.create_check_constraint(
        "ck_continuous_improvement_source_kind",
        "continuous_improvement_actions",
        "source_kind IN ('csat', 'reopen', 'qa_review', 'knowledge_gap', 'service_quality', 'sla_breach', 'problem_candidate', 'problem', 'manual')",
    )
    op.create_check_constraint(
        "ck_continuous_improvement_action_type",
        "continuous_improvement_actions",
        "action_type IN ('update_kb_article', 'create_kb_article', 'create_known_error', 'improve_request_form', 'update_routing_policy', 'adjust_sla_policy', 'add_diagnostic_playbook', 'train_support', 'open_problem_candidate', 'create_change_candidate', 'contact_requester', 'process_review', 'perform_rca', 'implement_permanent_fix', 'validate_workaround', 'update_known_error', 'other')",
    )


def downgrade() -> None:
    try:
        op.drop_constraint("ck_continuous_improvement_source_kind", "continuous_improvement_actions", type_="check")
        op.drop_constraint("ck_continuous_improvement_action_type", "continuous_improvement_actions", type_="check")
    except Exception:
        pass
    for column in ("problem_candidate_id", "problem_id"):
        if _has_column("continuous_improvement_actions", column):
            op.drop_column("continuous_improvement_actions", column)
    for table in (
        "problem_activity_events",
        "problem_candidates",
        "problem_detection_rules",
        "problem_affected_objects",
        "problem_known_error_links",
        "problem_rca_records",
    ):
        if _has_table(table):
            op.drop_table(table)
    _drop_index("uq_problem_ticket_links_active", "problem_ticket_links")
    _drop_index("ix_problem_ticket_links_problem_ticket", "problem_ticket_links")
    for column in ("metadata_json", "unlinked_at", "linked_by_actor_id", "evidence_summary", "confidence_score", "link_type", "link_id"):
        if _has_column("problem_ticket_links", column):
            op.drop_column("problem_ticket_links", column)
    _drop_index("uq_problems_problem_key", "problems")
    _drop_index("ix_problems_service_offering", "problems")
    for column in (
        "updated_by",
        "created_by",
        "metadata_json",
        "closure_summary",
        "permanent_fix_summary",
        "workaround_summary",
        "root_cause_category",
        "root_cause_summary",
        "target_resolution_at",
        "canceled_at",
        "permanent_fix_in_progress_at",
        "permanent_fix_planned_at",
        "workaround_available_at",
        "known_error_at",
        "investigation_started_at",
        "detected_at",
        "opened_at",
        "queue_id",
        "assignee_actor_id",
        "owner_actor_id",
        "reporting_category",
        "request_type",
        "offering_code",
        "service_code",
        "source_ref",
        "source_kind",
        "urgency",
        "impact",
        "severity",
        "problem_key",
    ):
        if _has_column("problems", column):
            op.drop_column("problems", column)
