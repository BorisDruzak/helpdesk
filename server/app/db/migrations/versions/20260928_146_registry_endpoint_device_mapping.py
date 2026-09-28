"""Keep an exact Endpoint to Registry device mapping.

Revision ID: 146
Revises: 145
"""
from alembic import op
import sqlalchemy as sa

revision = "146"
down_revision = "145"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("registry_endpoint_device_mappings",
        sa.Column("endpoint_device_ref", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.device_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table("registry_endpoint_device_mappings")
