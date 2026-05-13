"""operation dependencies for runtime capability prerequisites

Revision ID: 078
Revises: 077
Create Date: 2026-05-13 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("operations", sa.Column("phase", sa.String(length=40), nullable=True))
    op.create_index("ix_operations_phase", "operations", ["phase"])

    op.create_table(
        "operation_dependencies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("operation_id", sa.String(length=36), nullable=False),
        sa.Column("dependency_operation_id", sa.String(length=36), nullable=True),
        sa.Column("dependency_type", sa.String(length=40), nullable=False),
        sa.Column("dependency_key", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=True),
        sa.Column("module_name", sa.Text(), nullable=True),
        sa.Column("current_version", sa.Text(), nullable=True),
        sa.Column("target_version", sa.Text(), nullable=True),
        sa.Column("version_constraint", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("timeout_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resume_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["dependency_operation_id"], ["operations.operation_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operation_id"], ["operations.operation_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operation_dependencies_operation_id", "operation_dependencies", ["operation_id"])
    op.create_index(
        "ix_operation_dependencies_dependency_operation_id",
        "operation_dependencies",
        ["dependency_operation_id"],
    )
    op.create_index("ix_operation_dependencies_type", "operation_dependencies", ["dependency_type"])
    op.create_index("ix_operation_dependencies_key", "operation_dependencies", ["dependency_key"])
    op.create_index("ix_operation_dependencies_status", "operation_dependencies", ["status"])
    op.create_index("ix_operation_dependencies_timeout_at", "operation_dependencies", ["timeout_at"])


def downgrade() -> None:
    op.drop_index("ix_operation_dependencies_timeout_at", table_name="operation_dependencies")
    op.drop_index("ix_operation_dependencies_status", table_name="operation_dependencies")
    op.drop_index("ix_operation_dependencies_key", table_name="operation_dependencies")
    op.drop_index("ix_operation_dependencies_type", table_name="operation_dependencies")
    op.drop_index("ix_operation_dependencies_dependency_operation_id", table_name="operation_dependencies")
    op.drop_index("ix_operation_dependencies_operation_id", table_name="operation_dependencies")
    op.drop_table("operation_dependencies")
    op.drop_index("ix_operations_phase", table_name="operations")
    op.drop_column("operations", "phase")
