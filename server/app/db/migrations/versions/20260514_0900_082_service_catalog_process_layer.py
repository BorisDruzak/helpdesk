"""service catalog process layer

Revision ID: 082
Revises: 081
Create Date: 2026-05-14 09:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "082"
down_revision: Union[str, None] = "081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Service Catalog is a process/requester-facing layer. It links to CMDB
    # registry services but does not replace registry_services or legacy
    # tickets.service_id/category fields.
    op.create_table(
        "helpdesk_services",
        sa.Column("service_id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("public_title", sa.Text(), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=80), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="internal"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("business_criticality", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("owner_person_id", sa.String(length=36), sa.ForeignKey("registry_people.person_id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_queue_id", sa.BigInteger(), sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("support_group_code", sa.String(length=120), nullable=True),
        sa.Column("registry_service_id", sa.String(length=36), sa.ForeignKey("registry_services.service_id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_ticket_type_code", sa.String(length=64), nullable=True),
        sa.Column("default_queue_id", sa.BigInteger(), sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("default_priority_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_routing_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_sla_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_ola_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_approval_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_diagnostic_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_closure_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_visibility_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_notification_policy_code", sa.String(length=100), nullable=True),
        sa.Column("default_reporting_policy_code", sa.String(length=100), nullable=True),
        sa.Column("reporting_category", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("retired_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_services_code_safe"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'published', 'retired')", name="ck_helpdesk_services_lifecycle"),
        sa.CheckConstraint("visibility IN ('public', 'internal', 'restricted')", name="ck_helpdesk_services_visibility"),
        sa.CheckConstraint("business_criticality IN ('low', 'medium', 'high', 'critical')", name="ck_helpdesk_services_criticality"),
    )
    op.create_index("ix_helpdesk_services_status_visibility", "helpdesk_services", ["lifecycle_status", "visibility"])
    op.create_index("ix_helpdesk_services_registry_service", "helpdesk_services", ["registry_service_id"])
    op.create_index("ix_helpdesk_services_sort", "helpdesk_services", ["sort_order", "code"])

    op.create_table(
        "helpdesk_service_offerings",
        sa.Column("offering_id", sa.String(length=36), primary_key=True),
        sa.Column("service_id", sa.String(length=36), sa.ForeignKey("helpdesk_services.service_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("full_code", sa.String(length=220), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("public_title", sa.Text(), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("lifecycle_status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=24), nullable=False, server_default="internal"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ticket_type_code", sa.String(length=64), nullable=True),
        sa.Column("request_type", sa.String(length=64), nullable=True),
        sa.Column("request_template_id", sa.String(length=36), nullable=True),
        sa.Column("request_template_key", sa.String(length=100), nullable=True),
        sa.Column("form_schema_id", sa.String(length=120), nullable=True),
        sa.Column("default_queue_id", sa.BigInteger(), sa.ForeignKey("ticket_queues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority_policy_code", sa.String(length=100), nullable=True),
        sa.Column("routing_policy_code", sa.String(length=100), nullable=True),
        sa.Column("sla_policy_code", sa.String(length=100), nullable=True),
        sa.Column("ola_policy_code", sa.String(length=100), nullable=True),
        sa.Column("approval_policy_code", sa.String(length=100), nullable=True),
        sa.Column("diagnostic_policy_code", sa.String(length=100), nullable=True),
        sa.Column("closure_policy_code", sa.String(length=100), nullable=True),
        sa.Column("visibility_policy_code", sa.String(length=100), nullable=True),
        sa.Column("notification_policy_code", sa.String(length=100), nullable=True),
        sa.Column("reporting_policy_code", sa.String(length=100), nullable=True),
        sa.Column("reporting_category", sa.String(length=120), nullable=True),
        sa.Column("kb_article_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("availability_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("retired_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("service_id", "code", name="uq_helpdesk_service_offerings_service_code"),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_offerings_code_safe"),
        sa.CheckConstraint("full_code ~ '^[a-z0-9][a-z0-9_-]*[.][a-z0-9][a-z0-9_-]*$'", name="ck_helpdesk_offerings_full_code_safe"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'published', 'retired')", name="ck_helpdesk_offerings_lifecycle"),
        sa.CheckConstraint("visibility IN ('public', 'internal', 'restricted')", name="ck_helpdesk_offerings_visibility"),
    )
    op.create_index("ix_helpdesk_offerings_service_status_visibility", "helpdesk_service_offerings", ["service_id", "lifecycle_status", "visibility", "sort_order"])
    op.create_index("ix_helpdesk_offerings_template", "helpdesk_service_offerings", ["request_template_key"])
    op.create_index("ix_helpdesk_offerings_full_code", "helpdesk_service_offerings", ["full_code"])

    op.create_table(
        "helpdesk_service_catalog_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("object_type", sa.String(length=40), nullable=False),
        sa.Column("object_code", sa.String(length=220), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("issues_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_helpdesk_service_catalog_audit_object", "helpdesk_service_catalog_audit", ["object_type", "object_code", "created_at"])

    op.add_column("tickets", sa.Column("catalog_service_id", sa.String(length=36), nullable=True))
    op.add_column("tickets", sa.Column("catalog_offering_id", sa.String(length=36), nullable=True))
    op.add_column("tickets", sa.Column("service_code", sa.String(length=100), nullable=True))
    op.add_column("tickets", sa.Column("offering_code", sa.String(length=220), nullable=True))
    op.add_column("tickets", sa.Column("request_type", sa.String(length=64), nullable=True))
    op.add_column("tickets", sa.Column("business_criticality", sa.String(length=20), nullable=True))
    op.add_column("tickets", sa.Column("reporting_category", sa.String(length=120), nullable=True))
    op.add_column("tickets", sa.Column("service_owner_actor_id", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("support_group_code", sa.String(length=120), nullable=True))
    op.create_foreign_key("fk_tickets_catalog_service", "tickets", "helpdesk_services", ["catalog_service_id"], ["service_id"], ondelete="SET NULL")
    op.create_foreign_key("fk_tickets_catalog_offering", "tickets", "helpdesk_service_offerings", ["catalog_offering_id"], ["offering_id"], ondelete="SET NULL")
    op.create_index("ix_tickets_service_code", "tickets", ["service_code"])
    op.create_index("ix_tickets_offering_code", "tickets", ["offering_code"])
    op.create_index("ix_tickets_request_type", "tickets", ["request_type"])
    op.create_index("ix_tickets_reporting_category", "tickets", ["reporting_category"])
    op.create_index("ix_tickets_service_offering_created", "tickets", ["service_code", "offering_code", "created_at"])
    op.create_index("ix_tickets_catalog_service_created", "tickets", ["catalog_service_id", "created_at"])
    op.create_index("ix_tickets_catalog_offering_created", "tickets", ["catalog_offering_id", "created_at"])
    op.create_index("ix_tickets_reporting_category_created", "tickets", ["reporting_category", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_tickets_reporting_category_created", table_name="tickets")
    op.drop_index("ix_tickets_catalog_offering_created", table_name="tickets")
    op.drop_index("ix_tickets_catalog_service_created", table_name="tickets")
    op.drop_index("ix_tickets_service_offering_created", table_name="tickets")
    op.drop_index("ix_tickets_reporting_category", table_name="tickets")
    op.drop_index("ix_tickets_request_type", table_name="tickets")
    op.drop_index("ix_tickets_offering_code", table_name="tickets")
    op.drop_index("ix_tickets_service_code", table_name="tickets")
    op.drop_constraint("fk_tickets_catalog_offering", "tickets", type_="foreignkey")
    op.drop_constraint("fk_tickets_catalog_service", "tickets", type_="foreignkey")
    for column in (
        "support_group_code",
        "service_owner_actor_id",
        "reporting_category",
        "business_criticality",
        "request_type",
        "offering_code",
        "service_code",
        "catalog_offering_id",
        "catalog_service_id",
    ):
        op.drop_column("tickets", column)

    op.drop_index("ix_helpdesk_service_catalog_audit_object", table_name="helpdesk_service_catalog_audit")
    op.drop_table("helpdesk_service_catalog_audit")
    op.drop_index("ix_helpdesk_offerings_full_code", table_name="helpdesk_service_offerings")
    op.drop_index("ix_helpdesk_offerings_template", table_name="helpdesk_service_offerings")
    op.drop_index("ix_helpdesk_offerings_service_status_visibility", table_name="helpdesk_service_offerings")
    op.drop_table("helpdesk_service_offerings")
    op.drop_index("ix_helpdesk_services_sort", table_name="helpdesk_services")
    op.drop_index("ix_helpdesk_services_registry_service", table_name="helpdesk_services")
    op.drop_index("ix_helpdesk_services_status_visibility", table_name="helpdesk_services")
    op.drop_table("helpdesk_services")
