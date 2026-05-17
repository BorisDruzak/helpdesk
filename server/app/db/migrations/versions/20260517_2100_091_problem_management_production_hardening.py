"""problem management production hardening

Revision ID: 091
Revises: 090
Create Date: 2026-05-17 21:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "091"
down_revision: Union[str, None] = "090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    return index_name in {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_index(name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if not _has_index(table_name, name):
        op.create_index(name, table_name, columns, unique=unique)


def upgrade() -> None:
    _add_column("problems", sa.Column("investigation_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("known_error_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("workaround_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("rca_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("resolution_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("closure_due_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problems", sa.Column("breached_milestones", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    _create_index(
        "ix_problems_slo_due",
        "problems",
        ["investigation_due_at", "known_error_due_at", "workaround_due_at", "rca_due_at", "resolution_due_at", "closure_due_at"],
    )

    _add_column("problem_detection_rules", sa.Column("min_failed_qa_count", sa.Integer(), nullable=False, server_default="2"))
    _add_column("problem_detection_rules", sa.Column("min_knowledge_gap_count", sa.Integer(), nullable=False, server_default="1"))
    _add_column("problem_detection_rules", sa.Column("signal_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    _add_column("problem_detection_rules", sa.Column("breach_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))

    _add_column("problem_candidates", sa.Column("fingerprint_version", sa.Integer(), nullable=False, server_default="1"))
    _add_column("problem_candidates", sa.Column("evidence_hash", sa.String(length=64), nullable=True))
    _add_column("problem_candidates", sa.Column("first_seen_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problem_candidates", sa.Column("last_seen_at", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problem_candidates", sa.Column("dismissed_until", TIMESTAMP(timezone=True), nullable=True))
    _add_column("problem_candidates", sa.Column("merged_into_candidate_id", sa.String(length=36), nullable=True))
    _add_column("problem_candidates", sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"))
    if not _has_index("problem_candidates", "ix_problem_candidates_seen"):
        op.create_index("ix_problem_candidates_seen", "problem_candidates", ["first_seen_at", "last_seen_at"])
    if _has_column("problem_candidates", "merged_into_candidate_id"):
        try:
            op.create_foreign_key(
                "fk_problem_candidates_merged_into",
                "problem_candidates",
                "problem_candidates",
                ["merged_into_candidate_id"],
                ["candidate_id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass

    if not _has_table("problem_scanner_runs"):
        op.create_table(
            "problem_scanner_runs",
            sa.Column("run_id", sa.String(length=36), nullable=False),
            sa.Column("started_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("finished_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
            sa.Column("triggered_by", sa.String(length=30), nullable=False, server_default="manual"),
            sa.Column("lookback_hours", sa.Integer(), nullable=False, server_default="168"),
            sa.Column("rules_run", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("candidates_created", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("candidates_updated", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("candidates_skipped", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("errors_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("status IN ('running', 'completed', 'failed', 'canceled', 'skipped_overlap')", name="ck_problem_scanner_runs_status"),
            sa.CheckConstraint("triggered_by IN ('scheduler', 'manual', 'api')", name="ck_problem_scanner_runs_triggered_by"),
            sa.PrimaryKeyConstraint("run_id"),
        )
        _create_index("ix_problem_scanner_runs_started", "problem_scanner_runs", ["started_at"])
        _create_index("ix_problem_scanner_runs_status_started", "problem_scanner_runs", ["status", "started_at"])

    if not _has_table("problem_slo_policies"):
        op.create_table(
            "problem_slo_policies",
            sa.Column("policy_id", sa.String(length=36), nullable=False),
            sa.Column("scope_type", sa.String(length=30), nullable=False, server_default="global"),
            sa.Column("severity", sa.String(length=20), nullable=True),
            sa.Column("service_code", sa.String(length=100), nullable=True),
            sa.Column("offering_code", sa.String(length=220), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("investigation_due_hours", sa.Integer(), nullable=False, server_default="24"),
            sa.Column("known_error_due_hours", sa.Integer(), nullable=False, server_default="72"),
            sa.Column("workaround_due_hours", sa.Integer(), nullable=False, server_default="96"),
            sa.Column("rca_due_hours", sa.Integer(), nullable=False, server_default="120"),
            sa.Column("resolution_due_hours", sa.Integer(), nullable=False, server_default="336"),
            sa.Column("closure_due_hours", sa.Integer(), nullable=False, server_default="504"),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("scope_type IN ('global', 'severity', 'service', 'offering')", name="ck_problem_slo_policies_scope"),
            sa.CheckConstraint("severity IS NULL OR severity IN ('low', 'medium', 'high', 'critical')", name="ck_problem_slo_policies_severity"),
            sa.CheckConstraint("investigation_due_hours > 0 AND known_error_due_hours > 0 AND workaround_due_hours > 0 AND rca_due_hours > 0 AND resolution_due_hours > 0 AND closure_due_hours > 0", name="ck_problem_slo_policies_positive_hours"),
            sa.PrimaryKeyConstraint("policy_id"),
        )
        _create_index("ix_problem_slo_policies_scope", "problem_slo_policies", ["scope_type", "severity", "service_code", "offering_code"])


def downgrade() -> None:
    for table in ("problem_scanner_runs", "problem_slo_policies"):
        if _has_table(table):
            op.drop_table(table)
    if _has_index("problem_candidates", "ix_problem_candidates_seen"):
        op.drop_index("ix_problem_candidates_seen", table_name="problem_candidates")
    for column in (
        "duplicate_count",
        "merged_into_candidate_id",
        "dismissed_until",
        "last_seen_at",
        "first_seen_at",
        "evidence_hash",
        "fingerprint_version",
    ):
        if _has_column("problem_candidates", column):
            op.drop_column("problem_candidates", column)
    for column in ("breach_types", "signal_types", "min_knowledge_gap_count", "min_failed_qa_count"):
        if _has_column("problem_detection_rules", column):
            op.drop_column("problem_detection_rules", column)
    if _has_index("problems", "ix_problems_slo_due"):
        op.drop_index("ix_problems_slo_due", table_name="problems")
    for column in (
        "breached_milestones",
        "closure_due_at",
        "resolution_due_at",
        "rca_due_at",
        "workaround_due_at",
        "known_error_due_at",
        "investigation_due_at",
    ):
        if _has_column("problems", column):
            op.drop_column("problems", column)
