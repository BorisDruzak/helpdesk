"""add last_tools_changed_at to devices

Revision ID: 011
Revises: 010
Create Date: 2026-01-17 10:00:00.000000

Добавление поля last_tools_changed_at в таблицу devices для отслеживания времени последнего изменения toolset.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add last_tools_changed_at column to devices table.
    """
    op.add_column(
        'devices',
        sa.Column(
            'last_tools_changed_at',
            sa.TIMESTAMP(timezone=True),
            nullable=True
        )
    )


def downgrade() -> None:
    """
    Remove last_tools_changed_at column from devices table.
    """
    op.drop_column('devices', 'last_tools_changed_at')


