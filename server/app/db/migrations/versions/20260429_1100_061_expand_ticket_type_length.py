"""expand ticket type length

Revision ID: 061
Revises: 060
Create Date: 2026-04-29 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "061"
down_revision: Union[str, None] = "060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "tickets",
        "ticket_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=64),
        existing_nullable=False,
        existing_server_default="request",
    )


def downgrade() -> None:
    op.alter_column(
        "tickets",
        "ticket_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default="request",
    )
