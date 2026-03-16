"""add device_outbox table for Phase C

Revision ID: 003
Revises: 002
Create Date: 2026-01-10 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create device_outbox table for server-side command outbox.
    
    This table enables reliable command delivery with:
    - Persistence before sending
    - Lifecycle tracking (pending -> sent -> delivered/failed)
    - Retry logic with configurable max_retries
    - Error tracking for failed commands
    """
    
    # Create device_outbox table
    op.create_table(
        'device_outbox',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('command_id', sa.String(length=36), nullable=False),
        sa.Column('command', sa.Text(), nullable=False),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        
        # Lifecycle tracking
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        
        # Metadata
        sa.Column('request_id', sa.String(length=36), nullable=True),
        sa.Column('trace_id', sa.String(length=36), nullable=True),
        sa.Column('actor_role', sa.String(length=20), nullable=False, server_default='user'),
        
        # Retry tracking
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        
        # Timestamps
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('sent_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('delivered_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('failed_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        
        # Error tracking
        sa.Column('error_code', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for device_outbox
    op.create_index('ix_device_outbox_device_id', 'device_outbox', ['device_id'])
    op.create_index('ix_device_outbox_command_id', 'device_outbox', ['command_id'])
    op.create_index('ix_device_outbox_status', 'device_outbox', ['status'])
    op.create_index('ix_device_outbox_device_id_status', 'device_outbox', ['device_id', 'status'])
    op.create_index('ix_device_outbox_command_id_status', 'device_outbox', ['command_id', 'status'])
    op.create_index('ix_device_outbox_created_at', 'device_outbox', ['created_at'])
    op.create_index('ix_device_outbox_trace_id', 'device_outbox', ['trace_id'])


def downgrade() -> None:
    """
    Drop device_outbox table and its indexes.
    """
    op.drop_index('ix_device_outbox_trace_id', table_name='device_outbox')
    op.drop_index('ix_device_outbox_created_at', table_name='device_outbox')
    op.drop_index('ix_device_outbox_command_id_status', table_name='device_outbox')
    op.drop_index('ix_device_outbox_device_id_status', table_name='device_outbox')
    op.drop_index('ix_device_outbox_status', table_name='device_outbox')
    op.drop_index('ix_device_outbox_command_id', table_name='device_outbox')
    op.drop_index('ix_device_outbox_device_id', table_name='device_outbox')
    op.drop_table('device_outbox')
