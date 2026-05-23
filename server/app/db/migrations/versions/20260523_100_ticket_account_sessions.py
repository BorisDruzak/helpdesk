"""ticket account session boundary

Revision ID: 100
Revises: 099
Create Date: 2026-05-23 18:10:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "100"
down_revision: Union[str, None] = "099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if _has_table("tickets"):
        for column_name, column_type in (
            ("requester_account_session_id", sa.String(36)),
            ("requester_account_mode", sa.String(40)),
            ("requester_account_warning", sa.String(80)),
        ):
            if not _has_column("tickets", column_name):
                op.add_column("tickets", sa.Column(column_name, column_type, nullable=True))

        for index_name, columns in (
            ("ix_tickets_requester_account_session_id", ["requester_account_session_id"]),
            ("ix_tickets_device_account_session", ["device_id", "requester_account_session_id"]),
            ("ix_tickets_requester_account_mode", ["requester_account_mode"]),
            ("ix_tickets_requester_account_warning", ["requester_account_warning"]),
        ):
            if not _has_index("tickets", index_name):
                op.create_index(index_name, "tickets", columns)

    if not _has_table("device_account_events"):
        op.create_table(
            "device_account_events",
            sa.Column("event_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("session_id", sa.String(36), nullable=True),
            sa.Column("request_id", sa.String(36), nullable=True),
            sa.Column("ticket_id", sa.String(36), nullable=True),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("event_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["device_account_sessions.session_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["request_id"], ["device_account_login_requests.request_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("event_id"),
        )

    for index_name, columns in (
        ("ix_device_account_events_device_event_at", ["device_id", "event_at"]),
        ("ix_device_account_events_session_event_at", ["session_id", "event_at"]),
        ("ix_device_account_events_request_event_at", ["request_id", "event_at"]),
        ("ix_device_account_events_ticket_event_at", ["ticket_id", "event_at"]),
        ("ix_device_account_events_type_event_at", ["event_type", "event_at"]),
    ):
        if not _has_index("device_account_events", index_name):
            op.create_index(index_name, "device_account_events", columns)


def downgrade() -> None:
    if _has_table("device_account_events"):
        for index_name in (
            "ix_device_account_events_type_event_at",
            "ix_device_account_events_ticket_event_at",
            "ix_device_account_events_request_event_at",
            "ix_device_account_events_session_event_at",
            "ix_device_account_events_device_event_at",
        ):
            if _has_index("device_account_events", index_name):
                op.drop_index(index_name, table_name="device_account_events")
        op.drop_table("device_account_events")

    if _has_table("tickets"):
        for index_name in (
            "ix_tickets_requester_account_warning",
            "ix_tickets_requester_account_mode",
            "ix_tickets_device_account_session",
            "ix_tickets_requester_account_session_id",
        ):
            if _has_index("tickets", index_name):
                op.drop_index(index_name, table_name="tickets")
        for column_name in (
            "requester_account_warning",
            "requester_account_mode",
            "requester_account_session_id",
        ):
            if _has_column("tickets", column_name):
                op.drop_column("tickets", column_name)
