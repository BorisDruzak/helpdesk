"""make connection request request_id unique

Revision ID: 102
Revises: 101
Create Date: 2026-05-24 14:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "102"
down_revision: Union[str, None] = "101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("connection_requests"):
        return
    if not _has_index("connection_requests", "uq_connection_requests_request_id_not_null"):
        op.create_index(
            "uq_connection_requests_request_id_not_null",
            "connection_requests",
            ["request_id"],
            unique=True,
            postgresql_where=sa.text("request_id IS NOT NULL"),
        )


def downgrade() -> None:
    if not _has_table("connection_requests"):
        return
    if _has_index("connection_requests", "uq_connection_requests_request_id_not_null"):
        op.drop_index("uq_connection_requests_request_id_not_null", table_name="connection_requests")
