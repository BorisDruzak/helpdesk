"""registry management center p1 policy and admin events

Revision ID: 103
Revises: 102
Create Date: 2026-05-24 18:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "103"
down_revision: Union[str, None] = "102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("registry_admin_policies"):
        op.create_table(
            "registry_admin_policies",
            sa.Column("policy_key", sa.String(length=80), nullable=False),
            sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("policy_key"),
        )

    if not _has_table("registry_admin_events"):
        op.create_table(
            "registry_admin_events",
            sa.Column("event_id", sa.String(length=36), nullable=False),
            sa.Column("object_type", sa.String(length=50), nullable=False),
            sa.Column("object_id", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("actor_id", sa.Text(), nullable=True),
            sa.Column("actor_role", sa.String(length=40), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("related_device_id", sa.String(length=36), nullable=True),
            sa.Column("related_person_id", sa.String(length=36), nullable=True),
            sa.Column("event_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.PrimaryKeyConstraint("event_id"),
        )

    for name, columns in {
        "ix_registry_admin_events_object_event_at": ["object_type", "object_id", "event_at"],
        "ix_registry_admin_events_device_event_at": ["related_device_id", "event_at"],
        "ix_registry_admin_events_person_event_at": ["related_person_id", "event_at"],
        "ix_registry_admin_events_type_event_at": ["event_type", "event_at"],
    }.items():
        if not _has_index("registry_admin_events", name):
            op.create_index(name, "registry_admin_events", columns)


def downgrade() -> None:
    if _has_table("registry_admin_events"):
        for name in (
            "ix_registry_admin_events_type_event_at",
            "ix_registry_admin_events_person_event_at",
            "ix_registry_admin_events_device_event_at",
            "ix_registry_admin_events_object_event_at",
        ):
            if _has_index("registry_admin_events", name):
                op.drop_index(name, table_name="registry_admin_events")
        op.drop_table("registry_admin_events")
    if _has_table("registry_admin_policies"):
        op.drop_table("registry_admin_policies")
