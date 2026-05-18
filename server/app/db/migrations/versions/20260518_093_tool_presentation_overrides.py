"""tool presentation overrides

Revision ID: 093
Revises: 092
Create Date: 2026-05-18 18:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "093"
down_revision: Union[str, None] = "092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("tool_presentation_overrides"):
        op.create_table(
            "tool_presentation_overrides",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("tool_id", sa.Text(), nullable=False),
            sa.Column("tool_version", sa.String(64), nullable=True),
            sa.Column("scope", sa.String(32), nullable=False, server_default="global"),
            sa.Column("device_id", sa.String(36), nullable=True),
            sa.Column("presentation_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table("tool_presentation_overrides"):
        if not _has_index("tool_presentation_overrides", "ix_tool_presentation_overrides_tool"):
            op.create_index("ix_tool_presentation_overrides_tool", "tool_presentation_overrides", ["tool_id"])
        if not _has_index("tool_presentation_overrides", "ix_tool_presentation_overrides_enabled"):
            op.create_index("ix_tool_presentation_overrides_enabled", "tool_presentation_overrides", ["enabled"])
        if not _has_index("tool_presentation_overrides", "uq_tool_presentation_override_scope"):
            op.create_index(
                "uq_tool_presentation_override_scope",
                "tool_presentation_overrides",
                [
                    "tool_id",
                    sa.text("COALESCE(tool_version, '')"),
                    "scope",
                    sa.text("COALESCE(device_id, '')"),
                ],
                unique=True,
            )


def downgrade() -> None:
    if _has_table("tool_presentation_overrides"):
        for index_name in (
            "uq_tool_presentation_override_scope",
            "ix_tool_presentation_overrides_enabled",
            "ix_tool_presentation_overrides_tool",
        ):
            if _has_index("tool_presentation_overrides", index_name):
                op.drop_index(index_name, table_name="tool_presentation_overrides")
        op.drop_table("tool_presentation_overrides")
