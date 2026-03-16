"""Stage 10.1: ticket_code — человекочитаемый код тикета (T-000001)

Revision ID: 031
Revises: 030
Create Date: 2026-02-18 10:00:00.000000

- tickets.ticket_code: VARCHAR(20) UNIQUE NOT NULL, формат T-000001
- Последовательность ticket_code_seq для генерации номеров
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_code_seq")
    op.add_column(
        "tickets",
        sa.Column("ticket_code", sa.String(20), nullable=True),
    )
    # Backfill: присвоить T-000001, T-000002, ... по порядку created_at
    op.execute("""
        WITH numbered AS (
            SELECT ticket_id, row_number() OVER (ORDER BY created_at) AS n
            FROM tickets
        )
        UPDATE tickets t
        SET ticket_code = 'T-' || lpad(n::text, 6, '0')
        FROM numbered n
        WHERE t.ticket_id = n.ticket_id
    """)
    op.alter_column(
        "tickets",
        "ticket_code",
        existing_type=sa.String(20),
        nullable=False,
    )
    op.create_unique_constraint("uq_tickets_ticket_code", "tickets", ["ticket_code"])
    # Синхронизировать sequence с максимальным номером
    op.execute("""
        SELECT setval(
            'ticket_code_seq',
            COALESCE((SELECT MAX(CAST(SUBSTRING(ticket_code FROM 4) AS INTEGER)) FROM tickets), 1),
            EXISTS(SELECT 1 FROM tickets)
        )
    """)
    # Default для новых строк
    op.alter_column(
        "tickets",
        "ticket_code",
        existing_type=sa.String(20),
        server_default=sa.text("'T-' || lpad(nextval('ticket_code_seq')::text, 6, '0')"),
    )


def downgrade() -> None:
    op.alter_column(
        "tickets",
        "ticket_code",
        server_default=None,
    )
    op.drop_constraint("uq_tickets_ticket_code", "tickets", type_="unique")
    op.drop_column("tickets", "ticket_code")
    op.execute("DROP SEQUENCE IF EXISTS ticket_code_seq")
