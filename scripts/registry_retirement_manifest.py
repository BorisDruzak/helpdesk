"""Declarative boundary for the future forward-only Registry/Knowledge retirement.

This module deliberately contains no database connection, SQL, Alembic call or
write operation.  It is the reviewed input to the later PR-11 migration, not
that migration itself.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


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
        # These are the actual Helpdesk UI/session/RBAC model tables.  They
        # are protected even though none belongs to the Registry model set.
        "auth_sessions",
        "ui_tokens",
        "ui_user_audit",
        "ui_password_reset_requests",
        "ticket_public_sessions",
        "access_groups",
        "access_group_members",
        "access_group_permissions",
        "access_group_queue_members",
        "access_audit",
        "ticket_queues",
        "ticket_queue_members",
        "ticket_queue_ola_targets",
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

def _models_path() -> Path:
    return Path(__file__).resolve().parents[1] / "server" / "app" / "db" / "models.py"


def _table_names_by_class(tree: ast.Module) -> dict[str, str]:
    table_names: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for child in node.body:
            if (
                isinstance(child, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__tablename__" for target in child.targets)
                and isinstance(child.value, ast.Constant)
                and isinstance(child.value.value, str)
            ):
                table_names[node.name] = child.value.value
    return table_names


def _foreign_key_target(call: ast.Call) -> str | None:
    function = call.func
    is_foreign_key = (
        isinstance(function, ast.Name) and function.id == "ForeignKey"
    ) or (
        isinstance(function, ast.Attribute) and function.attr == "ForeignKey"
    )
    if not is_foreign_key or not call.args:
        return None
    first = call.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return first.value.partition(".")[0] or None


def current_target_foreign_key_edges(
    target_tables: frozenset[str] | None = None,
    *,
    models_path: Path | None = None,
) -> tuple[tuple[str, str], ...]:
    """Read current model FKs without importing models or connecting to PostgreSQL.

    Each returned tuple is ``(child_table, parent_table)``.  A self-reference
    is intentionally omitted: dropping a table also drops its own constraint,
    so it does not impose an inter-table retirement order.
    """

    targets = target_tables or (RETIRED_KNOWLEDGE_AI_TABLES | RETIRED_REGISTRY_TABLES)
    source = (models_path or _models_path()).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(models_path or _models_path()))
    table_names = _table_names_by_class(tree)
    edges: set[tuple[str, str]] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        child_table = table_names.get(node.name)
        if child_table not in targets:
            continue
        for descendant in ast.walk(node):
            if not isinstance(descendant, ast.Call):
                continue
            parent_table = _foreign_key_target(descendant)
            if parent_table in targets and parent_table != child_table:
                edges.add((child_table, parent_table))
    return tuple(sorted(edges))


def _deterministic_reverse_fk_drop_order(
    target_tables: frozenset[str], edges: Iterable[tuple[str, str]],
) -> tuple[tuple[str, ...], ...]:
    """Return leaf-to-root drop groups for child -> parent FK edges."""

    remaining = set(target_tables)
    graph = set(edges)
    groups: list[tuple[str, ...]] = []
    while remaining:
        # A table is droppable only after every target child referencing it has
        # gone.  Sorting makes the reviewed order reproducible.
        group = tuple(
            sorted(
                table
                for table in remaining
                if not any(child in remaining and parent == table for child, parent in graph)
            )
        )
        if not group:
            cycle = ", ".join(sorted(remaining))
            raise ValueError(f"target FK graph has a cycle: {cycle}")
        groups.append(group)
        remaining.difference_update(group)
    return tuple(groups)


# Child-to-parent dependency order generated from the current SQLAlchemy model
# source.  The later migration must detach retained-table columns before these
# groups.  This is deterministic, source-only and never queries PostgreSQL.
_RETIREMENT_TARGETS = RETIRED_KNOWLEDGE_AI_TABLES | RETIRED_REGISTRY_TABLES
REVERSE_FOREIGN_KEY_DROP_ORDER = _deterministic_reverse_fk_drop_order(
    _RETIREMENT_TARGETS,
    current_target_foreign_key_edges(_RETIREMENT_TARGETS),
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
    ordered_sequence = tuple(table for group in manifest.drop_order for table in group)
    ordered = set(ordered_sequence)
    duplicates = sorted({table for table in ordered_sequence if ordered_sequence.count(table) > 1})
    if duplicates:
        errors.append(f"drop order contains duplicate target tables: {', '.join(duplicates)}")
    missing_order = manifest.target_tables - ordered
    extra_order = ordered - manifest.target_tables
    if missing_order:
        errors.append(f"target tables missing from drop order: {', '.join(sorted(missing_order))}")
    if extra_order:
        errors.append(f"drop order contains non-target tables: {', '.join(sorted(extra_order))}")
    positions = {table: index for index, table in enumerate(ordered_sequence)}
    for child, parent in current_target_foreign_key_edges(manifest.target_tables):
        if positions.get(child, -1) >= positions.get(parent, -1):
            errors.append(f"reverse FK order violates {child} -> {parent}")
    return tuple(errors)
