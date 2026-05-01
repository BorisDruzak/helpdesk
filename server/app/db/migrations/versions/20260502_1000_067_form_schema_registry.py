"""form schema registry

Revision ID: 067
Revises: 066
Create Date: 2026-05-02 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "067"
down_revision: Union[str, None] = "066"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("form_schemas"):
        op.create_table(
            "form_schemas",
            sa.Column("schema_id", sa.String(length=120), nullable=False),
            sa.Column("version", sa.String(length=32), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("form_key", sa.String(length=100), nullable=True),
            sa.Column("request_template_code", sa.String(length=100), nullable=True),
            sa.Column("ticket_type", sa.String(length=64), nullable=True),
            sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("schema_id", "version"),
        )
        op.create_index("ix_form_schemas_active", "form_schemas", ["schema_id", "is_active"])
        op.create_index("ix_form_schemas_template", "form_schemas", ["request_template_code", "is_active"])
        op.create_index("ix_form_schemas_published_at", "form_schemas", ["published_at"])

    if not inspector.has_table("form_fields"):
        op.create_table(
            "form_fields",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("schema_id", sa.String(length=120), nullable=False),
            sa.Column("schema_version", sa.String(length=32), nullable=False),
            sa.Column("key", sa.String(length=100), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("field_type", sa.String(length=32), nullable=False),
            sa.Column("required", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("options_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("validation_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("process_mapping_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("visibility_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("schema_id", "schema_version", "key", name="uq_form_fields_schema_key"),
        )
        op.create_index("ix_form_fields_schema", "form_fields", ["schema_id", "schema_version"])

    if not inspector.has_table("form_conditions"):
        op.create_table(
            "form_conditions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("schema_id", sa.String(length=120), nullable=False),
            sa.Column("schema_version", sa.String(length=32), nullable=False),
            sa.Column("condition_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("show_fields_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("require_fields_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_form_conditions_schema", "form_conditions", ["schema_id", "schema_version"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("form_conditions"):
        indexes = {index["name"] for index in inspector.get_indexes("form_conditions")}
        if "ix_form_conditions_schema" in indexes:
            op.drop_index("ix_form_conditions_schema", table_name="form_conditions")
        op.drop_table("form_conditions")
    if inspector.has_table("form_fields"):
        indexes = {index["name"] for index in inspector.get_indexes("form_fields")}
        if "ix_form_fields_schema" in indexes:
            op.drop_index("ix_form_fields_schema", table_name="form_fields")
        op.drop_table("form_fields")
    if inspector.has_table("form_schemas"):
        indexes = {index["name"] for index in inspector.get_indexes("form_schemas")}
        if "ix_form_schemas_published_at" in indexes:
            op.drop_index("ix_form_schemas_published_at", table_name="form_schemas")
        if "ix_form_schemas_template" in indexes:
            op.drop_index("ix_form_schemas_template", table_name="form_schemas")
        if "ix_form_schemas_active" in indexes:
            op.drop_index("ix_form_schemas_active", table_name="form_schemas")
        op.drop_table("form_schemas")
