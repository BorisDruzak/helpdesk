"""Add immutable tool ownership without rewriting historical intents.

Revision ID: 148
Revises: 147 (combined staging preview; main integration remains separate)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "148"
down_revision = "147"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("endpoint_operation_links", sa.Column("context_profile", sa.String(32), nullable=True))
    op.add_column("endpoint_operation_links", sa.Column("endpoint_collection_ref", sa.String(36), nullable=True))
    op.create_index("uq_endpoint_operation_links_collection_ref", "endpoint_operation_links", ["endpoint_collection_ref"], unique=True)
    op.drop_constraint("ck_endpoint_operation_links_capability_code", "endpoint_operation_links", type_="check")
    op.create_check_constraint("ck_endpoint_operation_links_capability_code", "endpoint_operation_links",
        "(capability_code = 'context.diagnostic.collect' AND module_key IS NULL AND module_version IS NULL AND context_profile IS NULL) "
        "OR (capability_code = 'endpoint.module.recipe' AND module_key IS NOT NULL AND module_version IS NOT NULL AND context_profile IS NULL) "
        "OR (capability_code = 'endpoint.context.collection' AND module_key IS NULL AND module_version IS NULL AND context_profile IS NOT NULL AND context_profile IN "
        "('inventory_v1', 'health_v1', 'network_v1', 'baseline_v1', 'session_v1'))")
    op.create_table("endpoint_tool_runs",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("operations.operation_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("caller_key", sa.String(128), nullable=False),
        sa.Column("execution_kind", sa.String(32), nullable=False),
        sa.Column("request_snapshot_json", JSONB(), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("batch_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("actor_id", "ticket_id", "caller_key", name="uq_endpoint_tool_runs_caller"),
        sa.CheckConstraint("execution_kind IN ('module', 'context_collection', 'diagnostic')", name="ck_endpoint_tool_runs_kind"))
    op.create_index("ix_endpoint_tool_runs_ticket_created", "endpoint_tool_runs", ["ticket_id", "created_at"])
    op.create_index("ix_endpoint_tool_runs_batch", "endpoint_tool_runs", ["batch_id"])


def downgrade():
    raise RuntimeError("Revision 148 is forward-only; restore the reviewed database backup.")
