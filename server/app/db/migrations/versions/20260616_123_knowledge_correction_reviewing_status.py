"""Rename knowledge correction review status away from ticket triaged alias.

Revision ID: 123
Revises: 122
Create Date: 2026-06-16 15:45:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "123"
down_revision: Union[str, None] = "122"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


TABLE_NAME = "knowledge_correction_requests"
CONSTRAINT_NAME = "ck_knowledge_correction_requests_status"
OLD_STATUSES = "'open', 'triaged', 'accepted', 'rejected', 'closed'"
NEW_STATUSES = "'open', 'reviewing', 'accepted', 'rejected', 'closed'"


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


def _replace_constraint(statuses_sql: str) -> None:
    if _has_check_constraint(TABLE_NAME, CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.create_check_constraint(CONSTRAINT_NAME, TABLE_NAME, f"status IN ({statuses_sql})")


def upgrade() -> None:
    if not _has_table(TABLE_NAME):
        return
    if _has_check_constraint(TABLE_NAME, CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.execute(f"UPDATE {TABLE_NAME} SET status = 'reviewing' WHERE status = 'triaged'")
    op.create_check_constraint(CONSTRAINT_NAME, TABLE_NAME, f"status IN ({NEW_STATUSES})")


def downgrade() -> None:
    if not _has_table(TABLE_NAME):
        return
    if _has_check_constraint(TABLE_NAME, CONSTRAINT_NAME):
        op.drop_constraint(CONSTRAINT_NAME, TABLE_NAME, type_="check")
    op.execute(f"UPDATE {TABLE_NAME} SET status = 'triaged' WHERE status = 'reviewing'")
    op.create_check_constraint(CONSTRAINT_NAME, TABLE_NAME, f"status IN ({OLD_STATUSES})")
