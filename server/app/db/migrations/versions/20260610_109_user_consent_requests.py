"""Add canonical user consent requests.

Revision ID: 109
Revises: 108
Create Date: 2026-06-10
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "109"
down_revision: Union[str, None] = "108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("user_consent_requests"):
        op.create_table(
            "user_consent_requests",
            sa.Column("consent_id", sa.String(36), primary_key=True),
            sa.Column("subject_type", sa.String(40), nullable=False),
            sa.Column("subject_id", sa.String(80), nullable=False),
            sa.Column("ticket_id", sa.String(36), nullable=True),
            sa.Column("device_id", sa.String(36), nullable=True),
            sa.Column("requester_person_id", sa.String(36), nullable=True),
            sa.Column("requester_binding_id", sa.String(36), nullable=True),
            sa.Column("requester_account_session_id", sa.String(36), nullable=True),
            sa.Column("requested_by_actor_id", sa.Text(), nullable=True),
            sa.Column("requested_by_role", sa.String(40), nullable=True),
            sa.Column("risk_level", sa.String(40), nullable=True),
            sa.Column("policy_snapshot", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("risk_explanation", sa.Text(), nullable=True),
            sa.Column("requested_action_payload_redacted", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("decided_by_actor_id", sa.Text(), nullable=True),
            sa.Column("decided_by_role", sa.String(40), nullable=True),
            sa.Column("decided_from_surface", sa.String(30), nullable=True),
            sa.Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint(
                "subject_type IN ('operation', 'remote_assist', 'diagnostic', 'tool_run', 'file_transfer', 'clipboard', 'elevated')",
                name="ck_user_consent_requests_subject_type",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'approved', 'denied', 'expired', 'superseded', 'canceled')",
                name="ck_user_consent_requests_status",
            ),
            sa.CheckConstraint(
                "decided_from_surface IS NULL OR decided_from_surface IN ('browser', 'agent_gui', 'api')",
                name="ck_user_consent_requests_surface",
            ),
            sa.ForeignKeyConstraint(["ticket_id"], ["tickets.ticket_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requester_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requester_binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["requester_account_session_id"],
                ["device_account_sessions.session_id"],
                ondelete="SET NULL",
            ),
        )

    indexes = [
        ("ix_user_consent_requests_status_expires", ["status", "expires_at"], False, None),
        ("ix_user_consent_requests_person_status", ["requester_person_id", "status"], False, None),
        ("ix_user_consent_requests_device_status", ["device_id", "status"], False, None),
        ("ix_user_consent_requests_ticket", ["ticket_id"], False, None),
        ("ix_user_consent_requests_subject", ["subject_type", "subject_id"], False, None),
        (
            "ux_user_consent_requests_pending_subject",
            ["subject_type", "subject_id"],
            True,
            sa.text("status = 'pending'"),
        ),
    ]
    for name, columns, unique, where in indexes:
        if not _has_index("user_consent_requests", name):
            kwargs = {"unique": unique}
            if where is not None:
                kwargs["postgresql_where"] = where
            op.create_index(name, "user_consent_requests", columns, **kwargs)


def downgrade() -> None:
    if not _has_table("user_consent_requests"):
        return
    for name in (
        "ux_user_consent_requests_pending_subject",
        "ix_user_consent_requests_subject",
        "ix_user_consent_requests_ticket",
        "ix_user_consent_requests_device_status",
        "ix_user_consent_requests_person_status",
        "ix_user_consent_requests_status_expires",
    ):
        if _has_index("user_consent_requests", name):
            op.drop_index(name, table_name="user_consent_requests")
    op.drop_table("user_consent_requests")
