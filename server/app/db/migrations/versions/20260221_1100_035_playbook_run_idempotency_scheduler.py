"""Playbook run: idempotency_key, индекс для планировщика (Этап 6)

Revision ID: 035
Revises: 034
Create Date: 2026-02-21 11:00:00.000000

Для Deferred Playbook Scheduler: idempotency_key (retry-safe),
композитный индекс (status, scheduled_at) для выборки due runs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "playbook_run",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_playbook_run_idempotency_key",
        "playbook_run",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_playbook_run_status_scheduled_at",
        "playbook_run",
        ["status", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_playbook_run_status_scheduled_at", table_name="playbook_run")
    op.drop_index("ix_playbook_run_idempotency_key", table_name="playbook_run")
    op.drop_column("playbook_run", "idempotency_key")
