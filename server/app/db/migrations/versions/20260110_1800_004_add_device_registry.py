"""add device registry

Revision ID: 004_add_device_registry
Revises: 20260110_1500_003_add_device_outbox
Create Date: 2026-01-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_device_registry'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('first_seen_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_seen_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_handshake_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('last_toolset_refresh_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('protocol_version', sa.Text(), nullable=False),
        sa.Column('agent_version', sa.Text(), nullable=False),
        sa.Column('hostname', sa.Text(), nullable=True),
        sa.Column('os', sa.Text(), nullable=True),
        sa.Column('capabilities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('tools_version', sa.Text(), nullable=True),
        sa.Column('current_toolset_hash', sa.Text(), nullable=True),
        sa.Column('current_toolset_snapshot_id', sa.BigInteger(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('device_id')
    )
    op.create_index('ix_devices_agent_version', 'devices', ['agent_version'], unique=False)
    op.create_index('ix_devices_last_seen_at', 'devices', ['last_seen_at'], unique=False)
    op.create_index('ix_devices_last_toolset_refresh_at', 'devices', ['last_toolset_refresh_at'], unique=False)

    # Create device_config table
    op.create_table(
        'device_config',
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('desired_revision', sa.Integer(), nullable=False),
        sa.Column('desired_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('applied_revision', sa.Integer(), nullable=True),
        sa.Column('applied_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_apply_status', sa.Text(), nullable=True),
        sa.Column('last_apply_error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('device_id')
    )

    # Create device_toolset_snapshots table
    op.create_table(
        'device_toolset_snapshots',
        sa.Column('snapshot_id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('device_id', sa.String(length=36), nullable=False),
        sa.Column('captured_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('agent_version', sa.Text(), nullable=False),
        sa.Column('toolset_hash', sa.Text(), nullable=False),
        sa.Column('toolset_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('tool_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('snapshot_id'),
        # КРИТИЧНО: UNIQUE constraint для предотвращения дубликатов snapshots
        sa.UniqueConstraint('device_id', 'toolset_hash', name='uq_device_toolset_snapshots_device_hash')
    )
    op.create_index('ix_toolset_snapshots_device_captured', 'device_toolset_snapshots', ['device_id', 'captured_at'], unique=False)
    op.create_index('ix_toolset_snapshots_device_hash', 'device_toolset_snapshots', ['device_id', 'toolset_hash'], unique=False)


def downgrade() -> None:
    # Drop device_toolset_snapshots table
    op.drop_index('ix_toolset_snapshots_device_hash', table_name='device_toolset_snapshots')
    op.drop_index('ix_toolset_snapshots_device_captured', table_name='device_toolset_snapshots')
    op.drop_table('device_toolset_snapshots')

    # Drop device_config table
    op.drop_table('device_config')

    # Drop devices table
    op.drop_index('ix_devices_last_toolset_refresh_at', table_name='devices')
    op.drop_index('ix_devices_last_seen_at', table_name='devices')
    op.drop_index('ix_devices_agent_version', table_name='devices')
    op.drop_table('devices')
