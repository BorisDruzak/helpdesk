"""device inventory snapshots

Revision ID: 094
Revises: 093
Create Date: 2026-05-18 20:20:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "094"
down_revision: Union[str, None] = "093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("device_inventory_snapshots"):
        op.create_table(
            "device_inventory_snapshots",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("source_tool", sa.Text(), nullable=False, server_default="inventory.collect"),
            sa.Column("source_version", sa.String(64), nullable=True),
            sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("normalized", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="ok"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("collected_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("received_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("snapshot_hash", sa.String(64), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table("device_inventory_snapshots"):
        if not _has_index("device_inventory_snapshots", "ix_device_inventory_snapshots_device_collected"):
            op.create_index(
                "ix_device_inventory_snapshots_device_collected",
                "device_inventory_snapshots",
                ["device_id", sa.text("collected_at DESC")],
            )
        if not _has_index("device_inventory_snapshots", "ix_device_inventory_snapshots_source_tool"):
            op.create_index("ix_device_inventory_snapshots_source_tool", "device_inventory_snapshots", ["source_tool"])
        if not _has_index("device_inventory_snapshots", "ix_device_inventory_snapshots_status"):
            op.create_index("ix_device_inventory_snapshots_status", "device_inventory_snapshots", ["status"])
        if not _has_index("device_inventory_snapshots", "ix_device_inventory_snapshots_hash"):
            op.create_index("ix_device_inventory_snapshots_hash", "device_inventory_snapshots", ["snapshot_hash"])


def downgrade() -> None:
    if _has_table("device_inventory_snapshots"):
        for index_name in (
            "ix_device_inventory_snapshots_hash",
            "ix_device_inventory_snapshots_status",
            "ix_device_inventory_snapshots_source_tool",
            "ix_device_inventory_snapshots_device_collected",
        ):
            if _has_index("device_inventory_snapshots", index_name):
                op.drop_index(index_name, table_name="device_inventory_snapshots")
        op.drop_table("device_inventory_snapshots")
