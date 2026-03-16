"""make agent_seq nullable and update constraints for server-originated events

Revision ID: 005
Revises: 004
Create Date: 2026-01-10 19:00:00.000000

ВАЖНО: Эта миграция обновляет ticket_events для поддержки server-originated событий.

Изменения:
1. agent_seq становится nullable (для server messages)
2. UNIQUE constraint становится частичным (только для agent_seq IS NOT NULL)
3. Добавлен composite index для фильтрации по event_type

Семантика:
- agent_seq = int: Agent-originated события (монотонный seq от агента)
- agent_seq = NULL: Server-originated события (support/user messages)

Сортировка событий: ORDER BY agent_seq ASC NULLS LAST, created_at ASC, id ASC
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004_add_device_registry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Make agent_seq nullable and update UNIQUE constraint to support server-originated events.
    
    Steps:
    1. Drop old UNIQUE constraint
    2. Alter agent_seq column to nullable
    3. Create partial UNIQUE constraint (only for agent_seq IS NOT NULL)
    4. Add composite index for event_type filtering
    """
    
    # Step 1: Drop old UNIQUE constraint
    op.drop_constraint(
        'uq_ticket_events_device_ticket_seq',
        'ticket_events',
        type_='unique'
    )
    
    # Step 2: Make agent_seq nullable
    op.alter_column(
        'ticket_events',
        'agent_seq',
        existing_type=sa.Integer(),
        nullable=True
    )
    
    # Step 3: Create partial UNIQUE constraint (only for agent_seq IS NOT NULL)
    # This allows multiple events with agent_seq = NULL (server-originated)
    # but maintains uniqueness for agent events
    # В PostgreSQL частичный UNIQUE constraint создается через CREATE UNIQUE INDEX
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ticket_events_device_ticket_seq
        ON ticket_events (device_id, ticket_id, agent_seq)
        WHERE agent_seq IS NOT NULL
        """
    )
    
    # Step 4: Add composite index for efficient event_type filtering
    op.create_index(
        'ix_ticket_events_ticket_type_seq',
        'ticket_events',
        ['ticket_id', 'event_type', 'agent_seq']
    )


def downgrade() -> None:
    """
    Revert changes: make agent_seq NOT NULL again and restore original constraint.
    
    WARNING: This will fail if there are any rows with agent_seq = NULL.
    You must delete or update those rows before downgrading.
    """
    
    # Step 1: Drop composite index
    op.drop_index('ix_ticket_events_ticket_type_seq', table_name='ticket_events')
    
    # Step 2: Drop partial UNIQUE index (создано через CREATE UNIQUE INDEX)
    op.drop_index(
        'uq_ticket_events_device_ticket_seq',
        table_name='ticket_events'
    )
    
    # Step 3: Make agent_seq NOT NULL
    # WARNING: This will fail if there are NULL values
    op.alter_column(
        'ticket_events',
        'agent_seq',
        existing_type=sa.Integer(),
        nullable=False
    )
    
    # Step 4: Recreate original UNIQUE constraint
    op.create_unique_constraint(
        'uq_ticket_events_device_ticket_seq',
        'ticket_events',
        ['device_id', 'ticket_id', 'agent_seq']
    )
