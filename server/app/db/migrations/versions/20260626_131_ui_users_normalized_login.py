"""Enforce normalized UI login uniqueness.

Revision ID: 131
Revises: 130
Create Date: 2026-06-26 13:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "131"
down_revision: Union[str, None] = "130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("ui_users"):
        return

    op.execute(
        sa.text(
            """
            DO $$
            DECLARE
                duplicate_count integer;
                duplicate_sample text;
            BEGIN
                SELECT count(*), min(normalized_login)
                  INTO duplicate_count, duplicate_sample
                  FROM (
                      SELECT lower(trim(user_login)) AS normalized_login
                        FROM ui_users
                       GROUP BY lower(trim(user_login))
                      HAVING count(*) > 1
                  ) duplicates;

                IF duplicate_count > 0 THEN
                    RAISE EXCEPTION
                        'ui_users contains % normalized login collisions, sample=%',
                        duplicate_count,
                        duplicate_sample;
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_ui_users_user_login_normalized
                ON ui_users (lower(trim(user_login)))
            """
        )
    )


def downgrade() -> None:
    if not _has_table("ui_users"):
        return
    op.execute(sa.text("DROP INDEX IF EXISTS uq_ui_users_user_login_normalized"))
