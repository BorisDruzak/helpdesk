"""Stage 8: ticket_notification_prefs — настройки уведомлений (mute_internal, muted_event_types, suppress_self)

Revision ID: 026
Revises: 025
Create Date: 2026-02-17 12:00:00.000000

- ticket_notification_prefs: actor_id (PK), mute_internal, muted_event_types (JSONB), suppress_self, updated_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ticket_notification_prefs",
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("mute_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("muted_event_types", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("suppress_self", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("actor_id"),
    )


def downgrade() -> None:
    op.drop_table("ticket_notification_prefs")
