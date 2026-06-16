"""Allow GUI password account session verification method.

Revision ID: 122
Revises: 121
Create Date: 2026-06-16 12:20:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "122"
down_revision: Union[str, None] = "121"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


CONSTRAINT_NAME = "ck_device_account_sessions_verification_method"
TABLE_NAME = "device_account_sessions"
OLD_METHODS = "'device_binding', 'registration_claim', 'admin_approval', 'email_otp', 'sso', 'break_glass'"
NEW_METHODS = "'device_binding', 'registration_claim', 'admin_approval', 'gui_password', 'email_otp', 'sso', 'break_glass'"


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_check_constraint(table_name: str, constraint_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(item.get("name") == constraint_name for item in inspector.get_check_constraints(table_name))


def _replace_constraint(methods_sql: str) -> None:
    if not _has_table(TABLE_NAME):
        return
    if _has_check_constraint(TABLE_NAME, CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(
        CONSTRAINT_NAME,
        TABLE_NAME,
        f"verification_method IS NULL OR verification_method IN ({methods_sql})",
    )


def upgrade() -> None:
    _replace_constraint(NEW_METHODS)


def downgrade() -> None:
    _replace_constraint(OLD_METHODS)
