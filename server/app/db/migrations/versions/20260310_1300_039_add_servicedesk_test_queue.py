"""Ensure default public test queue exists and is active.

Revision ID: 039
Revises: 038
Create Date: 2026-03-10 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ticket_queues (code, name, is_triage, is_active)
        VALUES ('servicedesk_test', 'ServiceDesk Test', false, true)
        ON CONFLICT (code) DO UPDATE
        SET
            name = EXCLUDED.name,
            is_active = true
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE ticket_queues
        SET is_active = false
        WHERE code = 'servicedesk_test'
        """
    )

