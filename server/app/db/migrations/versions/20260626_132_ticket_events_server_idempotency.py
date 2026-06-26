"""Add DB idempotency guards for server ticket events.

Revision ID: 132
Revises: 131
Create Date: 2026-06-26 17:30:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "132"
down_revision: Union[str, None] = "131"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("ticket_events"):
        return

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY ticket_id, event_id
                        ORDER BY created_at ASC, id ASC
                    ) AS rn
                FROM ticket_events
                WHERE agent_seq IS NULL
                  AND event_id IS NOT NULL
                  AND btrim(event_id) <> ''
            )
            DELETE FROM ticket_events te
            USING ranked r
            WHERE te.id = r.id
              AND r.rn > 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY ticket_id, event_type, payload ->> 'message_id'
                        ORDER BY created_at ASC, id ASC
                    ) AS rn
                FROM ticket_events
                WHERE agent_seq IS NULL
                  AND btrim(COALESCE(payload ->> 'message_id', '')) <> ''
            )
            DELETE FROM ticket_events te
            USING ranked r
            WHERE te.id = r.id
              AND r.rn > 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ticket_events_server_event_id
                ON ticket_events (ticket_id, event_id)
                WHERE agent_seq IS NULL
                  AND event_id IS NOT NULL
                  AND btrim(event_id) <> ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ticket_events_server_message_id
                ON ticket_events (ticket_id, event_type, (payload ->> 'message_id'))
                WHERE agent_seq IS NULL
                  AND btrim(COALESCE(payload ->> 'message_id', '')) <> ''
            """
        )
    )


def downgrade() -> None:
    if not _has_table("ticket_events"):
        return
    op.execute(sa.text("DROP INDEX IF EXISTS uq_ticket_events_server_message_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_ticket_events_server_event_id"))
