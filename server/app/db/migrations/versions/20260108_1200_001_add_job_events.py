"""add job_events table

Revision ID: 001
Revises: 
Create Date: 2026-01-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create job_events table with indexes and constraints.
    """
    # Create job_events table
    op.create_table(
        'job_events',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column('job_id', sa.Text(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=True),
        sa.Column('ts', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('message_id', sa.Text(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('ix_job_events_job_id', 'job_events', ['job_id'])
    op.create_index('ix_job_events_job_id_seq', 'job_events', ['job_id', 'seq'])
    op.create_index('ix_job_events_job_id_ts', 'job_events', ['job_id', 'ts'])
    
    # Create unique constraint for deduplication
    # Only enforces uniqueness where message_id IS NOT NULL
    op.create_index(
        'uq_job_events_job_id_message_id_not_null',
        'job_events',
        ['job_id', 'message_id'],
        unique=True,
        postgresql_where=sa.text('message_id IS NOT NULL')
    )


def downgrade() -> None:
    op.drop_index('uq_job_events_job_id_message_id_not_null', table_name='job_events')
    op.drop_index('ix_job_events_job_id_ts', table_name='job_events')
    op.drop_index('ix_job_events_job_id_seq', table_name='job_events')
    op.drop_index('ix_job_events_job_id', table_name='job_events')
    op.drop_table('job_events')


