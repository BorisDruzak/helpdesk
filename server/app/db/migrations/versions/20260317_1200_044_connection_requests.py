"""Connection requests and server config (connection policy).

Revision ID: 044
Revises: 043
Create Date: 2026-03-17 12:00:00.000000

- connection_requests: pending/approved/rejected device connection requests
- server_config: key-value for connection_policy (reject_all | accept_all | manual)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "044"
down_revision: Union[str, None] = "043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connection_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("hostname", sa.String(255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_connection_requests_device_id",
        "connection_requests",
        ["device_id"],
        unique=False,
    )
    op.create_index(
        "ix_connection_requests_status",
        "connection_requests",
        ["status"],
        unique=False,
    )

    op.create_table(
        "server_config",
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
    op.execute(
        "INSERT INTO server_config (key, value) VALUES ('connection_policy', 'manual')"
    )


def downgrade() -> None:
    op.drop_index("ix_connection_requests_status", table_name="connection_requests")
    op.drop_index("ix_connection_requests_device_id", table_name="connection_requests")
    op.drop_table("connection_requests")
    op.drop_table("server_config")
