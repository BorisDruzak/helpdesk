"""add auth tokens tables

Revision ID: 012
Revises: 011
Create Date: 2026-01-18 10:00:00.000000

Добавление таблиц для аутентификации:
- agent_tokens: токены агентов (SHA256 hash, не raw token)
- ui_tokens: токены UI пользователей (SHA256 hash, не raw token)
- auth_sessions: сессии для Phase 2 (подготовка)

КРИТИЧНО: Токены хранятся как SHA256 hash для безопасности.
Поддержка token rotation с grace period (5 минут).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

# revision identifiers, used by Alembic.
revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create auth tokens tables:
    - agent_tokens: для токенов агентов
    - ui_tokens: для токенов UI пользователей
    - auth_sessions: для session-based auth (Phase 2)
    """
    
    # Create agent_tokens table
    op.create_table(
        'agent_tokens',
        sa.Column('token_hash', sa.String(64), nullable=False),  # SHA256 hash
        sa.Column('token_prefix', sa.String(8), nullable=False),  # First 8 chars for logs
        sa.Column('device_id', sa.String(36), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('revoked_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('replaced_by_token_hash', sa.String(64), nullable=True),  # Rotation support
        sa.Column('rotated_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_used_at', TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('token_hash'),
        sa.ForeignKeyConstraint(
            ['device_id'],
            ['devices.device_id'],
            ondelete='CASCADE'
        ),
        # Self-referencing foreign key for rotation (deferred, added after table creation)
    )
    
    # Create indexes for agent_tokens
    op.create_index('ix_agent_tokens_device_id', 'agent_tokens', ['device_id'])
    # Partial index for active tokens (not revoked)
    op.execute("""
        CREATE INDEX ix_agent_tokens_active 
        ON agent_tokens(device_id, revoked_at) 
        WHERE revoked_at IS NULL
    """)
    op.create_index('ix_agent_tokens_prefix', 'agent_tokens', ['token_prefix'])
    
    # Add self-referencing foreign key for rotation (after table creation)
    op.create_foreign_key(
        'fk_agent_tokens_replaced_by',
        'agent_tokens',
        'agent_tokens',
        ['replaced_by_token_hash'],
        ['token_hash']
    )
    
    # Create ui_tokens table
    op.create_table(
        'ui_tokens',
        sa.Column('token_hash', sa.String(64), nullable=False),  # SHA256 hash
        sa.Column('token_prefix', sa.String(8), nullable=False),  # First 8 chars for logs
        sa.Column('user_login', sa.String(100), nullable=False),
        sa.Column('actor_role', sa.String(20), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('revoked_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('replaced_by_token_hash', sa.String(64), nullable=True),  # Rotation support
        sa.Column('rotated_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_used_at', TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('token_hash'),
    )
    
    # Create indexes for ui_tokens
    op.create_index('ix_ui_tokens_user_login', 'ui_tokens', ['user_login'])
    # Partial index for active tokens (not revoked)
    op.execute("""
        CREATE INDEX ix_ui_tokens_active 
        ON ui_tokens(user_login, revoked_at) 
        WHERE revoked_at IS NULL
    """)
    op.create_index('ix_ui_tokens_prefix', 'ui_tokens', ['token_prefix'])
    
    # Add self-referencing foreign key for rotation (after table creation)
    op.create_foreign_key(
        'fk_ui_tokens_replaced_by',
        'ui_tokens',
        'ui_tokens',
        ['replaced_by_token_hash'],
        ['token_hash']
    )
    
    # Create auth_sessions table (for Phase 2)
    op.create_table(
        'auth_sessions',
        sa.Column('session_id', sa.String(64), nullable=False),
        sa.Column('user_login', sa.String(100), nullable=False),
        sa.Column('actor_role', sa.String(20), nullable=False),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_used_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),  # IPv6 support
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('session_id'),
    )
    
    # Create indexes for auth_sessions
    op.create_index('ix_auth_sessions_user_login', 'auth_sessions', ['user_login'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])


def downgrade() -> None:
    """
    Drop auth tokens tables.
    """
    op.drop_index('ix_auth_sessions_expires_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_user_login', table_name='auth_sessions')
    op.drop_table('auth_sessions')
    
    # Drop foreign keys first
    op.drop_constraint('fk_ui_tokens_replaced_by', 'ui_tokens', type_='foreignkey')
    op.drop_index('ix_ui_tokens_prefix', table_name='ui_tokens')
    op.execute('DROP INDEX IF EXISTS ix_ui_tokens_active')
    op.drop_index('ix_ui_tokens_user_login', table_name='ui_tokens')
    op.drop_table('ui_tokens')
    
    # Drop foreign keys first
    op.drop_constraint('fk_agent_tokens_replaced_by', 'agent_tokens', type_='foreignkey')
    op.drop_index('ix_agent_tokens_prefix', table_name='agent_tokens')
    op.execute('DROP INDEX IF EXISTS ix_agent_tokens_active')
    op.drop_index('ix_agent_tokens_device_id', table_name='agent_tokens')
    op.drop_table('agent_tokens')

