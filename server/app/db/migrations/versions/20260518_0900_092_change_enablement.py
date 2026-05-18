"""change enablement

Revision ID: 092
Revises: 091
Create Date: 2026-05-18 09:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "092"
down_revision: Union[str, None] = "091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _create_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if not _has_index(table, name):
        op.create_index(name, table, columns, unique=unique)


def _jsonb(default: str):
    return postgresql.JSONB(astext_type=sa.Text()), sa.text(default)


def upgrade() -> None:
    jsonb_obj, empty_obj = _jsonb("'{}'::jsonb")
    jsonb_arr, empty_arr = _jsonb("'[]'::jsonb")

    if not _has_table("changes"):
        op.create_table(
            "changes",
            sa.Column("change_id", sa.String(36), nullable=False),
            sa.Column("change_key", sa.String(24), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("change_type", sa.String(20), nullable=False, server_default="normal"),
            sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
            sa.Column("category", sa.String(40), nullable=False, server_default="other"),
            sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("impact_level", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("urgency", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("source_kind", sa.String(40), nullable=False, server_default="manual"),
            sa.Column("source_ref", sa.Text(), nullable=True),
            sa.Column("problem_id", sa.String(36), sa.ForeignKey("problems.problem_id", ondelete="SET NULL"), nullable=True),
            sa.Column("improvement_action_id", sa.String(36), sa.ForeignKey("continuous_improvement_actions.action_id", ondelete="SET NULL"), nullable=True),
            sa.Column("service_code", sa.String(100), nullable=True),
            sa.Column("offering_code", sa.String(220), nullable=True),
            sa.Column("request_type", sa.String(64), nullable=True),
            sa.Column("reporting_category", sa.String(120), nullable=True),
            sa.Column("owner_actor_id", sa.Text(), nullable=True),
            sa.Column("assignee_actor_id", sa.Text(), nullable=True),
            sa.Column("queue_id", sa.BigInteger(), nullable=True),
            sa.Column("requested_by_actor_id", sa.Text(), nullable=True),
            sa.Column("submitted_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("assessed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("scheduled_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("implementation_started_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("implemented_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("closed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("canceled_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("failed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("planned_start_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("planned_end_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("actual_start_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("actual_end_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("blackout_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("emergency_justification", sa.Text(), nullable=True),
            sa.Column("risk_summary", sa.Text(), nullable=True),
            sa.Column("impact_summary", sa.Text(), nullable=True),
            sa.Column("implementation_summary", sa.Text(), nullable=True),
            sa.Column("rollback_summary", sa.Text(), nullable=True),
            sa.Column("communication_summary", sa.Text(), nullable=True),
            sa.Column("validation_summary", sa.Text(), nullable=True),
            sa.Column("closure_summary", sa.Text(), nullable=True),
            sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("change_type IN ('standard', 'normal', 'emergency')", name="ck_changes_type"),
            sa.CheckConstraint("status IN ('draft', 'submitted', 'assessing', 'awaiting_approval', 'approved', 'scheduled', 'implementation_in_progress', 'implemented', 'pir_required', 'closed', 'rejected', 'canceled', 'failed', 'rolled_back')", name="ck_changes_status"),
            sa.CheckConstraint("category IN ('infrastructure', 'application', 'network', 'security', 'access', 'service_catalog', 'knowledge', 'process', 'other')", name="ck_changes_category"),
            sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_changes_priority"),
            sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name="ck_changes_risk_level"),
            sa.CheckConstraint("impact_level IN ('low', 'medium', 'high', 'critical')", name="ck_changes_impact_level"),
            sa.CheckConstraint("urgency IN ('low', 'medium', 'high', 'critical')", name="ck_changes_urgency"),
            sa.CheckConstraint("planned_end_at IS NULL OR planned_start_at IS NULL OR planned_end_at > planned_start_at", name="ck_changes_planned_window"),
            sa.PrimaryKeyConstraint("change_id"),
            sa.UniqueConstraint("change_key", name="uq_changes_change_key"),
        )
        _create_index("ix_changes_status_type", "changes", ["status", "change_type"])
        _create_index("ix_changes_service_offering", "changes", ["service_code", "offering_code"])
        _create_index("ix_changes_planned_window", "changes", ["planned_start_at", "planned_end_at"])

    if _has_table("continuous_improvement_actions") and not _has_column("continuous_improvement_actions", "change_id"):
        op.add_column("continuous_improvement_actions", sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="SET NULL"), nullable=True))
        try:
            op.drop_constraint("ck_continuous_improvement_source_kind", "continuous_improvement_actions", type_="check")
        except Exception:
            pass
        op.create_check_constraint(
            "ck_continuous_improvement_source_kind",
            "continuous_improvement_actions",
            "source_kind IN ('csat', 'reopen', 'qa_review', 'knowledge_gap', 'service_quality', 'sla_breach', 'problem_candidate', 'problem', 'change', 'manual')",
        )

    def create_table(name: str, *columns_and_constraints) -> None:
        if not _has_table(name):
            op.create_table(name, *columns_and_constraints)

    create_table(
        "change_risk_assessments",
        sa.Column("assessment_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("impact_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("suggested_risk_level", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("risk_factors_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.Column("mitigation_plan", sa.Text(), nullable=True),
        sa.Column("test_plan_summary", sa.Text(), nullable=True),
        sa.Column("assessed_by_actor_id", sa.Text(), nullable=True),
        sa.Column("approved_by_actor_id", sa.Text(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected', 'archived')", name="ck_change_risk_status"),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("change_id", "version_number", name="uq_change_risk_change_version"),
    )
    create_table(
        "change_plans",
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("implementation_steps_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("rollback_steps_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("validation_steps_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("communication_steps_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("pre_checks_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("post_checks_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("downtime_expected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("downtime_minutes", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.CheckConstraint("status IN ('draft', 'in_review', 'approved', 'archived')", name="ck_change_plans_status"),
        sa.PrimaryKeyConstraint("plan_id"),
        sa.UniqueConstraint("change_id", "version_number", name="uq_change_plans_change_version"),
    )
    create_table(
        "change_approvals",
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("approval_stage", sa.String(40), nullable=False, server_default="cab"),
        sa.Column("approver_actor_id", sa.Text(), nullable=True),
        sa.Column("approver_role", sa.String(40), nullable=True),
        sa.Column("approver_group", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("decision_comment", sa.Text(), nullable=True),
        sa.Column("decided_by_actor_id", sa.Text(), nullable=True),
        sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("due_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'skipped', 'expired')", name="ck_change_approvals_status"),
        sa.PrimaryKeyConstraint("approval_id"),
    )
    create_table(
        "change_windows",
        sa.Column("window_id", sa.String(36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("window_type", sa.String(30), nullable=False, server_default="maintenance"),
        sa.Column("service_code", sa.String(100), nullable=True),
        sa.Column("offering_code", sa.String(220), nullable=True),
        sa.Column("object_type", sa.String(40), nullable=True),
        sa.Column("object_ref", sa.Text(), nullable=True),
        sa.Column("starts_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("recurrence_rule", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.CheckConstraint("window_type IN ('standard', 'maintenance', 'blackout', 'emergency_allowed')", name="ck_change_windows_type"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_change_windows_range"),
        sa.PrimaryKeyConstraint("window_id"),
    )
    create_table(
        "change_affected_objects",
        sa.Column("affected_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("object_ref", sa.Text(), nullable=False),
        sa.Column("service_code", sa.String(100), nullable=True),
        sa.Column("offering_code", sa.String(220), nullable=True),
        sa.Column("impact", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("planned_downtime", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.PrimaryKeyConstraint("affected_id"),
    )
    create_table(
        "change_tasks",
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(30), nullable=False, server_default="implementation"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("result_notes", sa.Text(), nullable=True),
        sa.Column("evidence_refs_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.PrimaryKeyConstraint("task_id"),
    )
    create_table(
        "change_pir_records",
        sa.Column("pir_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("implementation_successful", sa.Boolean(), nullable=True),
        sa.Column("rollback_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("caused_incident", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("met_objectives", sa.Boolean(), nullable=True),
        sa.Column("downtime_actual_minutes", sa.Integer(), nullable=True),
        sa.Column("issues_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("lessons_learned", sa.Text(), nullable=True),
        sa.Column("follow_up_actions_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("reviewed_by_actor_id", sa.Text(), nullable=True),
        sa.Column("approved_by_actor_id", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.PrimaryKeyConstraint("pir_id"),
    )
    create_table(
        "change_activity_events",
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("change_id", sa.String(36), sa.ForeignKey("changes.change_id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(40), nullable=True),
        sa.Column("payload_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("event_id"),
    )
    create_table(
        "change_policies",
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scope_type", sa.String(30), nullable=False, server_default="global"),
        sa.Column("service_code", sa.String(100), nullable=True),
        sa.Column("offering_code", sa.String(220), nullable=True),
        sa.Column("change_type", sa.String(20), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("require_risk_assessment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_plan", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_rollback_plan", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_pir", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("standard_preapproved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_mode", sa.String(20), nullable=False, server_default="single"),
        sa.Column("approver_roles_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("approver_actor_ids_json", jsonb_arr, nullable=False, server_default=empty_arr),
        sa.Column("cab_group", sa.Text(), nullable=True),
        sa.Column("min_lead_time_hours", sa.Integer(), nullable=True),
        sa.Column("max_emergency_retro_hours", sa.Integer(), nullable=True),
        sa.Column("blackout_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata_json", jsonb_obj, nullable=False, server_default=empty_obj),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("policy_id"),
        sa.UniqueConstraint("code", name="uq_change_policies_code"),
    )
    for table, cols in {
        "change_risk_assessments": ["change_id", "status"],
        "change_plans": ["change_id", "status"],
        "change_approvals": ["change_id", "status"],
        "change_windows": ["starts_at", "ends_at"],
        "change_affected_objects": ["change_id", "object_type"],
        "change_tasks": ["change_id", "status"],
        "change_pir_records": ["change_id", "status"],
        "change_activity_events": ["change_id", "created_at"],
        "change_policies": ["scope_type", "service_code", "offering_code", "change_type", "risk_level"],
    }.items():
        _create_index(f"ix_{table}_{'_'.join(cols[:2])}", table, cols)


def downgrade() -> None:
    if _has_table("continuous_improvement_actions") and _has_column("continuous_improvement_actions", "change_id"):
        op.drop_column("continuous_improvement_actions", "change_id")
    for table in (
        "change_policies",
        "change_activity_events",
        "change_pir_records",
        "change_tasks",
        "change_affected_objects",
        "change_windows",
        "change_approvals",
        "change_plans",
        "change_risk_assessments",
        "changes",
    ):
        if _has_table(table):
            op.drop_table(table)
