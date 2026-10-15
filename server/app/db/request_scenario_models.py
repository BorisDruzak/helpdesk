"""Guided Studio persistence; catalog, policies and tickets stay canonical."""
from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class RequestStudioCategory(Timestamps, Base):
    __tablename__ = "request_studio_categories"
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    service_code: Mapped[str] = mapped_column(sa.String(100), sa.ForeignKey("helpdesk_services.code", ondelete="RESTRICT"))
    parent_id: Mapped[str | None] = mapped_column(sa.String(36))
    slug: Mapped[str] = mapped_column(sa.String(100))
    title: Mapped[str] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, server_default="")
    sort_order: Mapped[int] = mapped_column(sa.Integer, server_default="0")
    visibility: Mapped[str] = mapped_column(sa.String(24), server_default="internal")
    lifecycle_status: Mapped[str] = mapped_column(sa.String(24), server_default="draft")
    revision: Mapped[int] = mapped_column(sa.Integer, server_default="1")
    created_by: Mapped[str | None] = mapped_column(sa.Text)
    updated_by: Mapped[str | None] = mapped_column(sa.Text)
    __table_args__ = (
        sa.UniqueConstraint("id", "service_code", name="uq_studio_category_id_service"),
        sa.ForeignKeyConstraint(["parent_id", "service_code"], ["request_studio_categories.id", "request_studio_categories.service_code"], name="fk_studio_category_parent_service", ondelete="RESTRICT"),
        sa.UniqueConstraint("service_code", "parent_id", "slug", name="uq_studio_category_sibling_slug"),
        sa.Index("uq_studio_category_root_slug", "service_code", "slug", unique=True, postgresql_where=sa.text("parent_id IS NULL")),
        sa.Index("ix_studio_category_tree", "service_code", "parent_id", "sort_order"),
        sa.CheckConstraint("visibility IN ('public','internal','restricted')", name="ck_studio_category_visibility"),
        sa.CheckConstraint("lifecycle_status IN ('draft','published','archived')", name="ck_studio_category_status"),
        sa.CheckConstraint("revision > 0", name="ck_studio_category_revision"),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_studio_category_slug"),
    )


class RequestStudioScenario(Timestamps, Base):
    __tablename__ = "request_studio_scenarios"
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_key: Mapped[str] = mapped_column(sa.String(100), unique=True)
    service_code: Mapped[str] = mapped_column(sa.String(100), sa.ForeignKey("helpdesk_services.code", ondelete="RESTRICT"))
    offering_full_code: Mapped[str] = mapped_column(sa.String(220), sa.ForeignKey("helpdesk_service_offerings.full_code", ondelete="RESTRICT"))
    category_id: Mapped[str | None] = mapped_column(sa.String(36))
    title: Mapped[str] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, server_default="")
    published_version_id: Mapped[str | None] = mapped_column(sa.String(36))
    enabled: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    archived: Mapped[bool] = mapped_column(sa.Boolean, server_default=sa.false())
    created_by: Mapped[str | None] = mapped_column(sa.Text)
    updated_by: Mapped[str | None] = mapped_column(sa.Text)
    __table_args__ = (
        sa.UniqueConstraint("id", "offering_full_code", name="uq_studio_scenario_id_offering"),
        sa.ForeignKeyConstraint(["category_id", "service_code"], ["request_studio_categories.id", "request_studio_categories.service_code"], name="fk_studio_scenario_category_service", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["id", "published_version_id"], ["request_studio_scenario_versions.scenario_id", "request_studio_scenario_versions.id"], name="fk_studio_scenario_active_version", use_alter=True, deferrable=True, initially="DEFERRED"),
        sa.CheckConstraint("split_part(offering_full_code,'.',1) = service_code", name="ck_studio_scenario_service"),
        sa.Index("ix_studio_scenario_offering", "offering_full_code"),
        sa.Index("ix_studio_scenario_category", "category_id"),
    )


class RequestStudioScenarioVersion(Base):
    __tablename__ = "request_studio_scenario_versions"
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(sa.String(36))
    offering_full_code: Mapped[str] = mapped_column(sa.String(220))
    version: Mapped[int] = mapped_column(sa.Integer)
    schema_version: Mapped[int] = mapped_column(sa.Integer)
    definition: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(sa.String(64))
    source_snapshot: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(sa.String(24), server_default="published")
    published_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now())
    published_by: Mapped[str] = mapped_column(sa.Text)
    __table_args__ = (
        sa.ForeignKeyConstraint(["scenario_id", "offering_full_code"], ["request_studio_scenarios.id", "request_studio_scenarios.offering_full_code"], name="fk_studio_version_scenario_offering", ondelete="RESTRICT"),
        sa.UniqueConstraint("scenario_id", "version", name="uq_studio_version_number"),
        sa.UniqueConstraint("scenario_id", "id", name="uq_studio_version_scenario_id"),
        sa.Index("uq_studio_version_active_offering", "offering_full_code", unique=True, postgresql_where=sa.text("state = 'published'")),
        sa.CheckConstraint("state IN ('published','retired','revoked')", name="ck_studio_version_state"),
        sa.CheckConstraint("version > 0 AND schema_version IN (1,2,3)", name="ck_studio_version_schema"),
        sa.CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'", name="ck_studio_version_hash"),
    )


class RequestStudioDraft(Base):
    __tablename__ = "request_studio_drafts"
    scenario_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("request_studio_scenarios.id", ondelete="CASCADE"), primary_key=True)
    definition: Mapped[dict] = mapped_column(JSONB)
    revision: Mapped[int] = mapped_column(sa.Integer, server_default="1")
    base_version_id: Mapped[str | None] = mapped_column(sa.String(36))
    updated_by: Mapped[str] = mapped_column(sa.Text)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    __table_args__ = (
        sa.ForeignKeyConstraint(["scenario_id", "base_version_id"], ["request_studio_scenario_versions.scenario_id", "request_studio_scenario_versions.id"], name="fk_studio_draft_base_version"),
        sa.CheckConstraint("revision > 0", name="ck_studio_draft_revision"),
    )


class RequestStudioSession(Timestamps, Base):
    __tablename__ = "request_studio_sessions"
    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_actor_id: Mapped[str] = mapped_column(sa.Text)
    version_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("request_studio_scenario_versions.id", ondelete="RESTRICT"))
    current_block_id: Mapped[str] = mapped_column(sa.String(100))
    revision: Mapped[int] = mapped_column(sa.Integer, server_default="1")
    answers: Mapped[dict] = mapped_column(JSONB, server_default=sa.text("'{}'::jsonb"))
    history: Mapped[list] = mapped_column(JSONB, server_default=sa.text("'[]'::jsonb"))
    results: Mapped[dict] = mapped_column(JSONB, server_default=sa.text("'{}'::jsonb"))
    state: Mapped[str] = mapped_column(sa.String(32), server_default="active")
    linked_ticket_id: Mapped[str | None] = mapped_column(sa.String(36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    __table_args__ = (
        sa.Index("ix_studio_session_owner", "owner_actor_id", "state", "expires_at"),
        sa.Index("ix_studio_session_version", "version_id"),
        sa.Index("ix_studio_session_ticket", "linked_ticket_id"),
        sa.CheckConstraint("revision > 0", name="ck_studio_session_revision"),
        sa.CheckConstraint("state IN ('active','completed_self_service','ticket_created','canceled','expired','revoked')", name="ck_studio_session_state"),
        sa.CheckConstraint("expires_at > created_at", name="ck_studio_session_expiry"),
    )
