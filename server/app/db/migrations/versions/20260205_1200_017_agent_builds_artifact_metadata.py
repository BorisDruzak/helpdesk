"""agent_builds: artifact_filename, archive_type, mime_type

Revision ID: 017
Revises: 016
Create Date: 2026-02-05 12:00:00.000000

Support zip and tar.gz; storage_path may end with .zip or .tar.gz.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_builds", sa.Column("artifact_filename", sa.Text(), nullable=True))
    op.add_column("agent_builds", sa.Column("archive_type", sa.String(20), nullable=True))
    op.add_column("agent_builds", sa.Column("mime_type", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_builds", "mime_type")
    op.drop_column("agent_builds", "archive_type")
    op.drop_column("agent_builds", "artifact_filename")
