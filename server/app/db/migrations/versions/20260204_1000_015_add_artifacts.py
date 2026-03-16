"""add artifacts table

Revision ID: 015
Revises: 014
Create Date: 2026-02-04 10:00:00.000000

Этап 1 (план скриншот/запись экрана): таблица artifacts для хранения
метаданных загруженных файлов (скриншоты, видео). Файлы на диске в UPLOAD_DIR.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = '015'
down_revision: Union[str, None] = '014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'artifacts',
        sa.Column('artifact_id', sa.String(36), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('original_name', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('kind', sa.String(50), nullable=True),
        sa.Column('device_id', sa.String(36), nullable=False),
        sa.Column('ticket_id', sa.String(36), nullable=True),
        sa.Column('operation_id', sa.String(36), nullable=True),
        sa.Column('expires_at', TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('artifact_id')
    )
    op.create_index('ix_artifacts_device_id', 'artifacts', ['device_id'])
    op.create_index('ix_artifacts_ticket_id', 'artifacts', ['ticket_id'])
    op.create_index('ix_artifacts_operation_id', 'artifacts', ['operation_id'])
    op.create_index('ix_artifacts_expires_at', 'artifacts', ['expires_at'])
    op.create_index('ix_artifacts_sha256', 'artifacts', ['sha256'])


def downgrade() -> None:
    op.drop_index('ix_artifacts_sha256', table_name='artifacts')
    op.drop_index('ix_artifacts_expires_at', table_name='artifacts')
    op.drop_index('ix_artifacts_operation_id', table_name='artifacts')
    op.drop_index('ix_artifacts_ticket_id', table_name='artifacts')
    op.drop_index('ix_artifacts_device_id', table_name='artifacts')
    op.drop_table('artifacts')
