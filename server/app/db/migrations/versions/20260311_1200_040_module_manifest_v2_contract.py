"""Add manifest_json and validation_json to modules.

Revision ID: 040
Revises: 039
Create Date: 2026-03-11 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("modules", sa.Column("manifest_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("modules", sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("modules", "validation_json")
    op.drop_column("modules", "manifest_json")

