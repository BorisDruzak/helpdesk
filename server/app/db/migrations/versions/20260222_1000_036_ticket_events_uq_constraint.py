"""Восстановить UNIQUE constraint uq_ticket_events_device_ticket_seq для ticket_events

Revision ID: 036
Revises: 035
Create Date: 2026-02-22 10:00:00.000000

Миграция 005 заменила UNIQUE constraint на частичный UNIQUE INDEX (WHERE agent_seq IS NOT NULL).
INSERT ... ON CONFLICT ON CONSTRAINT требует именно constraint; в PostgreSQL уникальный индекс
не является constraint. Поэтому восстанавливаем именованный UNIQUE constraint.

В PostgreSQL UNIQUE(device_id, ticket_id, agent_seq) допускает несколько строк с agent_seq = NULL
(каждый NULL считается отличным от другого), что сохраняет поведение для server-originated событий.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем частичный UNIQUE INDEX из миграции 005 (он не поддерживает ON CONFLICT ON CONSTRAINT)
    op.drop_index(
        "uq_ticket_events_device_ticket_seq",
        table_name="ticket_events",
    )
    # Создаём именованный UNIQUE constraint для ON CONFLICT ON CONSTRAINT в репозитории
    op.create_unique_constraint(
        "uq_ticket_events_device_ticket_seq",
        "ticket_events",
        ["device_id", "ticket_id", "agent_seq"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ticket_events_device_ticket_seq",
        "ticket_events",
        type_="unique",
    )
    # Восстанавливаем частичный UNIQUE INDEX как в миграции 005
    op.execute(
        """
        CREATE UNIQUE INDEX uq_ticket_events_device_ticket_seq
        ON ticket_events (device_id, ticket_id, agent_seq)
        WHERE agent_seq IS NOT NULL
        """
    )
