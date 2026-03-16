"""add agent_builds tables

Revision ID: 016
Revises: 015
Create Date: 2026-02-05 10:00:00.000000

Remote agent self-update: registry of uploaded pc_agent builds + download audit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_builds",
        sa.Column("target", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="stable"),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("uploaded_by", sa.String(20), nullable=False, server_default="admin"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("target", "channel", "version"),
        sa.UniqueConstraint("sha256", name="uq_agent_builds_sha256"),
    )
    op.create_index("ix_agent_builds_sha256", "agent_builds", ["sha256"])
    op.create_index("ix_agent_builds_created_at", "agent_builds", ["created_at"])
    op.create_index(
        "ix_agent_builds_target_channel_created_at",
        "agent_builds",
        ["target", "channel", "created_at"],
    )

    op.create_table(
        "agent_build_download_audit",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_prefix", sa.String(8), nullable=True),
        sa.Column("target", sa.String(50), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("downloaded_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
    )
    op.create_index("ix_agent_build_dl_audit_token_hash", "agent_build_download_audit", ["token_hash"])
    op.create_index(
        "ix_agent_build_dl_audit_build",
        "agent_build_download_audit",
        ["target", "channel", "version"],
    )
    op.create_index(
        "ix_agent_build_dl_audit_downloaded_at",
        "agent_build_download_audit",
        ["downloaded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_build_dl_audit_downloaded_at", table_name="agent_build_download_audit")
    op.drop_index("ix_agent_build_dl_audit_build", table_name="agent_build_download_audit")
    op.drop_index("ix_agent_build_dl_audit_token_hash", table_name="agent_build_download_audit")
    op.drop_table("agent_build_download_audit")

    op.drop_index("ix_agent_builds_target_channel_created_at", table_name="agent_builds")
    op.drop_index("ix_agent_builds_created_at", table_name="agent_builds")
    op.drop_index("ix_agent_builds_sha256", table_name="agent_builds")
    op.drop_table("agent_builds")

