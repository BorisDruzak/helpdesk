"""add modules registry tables

Revision ID: 010
Revises: 009
Create Date: 2026-01-16 10:00:00.000000

Добавление таблиц modules и device_modules для server-side registry модулей.
- modules: реестр загруженных модулей (ZIP артефакты)
- device_modules: реестр установленных модулей на устройствах
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create modules and device_modules tables.
    """
    # Create modules table
    op.create_table(
        'modules',
        sa.Column('module_name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('uploaded_by', sa.String(20), nullable=False, server_default='admin'),
        sa.Column('manifest_summary', JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('module_name', 'version'),
    )
    
    # Create indexes for modules
    op.create_index('ix_modules_sha256', 'modules', ['sha256'], unique=True)
    op.create_index('ix_modules_created_at', 'modules', ['created_at'])
    
    # Create device_modules table
    op.create_table(
        'device_modules',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('device_id', sa.String(36), nullable=False),
        sa.Column('module_name', sa.String(100), nullable=False),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('installed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('installed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('activated_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_updated_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('state', sa.String(20), nullable=False, server_default='installed'),
        sa.Column('last_error_code', sa.String(50), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('device_id', 'module_name', 'version', name='uq_device_modules_device_name_version'),
    )
    
    # Create indexes for device_modules
    op.create_index('ix_device_modules_device_id', 'device_modules', ['device_id'])
    op.create_index('ix_device_modules_device_active', 'device_modules', ['device_id', 'active'])
    op.create_index('ix_device_modules_device_state', 'device_modules', ['device_id', 'state'])
    op.create_index('ix_device_modules_module_name', 'device_modules', ['module_name'])


def downgrade() -> None:
    """
    Drop modules and device_modules tables.
    """
    op.drop_index('ix_device_modules_module_name', table_name='device_modules')
    op.drop_index('ix_device_modules_device_state', table_name='device_modules')
    op.drop_index('ix_device_modules_device_active', table_name='device_modules')
    op.drop_index('ix_device_modules_device_id', table_name='device_modules')
    op.drop_table('device_modules')
    
    op.drop_index('ix_modules_created_at', table_name='modules')
    op.drop_index('ix_modules_sha256', table_name='modules')
    op.drop_table('modules')


