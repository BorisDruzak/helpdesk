"""Add queue auto-assign flag.

Revision ID: 050
Revises: 049
Create Date: 2026-03-31 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "050"
down_revision: Union[str, None] = "049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("ticket_queues")}
    if "auto_assign_enabled" not in columns:
        op.add_column(
            "ticket_queues",
            sa.Column(
                "auto_assign_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("ticket_queues")}
    if "auto_assign_enabled" in columns:
        op.drop_column("ticket_queues", "auto_assign_enabled")
