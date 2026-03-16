"""Operations: command_name, timeout_override_sec, playbook_run_id (Этап 5 Hardening)

Revision ID: 034
Revises: 033
Create Date: 2026-02-21 10:00:00.000000

Поля для: метрики list_tools (command_name), таймаут шага playbook (timeout_override_sec),
связь операции с playbook_run (playbook_run_id).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "operations",
        sa.Column("command_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "operations",
        sa.Column("timeout_override_sec", sa.Integer(), nullable=True),
    )
    op.add_column(
        "operations",
        sa.Column("playbook_run_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_operations_playbook_run_id",
        "operations",
        "playbook_run",
        ["playbook_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_operations_command_name", "operations", ["command_name"])


def downgrade() -> None:
    op.drop_index("ix_operations_command_name", table_name="operations")
    op.drop_constraint("fk_operations_playbook_run_id", "operations", type_="foreignkey")
    op.drop_column("operations", "playbook_run_id")
    op.drop_column("operations", "timeout_override_sec")
    op.drop_column("operations", "command_name")
