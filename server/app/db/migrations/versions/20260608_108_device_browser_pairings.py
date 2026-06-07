"""Add persisted browser pairing state.

Revision ID: 108
Revises: 107
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP


revision: str = "108"
down_revision: Union[str, None] = "107"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_index(table: str, name: str) -> bool:
    if not _has_table(table):
        return False
    return name in {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_table("device_browser_pairings"):
        op.create_table(
            "device_browser_pairings",
            sa.Column("pairing_id", sa.String(36), nullable=False),
            sa.Column("device_id", sa.String(36), nullable=False),
            sa.Column("purpose", sa.String(40), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("pairing_token_hash", sa.Text(), nullable=False),
            sa.Column("pairing_code_hash", sa.Text(), nullable=False),
            sa.Column("resulting_account_session_id", sa.String(36), nullable=True),
            sa.Column("confirmed_person_id", sa.String(36), nullable=True),
            sa.Column("binding_id", sa.String(36), nullable=True),
            sa.Column("claim_id", sa.String(36), nullable=True),
            sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
            sa.Column("confirmed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("confirmed_by", sa.Text(), nullable=True),
            sa.Column("consumed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.CheckConstraint("purpose IN ('login', 'registration')", name="ck_device_browser_pairings_purpose"),
            sa.CheckConstraint(
                "status IN ('pending', 'confirmed', 'consumed', 'expired', 'canceled', 'superseded', 'failed')",
                name="ck_device_browser_pairings_status",
            ),
            sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["resulting_account_session_id"], ["device_account_sessions.session_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["confirmed_person_id"], ["registry_people.person_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["binding_id"], ["device_user_bindings.binding_id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["claim_id"], ["device_registration_claims.claim_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("pairing_id"),
        )
    for index_name, columns in (
        ("ix_device_browser_pairings_device_status", ["device_id", "status"]),
        ("ix_device_browser_pairings_device_purpose_status", ["device_id", "purpose", "status"]),
        ("ix_device_browser_pairings_code_hash", ["pairing_code_hash"]),
        ("ix_device_browser_pairings_token_hash", ["pairing_token_hash"]),
        ("ix_device_browser_pairings_session", ["resulting_account_session_id"]),
    ):
        if not _has_index("device_browser_pairings", index_name):
            op.create_index(index_name, "device_browser_pairings", columns)


def downgrade() -> None:
    if _has_table("device_browser_pairings"):
        for index_name in (
            "ix_device_browser_pairings_session",
            "ix_device_browser_pairings_token_hash",
            "ix_device_browser_pairings_code_hash",
            "ix_device_browser_pairings_device_purpose_status",
            "ix_device_browser_pairings_device_status",
        ):
            if _has_index("device_browser_pairings", index_name):
                op.drop_index(index_name, table_name="device_browser_pairings")
        op.drop_table("device_browser_pairings")
