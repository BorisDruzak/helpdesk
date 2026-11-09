"""Confirmed identities and fail-closed server-side OIDC sessions.

Revision ID: 151
Revises: 150
Existing users retain password access; no identities are inferred or migrated.
"""
from alembic import op
import sqlalchemy as sa

revision = "151"
down_revision = "150"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ui_users", sa.Column("password_login_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("ui_tokens", sa.Column("auth_method", sa.String(20), nullable=False, server_default="password"))
    op.create_table("confirmed_identity_bindings",
        sa.Column("binding_id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("registry_people.person_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_login", sa.String(100), sa.ForeignKey("ui_users.user_login", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("ad_object_guid", sa.String(36), nullable=False, unique=True),
        sa.Column("confirmed_by", sa.String(100), nullable=False),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("verification_reference", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("revoked_by", sa.String(100)),
        sa.UniqueConstraint("issuer", "subject", name="uq_identity_binding_issuer_subject"))
    op.create_index("ix_identity_binding_person", "confirmed_identity_bindings", ["person_id"])
    op.create_table("identity_migration_candidates",
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("user_login", sa.String(100), nullable=False),
        sa.Column("issuer", sa.String(500), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("ad_object_guid", sa.String(36), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint("state IN ('pending','conflict','confirmed')", name="ck_identity_candidate_state"))
    op.create_table("oidc_flows",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("browser_hash", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(100), nullable=False),
        sa.Column("verifier_encrypted", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False))
    op.create_index("ix_oidc_flows_expires_at", "oidc_flows", ["expires_at"])
    op.create_table("oidc_sessions",
        sa.Column("token_hash", sa.String(64), sa.ForeignKey("ui_tokens.token_hash", ondelete="CASCADE"), primary_key=True),
        sa.Column("binding_id", sa.String(36), sa.ForeignKey("confirmed_identity_bindings.binding_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("upstream_token_encrypted", sa.Text(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text()),
        sa.Column("nonce", sa.String(100), nullable=False),
        sa.Column("upstream_sid", sa.String(255)),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("max_expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("acr", sa.String(255)))


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM confirmed_identity_bindings")):
        raise RuntimeError("Revoke and explicitly archive SSO identities before downgrade")
    for table in ("oidc_sessions", "oidc_flows", "identity_migration_candidates", "confirmed_identity_bindings"):
        op.drop_table(table)
    op.drop_column("ui_users", "password_login_enabled")
    op.drop_column("ui_tokens", "auth_method")
