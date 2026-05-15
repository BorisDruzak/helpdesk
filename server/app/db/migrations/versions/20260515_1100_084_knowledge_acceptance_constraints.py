"""knowledge acceptance enum constraints

Revision ID: 084
Revises: 083
Create Date: 2026-05-15 11:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "084"
down_revision: Union[str, None] = "083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VISIBILITY = (
    "('public', 'requester', 'agent_requester_safe', 'support_internal', "
    "'admin_internal', 'security_restricted', 'auditor_read')"
)
NODE_TYPES = (
    "('knowledge_item', 'article', 'known_error', 'workaround', 'glossary_term', "
    "'service', 'offering', 'ticket', 'asset', 'registry_service', "
    "'diagnostic_playbook', 'external_entity', 'concept', 'document')"
)
RELATIONS = (
    "('explains', 'causes', 'caused_by', 'depends_on', 'affects', 'affected_by', "
    "'has_workaround', 'has_permanent_fix', 'requires', 'replaces', 'duplicates', "
    "'similar_to', 'belongs_to_service', 'belongs_to_offering', 'suggested_for', "
    "'tried_in_ticket', 'resolved_by', 'source_of', 'mentions', 'synonym_of', "
    "'contradicts', 'supersedes')"
)
GRAPH_STATUSES = "('proposed', 'confirmed', 'rejected', 'archived')"
MENTION_STATUSES = "('proposed', 'confirmed', 'rejected')"
FEEDBACK_EVENTS = (
    "('suggested', 'viewed', 'helpful', 'not_helpful', 'deflected', "
    "'ticket_created_after_view', 'support_linked', 'support_used', "
    "'draft_created', 'published', 'archived')"
)
SURFACES = "('requester_portal', 'agent_gui', 'support_workspace', 'admin', 'api', 'search')"
ACTOR_ROLES = "('public', 'requester', 'user', 'agent', 'support', 'admin', 'auditor', 'security')"
INGESTION_KINDS = "('manual_upload', 'text', 'markdown', 'html', 'pdf', 'docx', 'external_url', 'ticket_passport', 'git_repo', 'api')"
INGESTION_STATUSES = "('queued', 'parsing', 'chunking', 'indexing', 'review_required', 'completed', 'failed', 'canceled')"
LINK_TYPES = "('suggested', 'user_tried', 'support_linked', 'used_for_resolution', 'generated_from_ticket')"


CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("knowledge_nodes", "ck_knowledge_nodes_node_type", f"node_type IN {NODE_TYPES}"),
    ("knowledge_nodes", "ck_knowledge_nodes_visibility", f"visibility IN {VISIBILITY}"),
    ("knowledge_nodes", "ck_knowledge_nodes_status", f"status IN {GRAPH_STATUSES}"),
    ("knowledge_nodes", "ck_knowledge_nodes_confidence", "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)"),
    ("knowledge_edges", "ck_knowledge_edges_relation_type", f"relation_type IN {RELATIONS}"),
    ("knowledge_edges", "ck_knowledge_edges_visibility", f"visibility IN {VISIBILITY}"),
    ("knowledge_edges", "ck_knowledge_edges_status", f"status IN {GRAPH_STATUSES}"),
    ("knowledge_edges", "ck_knowledge_edges_confidence", "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)"),
    ("knowledge_edges", "ck_knowledge_edges_weight_nonnegative", "weight >= 0"),
    ("knowledge_edges", "ck_knowledge_edges_no_self_relation", "source_node_id <> target_node_id"),
    ("knowledge_entity_mentions", "ck_knowledge_mentions_extraction_method", "extraction_method IN ('manual', 'rule', 'model', 'import')"),
    ("knowledge_entity_mentions", "ck_knowledge_mentions_status", f"status IN {MENTION_STATUSES}"),
    ("knowledge_entity_mentions", "ck_knowledge_mentions_confidence", "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)"),
    ("knowledge_feedback_events", "ck_knowledge_feedback_source_surface", f"source_surface IN {SURFACES}"),
    ("knowledge_feedback_events", "ck_knowledge_feedback_event_type", f"event_type IN {FEEDBACK_EVENTS}"),
    ("knowledge_feedback_events", "ck_knowledge_feedback_actor_role", f"actor_role IS NULL OR actor_role IN {ACTOR_ROLES}"),
    ("knowledge_ingestion_jobs", "ck_knowledge_ingestion_source_kind", f"source_kind IN {INGESTION_KINDS}"),
    ("knowledge_ingestion_jobs", "ck_knowledge_ingestion_status", f"status IN {INGESTION_STATUSES}"),
    ("ticket_knowledge_links", "ck_ticket_knowledge_links_link_type", f"link_type IN {LINK_TYPES}"),
    ("ticket_knowledge_links", "ck_ticket_knowledge_links_visibility", f"visibility IN {VISIBILITY}"),
)


def upgrade() -> None:
    # The constraints are intentionally added after the P2 schema migration so legacy
    # install databases can upgrade first, then enforce the acceptance contract.
    for table_name, constraint_name, condition in CONSTRAINTS:
        op.create_check_constraint(constraint_name, table_name, condition)


def downgrade() -> None:
    for table_name, constraint_name, _condition in reversed(CONSTRAINTS):
        op.drop_constraint(constraint_name, table_name, type_="check")
