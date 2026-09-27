"""Preserve supported UI logins in diagnostic actor attribution.

Revision ID: 145
Revises: 144
"""
from alembic import op
import sqlalchemy as sa

revision = "145"
down_revision = "144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "diagnostic_sessions", "started_by_user_id",
        existing_type=sa.String(36), type_=sa.String(100), existing_nullable=True,
    )


def downgrade() -> None:
    raise RuntimeError("Revision 145 is forward-only; roll back the application release instead.")
