"""Record Endpoint Platform as the sole agent control-plane authority.

Revision ID: 143
Revises: 142
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "143"
down_revision = "142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO server_config (key, value)
            VALUES ('endpoint_agent_control_plane_authority', 'endpoint_platform')
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError("Revision 143 is forward-only; roll back the application release instead.")
