"""add unique index for tool_call_started events with operation_id

Revision ID: 009
Revises: 008
Create Date: 2026-01-15 10:00:00.000000

Добавление UNIQUE индекса для идемпотентности tool_call_started событий.

Инвариант: tool_call_started всегда создаётся сервером до отправки run_tool команды.
Корреляция по operation_id (call_id - legacy, не используется для поиска).

UNIQUE индекс: (ticket_id, operation_id, event_type) WHERE operation_id IS NOT NULL
Это гарантирует, что для каждой операции может быть только одно tool_call_started событие.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add UNIQUE index for tool_call_started events with operation_id.
    """
    # КРИТИЧНО: Создаём частичный UNIQUE индекс только для событий с operation_id
    # Это гарантирует идемпотентность: для каждой операции может быть только одно tool_call_started
    op.execute("""
        CREATE UNIQUE INDEX uq_ticket_events_ticket_operation_type 
        ON ticket_events (ticket_id, operation_id, event_type)
        WHERE operation_id IS NOT NULL
    """)


def downgrade() -> None:
    """
    Remove UNIQUE index for tool_call_started events.
    """
    op.drop_index('uq_ticket_events_ticket_operation_type', table_name='ticket_events')


