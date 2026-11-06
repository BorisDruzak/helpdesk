"""Add retained shared Studio fragments and scoped material claims."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "158"
down_revision = "157"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("request_studio_fragments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_scenario_id", sa.String(36), sa.ForeignKey("request_studio_scenarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_title", sa.Text, nullable=False),
        sa.Column("source_revision", sa.Integer, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, server_default="1"),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("external_dependencies", JSONB, nullable=False),
        sa.Column("archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision > 0 AND source_revision > 0", name="ck_studio_fragment_revision"))
    op.create_table("request_studio_fragment_assets",
        sa.Column("fragment_id", sa.String(36), sa.ForeignKey("request_studio_fragments.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("request_studio_assets.id", ondelete="RESTRICT"), primary_key=True))


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM request_studio_fragments")):
        raise RuntimeError("Cannot downgrade while saved fragments exist")
    op.drop_table("request_studio_fragment_assets")
    op.drop_table("request_studio_fragments")
