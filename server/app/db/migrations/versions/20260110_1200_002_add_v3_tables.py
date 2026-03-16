"""add V3 protocol tables (tickets, ticket_events, device_events)

Revision ID: 002
Revises: 001
Create Date: 2026-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create Protocol V3 tables:
    - tickets: Support tickets bound to devices
    - ticket_events: Events for tickets with agent_seq ordering
    - device_events: Device events without ticket binding
    """
    
    # Create tickets table
    op.create_table(
        'tickets',
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('ticket_id')
    )
    
    # Create indexes for tickets
    op.create_index('ix_tickets_device_id', 'tickets', ['device_id'])
    op.create_index('ix_tickets_status', 'tickets', ['status'])
    op.create_index('ix_tickets_device_id_status', 'tickets', ['device_id', 'status'])
    
    # Create ticket_events table
    op.create_table(
        'ticket_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('agent_seq', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('trace_id', sa.String(length=36), nullable=True),
        sa.Column('event_id', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint for deduplication
    op.create_unique_constraint(
        'uq_ticket_events_device_ticket_seq',
        'ticket_events',
        ['device_id', 'ticket_id', 'agent_seq']
    )
    
    # Create indexes for ticket_events
    op.create_index('ix_ticket_events_ticket_id', 'ticket_events', ['ticket_id'])
    op.create_index('ix_ticket_events_ticket_id_agent_seq', 'ticket_events', ['ticket_id', 'agent_seq'])
    op.create_index('ix_ticket_events_trace_id', 'ticket_events', ['trace_id'])
    
    # Create device_events table
    op.create_table(
        'device_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('device_seq', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('trace_id', sa.String(length=36), nullable=True),
        sa.Column('event_id', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique constraint for deduplication
    op.create_unique_constraint(
        'uq_device_events_device_seq',
        'device_events',
        ['device_id', 'device_seq']
    )
    
    # Create indexes for device_events
    op.create_index('ix_device_events_device_id', 'device_events', ['device_id'])
    op.create_index('ix_device_events_device_id_device_seq', 'device_events', ['device_id', 'device_seq'])
    op.create_index('ix_device_events_trace_id', 'device_events', ['trace_id'])


def downgrade() -> None:
    """
    Drop Protocol V3 tables and their indexes.
    """
    # Drop device_events
    op.drop_index('ix_device_events_trace_id', table_name='device_events')
    op.drop_index('ix_device_events_device_id_device_seq', table_name='device_events')
    op.drop_index('ix_device_events_device_id', table_name='device_events')
    op.drop_constraint('uq_device_events_device_seq', 'device_events', type_='unique')
    op.drop_table('device_events')
    
    # Drop ticket_events
    op.drop_index('ix_ticket_events_trace_id', table_name='ticket_events')
    op.drop_index('ix_ticket_events_ticket_id_agent_seq', table_name='ticket_events')
    op.drop_index('ix_ticket_events_ticket_id', table_name='ticket_events')
    op.drop_constraint('uq_ticket_events_device_ticket_seq', 'ticket_events', type_='unique')
    op.drop_table('ticket_events')
    
    # Drop tickets
    op.drop_index('ix_tickets_device_id_status', table_name='tickets')
    op.drop_index('ix_tickets_status', table_name='tickets')
    op.drop_index('ix_tickets_device_id', table_name='tickets')
    op.drop_table('tickets')
