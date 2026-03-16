"""Stage 9: ticket_admin_config_audit — is_active в SLA policies + ticket_admin_audit

Revision ID: 027
Revises: 026
Create Date: 2026-02-17 14:00:00.000000

- ticket_sla_policies: добавить is_active BOOLEAN NOT NULL DEFAULT true
- ticket_admin_audit: id, entity_type, entity_id, action, actor_id, actor_role,
  before_json, after_json, trace_id, created_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ticket_sla_policies: is_active
    op.add_column(
        "ticket_sla_policies",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # ticket_admin_audit
    op.create_table(
        "ticket_admin_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("before_json", JSONB, nullable=True),
        sa.Column("after_json", JSONB, nullable=True),
        sa.Column("trace_id", sa.String(36), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_ticket_admin_audit_entity_type_entity_id_created_at",
        "ticket_admin_audit",
        ["entity_type", "entity_id", "created_at"],
    )
    op.create_index(
        "ix_ticket_admin_audit_actor_id_created_at",
        "ticket_admin_audit",
        ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_ticket_admin_audit_created_at",
        "ticket_admin_audit",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ticket_admin_audit_created_at", table_name="ticket_admin_audit")
    op.drop_index("ix_ticket_admin_audit_actor_id_created_at", table_name="ticket_admin_audit")
    op.drop_index(
        "ix_ticket_admin_audit_entity_type_entity_id_created_at",
        table_name="ticket_admin_audit",
    )
    op.drop_table("ticket_admin_audit")
    op.drop_column("ticket_sla_policies", "is_active")
