"""agent recipe runner

Revision ID: 077
Revises: 076
Create Date: 2026-05-13 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("diagnostic_capability_versions", sa.Column("status", sa.String(length=32), server_default="published", nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("params_schema_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("output_schema_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("output_contract_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("safety_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("evidence_mapping_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("deployment_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("readiness_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("contract_hash", sa.String(length=128), server_default="", nullable=False))
    op.add_column("diagnostic_capability_versions", sa.Column("created_by", sa.Text(), nullable=True))
    op.add_column("diagnostic_capability_versions", sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("diagnostic_capability_versions", sa.Column("deprecated_at", postgresql.TIMESTAMP(timezone=True), nullable=True))

    op.create_table(
        "agent_recipe_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("capability_version_id", sa.String(length=36), nullable=False),
        sa.Column("recipe_schema_version", sa.String(length=32), nullable=False),
        sa.Column("runner_provider_id", sa.Text(), server_default="agent_recipe_runner", nullable=False),
        sa.Column("min_runner_version", sa.String(length=64), nullable=False),
        sa.Column("primitive_id", sa.Text(), nullable=False),
        sa.Column("primitive_version", sa.String(length=64), nullable=True),
        sa.Column("platforms_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("platform_variants_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("recipe_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("parameter_bindings_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("resource_limits_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("redaction_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("validation_status", sa.String(length=32), server_default="unknown", nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["capability_version_id"], ["diagnostic_capability_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_recipe_versions_capability_version", "agent_recipe_versions", ["capability_version_id"])
    op.create_index("ix_agent_recipe_versions_primitive", "agent_recipe_versions", ["primitive_id"])
    op.create_index("ix_agent_recipe_versions_runner", "agent_recipe_versions", ["runner_provider_id"])
    op.create_index("ix_agent_recipe_versions_validation", "agent_recipe_versions", ["validation_status"])

    op.create_table(
        "agent_recipe_primitives",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("runner_provider_id", sa.Text(), server_default="agent_recipe_runner", nullable=False),
        sa.Column("runner_version", sa.String(length=64), nullable=False),
        sa.Column("primitive_id", sa.Text(), nullable=False),
        sa.Column("primitive_version", sa.String(length=64), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platforms_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("params_schema", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output_contract", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("safety_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence_defaults_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("resource_limits_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("redaction_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runner_provider_id", "runner_version", "primitive_id", "primitive_version", name="uq_agent_recipe_primitives_runner_primitive"),
    )
    op.create_index("ix_agent_recipe_primitives_runner", "agent_recipe_primitives", ["runner_provider_id", "runner_version"])
    op.create_index("ix_agent_recipe_primitives_primitive", "agent_recipe_primitives", ["primitive_id"])

    op.create_table(
        "agent_recipe_test_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("recipe_version_id", sa.String(length=36), nullable=False),
        sa.Column("target_device_id", sa.String(length=36), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("runner_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("result_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("artifacts_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["agent_recipe_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_recipe_test_runs_recipe", "agent_recipe_test_runs", ["recipe_version_id"])
    op.create_index("ix_agent_recipe_test_runs_status", "agent_recipe_test_runs", ["status"])
    op.create_index("ix_agent_recipe_test_runs_platform", "agent_recipe_test_runs", ["platform"])
    op.create_index("ix_agent_recipe_test_runs_device", "agent_recipe_test_runs", ["target_device_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_recipe_test_runs_device", table_name="agent_recipe_test_runs")
    op.drop_index("ix_agent_recipe_test_runs_platform", table_name="agent_recipe_test_runs")
    op.drop_index("ix_agent_recipe_test_runs_status", table_name="agent_recipe_test_runs")
    op.drop_index("ix_agent_recipe_test_runs_recipe", table_name="agent_recipe_test_runs")
    op.drop_table("agent_recipe_test_runs")

    op.drop_index("ix_agent_recipe_primitives_primitive", table_name="agent_recipe_primitives")
    op.drop_index("ix_agent_recipe_primitives_runner", table_name="agent_recipe_primitives")
    op.drop_table("agent_recipe_primitives")

    op.drop_index("ix_agent_recipe_versions_validation", table_name="agent_recipe_versions")
    op.drop_index("ix_agent_recipe_versions_runner", table_name="agent_recipe_versions")
    op.drop_index("ix_agent_recipe_versions_primitive", table_name="agent_recipe_versions")
    op.drop_index("ix_agent_recipe_versions_capability_version", table_name="agent_recipe_versions")
    op.drop_table("agent_recipe_versions")

    for column_name in (
        "deprecated_at",
        "published_at",
        "created_by",
        "contract_hash",
        "readiness_json",
        "deployment_json",
        "evidence_mapping_json",
        "safety_json",
        "output_contract_json",
        "output_schema_json",
        "params_schema_json",
        "status",
    ):
        op.drop_column("diagnostic_capability_versions", column_name)
