"""Retire the dead local Knowledge/AI physical schema.

Revision ID: 134
Revises: 133
Create Date: 2026-08-10 00:00:00

The active ORM deliberately has no Knowledge/AI model graph.  The target set,
FK edges and reverse-FK drop order below are therefore a static transcription
of revisions 083--087, 110--119, 121 and 123 plus the historical Problem
Management dependency.  Do not replace them with ORM or manifest imports.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "134"
down_revision: Union[str, None] = "133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# This is a static historical schema contract, intentionally independent from
# the current ORM and Registry retirement manifest.
RETIRED_KNOWLEDGE_AI_TABLES: tuple[str, ...] = (
    "ai_model_profiles",
    "ai_policy_profiles",
    "ai_providers",
    "ai_request_audit",
    "knowledge_ai_proposals",
    "knowledge_applicability_rules",
    "knowledge_article_editor_events",
    "knowledge_article_segments",
    "knowledge_article_subscriptions",
    "knowledge_article_views",
    "knowledge_audience_rules",
    "knowledge_bindings",
    "knowledge_chunk_embeddings",
    "knowledge_chunks",
    "knowledge_content_pack_items",
    "knowledge_content_packs",
    "knowledge_correction_requests",
    "knowledge_edges",
    "knowledge_entity_mentions",
    "knowledge_feedback_events",
    "knowledge_gap_findings",
    "knowledge_graph_layouts",
    "knowledge_index_jobs",
    "knowledge_ingestion_jobs",
    "knowledge_item_properties",
    "knowledge_item_taxonomy_terms",
    "knowledge_item_versions",
    "knowledge_items",
    "knowledge_nodes",
    "knowledge_property_definitions",
    "knowledge_quality_models",
    "knowledge_quality_snapshots",
    "knowledge_review_comments",
    "knowledge_review_tasks",
    "knowledge_rollout_policies",
    "knowledge_search_events",
    "knowledge_search_settings",
    "knowledge_segmentation_jobs",
    "knowledge_segmentation_profiles",
    "knowledge_spaces",
    "knowledge_taxonomy_terms",
    "knowledge_user_bookmarks",
    "knowledge_version_diff_cache",
    "problem_known_error_links",
    "ticket_knowledge_links",
)


# Child -> parent table edges from the historical migration graph.  Keeping
# this evidence beside the retirement migration makes review possible after
# the old runtime and ORM classes are gone.
HISTORICAL_KNOWLEDGE_AI_FK_EDGES: tuple[tuple[str, str], ...] = (
    ("ai_model_profiles", "ai_providers"),
    ("ai_request_audit", "ai_model_profiles"),
    ("ai_request_audit", "ai_providers"),
    ("knowledge_article_editor_events", "knowledge_item_versions"),
    ("knowledge_article_editor_events", "knowledge_items"),
    ("knowledge_article_segments", "knowledge_item_versions"),
    ("knowledge_article_segments", "knowledge_items"),
    ("knowledge_article_subscriptions", "knowledge_items"),
    ("knowledge_article_views", "knowledge_item_versions"),
    ("knowledge_article_views", "knowledge_items"),
    ("knowledge_bindings", "knowledge_items"),
    ("knowledge_chunk_embeddings", "ai_model_profiles"),
    ("knowledge_chunk_embeddings", "knowledge_chunks"),
    ("knowledge_chunk_embeddings", "knowledge_item_versions"),
    ("knowledge_chunk_embeddings", "knowledge_items"),
    ("knowledge_chunks", "knowledge_item_versions"),
    ("knowledge_chunks", "knowledge_items"),
    ("knowledge_content_pack_items", "knowledge_item_versions"),
    ("knowledge_content_pack_items", "knowledge_items"),
    ("knowledge_correction_requests", "knowledge_feedback_events"),
    ("knowledge_correction_requests", "knowledge_item_versions"),
    ("knowledge_correction_requests", "knowledge_items"),
    ("knowledge_edges", "knowledge_nodes"),
    ("knowledge_entity_mentions", "knowledge_chunks"),
    ("knowledge_entity_mentions", "knowledge_item_versions"),
    ("knowledge_entity_mentions", "knowledge_items"),
    ("knowledge_entity_mentions", "knowledge_nodes"),
    ("knowledge_feedback_events", "knowledge_chunks"),
    ("knowledge_feedback_events", "knowledge_item_versions"),
    ("knowledge_feedback_events", "knowledge_items"),
    ("knowledge_index_jobs", "ai_model_profiles"),
    ("knowledge_ingestion_jobs", "knowledge_item_versions"),
    ("knowledge_ingestion_jobs", "knowledge_items"),
    ("knowledge_ingestion_jobs", "knowledge_spaces"),
    ("knowledge_item_versions", "knowledge_items"),
    ("knowledge_items", "knowledge_spaces"),
    ("knowledge_nodes", "knowledge_items"),
    ("knowledge_quality_snapshots", "knowledge_item_versions"),
    ("knowledge_quality_snapshots", "knowledge_items"),
    ("knowledge_review_comments", "knowledge_review_tasks"),
    ("knowledge_review_tasks", "knowledge_item_versions"),
    ("knowledge_review_tasks", "knowledge_items"),
    ("knowledge_search_events", "knowledge_items"),
    ("knowledge_segmentation_jobs", "knowledge_item_versions"),
    ("knowledge_segmentation_jobs", "knowledge_items"),
    ("knowledge_user_bookmarks", "knowledge_item_versions"),
    ("knowledge_user_bookmarks", "knowledge_items"),
    ("knowledge_version_diff_cache", "knowledge_item_versions"),
    ("knowledge_version_diff_cache", "knowledge_items"),
    ("problem_known_error_links", "knowledge_items"),
    ("ticket_knowledge_links", "knowledge_item_versions"),
    ("ticket_knowledge_links", "knowledge_items"),
)


# Historical leaf-to-root reverse FK groups derived once from the static edge
# list above.  The migration uses this reviewed order directly rather than
# consulting runtime ORM metadata.
HISTORICAL_REVERSE_FK_DROP_ORDER: tuple[tuple[str, ...], ...] = (
    (
        "ai_policy_profiles",
        "ai_request_audit",
        "knowledge_ai_proposals",
        "knowledge_applicability_rules",
        "knowledge_article_editor_events",
        "knowledge_article_segments",
        "knowledge_article_subscriptions",
        "knowledge_article_views",
        "knowledge_audience_rules",
        "knowledge_bindings",
        "knowledge_chunk_embeddings",
        "knowledge_content_pack_items",
        "knowledge_content_packs",
        "knowledge_correction_requests",
        "knowledge_edges",
        "knowledge_entity_mentions",
        "knowledge_gap_findings",
        "knowledge_graph_layouts",
        "knowledge_index_jobs",
        "knowledge_ingestion_jobs",
        "knowledge_item_properties",
        "knowledge_item_taxonomy_terms",
        "knowledge_property_definitions",
        "knowledge_quality_models",
        "knowledge_quality_snapshots",
        "knowledge_review_comments",
        "knowledge_rollout_policies",
        "knowledge_search_events",
        "knowledge_search_settings",
        "knowledge_segmentation_jobs",
        "knowledge_segmentation_profiles",
        "knowledge_taxonomy_terms",
        "knowledge_user_bookmarks",
        "knowledge_version_diff_cache",
        "problem_known_error_links",
        "ticket_knowledge_links",
    ),
    (
        "ai_model_profiles",
        "knowledge_feedback_events",
        "knowledge_nodes",
        "knowledge_review_tasks",
    ),
    ("ai_providers", "knowledge_chunks"),
    ("knowledge_item_versions",),
    ("knowledge_items",),
    ("knowledge_spaces",),
)


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    """Drop the retired graph only, in static child-to-parent order."""

    for drop_group in HISTORICAL_REVERSE_FK_DROP_ORDER:
        for table_name in drop_group:
            if _has_table(table_name):
                op.drop_table(table_name)


def downgrade() -> None:
    raise RuntimeError(
        "Revision 134 is forward-only. Do not recreate retired Knowledge/AI tables with Alembic; "
        "roll back the application and restore the verified pre-retirement PostgreSQL backup."
    )
