"""Knowledge search settings.

Revision ID: 111
Revises: 110
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "111"
down_revision: Union[str, None] = "110"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("knowledge_search_settings"):
        op.create_table(
            "knowledge_search_settings",
            sa.Column("settings_id", sa.String(36), primary_key=True),
            sa.Column("scope_type", sa.String(40), nullable=False, server_default="global"),
            sa.Column("space_id", sa.String(36), nullable=True),
            sa.Column("visibility", sa.String(40), nullable=True),
            sa.Column("search_mode", sa.String(40), nullable=False, server_default="keyword_only"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("keyword_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("full_text_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("vector_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rerank_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("ai_query_rewrite_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rag_answer_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("keyword_weight", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("full_text_weight", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("vector_weight", sa.Numeric(8, 4), nullable=False, server_default="1.0"),
            sa.Column("max_results", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("snippet_length", sa.Integer(), nullable=False, server_default="180"),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint("scope_type IN ('global', 'space', 'visibility')", name="ck_knowledge_search_settings_scope_type"),
            sa.CheckConstraint(
                "search_mode IN ('keyword_only', 'full_text', 'hybrid_no_ai', 'hybrid_vector', 'hybrid_vector_rerank', 'rag_answer')",
                name="ck_knowledge_search_settings_search_mode",
            ),
            sa.CheckConstraint("max_results BETWEEN 1 AND 50", name="ck_knowledge_search_settings_max_results"),
            sa.CheckConstraint("snippet_length BETWEEN 80 AND 1000", name="ck_knowledge_search_settings_snippet_length"),
        )

    if not _has_index("knowledge_search_settings", "ix_knowledge_search_settings_scope"):
        op.create_index("ix_knowledge_search_settings_scope", "knowledge_search_settings", ["scope_type", "space_id", "visibility"])


def downgrade() -> None:
    if _has_table("knowledge_search_settings"):
        if _has_index("knowledge_search_settings", "ix_knowledge_search_settings_scope"):
            op.drop_index("ix_knowledge_search_settings_scope", table_name="knowledge_search_settings")
        op.drop_table("knowledge_search_settings")
