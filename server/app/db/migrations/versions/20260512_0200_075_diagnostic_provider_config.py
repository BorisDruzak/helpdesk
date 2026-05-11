"""diagnostic provider config

Revision ID: 075
Revises: 074
Create Date: 2026-05-12 02:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "075"
down_revision = "074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_providers",
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), server_default="computed", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="available", nullable=False),
        sa.Column("config_schema", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("provider_id"),
    )
    op.create_index("ix_diag_providers_type_status", "diagnostic_providers", ["provider_type", "status"])

    op.create_table(
        "diagnostic_capabilities",
        sa.Column("capability_id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("execution_target", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="available", nullable=False),
        sa.Column("latest_version", sa.String(length=64), nullable=True),
        sa.Column("descriptor_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["diagnostic_providers.provider_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("capability_id"),
    )
    op.create_index("ix_diag_capabilities_provider", "diagnostic_capabilities", ["provider_id"])
    op.create_index("ix_diag_capabilities_target_status", "diagnostic_capabilities", ["execution_target", "status"])

    op.create_table(
        "diagnostic_capability_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capability_id", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("descriptor_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_hash", sa.String(length=128), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["capability_id"], ["diagnostic_capabilities.capability_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capability_id", "version", name="uq_diag_capability_versions_capability_version"),
    )
    op.create_index("ix_diag_capability_versions_capability", "diagnostic_capability_versions", ["capability_id", "is_current"])

    op.create_table(
        "diagnostic_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("integration_key", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="configured", nullable=False),
        sa.Column("config_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("redaction_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("health_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id", name="uq_diag_provider_configs_provider_id"),
    )
    op.create_index("ix_diag_provider_configs_provider", "diagnostic_provider_configs", ["provider_id"])
    op.create_index("ix_diag_provider_configs_integration_status", "diagnostic_provider_configs", ["integration_key", "status"])

    op.create_table(
        "diagnostic_provider_credential_refs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_config_id", sa.String(length=36), nullable=False),
        sa.Column("credential_key", sa.String(length=120), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="missing", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_config_id"], ["diagnostic_provider_configs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_config_id", "credential_key", name="uq_diag_provider_credential_key"),
    )
    op.create_index("ix_diag_provider_credential_refs_config", "diagnostic_provider_credential_refs", ["provider_config_id"])
    op.create_index("ix_diag_provider_credential_refs_status", "diagnostic_provider_credential_refs", ["status"])

    op.create_table(
        "diagnostic_provider_audit",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("provider_config_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("before_json", postgresql.JSONB(), nullable=True),
        sa.Column("after_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diag_provider_audit_provider_created", "diagnostic_provider_audit", ["provider_id", "created_at"])
    op.create_index("ix_diag_provider_audit_actor_created", "diagnostic_provider_audit", ["actor_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_diag_provider_audit_actor_created", table_name="diagnostic_provider_audit")
    op.drop_index("ix_diag_provider_audit_provider_created", table_name="diagnostic_provider_audit")
    op.drop_table("diagnostic_provider_audit")

    op.drop_index("ix_diag_provider_credential_refs_status", table_name="diagnostic_provider_credential_refs")
    op.drop_index("ix_diag_provider_credential_refs_config", table_name="diagnostic_provider_credential_refs")
    op.drop_table("diagnostic_provider_credential_refs")

    op.drop_index("ix_diag_provider_configs_integration_status", table_name="diagnostic_provider_configs")
    op.drop_index("ix_diag_provider_configs_provider", table_name="diagnostic_provider_configs")
    op.drop_table("diagnostic_provider_configs")

    op.drop_index("ix_diag_capability_versions_capability", table_name="diagnostic_capability_versions")
    op.drop_table("diagnostic_capability_versions")

    op.drop_index("ix_diag_capabilities_target_status", table_name="diagnostic_capabilities")
    op.drop_index("ix_diag_capabilities_provider", table_name="diagnostic_capabilities")
    op.drop_table("diagnostic_capabilities")

    op.drop_index("ix_diag_providers_type_status", table_name="diagnostic_providers")
    op.drop_table("diagnostic_providers")
