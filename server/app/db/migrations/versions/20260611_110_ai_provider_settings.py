"""AI provider settings for Knowledge vNext.

Revision ID: 110
Revises: 109
Create Date: 2026-06-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "110"
down_revision: Union[str, None] = "109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("ai_providers"):
        op.create_table(
            "ai_providers",
            sa.Column("provider_id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(100), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("provider_type", sa.String(40), nullable=False),
            sa.Column("base_url", sa.Text(), nullable=True),
            sa.Column("auth_type", sa.String(40), nullable=False, server_default="api_key"),
            sa.Column("api_key_secret_ref", sa.Text(), nullable=True),
            sa.Column("default_headers_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("data_policy", sa.String(40), nullable=False, server_default="no_sensitive"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("health_status", sa.String(40), nullable=True),
            sa.Column("last_health_check_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("last_error_redacted", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "provider_type IN ('openrouter', 'openai_compatible', 'ollama', 'local_custom')",
                name="ck_ai_providers_provider_type",
            ),
            sa.CheckConstraint(
                "auth_type IN ('api_key', 'bearer', 'none', 'custom_header')",
                name="ck_ai_providers_auth_type",
            ),
            sa.CheckConstraint(
                "data_policy IN ('local_only', 'cloud_allowed', 'no_sensitive', 'allow_public')",
                name="ck_ai_providers_data_policy",
            ),
            sa.UniqueConstraint("code", name="uq_ai_providers_code"),
        )

    if not _has_table("ai_model_profiles"):
        op.create_table(
            "ai_model_profiles",
            sa.Column("profile_id", sa.String(36), primary_key=True),
            sa.Column("provider_id", sa.String(36), sa.ForeignKey("ai_providers.provider_id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(100), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("task_type", sa.String(40), nullable=False),
            sa.Column("model_name", sa.Text(), nullable=False),
            sa.Column("context_window", sa.Integer(), nullable=True),
            sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
            sa.Column("timeout_ms", sa.Integer(), nullable=False, server_default="30000"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("top_p", sa.Float(), nullable=True),
            sa.Column("structured_output_supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("streaming_supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("fallback_profile_id", sa.String(36), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "task_type IN ('chat', 'embedding', 'rerank', 'rewrite', 'summarize', 'classify', 'extract', 'answer', 'markup', 'moderation')",
                name="ck_ai_model_profiles_task_type",
            ),
            sa.UniqueConstraint("code", name="uq_ai_model_profiles_code"),
        )

    if not _has_table("ai_policy_profiles"):
        op.create_table(
            "ai_policy_profiles",
            sa.Column("policy_id", sa.String(36), primary_key=True),
            sa.Column("scope_type", sa.String(40), nullable=False),
            sa.Column("space_id", sa.String(36), nullable=True),
            sa.Column("visibility", sa.String(40), nullable=True),
            sa.Column("task_type", sa.String(40), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("ai_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("embedding_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rerank_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("answer_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("rewrite_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("auto_markup_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("require_local_for_security_restricted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("allow_cloud_for_requester_safe", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("redact_before_send", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("store_prompts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("store_outputs", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("max_tokens_per_request", sa.Integer(), nullable=True),
            sa.Column("max_requests_per_day", sa.Integer(), nullable=True),
            sa.Column("max_cost_per_day", sa.Numeric(12, 4), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "scope_type IN ('global', 'space', 'visibility', 'task_type')",
                name="ck_ai_policy_profiles_scope_type",
            ),
        )

    if not _has_table("ai_request_audit"):
        op.create_table(
            "ai_request_audit",
            sa.Column("audit_id", sa.String(36), primary_key=True),
            sa.Column("provider_id", sa.String(36), sa.ForeignKey("ai_providers.provider_id", ondelete="SET NULL"), nullable=True),
            sa.Column("model_profile_id", sa.String(36), sa.ForeignKey("ai_model_profiles.profile_id", ondelete="SET NULL"), nullable=True),
            sa.Column("task_type", sa.String(40), nullable=True),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("error_code", sa.String(80), nullable=True),
            sa.Column("error_message_redacted", sa.Text(), nullable=True),
            sa.Column("prompt_redacted", sa.Text(), nullable=True),
            sa.Column("output_redacted", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        )

    for table, indexes in {
        "ai_providers": [
            ("ix_ai_providers_type_enabled", ["provider_type", "enabled"]),
            ("ix_ai_providers_health", ["health_status"]),
        ],
        "ai_model_profiles": [
            ("ix_ai_model_profiles_provider_task", ["provider_id", "task_type"]),
            ("ix_ai_model_profiles_task_default", ["task_type", "is_default"]),
        ],
        "ai_policy_profiles": [
            ("ix_ai_policy_profiles_scope_task", ["scope_type", "task_type"]),
            ("ix_ai_policy_profiles_visibility", ["visibility"]),
        ],
        "ai_request_audit": [
            ("ix_ai_request_audit_provider_created", ["provider_id", "created_at"]),
            ("ix_ai_request_audit_task_status", ["task_type", "status"]),
        ],
    }.items():
        for name, columns in indexes:
            if not _has_index(table, name):
                op.create_index(name, table, columns)


def downgrade() -> None:
    for table, indexes in {
        "ai_request_audit": (
            "ix_ai_request_audit_task_status",
            "ix_ai_request_audit_provider_created",
        ),
        "ai_policy_profiles": (
            "ix_ai_policy_profiles_visibility",
            "ix_ai_policy_profiles_scope_task",
        ),
        "ai_model_profiles": (
            "ix_ai_model_profiles_task_default",
            "ix_ai_model_profiles_provider_task",
        ),
        "ai_providers": (
            "ix_ai_providers_health",
            "ix_ai_providers_type_enabled",
        ),
    }.items():
        if _has_table(table):
            for name in indexes:
                if _has_index(table, name):
                    op.drop_index(name, table_name=table)
    for table in ("ai_request_audit", "ai_policy_profiles", "ai_model_profiles", "ai_providers"):
        if _has_table(table):
            op.drop_table(table)
