"""support queue saved views

Revision ID: 072
Revises: 071
Create Date: 2026-05-11 16:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "support_queue_saved_views",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=20), server_default="personal", nullable=False),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column(
            "queue_id",
            sa.BigInteger(),
            sa.ForeignKey("ticket_queues.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("filters_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("columns_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("sort_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_favorite", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_queue_saved_views_owner", "support_queue_saved_views", ["owner_actor_id", "updated_at"])
    op.create_index("ix_support_queue_saved_views_scope", "support_queue_saved_views", ["scope", "queue_id"])
    op.create_index(
        "ix_support_queue_saved_views_default",
        "support_queue_saved_views",
        ["scope", "owner_actor_id", "queue_id", "is_default"],
    )


def downgrade() -> None:
    op.drop_index("ix_support_queue_saved_views_default", table_name="support_queue_saved_views")
    op.drop_index("ix_support_queue_saved_views_scope", table_name="support_queue_saved_views")
    op.drop_index("ix_support_queue_saved_views_owner", table_name="support_queue_saved_views")
    op.drop_table("support_queue_saved_views")
