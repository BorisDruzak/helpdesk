"""inventory v3 lightweight cmdb

Revision ID: 096
Revises: 095
Create Date: 2026-05-19 14:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "096"
down_revision: Union[str, None] = "095"
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
    if _has_table("device_inventory_bindings"):
        if not _has_column("device_inventory_bindings", "status"):
            op.add_column("device_inventory_bindings", sa.Column("status", sa.String(32), nullable=True))
        if not _has_column("device_inventory_bindings", "tags"):
            op.add_column(
                "device_inventory_bindings",
                sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            )
            op.alter_column("device_inventory_bindings", "tags", server_default=None)

    if not _has_table("device_inventory_binding_history"):
        op.create_table(
            "device_inventory_binding_history",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("changed_by", sa.Text(), nullable=True),
            sa.Column("changed_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("old_binding", JSONB(), nullable=True),
            sa.Column("new_binding", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("changed_fields", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("device_inventory_binding_history", "ix_device_inventory_binding_history_device_changed"):
        op.create_index(
            "ix_device_inventory_binding_history_device_changed",
            "device_inventory_binding_history",
            ["device_id", "changed_at"],
        )

    if not _has_table("device_inventory_refresh_runs"):
        op.create_table(
            "device_inventory_refresh_runs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=True),
            sa.Column("policy_id", sa.String(36), nullable=True),
            sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("requested_by", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="requested"),
            sa.Column("job_id", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("device_inventory_refresh_runs", "ix_device_inventory_refresh_runs_device_requested"):
        op.create_index(
            "ix_device_inventory_refresh_runs_device_requested",
            "device_inventory_refresh_runs",
            ["device_id", "requested_at"],
        )
    if not _has_index("device_inventory_refresh_runs", "ix_device_inventory_refresh_runs_policy_requested"):
        op.create_index(
            "ix_device_inventory_refresh_runs_policy_requested",
            "device_inventory_refresh_runs",
            ["policy_id", "requested_at"],
        )
    if not _has_index("device_inventory_refresh_runs", "ix_device_inventory_refresh_runs_status"):
        op.create_index("ix_device_inventory_refresh_runs_status", "device_inventory_refresh_runs", ["status"])


def downgrade() -> None:
    if _has_table("device_inventory_refresh_runs"):
        for index_name in (
            "ix_device_inventory_refresh_runs_status",
            "ix_device_inventory_refresh_runs_policy_requested",
            "ix_device_inventory_refresh_runs_device_requested",
        ):
            if _has_index("device_inventory_refresh_runs", index_name):
                op.drop_index(index_name, table_name="device_inventory_refresh_runs")
        op.drop_table("device_inventory_refresh_runs")

    if _has_table("device_inventory_binding_history"):
        if _has_index("device_inventory_binding_history", "ix_device_inventory_binding_history_device_changed"):
            op.drop_index("ix_device_inventory_binding_history_device_changed", table_name="device_inventory_binding_history")
        op.drop_table("device_inventory_binding_history")

    if _has_table("device_inventory_bindings"):
        if _has_column("device_inventory_bindings", "tags"):
            op.drop_column("device_inventory_bindings", "tags")
        if _has_column("device_inventory_bindings", "status"):
            op.drop_column("device_inventory_bindings", "status")
