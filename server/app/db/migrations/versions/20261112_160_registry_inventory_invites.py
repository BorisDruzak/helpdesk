"""Add hashed one-use invitations to requester registration."""

from alembic import op
import sqlalchemy as sa

revision = "160"
down_revision = "159"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "registry_inventory_invites",
        sa.Column("inventory_person_id", sa.String(36), primary_key=True),
        sa.Column("code_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("inventory_department", sa.String(255), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=False),
        sa.Column("issued_by", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM registry_inventory_invites)")):
        raise RuntimeError("Cannot downgrade while inventory invitations exist")
    op.drop_table("registry_inventory_invites")
