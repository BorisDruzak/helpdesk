"""add cancel fields to operations table

Revision ID: 008
Revises: 007
Create Date: 2026-01-14 12:00:00.000000

Добавление полей для поддержки отмены операций (cancel operations).

Поля:
- status_before_cancel: Исходный статус перед cancel_requested (для rollback)
- cancel_target_operation_id: Для cancel-операций, ссылка на таргет операцию
- active_cancel_operation_id: Для target-op, ссылка на активную cancel-op (для идемпотентности)
- cancel_reason: Причина отмены
- cancel_requested_at: Время запроса отмены
- canceled_at: Время подтверждения отмены

Индексы:
- ix_operations_cancel_target: на cancel_target_operation_id (для поиска связанных cancel-op)
- ix_operations_active_cancel: на active_cancel_operation_id (для быстрого lookup)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add cancel fields to operations table.
    """
    # Add cancel fields
    op.add_column(
        'operations',
        sa.Column('status_before_cancel', sa.Text(), nullable=True)
    )
    op.add_column(
        'operations',
        sa.Column('cancel_target_operation_id', sa.String(36), nullable=True)
    )
    op.add_column(
        'operations',
        sa.Column('active_cancel_operation_id', sa.String(36), nullable=True)
    )
    op.add_column(
        'operations',
        sa.Column('cancel_reason', sa.Text(), nullable=True)
    )
    op.add_column(
        'operations',
        sa.Column('cancel_requested_at', TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        'operations',
        sa.Column('canceled_at', TIMESTAMP(timezone=True), nullable=True)
    )
    
    # Create indexes
    op.create_index(
        'ix_operations_cancel_target',
        'operations',
        ['cancel_target_operation_id']
    )
    op.create_index(
        'ix_operations_active_cancel',
        'operations',
        ['active_cancel_operation_id']
    )


def downgrade() -> None:
    """
    Remove cancel fields from operations table.
    """
    # Drop indexes
    op.drop_index('ix_operations_active_cancel', table_name='operations')
    op.drop_index('ix_operations_cancel_target', table_name='operations')
    
    # Drop columns
    op.drop_column('operations', 'canceled_at')
    op.drop_column('operations', 'cancel_requested_at')
    op.drop_column('operations', 'cancel_reason')
    op.drop_column('operations', 'active_cancel_operation_id')
    op.drop_column('operations', 'cancel_target_operation_id')
    op.drop_column('operations', 'status_before_cancel')


