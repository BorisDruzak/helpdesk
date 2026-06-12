"""Enforce knowledge quality model uniqueness.

Revision ID: 119
Revises: 118
Create Date: 2026-06-13 01:05:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "119"
down_revision: Union[str, None] = "118"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("knowledge_quality_models"):
        return

    op.execute(
        """
        WITH ranked AS (
            SELECT
                model_id,
                code,
                row_number() OVER (
                    PARTITION BY code
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, model_id ASC
                ) AS rn
            FROM knowledge_quality_models
            WHERE space_id IS NULL
        )
        UPDATE knowledge_quality_models AS model
        SET
            code = left(model.code, 111) || '-' || left(model.model_id, 8),
            updated_at = now()
        FROM ranked
        WHERE model.model_id = ranked.model_id
          AND ranked.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                model_id,
                row_number() OVER (
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, model_id ASC
                ) AS rn
            FROM knowledge_quality_models
            WHERE space_id IS NULL
              AND status = 'active'
              AND is_default IS TRUE
        )
        UPDATE knowledge_quality_models AS model
        SET is_default = false, updated_at = now()
        FROM ranked
        WHERE model.model_id = ranked.model_id
          AND ranked.rn > 1
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                model_id,
                row_number() OVER (
                    PARTITION BY space_id
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, model_id ASC
                ) AS rn
            FROM knowledge_quality_models
            WHERE space_id IS NOT NULL
              AND status = 'active'
              AND is_default IS TRUE
        )
        UPDATE knowledge_quality_models AS model
        SET is_default = false, updated_at = now()
        FROM ranked
        WHERE model.model_id = ranked.model_id
          AND ranked.rn > 1
        """
    )

    if not _has_index("knowledge_quality_models", "uq_knowledge_quality_models_global_code"):
        op.create_index(
            "uq_knowledge_quality_models_global_code",
            "knowledge_quality_models",
            ["code"],
            unique=True,
            postgresql_where=sa.text("space_id IS NULL"),
        )
    if not _has_index("knowledge_quality_models", "uq_knowledge_quality_models_global_active_default"):
        op.create_index(
            "uq_knowledge_quality_models_global_active_default",
            "knowledge_quality_models",
            ["is_default"],
            unique=True,
            postgresql_where=sa.text("space_id IS NULL AND status = 'active' AND is_default IS TRUE"),
        )
    if not _has_index("knowledge_quality_models", "uq_knowledge_quality_models_space_active_default"):
        op.create_index(
            "uq_knowledge_quality_models_space_active_default",
            "knowledge_quality_models",
            ["space_id"],
            unique=True,
            postgresql_where=sa.text("space_id IS NOT NULL AND status = 'active' AND is_default IS TRUE"),
        )


def downgrade() -> None:
    if not _has_table("knowledge_quality_models"):
        return
    for index_name in (
        "uq_knowledge_quality_models_space_active_default",
        "uq_knowledge_quality_models_global_active_default",
        "uq_knowledge_quality_models_global_code",
    ):
        if _has_index("knowledge_quality_models", index_name):
            op.drop_index(index_name, table_name="knowledge_quality_models")
