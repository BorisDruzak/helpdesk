"""diagnostic layer

Revision ID: 074
Revises: 073
Create Date: 2026-05-11 20:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.Text(), nullable=True),
        sa.Column("profile_version", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("trigger_source", sa.String(length=64), nullable=True),
        sa.Column("started_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_sessions_ticket_id", "diagnostic_sessions", ["ticket_id"])
    op.create_index("ix_diagnostic_sessions_profile_id", "diagnostic_sessions", ["profile_id"])
    op.create_index("ix_diagnostic_sessions_status", "diagnostic_sessions", ["status"])
    op.create_index("ix_diag_sessions_ticket_status", "diagnostic_sessions", ["ticket_id", "status"])
    op.create_index("ix_diag_sessions_started_at", "diagnostic_sessions", ["started_at"])

    op.create_table(
        "diagnostic_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("playbook_run_id", sa.BigInteger(), nullable=True),
        sa.Column("playbook_step_id", sa.BigInteger(), nullable=True),
        sa.Column("remote_assist_session_id", sa.String(length=36), nullable=True),
        sa.Column("observer_trace_id", sa.String(length=36), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["playbook_run_id"], ["playbook_run.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["remote_assist_session_id"], ["remote_access_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_steps_session_id", "diagnostic_steps", ["session_id"])
    op.create_index("ix_diagnostic_steps_ticket_id", "diagnostic_steps", ["ticket_id"])
    op.create_index("ix_diagnostic_steps_operation_id", "diagnostic_steps", ["operation_id"])
    op.create_index("ix_diagnostic_steps_playbook_run_id", "diagnostic_steps", ["playbook_run_id"])
    op.create_index("ix_diagnostic_steps_remote_assist_session_id", "diagnostic_steps", ["remote_assist_session_id"])
    op.create_index("ix_diagnostic_steps_observer_trace_id", "diagnostic_steps", ["observer_trace_id"])
    op.create_index("ix_diag_steps_ticket_type", "diagnostic_steps", ["ticket_id", "step_type"])
    op.create_index("ix_diag_steps_session_status", "diagnostic_steps", ["session_id", "status"])

    op.create_table(
        "diagnostic_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("perspective", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("observed_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("normalized_payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("raw_ref", sa.Text(), nullable=True),
        sa.Column("artifact_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.Column("redaction_level", sa.String(length=32), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("passport_eligible", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("selected_for_passport", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.String(length=32), server_default="system", nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["step_id"], ["diagnostic_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_evidence_ticket_id", "diagnostic_evidence", ["ticket_id"])
    op.create_index("ix_diagnostic_evidence_session_id", "diagnostic_evidence", ["session_id"])
    op.create_index("ix_diagnostic_evidence_source_type", "diagnostic_evidence", ["source_type"])
    op.create_index("ix_diagnostic_evidence_kind", "diagnostic_evidence", ["kind"])
    op.create_index("ix_diagnostic_evidence_domain", "diagnostic_evidence", ["domain"])
    op.create_index("ix_diagnostic_evidence_perspective", "diagnostic_evidence", ["perspective"])
    op.create_index("ix_diagnostic_evidence_status", "diagnostic_evidence", ["status"])
    op.create_index("ix_diagnostic_evidence_severity", "diagnostic_evidence", ["severity"])
    op.create_index("ix_diagnostic_evidence_observed_at", "diagnostic_evidence", ["observed_at"])
    op.create_index("ix_diagnostic_evidence_selected_for_passport", "diagnostic_evidence", ["selected_for_passport"])
    op.create_index("ix_diag_ev_ticket_observed", "diagnostic_evidence", ["ticket_id", "observed_at"])
    op.create_index("ix_diag_ev_source_identity", "diagnostic_evidence", ["ticket_id", "source_type", "source_id", "kind"], unique=True)
    op.create_index("ix_diag_ev_ticket_status", "diagnostic_evidence", ["ticket_id", "status"])

    op.create_table(
        "diagnostic_findings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("root_cause_code", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="suspected", nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("recommended_actions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_by", sa.String(length=32), server_default="system", nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_findings_ticket_id", "diagnostic_findings", ["ticket_id"])
    op.create_index("ix_diagnostic_findings_session_id", "diagnostic_findings", ["session_id"])
    op.create_index("ix_diagnostic_findings_root_cause_code", "diagnostic_findings", ["root_cause_code"])
    op.create_index("ix_diagnostic_findings_status", "diagnostic_findings", ["status"])
    op.create_index("ix_diag_find_ticket_code", "diagnostic_findings", ["ticket_id", "root_cause_code"])
    op.create_index("ix_diag_find_ticket_status", "diagnostic_findings", ["ticket_id", "status"])

    op.create_table(
        "diagnostic_bundles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="building", nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("evidence_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("artifact_refs", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("observer_trace_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("remote_assist_session_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_bundles_ticket_id", "diagnostic_bundles", ["ticket_id"])
    op.create_index("ix_diagnostic_bundles_session_id", "diagnostic_bundles", ["session_id"])
    op.create_index("ix_diagnostic_bundles_status", "diagnostic_bundles", ["status"])
    op.create_index("ix_diag_bundles_ticket_created", "diagnostic_bundles", ["ticket_id", "created_at"])
    op.create_index("ix_diag_bundles_ticket_status", "diagnostic_bundles", ["ticket_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_diag_bundles_ticket_status", table_name="diagnostic_bundles")
    op.drop_index("ix_diag_bundles_ticket_created", table_name="diagnostic_bundles")
    op.drop_index("ix_diagnostic_bundles_status", table_name="diagnostic_bundles")
    op.drop_index("ix_diagnostic_bundles_session_id", table_name="diagnostic_bundles")
    op.drop_index("ix_diagnostic_bundles_ticket_id", table_name="diagnostic_bundles")
    op.drop_table("diagnostic_bundles")

    op.drop_index("ix_diag_find_ticket_status", table_name="diagnostic_findings")
    op.drop_index("ix_diag_find_ticket_code", table_name="diagnostic_findings")
    op.drop_index("ix_diagnostic_findings_status", table_name="diagnostic_findings")
    op.drop_index("ix_diagnostic_findings_root_cause_code", table_name="diagnostic_findings")
    op.drop_index("ix_diagnostic_findings_session_id", table_name="diagnostic_findings")
    op.drop_index("ix_diagnostic_findings_ticket_id", table_name="diagnostic_findings")
    op.drop_table("diagnostic_findings")

    op.drop_index("ix_diag_ev_ticket_status", table_name="diagnostic_evidence")
    op.drop_index("ix_diag_ev_source_identity", table_name="diagnostic_evidence")
    op.drop_index("ix_diag_ev_ticket_observed", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_selected_for_passport", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_observed_at", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_severity", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_status", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_perspective", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_domain", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_kind", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_source_type", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_session_id", table_name="diagnostic_evidence")
    op.drop_index("ix_diagnostic_evidence_ticket_id", table_name="diagnostic_evidence")
    op.drop_table("diagnostic_evidence")

    op.drop_index("ix_diag_steps_session_status", table_name="diagnostic_steps")
    op.drop_index("ix_diag_steps_ticket_type", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_observer_trace_id", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_remote_assist_session_id", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_playbook_run_id", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_operation_id", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_ticket_id", table_name="diagnostic_steps")
    op.drop_index("ix_diagnostic_steps_session_id", table_name="diagnostic_steps")
    op.drop_table("diagnostic_steps")

    op.drop_index("ix_diag_sessions_started_at", table_name="diagnostic_sessions")
    op.drop_index("ix_diag_sessions_ticket_status", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_status", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_profile_id", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_ticket_id", table_name="diagnostic_sessions")
    op.drop_table("diagnostic_sessions")
