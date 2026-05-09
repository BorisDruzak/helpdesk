"""remote assist lifecycle

Revision ID: 071
Revises: 070
Create Date: 2026-05-09 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "remote_access_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("operator_id", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Text(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("consent_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("consent_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("requested_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("approved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("denied_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("max_duration_sec", sa.Integer(), server_default=sa.text("900"), nullable=False),
        sa.Column("signaling_token_hash", sa.Text(), nullable=True),
        sa.Column("operator_token_hash", sa.Text(), nullable=True),
        sa.Column("agent_token_hash", sa.Text(), nullable=True),
        sa.Column("ice_config", postgresql.JSONB(), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("recording_ref", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_access_sessions_ticket_id", "remote_access_sessions", ["ticket_id"])
    op.create_index("ix_remote_access_sessions_device_id", "remote_access_sessions", ["device_id"])
    op.create_index("ix_remote_access_sessions_operator_id", "remote_access_sessions", ["operator_id"])
    op.create_index("ix_remote_access_sessions_status", "remote_access_sessions", ["status"])
    op.create_index("ix_remote_access_sessions_expires_at", "remote_access_sessions", ["expires_at"])
    op.create_index("ix_remote_access_sessions_ticket_created", "remote_access_sessions", ["ticket_id", "created_at"])

    op.create_table(
        "remote_access_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remote_access_events_session_id", "remote_access_events", ["session_id"])
    op.create_index("ix_remote_access_events_ticket_id", "remote_access_events", ["ticket_id"])
    op.create_index("ix_remote_access_events_event_type", "remote_access_events", ["event_type"])
    op.create_index("ix_remote_access_events_created_at", "remote_access_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_remote_access_events_created_at", table_name="remote_access_events")
    op.drop_index("ix_remote_access_events_event_type", table_name="remote_access_events")
    op.drop_index("ix_remote_access_events_ticket_id", table_name="remote_access_events")
    op.drop_index("ix_remote_access_events_session_id", table_name="remote_access_events")
    op.drop_table("remote_access_events")

    op.drop_index("ix_remote_access_sessions_ticket_created", table_name="remote_access_sessions")
    op.drop_index("ix_remote_access_sessions_expires_at", table_name="remote_access_sessions")
    op.drop_index("ix_remote_access_sessions_status", table_name="remote_access_sessions")
    op.drop_index("ix_remote_access_sessions_operator_id", table_name="remote_access_sessions")
    op.drop_index("ix_remote_access_sessions_device_id", table_name="remote_access_sessions")
    op.drop_index("ix_remote_access_sessions_ticket_id", table_name="remote_access_sessions")
    op.drop_table("remote_access_sessions")
