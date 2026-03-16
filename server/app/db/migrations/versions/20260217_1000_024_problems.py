"""Stage 7: problems, problem_ticket_links for ITSM Problem management

Revision ID: 024
Revises: 023
Create Date: 2026-02-17 10:00:00.000000

- problems: problem_id, title, description, status, priority, owner_id, created_at, updated_at,
  resolved_at, closed_at, root_cause, workaround, kb_article_ref
- problem_ticket_links: problem_id, ticket_id, linked_at, linked_by, UNIQUE(problem_id, ticket_id)
- Indexes: (status, priority, updated_at), (owner_id, status), (ticket_id) in links
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "problems",
        sa.Column("problem_id", sa.String(36), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="New"),
        sa.Column("priority", sa.String(5), nullable=False, server_default="P3"),
        sa.Column("owner_id", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("root_cause", sa.Text(), nullable=True),
        sa.Column("workaround", sa.Text(), nullable=True),
        sa.Column("kb_article_ref", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("problem_id"),
    )
    op.create_index(
        "ix_problems_status_priority_updated",
        "problems",
        ["status", "priority", "updated_at"],
        unique=False,
    )
    op.create_index("ix_problems_owner_status", "problems", ["owner_id", "status"], unique=False)

    op.create_table(
        "problem_ticket_links",
        sa.Column("problem_id", sa.String(36), sa.ForeignKey("problems.problem_id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("linked_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("linked_by", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("problem_id", "ticket_id"),
    )
    op.create_index("ix_problem_ticket_links_ticket_id", "problem_ticket_links", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_problem_ticket_links_ticket_id", table_name="problem_ticket_links")
    op.drop_table("problem_ticket_links")
    op.drop_index("ix_problems_owner_status", table_name="problems")
    op.drop_index("ix_problems_status_priority_updated", table_name="problems")
    op.drop_table("problems")
