"""Permit ticket-bound attachments without a legacy device identifier."""

from alembic import op
import sqlalchemy as sa


revision = "154"
down_revision = "153"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("artifacts", "device_id", existing_type=sa.String(36), nullable=True)
    op.create_check_constraint(
        "ck_artifacts_device_or_ticket", "artifacts",
        "device_id IS NOT NULL OR ticket_id IS NOT NULL",
    )


def downgrade():
    # PostgreSQL refuses this without modifying data if no-device rows exist.
    # Do not delete attachments or fabricate device identifiers for rollback.
    op.alter_column("artifacts", "device_id", existing_type=sa.String(36), nullable=False)
    op.drop_constraint("ck_artifacts_device_or_ticket", "artifacts", type_="check")
