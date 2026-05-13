"""runner rollout target operation id text

Revision ID: 080
Revises: 079
Create Date: 2026-05-13 14:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "080"
down_revision = "079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "runner_rollout_targets",
        "operation_id",
        existing_type=sa.String(length=36),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "runner_rollout_targets",
        "operation_id",
        existing_type=sa.Text(),
        type_=sa.String(length=36),
        existing_nullable=True,
    )
