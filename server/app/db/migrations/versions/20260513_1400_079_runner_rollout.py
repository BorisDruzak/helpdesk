"""runner rollout plans

Revision ID: 079
Revises: 078
Create Date: 2026-05-13 14:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "079"
down_revision = "078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runner_rollout_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("module_name", sa.String(length=100), nullable=False),
        sa.Column("target_version", sa.String(length=50), nullable=False),
        sa.Column("rollback_version", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("canary_size", sa.Integer(), nullable=False),
        sa.Column("wave_size", sa.Integer(), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paused_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rolled_back_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runner_rollout_plans_module_status", "runner_rollout_plans", ["module_name", "status"])
    op.create_index("ix_runner_rollout_plans_target_status", "runner_rollout_plans", ["target_version", "status"])

    op.create_table(
        "runner_rollout_waves",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("wave_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["runner_rollout_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "wave_index", name="uq_runner_rollout_waves_plan_index"),
    )
    op.create_index("ix_runner_rollout_waves_plan_status", "runner_rollout_waves", ["plan_id", "status"])

    op.create_table(
        "runner_rollout_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("wave_id", sa.String(length=36), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("module_name", sa.String(length=100), nullable=False),
        sa.Column("target_version", sa.String(length=50), nullable=False),
        sa.Column("rollback_version", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version", sa.String(length=50), nullable=True),
        sa.Column("operation_id", sa.Text(), nullable=True),
        sa.Column("desired_set_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("failed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rolled_back_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.Text(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["runner_rollout_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wave_id"], ["runner_rollout_waves.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "device_id", name="uq_runner_rollout_targets_plan_device"),
    )
    op.create_index("ix_runner_rollout_targets_device", "runner_rollout_targets", ["device_id"])
    op.create_index("ix_runner_rollout_targets_plan_status", "runner_rollout_targets", ["plan_id", "status"])
    op.create_index("ix_runner_rollout_targets_wave_status", "runner_rollout_targets", ["wave_id", "status"])

    op.create_table(
        "runner_rollout_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("wave_id", sa.String(length=36), nullable=True),
        sa.Column("target_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["runner_rollout_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id"], ["runner_rollout_targets.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["wave_id"], ["runner_rollout_waves.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_runner_rollout_events_plan", "runner_rollout_events", ["plan_id", "created_at"])
    op.create_index("ix_runner_rollout_events_type", "runner_rollout_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_runner_rollout_events_type", table_name="runner_rollout_events")
    op.drop_index("ix_runner_rollout_events_plan", table_name="runner_rollout_events")
    op.drop_table("runner_rollout_events")
    op.drop_index("ix_runner_rollout_targets_wave_status", table_name="runner_rollout_targets")
    op.drop_index("ix_runner_rollout_targets_plan_status", table_name="runner_rollout_targets")
    op.drop_index("ix_runner_rollout_targets_device", table_name="runner_rollout_targets")
    op.drop_table("runner_rollout_targets")
    op.drop_index("ix_runner_rollout_waves_plan_status", table_name="runner_rollout_waves")
    op.drop_table("runner_rollout_waves")
    op.drop_index("ix_runner_rollout_plans_target_status", table_name="runner_rollout_plans")
    op.drop_index("ix_runner_rollout_plans_module_status", table_name="runner_rollout_plans")
    op.drop_table("runner_rollout_plans")
