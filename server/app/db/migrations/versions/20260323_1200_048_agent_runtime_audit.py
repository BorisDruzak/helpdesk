"""Add agent runtime audit table for tech panel.

Revision ID: 048
Revises: 047
Create Date: 2026-03-23 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "048"
down_revision: Union[str, None] = "047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default=sa.text("'info'")),
        sa.Column("source", sa.String(length=64), nullable=False, server_default=sa.text("'server'")),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_runtime_audit_device_created",
        "agent_runtime_audit",
        ["device_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_runtime_audit_event_created",
        "agent_runtime_audit",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_runtime_audit_severity_created",
        "agent_runtime_audit",
        ["severity", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_agent_runtime_audit_created_at",
        "agent_runtime_audit",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_runtime_audit_created_at", table_name="agent_runtime_audit")
    op.drop_index("ix_agent_runtime_audit_severity_created", table_name="agent_runtime_audit")
    op.drop_index("ix_agent_runtime_audit_event_created", table_name="agent_runtime_audit")
    op.drop_index("ix_agent_runtime_audit_device_created", table_name="agent_runtime_audit")
    op.drop_table("agent_runtime_audit")
