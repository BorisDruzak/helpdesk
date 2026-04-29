"""access control groups

Revision ID: 062
Revises: 061
Create Date: 2026-04-29 12:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "062"
down_revision: Union[str, None] = "061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_groups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_access_groups_code", "access_groups", ["code"])
    op.create_index("ix_access_groups_is_active", "access_groups", ["is_active"])

    op.create_table(
        "access_group_members",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["access_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "actor_id"),
    )
    op.create_index("ix_access_group_members_actor_id", "access_group_members", ["actor_id"])

    op.create_table(
        "access_group_permissions",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_code", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["access_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "permission_code"),
    )
    op.create_index(
        "ix_access_group_permissions_permission",
        "access_group_permissions",
        ["permission_code"],
    )

    op.create_table(
        "access_group_queue_members",
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.Column("queue_id", sa.BigInteger(), nullable=False),
        sa.Column("role_in_queue", sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(["group_id"], ["access_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["queue_id"], ["ticket_queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("group_id", "queue_id"),
    )

    op.create_table(
        "access_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_audit_actor_created", "access_audit", ["actor_id", "created_at"])
    op.create_index("ix_access_audit_created_at", "access_audit", ["created_at"])
    op.create_index("ix_access_audit_entity_created", "access_audit", ["entity_type", "entity_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_access_audit_entity_created", table_name="access_audit")
    op.drop_index("ix_access_audit_created_at", table_name="access_audit")
    op.drop_index("ix_access_audit_actor_created", table_name="access_audit")
    op.drop_table("access_audit")
    op.drop_table("access_group_queue_members")
    op.drop_index("ix_access_group_permissions_permission", table_name="access_group_permissions")
    op.drop_table("access_group_permissions")
    op.drop_index("ix_access_group_members_actor_id", table_name="access_group_members")
    op.drop_table("access_group_members")
    op.drop_index("ix_access_groups_is_active", table_name="access_groups")
    op.drop_index("ix_access_groups_code", table_name="access_groups")
    op.drop_table("access_groups")
