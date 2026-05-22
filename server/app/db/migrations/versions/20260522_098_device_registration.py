"""device registration claims and user bindings

Revision ID: 098
Revises: 097
Create Date: 2026-05-22 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "098"
down_revision: Union[str, None] = "097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _has_constraint(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    inspector = sa.inspect(op.get_bind())
    constraints = []
    constraints.extend(inspector.get_unique_constraints(table))
    constraints.extend(inspector.get_check_constraints(table))
    constraints.extend(inspector.get_foreign_keys(table))
    return name in {item.get("name") for item in constraints}


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    if not _has_table("registry_person_identities"):
        op.create_table(
            "registry_person_identities",
            sa.Column("identity_id", sa.String(36), nullable=False),
            sa.Column("person_id", sa.String(36), nullable=False),
            sa.Column("provider", sa.String(40), nullable=False),
            sa.Column("identifier", sa.Text(), nullable=False),
            sa.Column("normalized_identifier", sa.Text(), nullable=False),
            sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("source", sa.String(40), nullable=False, server_default="manual"),
            sa.Column("last_seen_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            *_timestamps(),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("identity_id"),
            sa.UniqueConstraint("provider", "normalized_identifier", name="uq_registry_person_identities_provider_identifier"),
        )
    if not _has_index("registry_person_identities", "ix_registry_person_identities_person"):
        op.create_index("ix_registry_person_identities_person", "registry_person_identities", ["person_id"])
    if not _has_index("registry_person_identities", "ix_registry_person_identities_provider_identifier"):
        op.create_index(
            "ix_registry_person_identities_provider_identifier",
            "registry_person_identities",
            ["provider", "normalized_identifier"],
        )

    if not _has_table("device_registration_claims"):
        op.create_table(
            "device_registration_claims",
            sa.Column("claim_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("asset_id", sa.String(36), nullable=True),
            sa.Column("person_id", sa.String(36), nullable=True),
            sa.Column("claim_type", sa.String(40), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("relationship_type", sa.String(40), nullable=False, server_default="primary_user"),
            sa.Column("profile_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("device_snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
            sa.Column("source", sa.String(40), nullable=False, server_default="agent_profile"),
            sa.Column("source_ref", sa.Text(), nullable=True),
            sa.Column("submitted_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("user_confirmed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("conflict_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            *_timestamps(),
            sa.CheckConstraint(
                "claim_type IN ('self_reported', 'agent_detected', 'admin_created', 'presence_inferred', 'import', 'sso')",
                name="ck_device_registration_claims_type",
            ),
            sa.CheckConstraint(
                "status IN ('draft', 'self_reported', 'pending_user_confirmation', 'user_confirmed', "
                "'pending_admin_review', 'approved', 'rejected', 'superseded', 'expired', 'conflict')",
                name="ck_device_registration_claims_status",
            ),
            sa.CheckConstraint(
                "relationship_type IN ('primary_user', 'responsible', 'owner', 'shared_user', 'temporary_user')",
                name="ck_device_registration_claims_relationship",
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["registry_assets.asset_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("claim_id"),
        )
    for index_name, columns in (
        ("ix_device_registration_claims_device_status", ["device_id", "status"]),
        ("ix_device_registration_claims_person_status", ["person_id", "status"]),
        ("ix_device_registration_claims_status_submitted", ["status", "submitted_at"]),
        ("ix_device_registration_claims_source_ref", ["source", "source_ref"]),
        ("ix_device_registration_claims_device_submitted", ["device_id", "submitted_at"]),
    ):
        if not _has_index("device_registration_claims", index_name):
            op.create_index(index_name, "device_registration_claims", columns)

    if not _has_table("device_user_bindings"):
        op.create_table(
            "device_user_bindings",
            sa.Column("binding_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("asset_id", sa.String(36), nullable=True),
            sa.Column("person_id", sa.String(36), nullable=False),
            sa.Column("relationship_type", sa.String(40), nullable=False, server_default="primary_user"),
            sa.Column("status", sa.String(40), nullable=False, server_default="active"),
            sa.Column("source_claim_id", sa.String(36), nullable=True),
            sa.Column("source", sa.String(40), nullable=False, server_default="registration_claim"),
            sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
            sa.Column("valid_from", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("valid_to", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("last_seen_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("confirmed_by_user_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("confirmed_by_admin", sa.Text(), nullable=True),
            sa.Column("confirmed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("revoked_by", sa.Text(), nullable=True),
            sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("revoke_reason", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            *_timestamps(),
            sa.CheckConstraint(
                "relationship_type IN ('primary_user', 'responsible', 'owner', 'shared_user', 'temporary_user')",
                name="ck_device_user_bindings_relationship",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'active', 'stale', 'revoked', 'transferred')",
                name="ck_device_user_bindings_status",
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["registry_assets.asset_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_claim_id"], ["device_registration_claims.claim_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("binding_id"),
        )
    for index_name, columns in (
        ("ix_device_user_bindings_device_status", ["device_id", "status"]),
        ("ix_device_user_bindings_person_status", ["person_id", "status"]),
        ("ix_device_user_bindings_asset_status", ["asset_id", "status"]),
        ("ix_device_user_bindings_source_claim", ["source_claim_id"]),
        ("ix_device_user_bindings_relationship_status", ["relationship_type", "status"]),
    ):
        if not _has_index("device_user_bindings", index_name):
            op.create_index(index_name, "device_user_bindings", columns)
    if not _has_index("device_user_bindings", "uq_device_user_bindings_active_primary_device"):
        op.create_index(
            "uq_device_user_bindings_active_primary_device",
            "device_user_bindings",
            ["device_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active' AND relationship_type = 'primary_user'"),
        )

    if not _has_table("device_registration_events"):
        op.create_table(
            "device_registration_events",
            sa.Column("event_id", sa.String(36), nullable=False),
            sa.Column("claim_id", sa.String(36), nullable=True),
            sa.Column("binding_id", sa.String(36), nullable=True),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("person_id", sa.String(36), nullable=True),
            sa.Column("event_type", sa.String(60), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(40), nullable=True),
            sa.Column("event_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.ForeignKeyConstraint(["claim_id"], ["device_registration_claims.claim_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("event_id"),
        )
    for index_name, columns in (
        ("ix_device_registration_events_device_event_at", ["device_id", "event_at"]),
        ("ix_device_registration_events_person_event_at", ["person_id", "event_at"]),
        ("ix_device_registration_events_claim", ["claim_id"]),
        ("ix_device_registration_events_binding", ["binding_id"]),
        ("ix_device_registration_events_type_event_at", ["event_type", "event_at"]),
    ):
        if not _has_index("device_registration_events", index_name):
            op.create_index(index_name, "device_registration_events", columns)

    inventory_columns = (
        ("person_id", sa.Column("person_id", sa.String(36), nullable=True)),
        ("asset_id", sa.Column("asset_id", sa.String(36), nullable=True)),
        ("source_binding_id", sa.Column("source_binding_id", sa.String(36), nullable=True)),
        ("registration_status", sa.Column("registration_status", sa.String(40), nullable=True)),
    )
    for column_name, column in inventory_columns:
        if _has_table("device_inventory_bindings") and not _has_column("device_inventory_bindings", column_name):
            op.add_column("device_inventory_bindings", column)
    for index_name, columns in (
        ("ix_device_inventory_bindings_person", ["person_id"]),
        ("ix_device_inventory_bindings_asset", ["asset_id"]),
        ("ix_device_inventory_bindings_source_binding", ["source_binding_id"]),
        ("ix_device_inventory_bindings_registration_status", ["registration_status"]),
    ):
        if _has_table("device_inventory_bindings") and not _has_index("device_inventory_bindings", index_name):
            op.create_index(index_name, "device_inventory_bindings", columns)

    ticket_columns = (
        ("requester_person_id", sa.Column("requester_person_id", sa.String(36), nullable=True)),
        ("requester_binding_id", sa.Column("requester_binding_id", sa.String(36), nullable=True)),
        ("requester_registration_status", sa.Column("requester_registration_status", sa.String(40), nullable=True)),
    )
    for column_name, column in ticket_columns:
        if _has_table("tickets") and not _has_column("tickets", column_name):
            op.add_column("tickets", column)
    for index_name, columns in (
        ("ix_tickets_requester_person_created", ["requester_person_id", "created_at"]),
        ("ix_tickets_requester_binding", ["requester_binding_id"]),
        ("ix_tickets_requester_registration_status", ["requester_registration_status"]),
    ):
        if _has_table("tickets") and not _has_index("tickets", index_name):
            op.create_index(index_name, "tickets", columns)


def downgrade() -> None:
    if _has_table("tickets"):
        for index_name in (
            "ix_tickets_requester_registration_status",
            "ix_tickets_requester_binding",
            "ix_tickets_requester_person_created",
        ):
            if _has_index("tickets", index_name):
                op.drop_index(index_name, table_name="tickets")
        for column_name in ("requester_registration_status", "requester_binding_id", "requester_person_id"):
            if _has_column("tickets", column_name):
                op.drop_column("tickets", column_name)

    if _has_table("device_inventory_bindings"):
        for index_name in (
            "ix_device_inventory_bindings_registration_status",
            "ix_device_inventory_bindings_source_binding",
            "ix_device_inventory_bindings_asset",
            "ix_device_inventory_bindings_person",
        ):
            if _has_index("device_inventory_bindings", index_name):
                op.drop_index(index_name, table_name="device_inventory_bindings")
        for column_name in ("registration_status", "source_binding_id", "asset_id", "person_id"):
            if _has_column("device_inventory_bindings", column_name):
                op.drop_column("device_inventory_bindings", column_name)

    for table, indexes in (
        (
            "device_registration_events",
            (
                "ix_device_registration_events_type_event_at",
                "ix_device_registration_events_binding",
                "ix_device_registration_events_claim",
                "ix_device_registration_events_person_event_at",
                "ix_device_registration_events_device_event_at",
            ),
        ),
        (
            "device_user_bindings",
            (
                "uq_device_user_bindings_active_primary_device",
                "ix_device_user_bindings_relationship_status",
                "ix_device_user_bindings_source_claim",
                "ix_device_user_bindings_asset_status",
                "ix_device_user_bindings_person_status",
                "ix_device_user_bindings_device_status",
            ),
        ),
        (
            "device_registration_claims",
            (
                "ix_device_registration_claims_device_submitted",
                "ix_device_registration_claims_source_ref",
                "ix_device_registration_claims_status_submitted",
                "ix_device_registration_claims_person_status",
                "ix_device_registration_claims_device_status",
            ),
        ),
        (
            "registry_person_identities",
            (
                "ix_registry_person_identities_provider_identifier",
                "ix_registry_person_identities_person",
            ),
        ),
    ):
        if _has_table(table):
            for index_name in indexes:
                if _has_index(table, index_name):
                    op.drop_index(index_name, table_name=table)
            op.drop_table(table)
