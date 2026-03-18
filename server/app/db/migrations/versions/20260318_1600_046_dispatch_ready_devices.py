"""Add dispatch_ready_devices for DB-coordinated sharded dispatch.

Revision ID: 046
Revises: 045
Create Date: 2026-03-18 16:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "046"
down_revision: Union[str, None] = "045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispatch_ready_devices",
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("shard_key", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_index(
        "ix_dispatch_ready_shard_next_attempt",
        "dispatch_ready_devices",
        ["shard_key", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_ready_lease_until",
        "dispatch_ready_devices",
        ["lease_until"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_ready_devices_shard_key",
        "dispatch_ready_devices",
        ["shard_key"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_ready_devices_next_attempt_at",
        "dispatch_ready_devices",
        ["next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_ready_devices_lease_owner",
        "dispatch_ready_devices",
        ["lease_owner"],
        unique=False,
    )
    op.create_index(
        "ix_dispatch_ready_devices_lease_until",
        "dispatch_ready_devices",
        ["lease_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_dispatch_ready_devices_lease_until", table_name="dispatch_ready_devices")
    op.drop_index("ix_dispatch_ready_devices_lease_owner", table_name="dispatch_ready_devices")
    op.drop_index("ix_dispatch_ready_devices_next_attempt_at", table_name="dispatch_ready_devices")
    op.drop_index("ix_dispatch_ready_devices_shard_key", table_name="dispatch_ready_devices")
    op.drop_index("ix_dispatch_ready_lease_until", table_name="dispatch_ready_devices")
    op.drop_index("ix_dispatch_ready_shard_next_attempt", table_name="dispatch_ready_devices")
    op.drop_table("dispatch_ready_devices")
