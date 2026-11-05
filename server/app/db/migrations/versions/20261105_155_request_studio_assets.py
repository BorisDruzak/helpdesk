"""Own author material and requester files before a ticket exists."""
from alembic import op
import sqlalchemy as sa

revision = "155"
down_revision = "154"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("request_studio_assets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(36), sa.ForeignKey("request_studio_scenarios.id", ondelete="RESTRICT")),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("request_studio_sessions.id", ondelete="RESTRICT")),
        sa.Column("block_id", sa.String(100)), sa.Column("field_key", sa.String(100)),
        sa.Column("owner_actor_id", sa.Text, nullable=False),
        sa.Column("storage_path", sa.Text, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("artifact_id", sa.String(36), sa.ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"), unique=True),
        sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("(scenario_id IS NOT NULL AND session_id IS NULL AND block_id IS NULL AND field_key IS NULL) OR (scenario_id IS NULL AND session_id IS NOT NULL AND block_id IS NOT NULL AND field_key IS NOT NULL)", name="ck_studio_asset_scope"),
        sa.CheckConstraint("size_bytes >= 0 AND size_bytes <= 209715200", name="ck_studio_asset_size"),
        sa.CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="ck_studio_asset_hash"),
    )
    op.create_index("ix_request_studio_assets_scenario_id", "request_studio_assets", ["scenario_id"])
    op.create_index("ix_request_studio_assets_session_id", "request_studio_assets", ["session_id"])


def downgrade():
    # Preserve ownership and historical blobs; refuse a destructive downgrade.
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM request_studio_assets)")):
        raise RuntimeError("Studio assets exist; retain migration 155 to preserve file ownership")
    op.drop_table("request_studio_assets")
