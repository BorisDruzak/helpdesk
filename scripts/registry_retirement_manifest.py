"""Declarative boundary for the future forward-only Registry/Knowledge retirement.

This module deliberately contains no database connection, SQL, Alembic call or
write operation.  It is the reviewed input to the later PR-11 migration, not
that migration itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class RetirementManifest:
    """Approved deletion scope and immutable Helpdesk-owned exclusions."""

    target_tables: frozenset[str]
    retain_tables: frozenset[str]
    detach_columns: Mapping[str, frozenset[str]]
    drop_order: tuple[tuple[str, ...], ...]


RETIRED_KNOWLEDGE_AI_TABLES = frozenset(
    {
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
    }
)

RETIRED_REGISTRY_TABLES = frozenset(
    {
        "device_account_events",
        "device_account_login_requests",
        "device_account_sessions",
        "device_browser_pairings",
        "device_registration_claims",
        "device_registration_events",
        "device_user_bindings",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_assets",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_departments",
        "registry_locations",
        "registry_people",
        "registry_person_department_memberships",
        "registry_person_identities",
        "registry_quality_issue_overrides",
        "registry_services",
        "registry_vendors",
    }
)

RETAIN_HELPDESK_TABLES = frozenset(
    {
        "tickets",
        "ticket_kb_links",
        "ui_users",
        "user_consent_requests",
        # UI session, token and RBAC table names are intentionally protected
        # even though they are not part of the Registry model set.
        "web_sessions",
        "web_session_tokens",
        "rbac_role_bindings",
        "rbac_permissions",
    }
)

RETIRED_FOREIGN_KEY_COLUMNS: Mapping[str, frozenset[str]] = {
    "tickets": frozenset(
        {
            "asset_id",
            "requester_account_mode",
            "requester_account_session_id",
            "requester_account_warning",
            "requester_binding_id",
            "requester_person_id",
            "requester_registration_status",
        }
    ),
    "user_consent_requests": frozenset(
        {
            "requester_account_session_id",
            "requester_binding_id",
            "requester_person_id",
        }
    ),
    "helpdesk_services": frozenset({"owner_person_id", "registry_service_id"}),
}

# Child-to-parent dependency order.  The later migration must detach the
# retained-table columns before it can drop these groups, and must never use a
# downgrade as a rollback mechanism.
REVERSE_FOREIGN_KEY_DROP_ORDER = (
    ("device_account_events", "device_browser_pairings"),
    ("device_account_sessions", "device_account_login_requests"),
    ("device_registration_events", "device_user_bindings", "device_registration_claims"),
    (
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_person_identities",
        "registry_quality_issue_overrides",
        "registry_admin_events",
        "registry_admin_policies",
    ),
    ("registry_assets", "registry_people", "registry_services", "registry_vendors", "registry_locations", "registry_departments"),
    ("ticket_knowledge_links", "problem_known_error_links"),
    tuple(sorted(RETIRED_KNOWLEDGE_AI_TABLES - {"ticket_knowledge_links", "problem_known_error_links"})),
)

RETIREMENT_MANIFEST = RetirementManifest(
    target_tables=RETIRED_KNOWLEDGE_AI_TABLES | RETIRED_REGISTRY_TABLES,
    retain_tables=RETAIN_HELPDESK_TABLES,
    detach_columns=RETIRED_FOREIGN_KEY_COLUMNS,
    drop_order=REVERSE_FOREIGN_KEY_DROP_ORDER,
)


def manifest_validation_errors(manifest: RetirementManifest = RETIREMENT_MANIFEST) -> tuple[str, ...]:
    """Return invariant violations without consulting a database."""

    errors: list[str] = []
    overlap = manifest.target_tables & manifest.retain_tables
    if overlap:
        errors.append(f"target/retain overlap: {', '.join(sorted(overlap))}")
    required_retained = {"ui_users", "tickets", "user_consent_requests", "ticket_kb_links"}
    missing_retained = required_retained - manifest.retain_tables
    if missing_retained:
        errors.append(f"required retained tables missing: {', '.join(sorted(missing_retained))}")
    ordered = {table for group in manifest.drop_order for table in group}
    missing_order = manifest.target_tables - ordered
    extra_order = ordered - manifest.target_tables
    if missing_order:
        errors.append(f"target tables missing from drop order: {', '.join(sorted(missing_order))}")
    if extra_order:
        errors.append(f"drop order contains non-target tables: {', '.join(sorted(extra_order))}")
    return tuple(errors)
