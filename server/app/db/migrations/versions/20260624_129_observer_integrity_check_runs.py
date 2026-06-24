"""Add Observer integrity per-check run reports.

Revision ID: 129
Revises: 128
Create Date: 2026-06-24 18:20:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "129"
down_revision: Union[str, None] = "128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return any(str(index.get("name") or "") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("observer_integrity_check_runs"):
        op.create_table(
            "observer_integrity_check_runs",
            sa.Column("check_run_id", sa.String(length=36), nullable=False),
            sa.Column("scan_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=120), nullable=True),
            sa.Column("source", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("complete", sa.Boolean(), nullable=False),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("duration_ms", sa.BigInteger(), nullable=False),
            sa.Column("generated_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("resolved_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("scanned_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("limit_value", sa.Integer(), nullable=True),
            sa.Column(
                "window_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("error_type", sa.String(length=120), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "status IN ('passed', 'degraded', 'failed', 'timed_out')",
                name="ck_observer_integrity_check_runs_status",
            ),
            sa.PrimaryKeyConstraint("check_run_id"),
        )
    for name, columns in (
        ("ix_observer_integrity_check_runs_scan_id", ["scan_id"]),
        ("ix_observer_integrity_check_runs_run_id", ["run_id"]),
        ("ix_observer_integrity_check_runs_source", ["source"]),
        ("ix_observer_integrity_check_runs_status", ["status"]),
        ("ix_observer_integrity_check_runs_scan_source", ["scan_id", "source"]),
        ("ix_observer_integrity_check_runs_status_started", ["status", "started_at"]),
    ):
        if not _has_index("observer_integrity_check_runs", name):
            op.create_index(name, "observer_integrity_check_runs", columns)


def downgrade() -> None:
    if _has_table("observer_integrity_check_runs"):
        for name in (
            "ix_observer_integrity_check_runs_status_started",
            "ix_observer_integrity_check_runs_scan_source",
            "ix_observer_integrity_check_runs_status",
            "ix_observer_integrity_check_runs_source",
            "ix_observer_integrity_check_runs_run_id",
            "ix_observer_integrity_check_runs_scan_id",
        ):
            if _has_index("observer_integrity_check_runs", name):
                op.drop_index(name, table_name="observer_integrity_check_runs")
        op.drop_table("observer_integrity_check_runs")
