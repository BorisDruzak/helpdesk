"""Stage 12: Ticket archive and retention — archive tables + ticket_retention_runs

Revision ID: 030
Revises: 029
Create Date: 2026-02-17 20:00:00.000000

- ticket_events_archive: структура ticket_events + archived_at
- ticket_admin_audit_archive: структура ticket_admin_audit + archived_at
- ticket_retention_runs: started_at, finished_at, status, moved_events, moved_audit, error
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_events_archive",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("agent_seq", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.Text(), nullable=True),
        sa.Column("operation_id", sa.String(36), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("archived_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_events_archive_ticket_id", "ticket_events_archive", ["ticket_id"])
    op.create_index("ix_ticket_events_archive_created_at", "ticket_events_archive", ["created_at"])
    op.create_index("ix_ticket_events_archive_archived_at", "ticket_events_archive", ["archived_at"])

    op.create_table(
        "ticket_admin_audit_archive",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("before_json", JSONB, nullable=True),
        sa.Column("after_json", JSONB, nullable=True),
        sa.Column("trace_id", sa.String(36), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("archived_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_admin_audit_archive_created_at", "ticket_admin_audit_archive", ["created_at"])
    op.create_index("ix_ticket_admin_audit_archive_archived_at", "ticket_admin_audit_archive", ["archived_at"])

    op.create_table(
        "ticket_retention_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
        sa.Column("moved_events", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("moved_audit", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_ticket_retention_runs_started_at", "ticket_retention_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ticket_retention_runs_started_at", table_name="ticket_retention_runs")
    op.drop_table("ticket_retention_runs")
    op.drop_index("ix_ticket_admin_audit_archive_archived_at", table_name="ticket_admin_audit_archive")
    op.drop_index("ix_ticket_admin_audit_archive_created_at", table_name="ticket_admin_audit_archive")
    op.drop_table("ticket_admin_audit_archive")
    op.drop_index("ix_ticket_events_archive_archived_at", table_name="ticket_events_archive")
    op.drop_index("ix_ticket_events_archive_created_at", table_name="ticket_events_archive")
    op.drop_index("ix_ticket_events_archive_ticket_id", table_name="ticket_events_archive")
    op.drop_table("ticket_events_archive")
