"""Add opt-in links from Helpdesk accounts to web_ovpn inventory identities."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "159"
down_revision = "158"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "registry_inventory_links",
        sa.Column("person_id", sa.String(36), sa.ForeignKey("registry_people.person_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("inventory_person_id", sa.String(36), nullable=False, unique=True),
        sa.Column("user_login", sa.String(100), sa.ForeignKey("ui_users.user_login", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("approval_id", sa.String(36), nullable=False, unique=True),
        sa.Column("snapshot", JSONB, nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM registry_inventory_links)")):
        raise RuntimeError("Cannot downgrade while approved inventory links exist")
    op.drop_table("registry_inventory_links")
