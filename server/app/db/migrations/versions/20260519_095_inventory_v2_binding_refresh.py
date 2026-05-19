"""inventory v2 binding and refresh policy

Revision ID: 095
Revises: 094
Create Date: 2026-05-19 10:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "095"
down_revision: Union[str, None] = "094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("device_inventory_bindings"):
        op.create_table(
            "device_inventory_bindings",
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("building", sa.String(120), nullable=True),
            sa.Column("floor", sa.String(64), nullable=True),
            sa.Column("room", sa.String(120), nullable=True),
            sa.Column("department", sa.String(160), nullable=True),
            sa.Column("responsible_user", sa.String(160), nullable=True),
            sa.Column("responsible_user_login", sa.String(160), nullable=True),
            sa.Column("inventory_number", sa.String(120), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("device_id"),
        )

    if not _has_table("device_inventory_refresh_policies"):
        op.create_table(
            "device_inventory_refresh_policies",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("scope", sa.String(16), nullable=False, server_default="global"),
            sa.Column("device_id", sa.String(36), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="1440"),
            sa.Column("jitter_minutes", sa.Integer(), nullable=False, server_default="30"),
            sa.Column("last_requested_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("next_due_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if _has_table("device_inventory_refresh_policies"):
        if not _has_index("device_inventory_refresh_policies", "ix_device_inventory_refresh_policies_scope"):
            op.create_index(
                "ix_device_inventory_refresh_policies_scope",
                "device_inventory_refresh_policies",
                ["scope"],
            )
        if not _has_index("device_inventory_refresh_policies", "ix_device_inventory_refresh_policies_device"):
            op.create_index(
                "ix_device_inventory_refresh_policies_device",
                "device_inventory_refresh_policies",
                ["device_id"],
            )
        if not _has_index("device_inventory_refresh_policies", "ix_device_inventory_refresh_policies_enabled_due"):
            op.create_index(
                "ix_device_inventory_refresh_policies_enabled_due",
                "device_inventory_refresh_policies",
                ["enabled", "next_due_at"],
            )
        if not _has_index("device_inventory_refresh_policies", "uq_device_inventory_refresh_policy_global"):
            op.create_index(
                "uq_device_inventory_refresh_policy_global",
                "device_inventory_refresh_policies",
                ["scope"],
                unique=True,
                postgresql_where=sa.text("scope = 'global'"),
            )
        if not _has_index("device_inventory_refresh_policies", "uq_device_inventory_refresh_policy_device"):
            op.create_index(
                "uq_device_inventory_refresh_policy_device",
                "device_inventory_refresh_policies",
                ["device_id"],
                unique=True,
                postgresql_where=sa.text("scope = 'device' AND device_id IS NOT NULL"),
            )


def downgrade() -> None:
    if _has_table("device_inventory_refresh_policies"):
        for index_name in (
            "uq_device_inventory_refresh_policy_device",
            "uq_device_inventory_refresh_policy_global",
            "ix_device_inventory_refresh_policies_enabled_due",
            "ix_device_inventory_refresh_policies_device",
            "ix_device_inventory_refresh_policies_scope",
        ):
            if _has_index("device_inventory_refresh_policies", index_name):
                op.drop_index(index_name, table_name="device_inventory_refresh_policies")
        op.drop_table("device_inventory_refresh_policies")
    if _has_table("device_inventory_bindings"):
        op.drop_table("device_inventory_bindings")
