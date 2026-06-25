"""Split Observer integrity observation and recurrence counters.

Revision ID: 130
Revises: 129
Create Date: 2026-06-25 18:15:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "130"
down_revision: Union[str, None] = "129"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    table = "observer_integrity_events"
    if not _has_table(table):
        return

    if not _has_column(table, "scan_observation_count"):
        op.add_column(
            table,
            sa.Column("scan_observation_count", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_column(table, "recurrence_count"):
        op.add_column(
            table,
            sa.Column("recurrence_count", sa.Integer(), nullable=False, server_default="1"),
        )
    if not _has_column(table, "last_reopened_at"):
        op.add_column(table, sa.Column("last_reopened_at", sa.TIMESTAMP(timezone=True), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE observer_integrity_events
            SET
                scan_observation_count = GREATEST(COALESCE(scan_observation_count, occurrence_count, 1), 1),
                recurrence_count = GREATEST(COALESCE(recurrence_count, 1), 1),
                occurrence_count = GREATEST(COALESCE(recurrence_count, 1), 1)
            """
        )
    )


def downgrade() -> None:
    table = "observer_integrity_events"
    if not _has_table(table):
        return
    for column_name in ("last_reopened_at", "recurrence_count", "scan_observation_count"):
        if _has_column(table, column_name):
            op.drop_column(table, column_name)
