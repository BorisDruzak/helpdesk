"""inventory v4 registration presence

Revision ID: 097
Revises: 096
Create Date: 2026-05-19 18:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "097"
down_revision: Union[str, None] = "096"
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
    if _has_table("device_inventory_refresh_runs") and not _has_column("device_inventory_refresh_runs", "bulk_operation_id"):
        op.add_column("device_inventory_refresh_runs", sa.Column("bulk_operation_id", sa.String(36), nullable=True))
    if _has_table("device_inventory_refresh_runs") and not _has_index("device_inventory_refresh_runs", "ix_device_inventory_refresh_runs_bulk_operation"):
        op.create_index("ix_device_inventory_refresh_runs_bulk_operation", "device_inventory_refresh_runs", ["bulk_operation_id"])

    if not _has_table("device_inventory_bulk_operations"):
        op.create_table(
            "device_inventory_bulk_operations",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("operation_type", sa.String(40), nullable=False, server_default="inventory_refresh"),
            sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
            sa.Column("requested_by", sa.Text(), nullable=True),
            sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("filters", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("wave", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("dispatched_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("device_inventory_bulk_operations", "ix_device_inventory_bulk_operations_requested"):
        op.create_index("ix_device_inventory_bulk_operations_requested", "device_inventory_bulk_operations", ["requested_at"])
    if not _has_index("device_inventory_bulk_operations", "ix_device_inventory_bulk_operations_status"):
        op.create_index("ix_device_inventory_bulk_operations_status", "device_inventory_bulk_operations", ["status"])

    if not _has_table("device_inventory_bulk_operation_items"):
        op.create_table(
            "device_inventory_bulk_operation_items",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("operation_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("wave_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("job_id", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("operation_id", "device_id", name="uq_device_inventory_bulk_item_operation_device"),
        )
    if not _has_index("device_inventory_bulk_operation_items", "ix_device_inventory_bulk_items_operation"):
        op.create_index("ix_device_inventory_bulk_items_operation", "device_inventory_bulk_operation_items", ["operation_id"])
    if not _has_index("device_inventory_bulk_operation_items", "ix_device_inventory_bulk_items_device"):
        op.create_index("ix_device_inventory_bulk_items_device", "device_inventory_bulk_operation_items", ["device_id"])

    if not _has_table("device_binding_suggestions"):
        op.create_table(
            "device_binding_suggestions",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("source", sa.String(40), nullable=False, server_default="agent_profile"),
            sa.Column("source_ref", sa.Text(), nullable=True),
            sa.Column("suggested_binding", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("profile_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("confidence", sa.String(16), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("device_binding_suggestions", "ix_device_binding_suggestions_device_status"):
        op.create_index("ix_device_binding_suggestions_device_status", "device_binding_suggestions", ["device_id", "status"])
    if not _has_index("device_binding_suggestions", "ix_device_binding_suggestions_source_ref"):
        op.create_index("ix_device_binding_suggestions_source_ref", "device_binding_suggestions", ["source", "source_ref"])

    if not _has_table("device_presence_snapshots"):
        op.create_table(
            "device_presence_snapshots",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("collected_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("received_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("session_state", sa.String(32), nullable=True),
            sa.Column("current_user", sa.Text(), nullable=True),
            sa.Column("idle_seconds", sa.Integer(), nullable=True),
            sa.Column("locked", sa.Boolean(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("device_presence_snapshots", "ix_device_presence_snapshots_device_collected"):
        op.create_index("ix_device_presence_snapshots_device_collected", "device_presence_snapshots", ["device_id", "collected_at"])
    if not _has_index("device_presence_snapshots", "ix_device_presence_snapshots_state"):
        op.create_index("ix_device_presence_snapshots_state", "device_presence_snapshots", ["session_state"])

    if not _has_table("device_presence_daily_summaries"):
        op.create_table(
            "device_presence_daily_summaries",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("summary_date", sa.String(10), nullable=False),
            sa.Column("active_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("idle_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("locked_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("offline_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("unknown_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("device_id", "summary_date", name="uq_device_presence_daily_device_date"),
        )
    if not _has_index("device_presence_daily_summaries", "ix_device_presence_daily_device_date"):
        op.create_index("ix_device_presence_daily_device_date", "device_presence_daily_summaries", ["device_id", "summary_date"])


def downgrade() -> None:
    for table, indexes in (
        ("device_presence_daily_summaries", ("ix_device_presence_daily_device_date",)),
        ("device_presence_snapshots", ("ix_device_presence_snapshots_state", "ix_device_presence_snapshots_device_collected")),
        ("device_binding_suggestions", ("ix_device_binding_suggestions_source_ref", "ix_device_binding_suggestions_device_status")),
        ("device_inventory_bulk_operation_items", ("ix_device_inventory_bulk_items_device", "ix_device_inventory_bulk_items_operation")),
        ("device_inventory_bulk_operations", ("ix_device_inventory_bulk_operations_status", "ix_device_inventory_bulk_operations_requested")),
    ):
        if _has_table(table):
            for index_name in indexes:
                if _has_index(table, index_name):
                    op.drop_index(index_name, table_name=table)
            op.drop_table(table)

    if _has_table("device_inventory_refresh_runs"):
        if _has_index("device_inventory_refresh_runs", "ix_device_inventory_refresh_runs_bulk_operation"):
            op.drop_index("ix_device_inventory_refresh_runs_bulk_operation", table_name="device_inventory_refresh_runs")
        if _has_column("device_inventory_refresh_runs", "bulk_operation_id"):
            op.drop_column("device_inventory_refresh_runs", "bulk_operation_id")
