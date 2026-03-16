"""add operation_id to device_outbox, ticket_events, device_events

Revision ID: 007
Revises: 006
Create Date: 2026-01-12 10:30:00.000000

Добавление operation_id в device_outbox, ticket_events и device_events.

Инвариант: operation_id = request_id = command_id (один UUID на всю операцию end-to-end)

Поля operation_id:
- device_outbox.operation_id: Для связи команды с операцией
- ticket_events.operation_id: Для связи событий тикета с операцией
- device_events.operation_id: Для связи событий устройства с операцией

Все поля nullable для обратной совместимости с существующими данными.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add operation_id column to device_outbox, ticket_events, device_events.
    """
    # Add operation_id to device_outbox
    op.add_column(
        'device_outbox',
        sa.Column('operation_id', sa.String(36), nullable=True)
    )
    op.create_index(
        'ix_device_outbox_operation_id',
        'device_outbox',
        ['operation_id']
    )
    
    # Add operation_id to ticket_events
    op.add_column(
        'ticket_events',
        sa.Column('operation_id', sa.String(36), nullable=True)
    )
    op.create_index(
        'ix_ticket_events_operation_id',
        'ticket_events',
        ['operation_id']
    )
    
    # Add operation_id to device_events
    op.add_column(
        'device_events',
        sa.Column('operation_id', sa.String(36), nullable=True)
    )
    op.create_index(
        'ix_device_events_operation_id',
        'device_events',
        ['operation_id']
    )


def downgrade() -> None:
    """
    Remove operation_id column from device_outbox, ticket_events, device_events.
    """
    # Remove from device_events
    op.drop_index('ix_device_events_operation_id', table_name='device_events')
    op.drop_column('device_events', 'operation_id')
    
    # Remove from ticket_events
    op.drop_index('ix_ticket_events_operation_id', table_name='ticket_events')
    op.drop_column('ticket_events', 'operation_id')
    
    # Remove from device_outbox
    op.drop_index('ix_device_outbox_operation_id', table_name='device_outbox')
    op.drop_column('device_outbox', 'operation_id')
