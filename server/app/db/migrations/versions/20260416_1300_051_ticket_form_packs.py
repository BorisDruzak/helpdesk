"""Add ticket form pack registry.

Revision ID: 051
Revises: 050
Create Date: 2026-04-16 13:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "051"
down_revision: Union[str, None] = "050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ticket_form_packs" not in tables:
        op.create_table(
            "ticket_form_packs",
            sa.Column("pack_key", sa.String(length=64), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("pack_key", "version"),
        )
        op.create_index(
            "ix_ticket_form_packs_created_at",
            "ticket_form_packs",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ticket_form_packs" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("ticket_form_packs")}
        if "ix_ticket_form_packs_created_at" in indexes:
            op.drop_index("ix_ticket_form_packs_created_at", table_name="ticket_form_packs")
        op.drop_table("ticket_form_packs")
