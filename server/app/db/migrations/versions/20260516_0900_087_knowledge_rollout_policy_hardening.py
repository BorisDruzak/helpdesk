"""knowledge rollout policy hardening

Revision ID: 087
Revises: 086
Create Date: 2026-05-16 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "087"
down_revision: Union[str, None] = "086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _constraints(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name)} | {
        constraint["name"] for constraint in inspector.get_unique_constraints(table_name)
    }


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_check_if_missing(name: str, table_name: str, condition: str) -> None:
    if name not in _constraints(table_name):
        op.create_check_constraint(name, table_name, condition)


def _drop_constraint_if_exists(name: str, table_name: str, *, type_: str = "check") -> None:
    if name in _constraints(table_name):
        op.drop_constraint(name, table_name, type_=type_)


def upgrade() -> None:
    _drop_constraint_if_exists("ck_knowledge_content_pack_items_status", "knowledge_content_pack_items", type_="check")
    _create_check_if_missing(
        "ck_knowledge_content_pack_items_status",
        "knowledge_content_pack_items",
        "install_status IN ('created', 'skipped', 'updated', 'conflict', 'failed', 'retired', 'bindings_repaired')",
    )

    _add_column_if_missing("knowledge_rollout_policies", sa.Column("scope_type", sa.String(length=20), nullable=True))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("show_before_form", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("show_after_form", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("require_suggestions_before_submit", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("allow_skip", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("urgency_bypass", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("impact_bypass", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("min_suggestions", sa.Integer(), nullable=False, server_default="0"))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("max_suggestions", sa.Integer(), nullable=False, server_default="5"))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("deflection_prompt_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("feedback_required_on_article_view", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("show_known_errors", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("show_quality_badge", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("show_review_freshness", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("no_suggestions_behavior", sa.String(length=30), nullable=False, server_default="allow_submit"))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("api_unavailable_behavior", sa.String(length=30), nullable=False, server_default="allow_submit"))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("bypass_roles", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("effective_from", postgresql.TIMESTAMP(timezone=True), nullable=True))
    _add_column_if_missing("knowledge_rollout_policies", sa.Column("effective_until", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE knowledge_rollout_policies
        SET scope_type = CASE
            WHEN offering_code IS NOT NULL THEN 'offering'
            WHEN service_code IS NOT NULL THEN 'service'
            WHEN request_template_key IS NOT NULL THEN 'template'
            ELSE 'global'
        END
        """
    )
    op.alter_column("knowledge_rollout_policies", "scope_type", nullable=False, server_default="global")
    _drop_constraint_if_exists("ck_knowledge_rollout_policies_surface", "knowledge_rollout_policies", type_="check")
    _create_check_if_missing(
        "ck_knowledge_rollout_policies_surface",
        "knowledge_rollout_policies",
        "surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'api', 'all')",
    )
    _create_check_if_missing("ck_knowledge_rollout_scope_type", "knowledge_rollout_policies", "scope_type IN ('global', 'service', 'offering', 'template')")
    _create_check_if_missing("ck_knowledge_rollout_suggestion_bounds", "knowledge_rollout_policies", "min_suggestions >= 0 AND max_suggestions >= min_suggestions")
    _create_check_if_missing("ck_knowledge_rollout_no_suggestions_behavior", "knowledge_rollout_policies", "no_suggestions_behavior IN ('allow_submit', 'show_message', 'block_submit')")
    _create_check_if_missing("ck_knowledge_rollout_api_unavailable_behavior", "knowledge_rollout_policies", "api_unavailable_behavior IN ('allow_submit', 'show_warning', 'block_submit')")
    _create_check_if_missing(
        "ck_knowledge_rollout_scope_fields",
        "knowledge_rollout_policies",
        "((scope_type = 'global' AND service_code IS NULL AND offering_code IS NULL AND request_template_key IS NULL) "
        "OR (scope_type = 'service' AND service_code IS NOT NULL AND offering_code IS NULL AND request_template_key IS NULL) "
        "OR (scope_type = 'offering' AND service_code IS NOT NULL AND offering_code IS NOT NULL) "
        "OR (scope_type = 'template' AND request_template_key IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_knowledge_rollout_scope_fields", "knowledge_rollout_policies", type_="check")
    op.drop_constraint("ck_knowledge_rollout_api_unavailable_behavior", "knowledge_rollout_policies", type_="check")
    op.drop_constraint("ck_knowledge_rollout_no_suggestions_behavior", "knowledge_rollout_policies", type_="check")
    op.drop_constraint("ck_knowledge_rollout_suggestion_bounds", "knowledge_rollout_policies", type_="check")
    op.drop_constraint("ck_knowledge_rollout_scope_type", "knowledge_rollout_policies", type_="check")
    op.drop_constraint("ck_knowledge_rollout_policies_surface", "knowledge_rollout_policies", type_="check")
    op.create_check_constraint(
        "ck_knowledge_rollout_policies_surface",
        "knowledge_rollout_policies",
        "surface IN ('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')",
    )
    for column in (
        "effective_until",
        "effective_from",
        "bypass_roles",
        "api_unavailable_behavior",
        "no_suggestions_behavior",
        "show_review_freshness",
        "show_quality_badge",
        "show_known_errors",
        "feedback_required_on_article_view",
        "deflection_prompt_enabled",
        "max_suggestions",
        "min_suggestions",
        "impact_bypass",
        "urgency_bypass",
        "allow_skip",
        "require_suggestions_before_submit",
        "show_after_form",
        "show_before_form",
        "scope_type",
    ):
        op.drop_column("knowledge_rollout_policies", column)
    op.drop_constraint("ck_knowledge_content_pack_items_status", "knowledge_content_pack_items", type_="check")
    op.create_check_constraint(
        "ck_knowledge_content_pack_items_status",
        "knowledge_content_pack_items",
        "install_status IN ('created', 'skipped', 'updated', 'conflict', 'failed', 'retired')",
    )
