"""add download_audit table

Revision ID: 014
Revises: 013
Create Date: 2026-01-20 10:00:00.000000

Phase 6: Module Download Protection
- Добавление таблицы download_audit для аудита скачиваний модулей
- КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token
- Индексы для быстрого поиска по токену, модулю и времени
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create download_audit table.
    
    Таблица для аудита всех запросов на скачивание модулей.
    КРИТИЧНО: Сохраняется token_hash (SHA256), не raw token.
    """
    op.create_table(
        'download_audit',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('token_hash', sa.String(64), nullable=False),  # SHA256 hash
        sa.Column('token_prefix', sa.String(8), nullable=True),  # First 8 chars for logs
        sa.Column('module_name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('downloaded_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('ip_address', sa.String(45), nullable=True),  # IPv6 support
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_download_audit_token_hash', 'download_audit', ['token_hash'])
    op.create_index('ix_download_audit_module', 'download_audit', ['module_name', 'version'])
    op.create_index('ix_download_audit_downloaded_at', 'download_audit', ['downloaded_at'])


def downgrade() -> None:
    """
    Drop download_audit table.
    """
    op.drop_index('ix_download_audit_downloaded_at', table_name='download_audit')
    op.drop_index('ix_download_audit_module', table_name='download_audit')
    op.drop_index('ix_download_audit_token_hash', table_name='download_audit')
    op.drop_table('download_audit')


