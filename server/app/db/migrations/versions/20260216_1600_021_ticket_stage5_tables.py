"""Stage 5: ticket_resolution_codes, ticket_kb_links, ticket_links constraints

Revision ID: 021
Revises: 020
Create Date: 2026-02-16 16:00:00.000000

Stage 5:
- ticket_resolution_codes (code, name, is_active, sort_order) + seed.
- ticket_kb_links (ticket_id, article_ref, title, source, created_by, created_at) + indexes.
- ticket_links: unique uq_ticket_links_src_dst_type, check link_type IN ('duplicate','related').
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- ticket_resolution_codes ---
    op.create_table(
        "ticket_resolution_codes",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute("""
        INSERT INTO ticket_resolution_codes (code, name, is_active, sort_order)
        VALUES
            ('fixed', 'Fixed', true, 1),
            ('workaround', 'Workaround', true, 2),
            ('user_error', 'User Error', true, 3),
            ('duplicate', 'Duplicate', true, 4),
            ('cannot_reproduce', 'Cannot Reproduce', true, 5),
            ('vendor', 'Vendor', true, 6)
    """)

    # --- ticket_kb_links ---
    op.create_table(
        "ticket_kb_links",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("article_ref", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ticket_kb_links_ticket_id", "ticket_kb_links", ["ticket_id"])
    op.create_index("ix_ticket_kb_links_article_ref", "ticket_kb_links", ["article_ref"])

    # --- ticket_links: unique (src, dst, type) and check constraint ---
    op.create_unique_constraint(
        "uq_ticket_links_src_dst_type",
        "ticket_links",
        ["src_ticket_id", "dst_ticket_id", "link_type"],
    )
    op.create_check_constraint(
        "chk_ticket_links_link_type",
        "ticket_links",
        "link_type IN ('duplicate', 'related')",
    )


def downgrade() -> None:
    op.drop_constraint("chk_ticket_links_link_type", "ticket_links", type_="check")
    op.drop_constraint("uq_ticket_links_src_dst_type", "ticket_links", type_="unique")
    op.drop_index("ix_ticket_kb_links_article_ref", table_name="ticket_kb_links")
    op.drop_index("ix_ticket_kb_links_ticket_id", table_name="ticket_kb_links")
    op.drop_table("ticket_kb_links")
    op.drop_table("ticket_resolution_codes")
