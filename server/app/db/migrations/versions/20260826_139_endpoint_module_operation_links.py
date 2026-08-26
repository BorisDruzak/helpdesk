"""Persist separate Helpdesk links for Endpoint Module Platform operations.

Revision ID: 139
Revises: 138
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "139"
down_revision = "138"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "endpoint_module_operation_links",
        sa.Column("link_id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_operation_ref", sa.Text(), nullable=True),
        sa.Column("endpoint_device_ref", sa.Text(), nullable=False),
        sa.Column("module_key", sa.String(length=128), nullable=False),
        sa.Column("module_version", sa.String(length=64), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("remote_status", sa.String(length=32), nullable=False, server_default="create_pending"),
        sa.Column(
            "safe_result_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_synced_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "remote_status IN ('create_pending', 'queued', 'delivered', 'acknowledged', 'running', "
            "'succeeded', 'failed', 'canceled', 'expired')",
            name="ck_endpoint_module_operation_links_remote_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_endpoint_module_operation_links_attempt_count",
        ),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("link_id"),
        sa.UniqueConstraint("operation_id", name="uq_endpoint_module_operation_links_operation_id"),
        sa.UniqueConstraint(
            "endpoint_operation_ref",
            name="uq_endpoint_module_operation_links_endpoint_operation_ref",
        ),
        sa.UniqueConstraint(
            "create_idempotency_key",
            name="uq_endpoint_module_operation_links_create_idempotency_key",
        ),
    )
    op.create_index(
        "ix_endpoint_module_operation_links_ready",
        "endpoint_module_operation_links",
        ["remote_status", "next_attempt_at"],
        unique=False,
    )
    op.create_index(
        "ix_endpoint_module_operation_links_lease_until",
        "endpoint_module_operation_links",
        ["lease_until"],
        unique=False,
    )


def downgrade() -> None:
    raise RuntimeError("Revision 139 is forward-only; roll back the application release instead.")
