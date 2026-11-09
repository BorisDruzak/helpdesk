"""Durable retry receipts for requester signup.

Revision ID: 152
Revises: 151
No existing accounts or profiles are changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "152"
down_revision = "151"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("web_requester_registrations",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("user_login", sa.String(100), sa.ForeignKey("ui_users.user_login", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("registry_people.person_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("profile_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("web_requester_registrations")
