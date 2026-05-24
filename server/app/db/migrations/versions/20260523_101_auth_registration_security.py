"""auth and registration security hardening

Revision ID: 101
Revises: 100
Create Date: 2026-05-23 19:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "101"
down_revision: Union[str, None] = "100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _has_check(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if _has_table("connection_requests"):
        if not _has_column("connection_requests", "request_id"):
            op.add_column("connection_requests", sa.Column("request_id", sa.String(64), nullable=True))
        if not _has_column("connection_requests", "poll_secret_hash"):
            op.add_column("connection_requests", sa.Column("poll_secret_hash", sa.String(64), nullable=True))
        if not _has_index("connection_requests", "ix_connection_requests_request_id"):
            op.create_index("ix_connection_requests_request_id", "connection_requests", ["request_id"])

    if _has_table("ui_users"):
        op.alter_column("ui_users", "actor_role", server_default="user")
        if not _has_check("ui_users", "ck_ui_users_actor_role"):
            op.create_check_constraint(
                "ck_ui_users_actor_role",
                "ui_users",
                "actor_role IN ('admin', 'support', 'auditor', 'user')",
            )


def downgrade() -> None:
    if _has_table("ui_users"):
        if _has_check("ui_users", "ck_ui_users_actor_role"):
            op.drop_constraint("ck_ui_users_actor_role", "ui_users", type_="check")
        op.alter_column("ui_users", "actor_role", server_default="admin")

    if _has_table("connection_requests"):
        if _has_index("connection_requests", "ix_connection_requests_request_id"):
            op.drop_index("ix_connection_requests_request_id", table_name="connection_requests")
        if _has_column("connection_requests", "poll_secret_hash"):
            op.drop_column("connection_requests", "poll_secret_hash")
        if _has_column("connection_requests", "request_id"):
            op.drop_column("connection_requests", "request_id")
