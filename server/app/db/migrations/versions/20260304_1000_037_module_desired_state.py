"""Модульная система: desired state, last_seen_at/source в device_modules, GC политика

Revision ID: 037
Revises: 036
Create Date: 2026-03-04 10:00:00.000000

Этапы целевой архитектуры:
- device_desired_modules: желаемое состояние (source of truth для reconcile)
- device_modules.last_seen_at: время последнего подтверждения реального наличия
- device_modules.source: источник обновления (handshake|command_result|event)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем колонки к device_modules (actual state)
    op.add_column(
        "device_modules",
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Время последнего подтверждения реального наличия модуля (от агента)"
        ),
    )
    op.add_column(
        "device_modules",
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=True,
            comment="Источник обновления: handshake|command_result|event"
        ),
    )

    # Инициализируем last_seen_at = installed_at для существующих записей
    op.execute(
        """
        UPDATE device_modules
        SET last_seen_at = COALESCE(installed_at, last_updated_at),
            source = 'command_result'
        WHERE state IN ('active', 'installed')
        """
    )

    # Создаём таблицу device_desired_modules
    op.create_table(
        "device_desired_modules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=False),
        sa.Column("module_name", sa.String(length=100), nullable=False),
        # desired_version: NULL означает "absent" (желаем удалить)
        sa.Column("desired_version", sa.String(length=50), nullable=True),
        sa.Column("desired_sha256", sa.String(length=64), nullable=True),
        # state: installed | absent
        sa.Column(
            "state",
            sa.String(length=20),
            nullable=False,
            server_default="installed",
            comment="Желаемое состояние: installed|absent"
        ),
        # reason: manual|run_tool|policy|reconcile
        sa.Column(
            "reason",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
            comment="Причина изменения: manual|run_tool|policy|reconcile"
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_by",
            sa.String(length=50),
            nullable=True,
            comment="Кто изменил (actor_role или имя пользователя)"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "device_id", "module_name",
            name="uq_device_desired_modules_device_module"
        ),
    )
    op.create_index(
        "ix_device_desired_modules_device_id",
        "device_desired_modules",
        ["device_id"],
    )
    op.create_index(
        "ix_device_desired_modules_state",
        "device_desired_modules",
        ["state"],
    )

    # Индекс для быстрого поиска модулей требующих reconcile
    op.create_index(
        "ix_device_desired_modules_device_state",
        "device_desired_modules",
        ["device_id", "state"],
    )

    # Заполняем desired state из текущего actual (всё что active = installed)
    op.execute(
        """
        INSERT INTO device_desired_modules (device_id, module_name, desired_version, state, reason, updated_at)
        SELECT DISTINCT ON (device_id, module_name)
            device_id, module_name, version, 'installed', 'reconcile', NOW()
        FROM device_modules
        WHERE state = 'active' AND active = true
        ON CONFLICT (device_id, module_name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("device_desired_modules")
    op.drop_column("device_modules", "source")
    op.drop_column("device_modules", "last_seen_at")
