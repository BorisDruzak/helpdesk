"""Allow requester no-device tickets to store NULL device_id.

Revision ID: 127
Revises: 126
Create Date: 2026-06-22 12:35:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "127"
down_revision: Union[str, None] = "126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if _has_column("tickets", "device_id"):
        op.alter_column("tickets", "device_id", existing_type=sa.String(length=36), nullable=True)
    if _has_column("ticket_events", "device_id"):
        op.alter_column("ticket_events", "device_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_column("ticket_events", "device_id"):
        null_events = bind.execute(sa.text("SELECT count(*) FROM ticket_events WHERE device_id IS NULL")).scalar_one()
        if int(null_events or 0) == 0:
            op.alter_column("ticket_events", "device_id", existing_type=sa.String(length=36), nullable=False)
    if _has_column("tickets", "device_id"):
        null_tickets = bind.execute(sa.text("SELECT count(*) FROM tickets WHERE device_id IS NULL")).scalar_one()
        if int(null_tickets or 0) == 0:
            op.alter_column("tickets", "device_id", existing_type=sa.String(length=36), nullable=False)
