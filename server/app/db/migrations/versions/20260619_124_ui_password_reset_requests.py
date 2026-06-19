"""Add UI password reset request queue.

Revision ID: 124
Revises: 123
Create Date: 2026-06-19 09:50:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "124"
down_revision: Union[str, None] = "123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_NAME = "ui_password_reset_requests"


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table(TABLE_NAME):
        op.create_table(
            TABLE_NAME,
            sa.Column("request_id", sa.String(36), nullable=False),
            sa.Column("login", sa.String(100), nullable=False),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("requested_ip", sa.Text(), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_by", sa.Text(), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint(
                "status IN ('pending', 'completed', 'rejected', 'canceled')",
                name="ck_ui_password_reset_requests_status",
            ),
            sa.PrimaryKeyConstraint("request_id"),
        )
    for index_name, columns in (
        ("ix_ui_password_reset_requests_status_requested", ["status", "requested_at"]),
        ("ix_ui_password_reset_requests_login_status", ["login", "status"]),
    ):
        if not _has_index(TABLE_NAME, index_name):
            op.create_index(index_name, TABLE_NAME, columns)


def downgrade() -> None:
    if not _has_table(TABLE_NAME):
        return
    for index_name in (
        "ix_ui_password_reset_requests_login_status",
        "ix_ui_password_reset_requests_status_requested",
    ):
        if _has_index(TABLE_NAME, index_name):
            op.drop_index(index_name, table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
