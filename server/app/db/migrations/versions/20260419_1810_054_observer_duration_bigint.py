"""observer duration bigint

Revision ID: 054
Revises: 053
Create Date: 2026-04-19 18:10:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "observer_traces",
        "duration_ms",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="duration_ms::bigint",
    )
    op.alter_column(
        "observer_spans",
        "duration_ms",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
        postgresql_using="duration_ms::bigint",
    )


def downgrade() -> None:
    op.alter_column(
        "observer_spans",
        "duration_ms",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="duration_ms::integer",
    )
    op.alter_column(
        "observer_traces",
        "duration_ms",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="duration_ms::integer",
    )
