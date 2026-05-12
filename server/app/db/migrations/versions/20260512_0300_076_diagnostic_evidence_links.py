"""diagnostic evidence links

Revision ID: 076
Revises: 075
Create Date: 2026-05-12 03:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "076"
down_revision = "075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_session_capabilities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("provider_type", sa.String(length=64), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=False),
        sa.Column("capability_version", sa.String(length=64), nullable=True),
        sa.Column("execution_target", sa.String(length=64), nullable=False),
        sa.Column("readiness_status", sa.String(length=64), nullable=True),
        sa.Column("readiness_reason_code", sa.String(length=120), nullable=True),
        sa.Column("readiness_reason", sa.Text(), nullable=True),
        sa.Column("readiness_actions", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("params_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("result_snapshot", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence_id", sa.String(length=36), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("session_ref", sa.Text(), nullable=True),
        sa.Column("query_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="planned", nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["diagnostic_evidence.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diag_session_caps_session", "diagnostic_session_capabilities", ["session_id"])
    op.create_index("ix_diag_session_caps_ticket", "diagnostic_session_capabilities", ["ticket_id"])
    op.create_index("ix_diag_session_caps_capability", "diagnostic_session_capabilities", ["capability_id"])
    op.create_index("ix_diag_session_caps_evidence", "diagnostic_session_capabilities", ["evidence_id"])
    op.create_index("ix_diag_session_caps_operation", "diagnostic_session_capabilities", ["operation_id"])
    op.create_index("ix_diag_session_caps_session_capability", "diagnostic_session_capabilities", ["session_id", "capability_id"])

    op.create_table(
        "diagnostic_artifact_links",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("evidence_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_kind", sa.String(length=120), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("capability_id", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["step_id"], ["diagnostic_steps.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["evidence_id"], ["diagnostic_evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.artifact_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", "evidence_id", "artifact_id", "artifact_kind", name="uq_diag_artifact_link_identity"),
    )
    op.create_index("ix_diag_artifact_links_ticket", "diagnostic_artifact_links", ["ticket_id"])
    op.create_index("ix_diag_artifact_links_session", "diagnostic_artifact_links", ["session_id"])
    op.create_index("ix_diag_artifact_links_step", "diagnostic_artifact_links", ["step_id"])
    op.create_index("ix_diag_artifact_links_evidence", "diagnostic_artifact_links", ["evidence_id"])
    op.create_index("ix_diag_artifact_links_artifact", "diagnostic_artifact_links", ["artifact_id"])
    op.create_index("ix_diag_artifact_links_source", "diagnostic_artifact_links", ["source_type", "source_id"])
    op.create_index("ix_diag_artifact_links_capability", "diagnostic_artifact_links", ["capability_id"])


def downgrade() -> None:
    op.drop_index("ix_diag_artifact_links_capability", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_source", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_artifact", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_evidence", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_step", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_session", table_name="diagnostic_artifact_links")
    op.drop_index("ix_diag_artifact_links_ticket", table_name="diagnostic_artifact_links")
    op.drop_table("diagnostic_artifact_links")

    op.drop_index("ix_diag_session_caps_session_capability", table_name="diagnostic_session_capabilities")
    op.drop_index("ix_diag_session_caps_operation", table_name="diagnostic_session_capabilities")
    op.drop_index("ix_diag_session_caps_evidence", table_name="diagnostic_session_capabilities")
    op.drop_index("ix_diag_session_caps_capability", table_name="diagnostic_session_capabilities")
    op.drop_index("ix_diag_session_caps_ticket", table_name="diagnostic_session_capabilities")
    op.drop_index("ix_diag_session_caps_session", table_name="diagnostic_session_capabilities")
    op.drop_table("diagnostic_session_capabilities")
