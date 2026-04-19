"""ticket observer root trace id

Revision ID: 053
Revises: 052
Create Date: 2026-04-19 12:00:00.000000
"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "053"
down_revision: Union[str, None] = "052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("observer_root_trace_id", sa.String(length=36), nullable=True))
    op.create_index("ix_tickets_observer_root_trace_id", "tickets", ["observer_root_trace_id"], unique=False)

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT
                t.ticket_id,
                (
                    SELECT source_trace_id
                    FROM (
                        SELECT te.trace_id AS source_trace_id, te.created_at AS source_created_at
                        FROM ticket_events te
                        WHERE te.ticket_id = t.ticket_id
                          AND te.trace_id IS NOT NULL
                        UNION ALL
                        SELECT o.trace_id AS source_trace_id, o.queued_at AS source_created_at
                        FROM operations o
                        WHERE o.ticket_id = t.ticket_id
                          AND o.trace_id IS NOT NULL
                    ) AS trace_candidates
                    WHERE source_trace_id IS NOT NULL
                    ORDER BY source_created_at ASC NULLS LAST, source_trace_id ASC
                    LIMIT 1
                ) AS preferred_trace_id
            FROM tickets t
            """
        )
    ).mappings()

    update_stmt = sa.text(
        """
        UPDATE tickets
        SET observer_root_trace_id = :trace_id
        WHERE ticket_id = :ticket_id
        """
    )
    for row in rows:
        bind.execute(
            update_stmt,
            {
                "ticket_id": row["ticket_id"],
                "trace_id": row["preferred_trace_id"] or str(uuid.uuid4()),
            },
        )


def downgrade() -> None:
    op.drop_index("ix_tickets_observer_root_trace_id", table_name="tickets")
    op.drop_column("tickets", "observer_root_trace_id")
