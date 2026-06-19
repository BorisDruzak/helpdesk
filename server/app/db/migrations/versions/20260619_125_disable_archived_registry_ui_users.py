"""Disable UI logins linked to inactive registry people.

Revision ID: 125
Revises: 124
Create Date: 2026-06-19 14:10:00
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "125"
down_revision: Union[str, None] = "124"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    required_tables = {
        "registry_people",
        "registry_person_identities",
        "ui_users",
        "ui_tokens",
        "ui_user_audit",
    }
    if not all(_has_table(name) for name in required_tables):
        return

    op.execute(
        """
        WITH blocked_users AS (
            SELECT DISTINCT u.user_login
            FROM ui_users u
            JOIN registry_person_identities i
              ON i.provider = 'ui_login'
             AND i.verified IS TRUE
             AND lower(i.normalized_identifier) = lower(u.user_login)
            JOIN registry_people p ON p.person_id = i.person_id
            WHERE u.actor_role = 'user'
              AND p.status IN ('archived', 'inactive', 'deactivated', 'disabled')
        ),
        disabled AS (
            UPDATE ui_users u
               SET is_active = false,
                   updated_at = now()
              FROM blocked_users b
             WHERE lower(u.user_login) = lower(b.user_login)
               AND u.is_active IS TRUE
            RETURNING u.user_login
        ),
        revoked AS (
            UPDATE ui_tokens t
               SET revoked_at = now()
              FROM blocked_users b
             WHERE lower(t.user_login) = lower(b.user_login)
               AND t.revoked_at IS NULL
            RETURNING t.user_login
        )
        INSERT INTO ui_user_audit (user_login, action, actor_id, details_json, created_at)
        SELECT d.user_login,
               'user_disabled_by_registry_status',
               'migration_125',
               jsonb_build_object(
                   'reason', 'migration_existing_registry_person_inactive',
                   'revoked_ui_tokens', (
                       SELECT count(*) FROM revoked r WHERE lower(r.user_login) = lower(d.user_login)
                   )
               ),
               now()
          FROM disabled d
        """
    )


def downgrade() -> None:
    # This migration intentionally does not reactivate UI accounts or tokens.
    pass
