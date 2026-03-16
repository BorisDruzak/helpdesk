"""Ticket priority improvements: reason 500 char limit + priority_class index.

П.2: CHECK constraints на urgency_reason/importance_reason <= 500 символов,
     ALTER COLUMN Text -> VARCHAR(500).
П.5: Выражение-индекс по custom_fields->>'priority_class'.

Revision ID: 041
Revises: 040
Create Date: 2026-03-12 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Обрезаем существующие значения до 500 символов
    op.execute(
        "UPDATE tickets SET urgency_reason = LEFT(urgency_reason, 500) "
        "WHERE urgency_reason IS NOT NULL AND LENGTH(urgency_reason) > 500"
    )
    op.execute(
        "UPDATE tickets SET importance_reason = LEFT(importance_reason, 500) "
        "WHERE importance_reason IS NOT NULL AND LENGTH(importance_reason) > 500"
    )

    # Меняем тип столбцов: Text -> VARCHAR(500) с CHECK
    op.alter_column(
        "tickets",
        "urgency_reason",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )
    op.alter_column(
        "tickets",
        "importance_reason",
        existing_type=sa.Text(),
        type_=sa.String(500),
        existing_nullable=True,
    )

    # CHECK-ограничения на длину (VARCHAR(500) уже ограничивает, но CHECK даёт явный контракт)
    op.create_check_constraint(
        "ck_tickets_urgency_reason_len",
        "tickets",
        "urgency_reason IS NULL OR char_length(urgency_reason) <= 500",
    )
    op.create_check_constraint(
        "ck_tickets_importance_reason_len",
        "tickets",
        "importance_reason IS NULL OR char_length(importance_reason) <= 500",
    )

    # Индекс по priority_class из JSONB custom_fields
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tickets_custom_fields_priority_class "
        "ON tickets ((custom_fields->>'priority_class')) "
        "WHERE custom_fields ? 'priority_class'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tickets_custom_fields_priority_class")

    op.drop_constraint("ck_tickets_importance_reason_len", "tickets", type_="check")
    op.drop_constraint("ck_tickets_urgency_reason_len", "tickets", type_="check")

    op.alter_column(
        "tickets",
        "importance_reason",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "tickets",
        "urgency_reason",
        existing_type=sa.String(500),
        type_=sa.Text(),
        existing_nullable=True,
    )
