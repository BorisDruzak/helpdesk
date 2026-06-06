"""Add persisted server runtime snapshots.

Revision ID: 107
Revises: 106
Create Date: 2026-06-06
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "107"
down_revision: Union[str, None] = "106"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    return any(index.get("name") == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("server_runtime_snapshots"):
        op.create_table(
            "server_runtime_snapshots",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("process_kind", sa.String(length=40), nullable=False),
            sa.Column("instance_id", sa.String(length=80), nullable=False),
            sa.Column("pid", sa.Integer(), nullable=True),
            sa.Column("git_revision", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("collected_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("server_runtime_snapshots", "ix_server_runtime_snapshots_instance_id"):
        op.create_index(
            "ix_server_runtime_snapshots_instance_id",
            "server_runtime_snapshots",
            ["instance_id"],
        )
    if not _has_index("server_runtime_snapshots", "ix_server_runtime_snapshots_process_kind"):
        op.create_index(
            "ix_server_runtime_snapshots_process_kind",
            "server_runtime_snapshots",
            ["process_kind"],
        )
    if not _has_index("server_runtime_snapshots", "ix_server_runtime_snapshots_kind_collected"):
        op.create_index(
            "ix_server_runtime_snapshots_kind_collected",
            "server_runtime_snapshots",
            ["process_kind", "collected_at"],
        )
    if not _has_index("server_runtime_snapshots", "ix_server_runtime_snapshots_kind_expires"):
        op.create_index(
            "ix_server_runtime_snapshots_kind_expires",
            "server_runtime_snapshots",
            ["process_kind", "expires_at"],
        )


def downgrade() -> None:
    if _has_table("server_runtime_snapshots"):
        for index_name in (
            "ix_server_runtime_snapshots_kind_expires",
            "ix_server_runtime_snapshots_kind_collected",
            "ix_server_runtime_snapshots_process_kind",
            "ix_server_runtime_snapshots_instance_id",
        ):
            if _has_index("server_runtime_snapshots", index_name):
                op.drop_index(index_name, table_name="server_runtime_snapshots")
        op.drop_table("server_runtime_snapshots")
