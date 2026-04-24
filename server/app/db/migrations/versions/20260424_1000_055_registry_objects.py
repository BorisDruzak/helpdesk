"""registry objects

Revision ID: 055
Revises: 054
Create Date: 2026-04-24 10:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "055"
down_revision: Union[str, None] = "054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    ]


def upgrade() -> None:
    op.create_table(
        "registry_departments",
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_department_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["parent_department_id"], ["registry_departments.department_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("department_id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_registry_departments_name", "registry_departments", ["name"])
    op.create_index("ix_registry_departments_status", "registry_departments", ["status"])

    op.create_table(
        "registry_locations",
        sa.Column("location_id", sa.String(length=36), nullable=False),
        sa.Column("building", sa.Text(), nullable=False),
        sa.Column("floor", sa.String(length=50), nullable=True),
        sa.Column("room", sa.String(length=100), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.PrimaryKeyConstraint("location_id"),
        sa.UniqueConstraint("building", "floor", "room", name="uq_registry_locations_building_floor_room"),
    )
    op.create_index("ix_registry_locations_building_room", "registry_locations", ["building", "room"])
    op.create_index("ix_registry_locations_status", "registry_locations", ["status"])

    op.create_table(
        "registry_vendors",
        sa.Column("vendor_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=True),
        sa.Column("contact_phone", sa.Text(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.PrimaryKeyConstraint("vendor_id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "registry_services",
        sa.Column("service_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("owner_queue_id", sa.BigInteger(), nullable=True),
        sa.Column("vendor_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["owner_queue_id"], ["ticket_queues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["registry_vendors.vendor_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("service_id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_registry_services_owner_queue", "registry_services", ["owner_queue_id"])
    op.create_index("ix_registry_services_status", "registry_services", ["status"])

    op.create_table(
        "registry_people",
        sa.Column("person_id", sa.String(length=36), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("profile_key", sa.Text(), nullable=True),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["department_id"], ["registry_departments.department_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["registry_locations.location_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("person_id"),
        sa.UniqueConstraint("source", "profile_key", name="uq_registry_people_source_profile_key"),
    )
    op.create_index("ix_registry_people_department", "registry_people", ["department_id"])
    op.create_index("ix_registry_people_location", "registry_people", ["location_id"])
    op.create_index("ix_registry_people_status", "registry_people", ["status"])

    op.create_table(
        "registry_assets",
        sa.Column("asset_id", sa.String(length=36), nullable=False),
        sa.Column("asset_type", sa.String(length=30), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("hostname", sa.Text(), nullable=True),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("inventory_number", sa.Text(), nullable=True),
        sa.Column("serial_number", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_person_id", sa.String(length=36), nullable=True),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("service_id", sa.String(length=36), nullable=True),
        sa.Column("vendor_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("discovery_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_seen_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["assigned_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["registry_departments.department_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["location_id"], ["registry_locations.location_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["service_id"], ["registry_services.service_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["registry_vendors.vendor_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("asset_id"),
        sa.UniqueConstraint("device_id"),
    )
    op.create_index("ix_registry_assets_assigned_person", "registry_assets", ["assigned_person_id"])
    op.create_index("ix_registry_assets_department", "registry_assets", ["department_id"])
    op.create_index("ix_registry_assets_hostname", "registry_assets", ["hostname"])
    op.create_index("ix_registry_assets_location", "registry_assets", ["location_id"])
    op.create_index("ix_registry_assets_type_status", "registry_assets", ["asset_type", "status"])


def downgrade() -> None:
    op.drop_index("ix_registry_assets_type_status", table_name="registry_assets")
    op.drop_index("ix_registry_assets_location", table_name="registry_assets")
    op.drop_index("ix_registry_assets_hostname", table_name="registry_assets")
    op.drop_index("ix_registry_assets_department", table_name="registry_assets")
    op.drop_index("ix_registry_assets_assigned_person", table_name="registry_assets")
    op.drop_table("registry_assets")
    op.drop_index("ix_registry_people_status", table_name="registry_people")
    op.drop_index("ix_registry_people_location", table_name="registry_people")
    op.drop_index("ix_registry_people_department", table_name="registry_people")
    op.drop_table("registry_people")
    op.drop_index("ix_registry_services_status", table_name="registry_services")
    op.drop_index("ix_registry_services_owner_queue", table_name="registry_services")
    op.drop_table("registry_services")
    op.drop_table("registry_vendors")
    op.drop_index("ix_registry_locations_status", table_name="registry_locations")
    op.drop_index("ix_registry_locations_building_room", table_name="registry_locations")
    op.drop_table("registry_locations")
    op.drop_index("ix_registry_departments_status", table_name="registry_departments")
    op.drop_index("ix_registry_departments_name", table_name="registry_departments")
    op.drop_table("registry_departments")
