"""device account sessions

Revision ID: 099
Revises: 098
Create Date: 2026-05-23 13:40:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "099"
down_revision: Union[str, None] = "098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("device_account_sessions"):
        op.create_table(
            "device_account_sessions",
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("session_token_hash", sa.Text(), nullable=True),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("account_mode", sa.String(40), nullable=False),
            sa.Column("verification_status", sa.String(40), nullable=False),
            sa.Column("verification_method", sa.String(40), nullable=True),
            sa.Column("person_id", sa.String(36), nullable=True),
            sa.Column("binding_id", sa.String(36), nullable=True),
            sa.Column("claim_id", sa.String(36), nullable=True),
            sa.Column("base_binding_id", sa.String(36), nullable=True),
            sa.Column("base_person_id", sa.String(36), nullable=True),
            sa.Column("declared_account", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("warning_code", sa.String(80), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("verified_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("verified_by", sa.Text(), nullable=True),
            sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("revoked_by", sa.Text(), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint(
                "account_mode IN ('confirmed_binding', 'registration_pending', 'verified_other_account', 'unverified_other_account')",
                name="ck_device_account_sessions_mode",
            ),
            sa.CheckConstraint(
                "verification_status IN ('verified', 'pending_verification', 'rejected', 'expired', 'revoked')",
                name="ck_device_account_sessions_verification_status",
            ),
            sa.CheckConstraint(
                "verification_method IS NULL OR verification_method IN ('device_binding', 'registration_claim', 'admin_approval', 'email_otp', 'sso', 'break_glass')",
                name="ck_device_account_sessions_verification_method",
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["claim_id"], ["device_registration_claims.claim_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["base_binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["base_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("session_id"),
        )
    for index_name, columns in (
        ("ix_device_account_sessions_device_status", ["device_id", "verification_status"]),
        ("ix_device_account_sessions_person_status", ["person_id", "verification_status"]),
        ("ix_device_account_sessions_binding", ["binding_id"]),
        ("ix_device_account_sessions_base_binding", ["base_binding_id"]),
        ("ix_device_account_sessions_token_hash", ["session_token_hash"]),
        ("ix_device_account_sessions_mode_status", ["account_mode", "verification_status"]),
    ):
        if not _has_index("device_account_sessions", index_name):
            op.create_index(index_name, "device_account_sessions", columns)

    if not _has_table("device_account_login_requests"):
        op.create_table(
            "device_account_login_requests",
            sa.Column("request_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("requested_account", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("matched_person_id", sa.String(36), nullable=True),
            sa.Column("base_binding_id", sa.String(36), nullable=True),
            sa.Column("base_person_id", sa.String(36), nullable=True),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("verification_method", sa.String(40), nullable=False, server_default="admin_approval"),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column("reviewed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("resulting_session_id", sa.String(36), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint(
                "status IN ('pending_verification', 'approved', 'rejected', 'expired', 'canceled')",
                name="ck_device_account_login_requests_status",
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["matched_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["base_binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["base_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resulting_session_id"], ["device_account_sessions.session_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("request_id"),
        )
    for index_name, columns in (
        ("ix_device_account_login_requests_device_status", ["device_id", "status"]),
        ("ix_device_account_login_requests_matched_person_status", ["matched_person_id", "status"]),
        ("ix_device_account_login_requests_base_binding_status", ["base_binding_id", "status"]),
        ("ix_device_account_login_requests_status_requested", ["status", "requested_at"]),
    ):
        if not _has_index("device_account_login_requests", index_name):
            op.create_index(index_name, "device_account_login_requests", columns)


def downgrade() -> None:
    for table, indexes in (
        (
            "device_account_login_requests",
            (
                "ix_device_account_login_requests_status_requested",
                "ix_device_account_login_requests_base_binding_status",
                "ix_device_account_login_requests_matched_person_status",
                "ix_device_account_login_requests_device_status",
            ),
        ),
        (
            "device_account_sessions",
            (
                "ix_device_account_sessions_mode_status",
                "ix_device_account_sessions_token_hash",
                "ix_device_account_sessions_base_binding",
                "ix_device_account_sessions_binding",
                "ix_device_account_sessions_person_status",
                "ix_device_account_sessions_device_status",
            ),
        ),
    ):
        if _has_table(table):
            for index_name in indexes:
                if _has_index(table, index_name):
                    op.drop_index(index_name, table_name=table)
            op.drop_table(table)
