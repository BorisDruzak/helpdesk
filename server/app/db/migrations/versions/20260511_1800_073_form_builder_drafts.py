"""form builder drafts

Revision ID: 073
Revises: 072
Create Date: 2026-05-11 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "form_builder_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("pack_key", sa.String(length=64), nullable=False),
        sa.Column("base_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("schema_json", postgresql.JSONB(), nullable=False),
        sa.Column("validation_report_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("published_version", sa.String(length=32), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_form_builder_drafts_pack_key", "form_builder_drafts", ["pack_key"])
    op.create_index("ix_form_builder_drafts_status", "form_builder_drafts", ["status"])
    op.create_index("ix_form_builder_drafts_pack_status", "form_builder_drafts", ["pack_key", "status"])
    op.create_index("ix_form_builder_drafts_updated_at", "form_builder_drafts", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_form_builder_drafts_updated_at", table_name="form_builder_drafts")
    op.drop_index("ix_form_builder_drafts_pack_status", table_name="form_builder_drafts")
    op.drop_index("ix_form_builder_drafts_status", table_name="form_builder_drafts")
    op.drop_index("ix_form_builder_drafts_pack_key", table_name="form_builder_drafts")
    op.drop_table("form_builder_drafts")
