"""request template policy refs

Revision ID: 068
Revises: 067
Create Date: 2026-05-02 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("request_templates", sa.Column("sla_policy_code", sa.String(length=100), nullable=True))
    op.add_column("request_templates", sa.Column("reporting_policy_code", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("request_templates", "reporting_policy_code")
    op.drop_column("request_templates", "sla_policy_code")
