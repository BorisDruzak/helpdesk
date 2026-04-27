"""agent observer event source rows

Revision ID: 060
Revises: 059
Create Date: 2026-04-27 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "060"
down_revision: Union[str, None] = "059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_observer_events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("install_id", sa.String(length=128), nullable=True),
        sa.Column("machine_id", sa.String(length=128), nullable=True),
        sa.Column("agent_seq", sa.BigInteger(), nullable=True),
        sa.Column("trace_id", sa.String(length=36), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("playbook_run_id", sa.BigInteger(), nullable=True),
        sa.Column("playbook_step_run_id", sa.BigInteger(), nullable=True),
        sa.Column("root_kind", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("component", sa.String(length=64), nullable=False, server_default="agent"),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("module_name", sa.String(length=128), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("attrs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("received_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_agent_observer_events_event_id"),
    )
    op.create_index("ix_agent_observer_events_device_created", "agent_observer_events", ["device_id", "created_at"])
    op.create_index("ix_agent_observer_events_trace_id", "agent_observer_events", ["trace_id"])
    op.create_index("ix_agent_observer_events_operation_id", "agent_observer_events", ["operation_id"])
    op.create_index("ix_agent_observer_events_event_created", "agent_observer_events", ["event_type", "created_at"])
    op.create_index("ix_agent_observer_events_severity_created", "agent_observer_events", ["severity", "created_at"])
    op.create_index("ix_agent_observer_events_root_created", "agent_observer_events", ["root_kind", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_observer_events_root_created", table_name="agent_observer_events")
    op.drop_index("ix_agent_observer_events_severity_created", table_name="agent_observer_events")
    op.drop_index("ix_agent_observer_events_event_created", table_name="agent_observer_events")
    op.drop_index("ix_agent_observer_events_operation_id", table_name="agent_observer_events")
    op.drop_index("ix_agent_observer_events_trace_id", table_name="agent_observer_events")
    op.drop_index("ix_agent_observer_events_device_created", table_name="agent_observer_events")
    op.drop_table("agent_observer_events")
