"""Persist verified Endpoint device references and external operation links.

Revision ID: 135
Revises: 134
Create Date: 2026-08-17 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "135"
down_revision: Union[str, None] = "134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("endpoint_device_ref", sa.Text(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("endpoint_device_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_tickets_endpoint_device_ref", "tickets", ["endpoint_device_ref"], unique=False)

    op.create_table(
        "endpoint_operation_links",
        sa.Column("link_id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_operation_ref", sa.Text(), nullable=True),
        sa.Column("endpoint_device_ref", sa.Text(), nullable=False),
        sa.Column("capability_code", sa.String(length=128), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("remote_status", sa.String(length=32), nullable=False, server_default="create_pending"),
        sa.Column("diagnostic_session_id", sa.String(length=36), nullable=True),
        sa.Column("diagnostic_step_id", sa.String(length=36), nullable=True),
        sa.Column("safe_result_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_synced_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "capability_code = 'context.diagnostic.collect'",
            name="ck_endpoint_operation_links_capability_code",
        ),
        sa.CheckConstraint(
            "remote_status IN ('create_pending', 'queued', 'delivered', 'acknowledged', 'running', "
            "'succeeded', 'failed', 'canceled', 'expired')",
            name="ck_endpoint_operation_links_remote_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_endpoint_operation_links_attempt_count"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diagnostic_session_id"], ["diagnostic_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["diagnostic_step_id"], ["diagnostic_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint("operation_id", name="uq_endpoint_operation_links_operation_id"),
        sa.UniqueConstraint("endpoint_operation_ref", name="uq_endpoint_operation_links_endpoint_operation_ref"),
        sa.UniqueConstraint("create_idempotency_key", name="uq_endpoint_operation_links_create_idempotency_key"),
    )
    op.create_index(
        "ix_endpoint_operation_links_ready",
        "endpoint_operation_links",
        ["remote_status", "next_attempt_at"],
        unique=False,
    )
    op.create_index("ix_endpoint_operation_links_lease_until", "endpoint_operation_links", ["lease_until"], unique=False)


def downgrade() -> None:
    """Revision 135 is forward-only; roll back the application release instead."""

    raise RuntimeError("Revision 135 is forward-only; do not drop Endpoint operation history.")
