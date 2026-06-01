"""request studio publish tokens

Revision ID: 106
Revises: 105
Create Date: 2026-06-01 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "106"
down_revision: Union[str, None] = "105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("request_studio_publish_tokens"):
        op.create_table(
            "request_studio_publish_tokens",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("nonce_hash", sa.String(length=64), nullable=False),
            sa.Column("draft_hash", sa.String(length=64), nullable=False),
            sa.Column("scope", sa.String(length=80), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=False),
            sa.Column("actor_role", sa.String(length=40), nullable=False),
            sa.Column("issued_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("used_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("used_by", sa.Text(), nullable=True),
            sa.Column("preview_summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_request_studio_publish_tokens_hash"),
            sa.UniqueConstraint("nonce_hash", name="uq_request_studio_publish_tokens_nonce"),
        )
    for name, columns in (
        ("ix_request_studio_publish_tokens_hash", ["token_hash"]),
        ("ix_request_studio_publish_tokens_nonce", ["nonce_hash"]),
        ("ix_request_studio_publish_tokens_actor", ["actor_id", "actor_role", "expires_at"]),
        ("ix_request_studio_publish_tokens_draft", ["draft_hash", "scope"]),
        ("ix_request_studio_publish_tokens_unused", ["expires_at", "used_at"]),
    ):
        if not _has_index("request_studio_publish_tokens", name):
            op.create_index(name, "request_studio_publish_tokens", columns)


def downgrade() -> None:
    if _has_table("request_studio_publish_tokens"):
        for name in (
            "ix_request_studio_publish_tokens_unused",
            "ix_request_studio_publish_tokens_draft",
            "ix_request_studio_publish_tokens_actor",
            "ix_request_studio_publish_tokens_nonce",
            "ix_request_studio_publish_tokens_hash",
        ):
            if _has_index("request_studio_publish_tokens", name):
                op.drop_index(name, table_name="request_studio_publish_tokens")
        op.drop_table("request_studio_publish_tokens")
