"""Playbook Engine: playbook, playbook_version, playbook_step, playbook_run, playbook_step_run

Revision ID: 033
Revises: 032
Create Date: 2026-02-20 10:00:00.000000

Таблицы для Playbook Engine (см. docs/PLAYBOOK_ENGINE_DESIGN.md).
Исполнение шагов через operations + device_outbox.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "playbook",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_playbook_key", "playbook", ["key"], unique=True)
    op.create_index("ix_playbook_domain", "playbook", ["domain"])

    op.create_table(
        "playbook_version",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("playbook_id", sa.BigInteger(), sa.ForeignKey("playbook.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_playbook_version_playbook_id", "playbook_version", ["playbook_id"])
    op.create_index("ix_playbook_version_playbook_version", "playbook_version", ["playbook_id", "version"], unique=True)

    op.create_table(
        "playbook_step",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("playbook_version_id", sa.BigInteger(), sa.ForeignKey("playbook_version.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(length=64), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="run_tool"),
        sa.Column("tool", sa.Text(), nullable=True),
        sa.Column("params_template_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("if_expr", sa.Text(), nullable=True),
        sa.Column("timeout_sec", sa.Integer(), nullable=True),
        sa.Column("retry_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("continue_on_error", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parallel_group", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_playbook_step_playbook_version_id", "playbook_step", ["playbook_version_id"])
    op.create_index("ix_playbook_step_order", "playbook_step", ["playbook_version_id", "order_no"])

    op.create_table(
        "playbook_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("playbook_version_id", sa.BigInteger(), sa.ForeignKey("playbook_version.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("scheduled_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=True),
        sa.Column("context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_playbook_run_playbook_version_id", "playbook_run", ["playbook_version_id"])
    op.create_index("ix_playbook_run_device_id", "playbook_run", ["device_id"])
    op.create_index("ix_playbook_run_status", "playbook_run", ["status"])
    op.create_index("ix_playbook_run_scheduled_at", "playbook_run", ["scheduled_at"])

    op.create_table(
        "playbook_step_run",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("playbook_run_id", sa.BigInteger(), sa.ForeignKey("playbook_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("playbook_step_id", sa.BigInteger(), sa.ForeignKey("playbook_step.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("input_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
    )
    op.create_index("ix_playbook_step_run_playbook_run_id", "playbook_step_run", ["playbook_run_id"])
    op.create_index("ix_playbook_step_run_operation_id", "playbook_step_run", ["operation_id"])


def downgrade() -> None:
    op.drop_index("ix_playbook_step_run_operation_id", table_name="playbook_step_run")
    op.drop_index("ix_playbook_step_run_playbook_run_id", table_name="playbook_step_run")
    op.drop_table("playbook_step_run")
    op.drop_index("ix_playbook_run_scheduled_at", table_name="playbook_run")
    op.drop_index("ix_playbook_run_status", table_name="playbook_run")
    op.drop_index("ix_playbook_run_device_id", table_name="playbook_run")
    op.drop_index("ix_playbook_run_playbook_version_id", table_name="playbook_run")
    op.drop_table("playbook_run")
    op.drop_index("ix_playbook_step_order", table_name="playbook_step")
    op.drop_index("ix_playbook_step_playbook_version_id", table_name="playbook_step")
    op.drop_table("playbook_step")
    op.drop_index("ix_playbook_version_playbook_version", table_name="playbook_version")
    op.drop_index("ix_playbook_version_playbook_id", table_name="playbook_version")
    op.drop_table("playbook_version")
    op.drop_index("ix_playbook_domain", table_name="playbook")
    op.drop_index("ix_playbook_key", table_name="playbook")
    op.drop_table("playbook")
