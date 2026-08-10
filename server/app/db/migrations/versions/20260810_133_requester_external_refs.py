"""Add neutral requester references and snapshots.

Revision ID: 133
Revises: 132
Create Date: 2026-08-10 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "133"
down_revision: Union[str, None] = "132"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    for table_name, index_name in (
        ("tickets", "ix_tickets_requester_external_ref"),
        ("user_consent_requests", "ix_user_consent_requests_requester_external_ref"),
    ):
        if not _has_table(table_name):
            continue
        op.add_column(table_name, sa.Column("requester_external_ref", sa.Text(), nullable=True))
        op.add_column(
            table_name,
            sa.Column("requester_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
        op.create_index(index_name, table_name, ["requester_external_ref"], unique=False)


def downgrade() -> None:
    for table_name, index_name in (
        ("user_consent_requests", "ix_user_consent_requests_requester_external_ref"),
        ("tickets", "ix_tickets_requester_external_ref"),
    ):
        if not _has_table(table_name):
            continue
        op.drop_index(index_name, table_name=table_name)
        op.drop_column(table_name, "requester_snapshot_json")
        op.drop_column(table_name, "requester_external_ref")
