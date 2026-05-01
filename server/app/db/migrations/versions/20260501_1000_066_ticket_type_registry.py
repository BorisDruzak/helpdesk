"""ticket type registry

Revision ID: 066
Revises: 065
Create Date: 2026-05-01 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "066"
down_revision: Union[str, None] = "065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("ticket_types"):
        return
    op.create_table(
        "ticket_types",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("default_workflow_profile_id", sa.String(length=120), nullable=True),
        sa.Column("default_priority_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_routing_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_sla_policy_id", sa.BigInteger(), nullable=True),
        sa.Column("default_sla_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_ola_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_approval_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_diagnostic_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_closure_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_visibility_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_notification_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_reporting_policy_code", sa.String(length=100), nullable=True),
        sa.Column("sla_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("ola_required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("approval_allowed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("approval_required_by_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("diagnostics_allowed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("remediation_allowed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("portal_visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code", "version"),
    )
    op.create_index("ix_ticket_types_active", "ticket_types", ["code", "is_active"])
    op.create_index("ix_ticket_types_published_at", "ticket_types", ["published_at"])
    op.create_index("ix_ticket_types_portal_visible", "ticket_types", ["portal_visible", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_ticket_types_portal_visible", table_name="ticket_types")
    op.drop_index("ix_ticket_types_published_at", table_name="ticket_types")
    op.drop_index("ix_ticket_types_active", table_name="ticket_types")
    op.drop_table("ticket_types")
