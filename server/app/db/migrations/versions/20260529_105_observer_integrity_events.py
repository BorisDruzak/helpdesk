"""observer integrity events

Revision ID: 105
Revises: 104
Create Date: 2026-05-29 10:50:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "105"
down_revision: Union[str, None] = "104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("observer_integrity_events"):
        op.create_table(
            "observer_integrity_events",
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("detected_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("first_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("dedupe_key", sa.String(length=300), nullable=False),
            sa.Column("occurrence_count", sa.Integer(), nullable=False),
            sa.Column("device_id", sa.String(length=36), nullable=True),
            sa.Column("ticket_id", sa.String(length=36), nullable=True),
            sa.Column("operation_id", sa.String(length=36), nullable=True),
            sa.Column("command_id", sa.String(length=36), nullable=True),
            sa.Column("device_outbox_id", sa.BigInteger(), nullable=True),
            sa.Column("outbox_id", sa.String(length=120), nullable=True),
            sa.Column("trace_id", sa.String(length=36), nullable=True),
            sa.Column("actor_role", sa.String(length=30), nullable=True),
            sa.Column("expected", sa.Text(), nullable=False),
            sa.Column("actual", sa.Text(), nullable=False),
            sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("runbook", sa.Text(), nullable=True),
            sa.Column("suppression_reason", sa.Text(), nullable=True),
            sa.Column("run_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("event_id"),
            sa.UniqueConstraint("dedupe_key", name="uq_observer_integrity_events_dedupe_key"),
        )
    for name, columns in (
        ("ix_observer_integrity_events_event_type", ["event_type"]),
        ("ix_observer_integrity_events_severity", ["severity"]),
        ("ix_observer_integrity_events_source", ["source"]),
        ("ix_observer_integrity_events_status", ["status"]),
        ("ix_observer_integrity_events_detected_at", ["detected_at"]),
        ("ix_observer_integrity_events_last_seen_at", ["last_seen_at"]),
        ("ix_observer_integrity_events_device_id", ["device_id"]),
        ("ix_observer_integrity_events_ticket_id", ["ticket_id"]),
        ("ix_observer_integrity_events_operation_id", ["operation_id"]),
        ("ix_observer_integrity_events_command_id", ["command_id"]),
        ("ix_observer_integrity_events_device_outbox_id", ["device_outbox_id"]),
        ("ix_observer_integrity_events_trace_id", ["trace_id"]),
        ("ix_observer_integrity_events_run_id", ["run_id"]),
        ("ix_observer_integrity_status_severity", ["status", "severity", "last_seen_at"]),
        ("ix_observer_integrity_device_status", ["device_id", "status", "severity"]),
        ("ix_observer_integrity_operation", ["operation_id", "status"]),
        ("ix_observer_integrity_ticket", ["ticket_id", "status"]),
    ):
        if not _has_index("observer_integrity_events", name):
            op.create_index(name, "observer_integrity_events", columns)

    if not _has_table("observer_known_contamination"):
        op.create_table(
            "observer_known_contamination",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("source_phase", sa.String(length=30), nullable=False),
            sa.Column("entity_type", sa.String(length=80), nullable=False),
            sa.Column("entity_id", sa.String(length=160), nullable=False),
            sa.Column("suppression_scope", sa.String(length=160), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "source_phase",
                "entity_type",
                "entity_id",
                "suppression_scope",
                name="uq_observer_known_contamination_entity",
            ),
        )
    for name, columns in (
        ("ix_observer_known_contamination_entity", ["entity_type", "entity_id"]),
        ("ix_observer_known_contamination_active", ["active", "expires_at"]),
    ):
        if not _has_index("observer_known_contamination", name):
            op.create_index(name, "observer_known_contamination", columns)


def downgrade() -> None:
    for table, indexes in (
        (
            "observer_known_contamination",
            (
                "ix_observer_known_contamination_active",
                "ix_observer_known_contamination_entity",
            ),
        ),
        (
            "observer_integrity_events",
            (
                "ix_observer_integrity_ticket",
                "ix_observer_integrity_operation",
                "ix_observer_integrity_device_status",
                "ix_observer_integrity_status_severity",
                "ix_observer_integrity_events_run_id",
                "ix_observer_integrity_events_trace_id",
                "ix_observer_integrity_events_device_outbox_id",
                "ix_observer_integrity_events_command_id",
                "ix_observer_integrity_events_operation_id",
                "ix_observer_integrity_events_ticket_id",
                "ix_observer_integrity_events_device_id",
                "ix_observer_integrity_events_last_seen_at",
                "ix_observer_integrity_events_detected_at",
                "ix_observer_integrity_events_status",
                "ix_observer_integrity_events_source",
                "ix_observer_integrity_events_severity",
                "ix_observer_integrity_events_event_type",
            ),
        ),
    ):
        if _has_table(table):
            for name in indexes:
                if _has_index(table, name):
                    op.drop_index(name, table_name=table)
            op.drop_table(table)
