"""ticket resolution passport

Revision ID: 059
Revises: 058
Create Date: 2026-04-26 13:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "059"
down_revision: Union[str, None] = "058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_resolution_passports",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("summary_source", sa.String(length=30), nullable=False, server_default="deterministic"),
        sa.Column("requester_summary", sa.Text(), nullable=True),
        sa.Column("problem_summary", sa.Text(), nullable=True),
        sa.Column("affected_object_summary", sa.Text(), nullable=True),
        sa.Column("automated_checks_summary", sa.Text(), nullable=True),
        sa.Column("operator_checks_summary", sa.Text(), nullable=True),
        sa.Column("changes_made_summary", sa.Text(), nullable=True),
        sa.Column("approvals_summary", sa.Text(), nullable=True),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("user_result_summary", sa.Text(), nullable=True),
        sa.Column("internal_result_summary", sa.Text(), nullable=True),
        sa.Column("repeat_guidance", sa.Text(), nullable=True),
        sa.Column("source_event_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_operation_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("generated_by", sa.Text(), nullable=True),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticket_id", "version", name="uq_ticket_resolution_passports_ticket_version"),
    )
    op.create_index(
        "ix_ticket_resolution_passports_ticket_generated",
        "ticket_resolution_passports",
        ["ticket_id", "generated_at"],
    )

    op.create_table(
        "ticket_evidence_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("passport_id", sa.BigInteger(), sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("evidence_type", sa.String(length=30), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_evidence_items_ticket_created", "ticket_evidence_items", ["ticket_id", "created_at"])
    op.create_index("ix_ticket_evidence_items_passport", "ticket_evidence_items", ["passport_id"])

    op.create_table(
        "ticket_action_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("passport_id", sa.BigInteger(), sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("source_event_id", sa.BigInteger(), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ticket_action_log_ticket_created", "ticket_action_log", ["ticket_id", "created_at"])
    op.create_index("ix_ticket_action_log_operation", "ticket_action_log", ["operation_id"])

    op.create_table(
        "ticket_approvals",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("passport_id", sa.BigInteger(), sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approval_type", sa.String(length=40), nullable=False),
        sa.Column("approver_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="requested"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("requested_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_ticket_approvals_ticket_status", "ticket_approvals", ["ticket_id", "status"])
    op.create_index("ix_ticket_approvals_approver_status", "ticket_approvals", ["approver_id", "status"])

    op.create_table(
        "ticket_related_objects",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("passport_id", sa.BigInteger(), sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_ref", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("relation_type", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="snapshot"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "ticket_id",
            "object_type",
            "object_ref",
            "relation_type",
            name="uq_ticket_related_objects_unique_relation",
        ),
    )
    op.create_index("ix_ticket_related_objects_ticket", "ticket_related_objects", ["ticket_id"])
    op.create_index("ix_ticket_related_objects_passport", "ticket_related_objects", ["passport_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_related_objects_passport", table_name="ticket_related_objects")
    op.drop_index("ix_ticket_related_objects_ticket", table_name="ticket_related_objects")
    op.drop_table("ticket_related_objects")

    op.drop_index("ix_ticket_approvals_approver_status", table_name="ticket_approvals")
    op.drop_index("ix_ticket_approvals_ticket_status", table_name="ticket_approvals")
    op.drop_table("ticket_approvals")

    op.drop_index("ix_ticket_action_log_operation", table_name="ticket_action_log")
    op.drop_index("ix_ticket_action_log_ticket_created", table_name="ticket_action_log")
    op.drop_table("ticket_action_log")

    op.drop_index("ix_ticket_evidence_items_passport", table_name="ticket_evidence_items")
    op.drop_index("ix_ticket_evidence_items_ticket_created", table_name="ticket_evidence_items")
    op.drop_table("ticket_evidence_items")

    op.drop_index("ix_ticket_resolution_passports_ticket_generated", table_name="ticket_resolution_passports")
    op.drop_table("ticket_resolution_passports")
