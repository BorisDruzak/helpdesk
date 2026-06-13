"""Add registry audience groups.

Revision ID: 120
Revises: 119
Create Date: 2026-06-13 20:35:00
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "120"
down_revision: Union[str, None] = "119"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return name in inspector.get_table_names()


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(table_name):
        return False
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _has_table("registry_audience_groups"):
        op.create_table(
            "registry_audience_groups",
            sa.Column("audience_group_id", sa.String(length=36), nullable=False),
            sa.Column("code", sa.String(length=120), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("source", sa.String(length=40), server_default="manual", nullable=False),
            sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("audience_group_id"),
            sa.UniqueConstraint("code", name="uq_registry_audience_groups_code"),
            sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_registry_audience_groups_code_safe"),
            sa.CheckConstraint(
                "source IN ('manual', 'department_rule', 'import', 'system', 'future_sync')",
                name="ck_registry_audience_groups_source",
            ),
            sa.CheckConstraint("status IN ('active', 'archived')", name="ck_registry_audience_groups_status"),
        )
    if not _has_index("registry_audience_groups", "ix_registry_audience_groups_status"):
        op.create_index("ix_registry_audience_groups_status", "registry_audience_groups", ["status"])
    if not _has_index("registry_audience_groups", "ix_registry_audience_groups_code"):
        op.create_index("ix_registry_audience_groups_code", "registry_audience_groups", ["code"])

    if not _has_table("registry_audience_group_members"):
        op.create_table(
            "registry_audience_group_members",
            sa.Column("membership_id", sa.String(length=36), nullable=False),
            sa.Column("audience_group_id", sa.String(length=36), nullable=False),
            sa.Column("member_type", sa.String(length=40), nullable=False),
            sa.Column("member_id", sa.Text(), nullable=False),
            sa.Column("include_children", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("source", sa.String(length=40), server_default="manual", nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("created_by", sa.Text(), nullable=True),
            sa.Column("updated_by", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["audience_group_id"], ["registry_audience_groups.audience_group_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("membership_id"),
            sa.UniqueConstraint(
                "audience_group_id",
                "member_type",
                "member_id",
                "include_children",
                name="uq_registry_audience_group_members_unique",
            ),
            sa.CheckConstraint(
                "member_type IN ('person', 'department', 'department_tree', 'location', 'access_group', 'role', 'service')",
                name="ck_registry_audience_group_members_type",
            ),
            sa.CheckConstraint(
                "source IN ('manual', 'department_rule', 'import', 'system', 'future_sync')",
                name="ck_registry_audience_group_members_source",
            ),
        )
    if not _has_index("registry_audience_group_members", "ix_registry_audience_group_members_group"):
        op.create_index("ix_registry_audience_group_members_group", "registry_audience_group_members", ["audience_group_id"])
    if not _has_index("registry_audience_group_members", "ix_registry_audience_group_members_member"):
        op.create_index("ix_registry_audience_group_members_member", "registry_audience_group_members", ["member_type", "member_id"])

    if not _has_table("registry_person_department_memberships"):
        op.create_table(
            "registry_person_department_memberships",
            sa.Column("membership_id", sa.String(length=36), nullable=False),
            sa.Column("person_id", sa.String(length=36), nullable=False),
            sa.Column("department_id", sa.String(length=36), nullable=False),
            sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("role_in_department", sa.String(length=80), nullable=True),
            sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("source", sa.String(length=40), server_default="manual", nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["department_id"], ["registry_departments.department_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("membership_id"),
            sa.UniqueConstraint("person_id", "department_id", "source", name="uq_registry_person_department_memberships_source"),
            sa.CheckConstraint(
                "source IN ('manual', 'department_rule', 'import', 'system', 'future_sync')",
                name="ck_registry_person_department_memberships_source",
            ),
        )
        op.get_bind().exec_driver_sql(
            """
            INSERT INTO registry_person_department_memberships (
                membership_id,
                person_id,
                department_id,
                is_primary,
                source,
                metadata_json,
                created_at,
                updated_at
            )
            SELECT
                md5(person_id || ':' || department_id || ':system'),
                person_id,
                department_id,
                true,
                'system',
                '{"backfill": "registry_people.department_id"}'::jsonb,
                now(),
                now()
            FROM registry_people
            WHERE department_id IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )
    if not _has_index("registry_person_department_memberships", "ix_registry_person_department_memberships_person"):
        op.create_index("ix_registry_person_department_memberships_person", "registry_person_department_memberships", ["person_id"])
    if not _has_index("registry_person_department_memberships", "ix_registry_person_department_memberships_department"):
        op.create_index("ix_registry_person_department_memberships_department", "registry_person_department_memberships", ["department_id"])
    if not _has_index("registry_person_department_memberships", "uq_registry_person_department_memberships_primary"):
        op.create_index(
            "uq_registry_person_department_memberships_primary",
            "registry_person_department_memberships",
            ["person_id"],
            unique=True,
            postgresql_where=sa.text("is_primary IS TRUE"),
        )


def downgrade() -> None:
    for table_name, index_names in (
        (
            "registry_person_department_memberships",
            (
                "uq_registry_person_department_memberships_primary",
                "ix_registry_person_department_memberships_department",
                "ix_registry_person_department_memberships_person",
            ),
        ),
        (
            "registry_audience_group_members",
            ("ix_registry_audience_group_members_member", "ix_registry_audience_group_members_group"),
        ),
        ("registry_audience_groups", ("ix_registry_audience_groups_code", "ix_registry_audience_groups_status")),
    ):
        if _has_table(table_name):
            for index_name in index_names:
                if _has_index(table_name, index_name):
                    op.drop_index(index_name, table_name=table_name)

    for table_name in (
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
