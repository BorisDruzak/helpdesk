"""universal knowledge platform

Revision ID: 083
Revises: 082
Create Date: 2026-05-14 17:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "083"
down_revision: Union[str, None] = "082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VISIBILITY_CHECK = (
    "visibility IN ('public', 'requester', 'agent_requester_safe', 'support_internal', "
    "'admin_internal', 'security_restricted', 'auditor_read')"
)


def upgrade() -> None:
    op.create_table(
        "knowledge_spaces",
        sa.Column("space_id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("lifecycle_status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("default_reviewer_actor_id", sa.Text(), nullable=True),
        sa.Column("default_review_period_days", sa.Integer(), nullable=True),
        sa.Column("allowed_item_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("allow_publication", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_ingestion", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_rag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.CheckConstraint("code ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_spaces_code_safe"),
        sa.CheckConstraint(VISIBILITY_CHECK, name="ck_knowledge_spaces_visibility"),
        sa.CheckConstraint("lifecycle_status IN ('draft', 'active', 'archived')", name="ck_knowledge_spaces_lifecycle"),
    )
    op.create_index("ix_knowledge_spaces_status_visibility", "knowledge_spaces", ["lifecycle_status", "visibility"])

    op.create_table(
        "knowledge_items",
        sa.Column("item_id", sa.String(length=36), primary_key=True),
        sa.Column("space_id", sa.String(length=36), sa.ForeignKey("knowledge_spaces.space_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("language", sa.String(length=12), nullable=False, server_default="ru"),
        sa.Column("owner_actor_id", sa.Text(), nullable=True),
        sa.Column("reviewer_actor_id", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("source_kind", sa.String(length=40), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("source_ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_passport_id", sa.BigInteger(), sa.ForeignKey("ticket_resolution_passports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("review_due_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("archived_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.CheckConstraint("slug ~ '^[a-z0-9][a-z0-9_-]*$'", name="ck_knowledge_items_slug_safe"),
        sa.CheckConstraint("item_type IN ('article', 'faq', 'runbook', 'policy', 'document', 'known_error', 'workaround', 'troubleshooting_tree', 'glossary_term', 'service_description', 'external_source', 'resolution_draft')", name="ck_knowledge_items_type"),
        sa.CheckConstraint("status IN ('draft', 'in_review', 'published', 'needs_review', 'archived')", name="ck_knowledge_items_status"),
        sa.CheckConstraint(VISIBILITY_CHECK, name="ck_knowledge_items_visibility"),
        sa.CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)", name="ck_knowledge_items_confidence"),
    )
    op.create_index("ix_knowledge_items_space_status", "knowledge_items", ["space_id", "status"])
    op.create_index("ix_knowledge_items_type_status", "knowledge_items", ["item_type", "status"])
    op.create_index("ix_knowledge_items_visibility_status", "knowledge_items", ["visibility", "status"])
    op.create_index("ix_knowledge_items_source_ticket", "knowledge_items", ["source_ticket_id"])

    op.create_table(
        "knowledge_item_versions",
        sa.Column("version_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("body_format", sa.String(length=30), nullable=False, server_default="markdown"),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("rendered_body", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("source_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("published_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("item_id", "version_number", name="uq_knowledge_item_versions_item_number"),
        sa.CheckConstraint("body_format IN ('markdown', 'html', 'plain_text', 'json', 'structured_steps')", name="ck_knowledge_item_versions_body_format"),
    )
    op.create_index("ix_knowledge_item_versions_item_created", "knowledge_item_versions", ["item_id", "created_at"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_ref", sa.Text(), nullable=True),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("version_id", "chunk_index", name="uq_knowledge_chunks_version_index"),
    )
    op.create_index("ix_knowledge_chunks_item_version", "knowledge_chunks", ["item_id", "version_id"])
    op.create_index("ix_knowledge_chunks_hash", "knowledge_chunks", ["content_hash"])
    op.create_index("ix_knowledge_chunks_visibility", "knowledge_chunks", ["visibility"])

    op.create_table(
        "knowledge_bindings",
        sa.Column("binding_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_template_key", sa.String(length=100), nullable=True),
        sa.Column("ticket_type", sa.String(length=64), nullable=True),
        sa.Column("reporting_category", sa.String(length=120), nullable=True),
        sa.Column("device_class", sa.String(length=80), nullable=True),
        sa.Column("os_family", sa.String(length=80), nullable=True),
        sa.Column("symptom_code", sa.String(length=120), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("priority", sa.String(length=10), nullable=True),
        sa.Column("queue_code", sa.String(length=120), nullable=True),
        sa.Column("weight", sa.Numeric(6, 3), nullable=False, server_default="1"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_knowledge_bindings_item", "knowledge_bindings", ["item_id"])
    op.create_index("ix_knowledge_bindings_service_offering", "knowledge_bindings", ["service_code", "offering_code"])
    op.create_index("ix_knowledge_bindings_template", "knowledge_bindings", ["request_template_key"])
    op.create_index("ix_knowledge_bindings_symptom_error", "knowledge_bindings", ["symptom_code", "error_code"])

    op.create_table(
        "knowledge_nodes",
        sa.Column("node_id", sa.String(length=36), primary_key=True),
        sa.Column("node_type", sa.String(length=40), nullable=False),
        sa.Column("stable_key", sa.String(length=240), nullable=False, unique=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("linked_item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="confirmed"),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
    )
    op.create_index("ix_knowledge_nodes_type_status", "knowledge_nodes", ["node_type", "status"])
    op.create_index("ix_knowledge_nodes_item", "knowledge_nodes", ["linked_item_id"])
    op.create_index("ix_knowledge_nodes_service_offering", "knowledge_nodes", ["service_code", "offering_code"])

    op.create_table(
        "knowledge_edges",
        sa.Column("edge_id", sa.String(length=36), primary_key=True),
        sa.Column("source_node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(length=50), nullable=False),
        sa.Column("weight", sa.Numeric(6, 3), nullable=False, server_default="1"),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="confirmed"),
        sa.Column("source_kind", sa.String(length=40), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("valid_from", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("valid_to", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_node_id", "target_node_id", "relation_type", "source_ref", name="uq_knowledge_edges_exact"),
    )
    op.create_index("ix_knowledge_edges_source", "knowledge_edges", ["source_node_id", "relation_type"])
    op.create_index("ix_knowledge_edges_target", "knowledge_edges", ["target_node_id", "relation_type"])

    op.create_table(
        "knowledge_entity_mentions",
        sa.Column("mention_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="SET NULL"), nullable=True),
        sa.Column("node_id", sa.String(length=36), sa.ForeignKey("knowledge_nodes.node_id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=60), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("extraction_method", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="proposed"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_knowledge_mentions_item_version", "knowledge_entity_mentions", ["item_id", "version_id"])
    op.create_index("ix_knowledge_mentions_node", "knowledge_entity_mentions", ["node_id"])

    op.create_table(
        "knowledge_feedback_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_id", sa.String(length=36), sa.ForeignKey("knowledge_chunks.chunk_id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.String(length=40), nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="SET NULL"), nullable=True),
        sa.Column("service_code", sa.String(length=100), nullable=True),
        sa.Column("offering_code", sa.String(length=220), nullable=True),
        sa.Column("request_template_key", sa.String(length=100), nullable=True),
        sa.Column("source_surface", sa.String(length=40), nullable=False, server_default="api"),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("result", sa.String(length=80), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_knowledge_feedback_item_event_created", "knowledge_feedback_events", ["item_id", "event_type", "created_at"])
    op.create_index("ix_knowledge_feedback_service_offering_created", "knowledge_feedback_events", ["service_code", "offering_code", "created_at"])
    op.create_index("ix_knowledge_feedback_ticket", "knowledge_feedback_events", ["ticket_id"])

    op.create_table(
        "knowledge_ingestion_jobs",
        sa.Column("job_id", sa.String(length=36), primary_key=True),
        sa.Column("space_id", sa.String(length=36), sa.ForeignKey("knowledge_spaces.space_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("created_item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_message_redacted", sa.Text(), nullable=True),
        sa.Column("stats_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_knowledge_ingestion_jobs_space_status", "knowledge_ingestion_jobs", ["space_id", "status"])
    op.create_index("ix_knowledge_ingestion_jobs_created", "knowledge_ingestion_jobs", ["created_at"])

    op.create_table(
        "ticket_knowledge_links",
        sa.Column("link_id", sa.String(length=36), primary_key=True),
        sa.Column("ticket_id", sa.String(length=36), sa.ForeignKey("tickets.ticket_id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", sa.String(length=36), sa.ForeignKey("knowledge_items.item_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", sa.String(length=36), sa.ForeignKey("knowledge_item_versions.version_id", ondelete="SET NULL"), nullable=True),
        sa.Column("link_type", sa.String(length=40), nullable=False, server_default="support_linked"),
        sa.Column("visibility", sa.String(length=40), nullable=False, server_default="support_internal"),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("ticket_id", "item_id", "link_type", name="uq_ticket_knowledge_links_ticket_item_type"),
    )
    op.create_index("ix_ticket_knowledge_links_ticket", "ticket_knowledge_links", ["ticket_id", "created_at"])
    op.create_index("ix_ticket_knowledge_links_item", "ticket_knowledge_links", ["item_id"])


def downgrade() -> None:
    for index_name, table_name in (
        ("ix_ticket_knowledge_links_item", "ticket_knowledge_links"),
        ("ix_ticket_knowledge_links_ticket", "ticket_knowledge_links"),
        ("ix_knowledge_ingestion_jobs_created", "knowledge_ingestion_jobs"),
        ("ix_knowledge_ingestion_jobs_space_status", "knowledge_ingestion_jobs"),
        ("ix_knowledge_feedback_ticket", "knowledge_feedback_events"),
        ("ix_knowledge_feedback_service_offering_created", "knowledge_feedback_events"),
        ("ix_knowledge_feedback_item_event_created", "knowledge_feedback_events"),
        ("ix_knowledge_mentions_node", "knowledge_entity_mentions"),
        ("ix_knowledge_mentions_item_version", "knowledge_entity_mentions"),
        ("ix_knowledge_edges_target", "knowledge_edges"),
        ("ix_knowledge_edges_source", "knowledge_edges"),
        ("ix_knowledge_nodes_service_offering", "knowledge_nodes"),
        ("ix_knowledge_nodes_item", "knowledge_nodes"),
        ("ix_knowledge_nodes_type_status", "knowledge_nodes"),
        ("ix_knowledge_bindings_symptom_error", "knowledge_bindings"),
        ("ix_knowledge_bindings_template", "knowledge_bindings"),
        ("ix_knowledge_bindings_service_offering", "knowledge_bindings"),
        ("ix_knowledge_bindings_item", "knowledge_bindings"),
        ("ix_knowledge_chunks_visibility", "knowledge_chunks"),
        ("ix_knowledge_chunks_hash", "knowledge_chunks"),
        ("ix_knowledge_chunks_item_version", "knowledge_chunks"),
        ("ix_knowledge_item_versions_item_created", "knowledge_item_versions"),
        ("ix_knowledge_items_source_ticket", "knowledge_items"),
        ("ix_knowledge_items_visibility_status", "knowledge_items"),
        ("ix_knowledge_items_type_status", "knowledge_items"),
        ("ix_knowledge_items_space_status", "knowledge_items"),
        ("ix_knowledge_spaces_status_visibility", "knowledge_spaces"),
    ):
        op.drop_index(index_name, table_name=table_name)
    op.drop_table("ticket_knowledge_links")
    op.drop_table("knowledge_ingestion_jobs")
    op.drop_table("knowledge_feedback_events")
    op.drop_table("knowledge_entity_mentions")
    op.drop_table("knowledge_edges")
    op.drop_table("knowledge_nodes")
    op.drop_table("knowledge_bindings")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_item_versions")
    op.drop_table("knowledge_items")
    op.drop_table("knowledge_spaces")
