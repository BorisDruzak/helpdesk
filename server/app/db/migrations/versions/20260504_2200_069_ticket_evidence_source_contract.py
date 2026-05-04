"""ticket evidence source contract

Revision ID: 069
Revises: 068
Create Date: 2026-05-04 22:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ticket_evidence_items", sa.Column("source_kind", sa.String(length=40), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("source_id", sa.Text(), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("required_fact", sa.String(length=80), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("section_key", sa.String(length=80), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("artifact_id", sa.String(length=36), nullable=True))
    op.add_column(
        "ticket_evidence_items",
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="unverified"),
    )
    op.add_column("ticket_evidence_items", sa.Column("verified_by", sa.Text(), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("verified_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("captured_at", TIMESTAMP(timezone=True), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("public_summary", sa.Text(), nullable=True))
    op.add_column("ticket_evidence_items", sa.Column("internal_summary", sa.Text(), nullable=True))
    op.add_column(
        "ticket_evidence_items",
        sa.Column("metadata_json", JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "ticket_evidence_items",
        sa.Column("export_visibility", sa.String(length=30), nullable=False, server_default="internal"),
    )
    op.create_foreign_key(
        "fk_ticket_evidence_items_artifact_id",
        "ticket_evidence_items",
        "artifacts",
        ["artifact_id"],
        ["artifact_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ticket_evidence_items_source", "ticket_evidence_items", ["source_kind", "source_id"])
    op.create_index("ix_ticket_evidence_items_required_fact", "ticket_evidence_items", ["ticket_id", "required_fact"])
    op.create_index("ix_ticket_evidence_items_artifact", "ticket_evidence_items", ["artifact_id"])
    op.create_index(
        "uq_ticket_evidence_items_source_fact",
        "ticket_evidence_items",
        ["ticket_id", "evidence_type", "source_kind", "source_id", "required_fact"],
        unique=True,
        postgresql_where=sa.text("source_kind IS NOT NULL AND source_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_ticket_evidence_items_source_fact", table_name="ticket_evidence_items")
    op.drop_index("ix_ticket_evidence_items_artifact", table_name="ticket_evidence_items")
    op.drop_index("ix_ticket_evidence_items_required_fact", table_name="ticket_evidence_items")
    op.drop_index("ix_ticket_evidence_items_source", table_name="ticket_evidence_items")
    op.drop_constraint("fk_ticket_evidence_items_artifact_id", "ticket_evidence_items", type_="foreignkey")
    op.drop_column("ticket_evidence_items", "export_visibility")
    op.drop_column("ticket_evidence_items", "metadata_json")
    op.drop_column("ticket_evidence_items", "internal_summary")
    op.drop_column("ticket_evidence_items", "public_summary")
    op.drop_column("ticket_evidence_items", "captured_at")
    op.drop_column("ticket_evidence_items", "verified_at")
    op.drop_column("ticket_evidence_items", "verified_by")
    op.drop_column("ticket_evidence_items", "verification_status")
    op.drop_column("ticket_evidence_items", "artifact_id")
    op.drop_column("ticket_evidence_items", "section_key")
    op.drop_column("ticket_evidence_items", "required_fact")
    op.drop_column("ticket_evidence_items", "source_id")
    op.drop_column("ticket_evidence_items", "source_kind")
