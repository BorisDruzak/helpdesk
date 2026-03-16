"""add operations table

Revision ID: 006
Revises: 005
Create Date: 2026-01-12 10:00:00.000000

Создание таблицы operations для отслеживания lifecycle операций (commands/tool_calls).

Таблица operations - это материализованное состояние операций, синхронизированное с событиями.
Все обновления operations выполняются в тех же транзакциях, где пишутся события.

Статусы операций:
- queued: Команда добавлена в device_outbox
- sent: Команда отправлена агенту по WebSocket
- accepted: Агент подтвердил получение через command_ack
- running: Началось выполнение (tool_call_started/agent_action/collect_progress)
- waiting_consent: Ожидается подтверждение пользователя (consent_required)
- succeeded: Операция завершена успешно
- failed: Операция завершена с ошибкой
- timed_out: Превышен таймаут (delivery/execution/consent)
- cancel_requested: Запрошена отмена (POST /api/operations/{id}/cancel)
- canceled: Отмена подтверждена агентом

Инвариант: operation_id = request_id = command_id (один UUID на всю операцию end-to-end)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create operations table.
    """
    op.create_table(
        'operations',
        # Primary key
        sa.Column('operation_id', sa.String(36), primary_key=True),
        
        # Device/Ticket/Job context
        sa.Column('device_id', sa.String(36), nullable=False),
        sa.Column('ticket_id', sa.String(36), nullable=True),
        sa.Column('job_id', sa.String(36), nullable=True),
        
        # Operation metadata
        sa.Column('kind', sa.String(50), nullable=False),
        sa.Column('tool_name', sa.Text, nullable=True),
        sa.Column('actor_role', sa.String(20), nullable=False),
        sa.Column('trace_id', sa.String(36), nullable=False),
        
        # Status tracking
        sa.Column('status', sa.String(30), nullable=False),
        
        # SLA tracking
        sa.Column('deadline_at', TIMESTAMP(timezone=True), nullable=True),
        
        # Lifecycle timestamps
        sa.Column('queued_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('sent_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('accepted_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('started_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('finished_at', TIMESTAMP(timezone=True), nullable=True),
        
        # Retry tracking
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),
        
        # Result tracking
        sa.Column('error_code', sa.Text, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('result_summary', sa.Text, nullable=True),
        sa.Column('result_event_id', sa.BigInteger, nullable=True),
    )
    
    # Indexes
    op.create_index('ix_operations_device_id', 'operations', ['device_id'])
    op.create_index('ix_operations_ticket_id', 'operations', ['ticket_id'])
    op.create_index('ix_operations_trace_id', 'operations', ['trace_id'])
    op.create_index('ix_operations_status', 'operations', ['status'])
    op.create_index('ix_operations_status_queued_at', 'operations', ['status', 'queued_at'])
    op.create_index('ix_operations_device_id_status', 'operations', ['device_id', 'status'])
    op.create_index('ix_operations_deadline_at', 'operations', ['deadline_at'])


def downgrade() -> None:
    """
    Drop operations table.
    """
    op.drop_table('operations')
