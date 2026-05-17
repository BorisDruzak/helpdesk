"""quality loop production hardening

Revision ID: 089
Revises: 088
Create Date: 2026-05-17 15:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "089"
down_revision: Union[str, None] = "088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LATEST_FEEDBACK_INDEX = "uq_ticket_feedback_latest_per_ticket"


def _index_exists(table: str, name: str) -> bool:
    return any(idx["name"] == name for idx in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                feedback_id,
                row_number() OVER (
                    PARTITION BY ticket_id
                    ORDER BY submitted_at DESC, updated_at DESC, feedback_id DESC
                ) AS rn
            FROM ticket_feedback
            WHERE is_latest IS TRUE
        )
        UPDATE ticket_feedback tf
        SET is_latest = FALSE, updated_at = now()
        FROM ranked
        WHERE tf.feedback_id = ranked.feedback_id
          AND ranked.rn > 1
        """
    )
    if not _index_exists("ticket_feedback", LATEST_FEEDBACK_INDEX):
        op.create_index(
            LATEST_FEEDBACK_INDEX,
            "ticket_feedback",
            ["ticket_id"],
            unique=True,
            postgresql_where=sa.text("is_latest IS TRUE"),
        )


def downgrade() -> None:
    if _index_exists("ticket_feedback", LATEST_FEEDBACK_INDEX):
        op.drop_index(LATEST_FEEDBACK_INDEX, table_name="ticket_feedback")
