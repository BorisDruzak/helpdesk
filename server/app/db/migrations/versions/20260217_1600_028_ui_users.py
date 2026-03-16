"""Stage 10: UI users and roles from DB — ui_users, ui_user_audit

Revision ID: 028
Revises: 027
Create Date: 2026-02-17 16:00:00.000000

- ui_users: user_login PK, password_hash, actor_role, is_active, failed_attempts,
  locked_until, last_login_at, created_at, updated_at
- ui_user_audit: журнал действий по пользователям
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ui_users",
        sa.Column("user_login", sa.String(100), primary_key=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False, server_default=sa.text("'admin'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_login_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ui_users_is_active", "ui_users", ["is_active"])
    op.create_index("ix_ui_users_actor_role", "ui_users", ["actor_role"])
    op.create_index("ix_ui_users_locked_until", "ui_users", ["locked_until"])

    op.create_table(
        "ui_user_audit",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("user_login", sa.String(100), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("details_json", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ui_user_audit_user_login_created_at", "ui_user_audit", ["user_login", "created_at"])
    op.create_index("ix_ui_user_audit_created_at", "ui_user_audit", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ui_user_audit_created_at", table_name="ui_user_audit")
    op.drop_index("ix_ui_user_audit_user_login_created_at", table_name="ui_user_audit")
    op.drop_table("ui_user_audit")
    op.drop_index("ix_ui_users_locked_until", table_name="ui_users")
    op.drop_index("ix_ui_users_actor_role", table_name="ui_users")
    op.drop_index("ix_ui_users_is_active", table_name="ui_users")
    op.drop_table("ui_users")
