"""Knowledge graph persisted layouts.

Revision ID: 116
Revises: 115
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "116"
down_revision: Union[str, None] = "115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _has_unique(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_unique_constraints(table)}


def upgrade() -> None:
    if not _has_table("knowledge_graph_layouts"):
        op.create_table(
            "knowledge_graph_layouts",
            sa.Column("layout_id", sa.String(36), primary_key=True),
            sa.Column("scope_type", sa.String(40), nullable=False, server_default="graph"),
            sa.Column("scope_ref", sa.String(240), nullable=False),
            sa.Column("layout_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint("scope_type IN ('graph', 'space', 'item')", name="ck_knowledge_graph_layouts_scope_type"),
        )
    if not _has_unique("knowledge_graph_layouts", "uq_knowledge_graph_layouts_scope"):
        op.create_unique_constraint("uq_knowledge_graph_layouts_scope", "knowledge_graph_layouts", ["scope_type", "scope_ref"])
    if not _has_index("knowledge_graph_layouts", "ix_knowledge_graph_layouts_scope"):
        op.create_index("ix_knowledge_graph_layouts_scope", "knowledge_graph_layouts", ["scope_type", "scope_ref"])


def downgrade() -> None:
    if _has_index("knowledge_graph_layouts", "ix_knowledge_graph_layouts_scope"):
        op.drop_index("ix_knowledge_graph_layouts_scope", table_name="knowledge_graph_layouts")
    if _has_unique("knowledge_graph_layouts", "uq_knowledge_graph_layouts_scope"):
        op.drop_constraint("uq_knowledge_graph_layouts_scope", "knowledge_graph_layouts", type_="unique")
    if _has_table("knowledge_graph_layouts"):
        op.drop_table("knowledge_graph_layouts")
