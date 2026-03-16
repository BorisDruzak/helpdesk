"""Stage 11: SLA Calendar + OLA — ticket_business_calendars, ticket_queue_ola_targets, OLA fields on tickets

Revision ID: 029
Revises: 028
Create Date: 2026-02-17 18:00:00.000000

- ticket_business_calendars: id, code, name, timezone, weekly_hours_json, holidays_json, is_active, created_at, updated_at
- ticket_sla_policies: calendar_id FK (nullable)
- ticket_queue_ola_targets: queue_id, priority, ack_min, processing_min (PK queue_id+priority)
- tickets: OLA fields + indices
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ticket_business_calendars
    op.create_table(
        "ticket_business_calendars",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("weekly_hours_json", JSONB, nullable=True),
        sa.Column("holidays_json", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ticket_sla_policies: calendar_id
    op.add_column(
        "ticket_sla_policies",
        sa.Column("calendar_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ticket_sla_policies_calendar_id",
        "ticket_sla_policies",
        "ticket_business_calendars",
        ["calendar_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ticket_queue_ola_targets
    op.create_table(
        "ticket_queue_ola_targets",
        sa.Column("queue_id", sa.BigInteger(), sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("priority", sa.String(5), primary_key=True),
        sa.Column("ack_min", sa.Integer(), nullable=False),
        sa.Column("processing_min", sa.Integer(), nullable=False),
    )

    # tickets: OLA columns
    op.add_column("tickets", sa.Column("ola_queue_id", sa.BigInteger(), nullable=True))
    op.add_column("tickets", sa.Column("ola_started_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_ack_due_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_ack_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_ack_breached_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_processing_due_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_processing_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_processing_breached_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_paused_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("ola_paused_seconds", sa.Integer(), nullable=True))

    op.create_index("ix_tickets_ola_queue_id", "tickets", ["ola_queue_id"])
    op.create_index("ix_tickets_ola_ack_due_at", "tickets", ["ola_ack_due_at"])
    op.create_index("ix_tickets_ola_ack_breached_at", "tickets", ["ola_ack_breached_at"])
    op.create_index("ix_tickets_ola_processing_due_at", "tickets", ["ola_processing_due_at"])
    op.create_index("ix_tickets_ola_processing_breached_at", "tickets", ["ola_processing_breached_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_ola_processing_breached_at", table_name="tickets")
    op.drop_index("ix_tickets_ola_processing_due_at", table_name="tickets")
    op.drop_index("ix_tickets_ola_ack_breached_at", table_name="tickets")
    op.drop_index("ix_tickets_ola_ack_due_at", table_name="tickets")
    op.drop_index("ix_tickets_ola_queue_id", table_name="tickets")
    op.drop_column("tickets", "ola_paused_seconds")
    op.drop_column("tickets", "ola_paused_at")
    op.drop_column("tickets", "ola_processing_breached_at")
    op.drop_column("tickets", "ola_processing_at")
    op.drop_column("tickets", "ola_processing_due_at")
    op.drop_column("tickets", "ola_ack_breached_at")
    op.drop_column("tickets", "ola_ack_at")
    op.drop_column("tickets", "ola_ack_due_at")
    op.drop_column("tickets", "ola_started_at")
    op.drop_column("tickets", "ola_queue_id")
    op.drop_table("ticket_queue_ola_targets")
    op.drop_constraint("fk_ticket_sla_policies_calendar_id", "ticket_sla_policies", type_="foreignkey")
    op.drop_column("ticket_sla_policies", "calendar_id")
    op.drop_table("ticket_business_calendars")
