"""add consent_decisions table and denied status

Revision ID: 013
Revises: 012
Create Date: 2026-01-19 10:00:00.000000

Phase 5: Server-Side Consent Flow
- Добавление таблицы consent_decisions для отслеживания approve/deny решений
- Добавление статуса 'denied' в operations (терминальный статус для denied consent)
- Статус 'denied' отдельно от 'failed' для UX и аналитики
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create consent_decisions table.
    
    Таблица для отслеживания решений по операциям, требующим согласия.
    """
    op.create_table(
        'consent_decisions',
        # Primary key (foreign key to operations)
        sa.Column('operation_id', sa.String(36), primary_key=True),
        
        # Decision tracking
        sa.Column('decision', sa.String(10), nullable=False),  # 'approved' or 'denied'
        sa.Column('decided_by', sa.String(100), nullable=False),  # actor_role or user_login
        sa.Column('decided_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reason', sa.Text, nullable=True),
        
        # Foreign key constraint
        sa.ForeignKeyConstraint(
            ['operation_id'],
            ['operations.operation_id'],
            ondelete='CASCADE'
        ),
        
        # Check constraint
        sa.CheckConstraint(
            "decision IN ('approved', 'denied')",
            name='ck_consent_decisions_decision'
        ),
    )
    
    # Indexes
    op.create_index('ix_consent_decisions_decided_at', 'consent_decisions', ['decided_at'])
    
    # Примечание: Статус 'denied' уже поддерживается в operations.status (String(30))
    # Нет необходимости в ALTER TABLE, так как CHECK constraint не был создан в миграции 006
    # Статус 'denied' будет использоваться через application logic


def downgrade() -> None:
    """
    Drop consent_decisions table.
    """
    op.drop_index('ix_consent_decisions_decided_at', table_name='consent_decisions')
    op.drop_table('consent_decisions')


