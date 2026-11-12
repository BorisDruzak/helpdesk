"""Lease automatic inventory ownership independently of legacy active rows."""

from alembic import op
import sqlalchemy as sa

revision = "161"
down_revision = "160"
branch_labels = None
depends_on = None
TABLE = "device_user_bindings"
STATUS_CONSTRAINT = "ck_device_user_bindings_status"
PRIMARY_INDEX = "uq_device_user_bindings_active_primary_device"


def _status_rules(*, inventory: bool) -> None:
    states = "'pending', 'active', 'stale', 'revoked', 'transferred'"
    primary = "status = 'active'"
    if inventory:
        states += ", 'inventory_active'"
        primary = "status IN ('active', 'inventory_active')"
    op.drop_constraint(STATUS_CONSTRAINT, TABLE, type_="check")
    op.create_check_constraint(STATUS_CONSTRAINT, TABLE, f"status IN ({states})")
    op.drop_index(PRIMARY_INDEX, table_name=TABLE)
    op.create_index(PRIMARY_INDEX, TABLE, ["device_id"], unique=True,
                    postgresql_where=sa.text(f"{primary} AND relationship_type = 'primary_user'"))


def upgrade():
    op.add_column(TABLE, sa.Column("inventory_verified_until", sa.DateTime(timezone=True), nullable=True))
    _status_rules(inventory=True)


def downgrade():
    if op.get_bind().scalar(sa.text(
        "SELECT EXISTS (SELECT 1 FROM device_user_bindings WHERE status='inventory_active')"
    )):
        raise RuntimeError("Cannot downgrade while inventory bindings are active")
    _status_rules(inventory=False)
    op.drop_column(TABLE, "inventory_verified_until")
