"""Add browser subscriptions and transactional Web Push delivery queue."""
from alembic import op
import sqlalchemy as sa

revision = "156"
down_revision = "155"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("web_push_subscriptions",
        sa.Column("endpoint_hash", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.Text, nullable=False),
        sa.Column("endpoint", sa.Text, nullable=False),
        sa.Column("vapid_public_key", sa.String(100), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("failures", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_web_push_subscriptions_actor_id", "web_push_subscriptions", ["actor_id"])
    op.create_table("web_push_deliveries",
        sa.Column("endpoint_hash", sa.String(64), sa.ForeignKey("web_push_subscriptions.endpoint_hash", ondelete="CASCADE"), primary_key=True),
        sa.Column("notification_id", sa.BigInteger, sa.ForeignKey("ticket_notifications.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("shown_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("web_push_deliveries")
    op.drop_table("web_push_subscriptions")
