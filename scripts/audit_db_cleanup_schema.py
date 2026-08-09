#!/usr/bin/env python3
"""Audit DB cleanup table coverage against schema classification."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import tomllib


WORKSPACE = Path(os.environ.get("PC_CLIENT_WORKSPACE") or Path(__file__).resolve().parent.parent)
DEFAULT_CLASSIFICATION = WORKSPACE / "quality" / "db_table_classification.toml"
DEFAULT_STATIC_CLEANUP = WORKSPACE / "server" / "tests" / "conftest.py"

ALLOWED_CLASSIFICATIONS = {
    "ephemeral_test_data",
    "persistent_reference_fixture",
    "migration_metadata",
    "explicitly_excluded",
    "special_cleanup",
}
CLEANUP_REQUIRED_CLASSIFICATIONS = {"ephemeral_test_data"}
CASCADE_SAFE_ACTIONS = {"CASCADE", "SET NULL", "SET DEFAULT"}
RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES = {
    "ai_model_profiles",
    "ai_policy_profiles",
    "ai_providers",
    "ai_request_audit",
    "knowledge_ai_proposals",
    "knowledge_applicability_rules",
    "knowledge_article_editor_events",
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
    "knowledge_spaces",
    "knowledge_taxonomy_terms",
    "knowledge_user_bookmarks",
    "knowledge_version_diff_cache",
    "problem_known_error_links",
    "ticket_knowledge_links",
}

MIGRATION_ONLY_TABLES = {
    "knowledge_article_segments",
    "knowledge_segmentation_jobs",
    "knowledge_segmentation_profiles",
    "ticket_admin_audit_archive",
    "ticket_events_archive",
    "ticket_retention_runs",
} | RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES


@dataclass(frozen=True)
class ForeignKeyRef:
    child_table: str
    parent_table: str
    delete_action: str


@dataclass(frozen=True)
class SchemaSnapshot:
    tables: set[str]
    foreign_keys: tuple[ForeignKeyRef, ...] = ()


@dataclass(frozen=True)
class ClassificationRule:
    name: str
    classification: str
    tables: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    reason: str = ""

    def matches(self, table: str) -> bool:
        return table in self.tables or any(fnmatch(table, pattern) for pattern in self.patterns)


@dataclass(frozen=True)
class ClassificationCatalog:
    rules: tuple[ClassificationRule, ...]

    def matching_rules(self, table: str) -> tuple[ClassificationRule, ...]:
        return tuple(rule for rule in self.rules if rule.matches(table))

    @property
    def explicit_tables(self) -> set[str]:
        tables: set[str] = set()
        for rule in self.rules:
            tables.update(rule.tables)
        return tables


@dataclass(frozen=True)
class SchemaAuditReport:
    unclassified_tables: tuple[str, ...] = ()
    multiply_classified_tables: dict[str, tuple[str, ...]] = field(default_factory=dict)
    stale_catalog_tables: tuple[str, ...] = ()
    stale_static_cleanup_tables: tuple[str, ...] = ()
    stale_dynamic_cleanup_tables: tuple[str, ...] = ()
    ephemeral_missing_from_static_cleanup: tuple[str, ...] = ()
    dynamic_cleanup_missing_from_static: tuple[str, ...] = ()
    fk_cleanup_risks: tuple[str, ...] = ()

    @property
    def has_failures(self) -> bool:
        return any(
            (
                self.unclassified_tables,
                self.multiply_classified_tables,
                self.stale_catalog_tables,
                self.stale_static_cleanup_tables,
                self.stale_dynamic_cleanup_tables,
                self.ephemeral_missing_from_static_cleanup,
                self.dynamic_cleanup_missing_from_static,
                self.fk_cleanup_risks,
            )
        )

    def summary_counts(self) -> dict[str, int]:
        return {
            "unclassified_tables": len(self.unclassified_tables),
            "multiply_classified_tables": len(self.multiply_classified_tables),
            "stale_catalog_tables": len(self.stale_catalog_tables),
            "stale_static_cleanup_tables": len(self.stale_static_cleanup_tables),
            "stale_dynamic_cleanup_tables": len(self.stale_dynamic_cleanup_tables),
            "ephemeral_missing_from_static_cleanup": len(self.ephemeral_missing_from_static_cleanup),
            "dynamic_cleanup_missing_from_static": len(self.dynamic_cleanup_missing_from_static),
            "fk_cleanup_risks": len(self.fk_cleanup_risks),
        }


def load_classification_catalog(path: Path) -> ClassificationCatalog:
    data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError(f"{path} must define at least one [[rules]] entry")

    rules: list[ClassificationRule] = []
    for index, raw_rule in enumerate(raw_rules, start=1):
        if not isinstance(raw_rule, dict):
            raise ValueError(f"{path} rule #{index} must be a table")
        name = str(raw_rule.get("name") or f"rule-{index}")
        classification = str(raw_rule.get("classification") or "")
        if classification not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(
                f"{path} rule {name!r} has invalid classification {classification!r}; "
                f"expected one of {sorted(ALLOWED_CLASSIFICATIONS)}"
            )
        tables = _string_tuple(raw_rule.get("tables", ()), field_name=f"{name}.tables")
        patterns = _string_tuple(raw_rule.get("patterns", ()), field_name=f"{name}.patterns")
        if not tables and not patterns:
            raise ValueError(f"{path} rule {name!r} must define tables or patterns")
        rules.append(
            ClassificationRule(
                name=name,
                classification=classification,
                tables=tables,
                patterns=patterns,
                reason=str(raw_rule.get("reason") or ""),
            )
        )
    return ClassificationCatalog(tuple(rules))


def _string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list of strings")
    result = tuple(str(item) for item in value)
    if any(not item for item in result):
        raise ValueError(f"{field_name} must not contain empty strings")
    return result


def load_static_cleanup_tables(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FULL_CLEANUP_TABLES" for target in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except (SyntaxError, ValueError) as exc:
                raise ValueError(f"Cannot evaluate FULL_CLEANUP_TABLES in {path}: {exc}") from exc
            if not isinstance(value, (tuple, list, set)):
                raise ValueError(f"FULL_CLEANUP_TABLES in {path} must be a sequence")
            return {str(item) for item in value}
    raise ValueError(f"FULL_CLEANUP_TABLES not found in {path}")


def load_schema_json(path: Path) -> SchemaSnapshot:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    tables = {str(table) for table in data.get("tables", ())}
    foreign_keys = tuple(_foreign_key_from_mapping(row) for row in data.get("foreign_keys", ()))
    return SchemaSnapshot(tables=tables, foreign_keys=foreign_keys)


def load_schema_from_models(workspace: Path) -> SchemaSnapshot:
    server_root = workspace / "server"
    if str(server_root) not in sys.path:
        sys.path.insert(0, str(server_root))
    from app.db.base import Base  # type: ignore
    import app.db.models  # noqa: F401  # type: ignore

    foreign_keys: list[ForeignKeyRef] = []
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            foreign_keys.append(
                ForeignKeyRef(
                    child_table=table.name,
                    parent_table=fk.column.table.name,
                    delete_action=(fk.ondelete or "NO ACTION").upper(),
                )
            )
    tables = set(Base.metadata.tables)
    tables.add("alembic_version")
    tables.update(MIGRATION_ONLY_TABLES)
    return SchemaSnapshot(tables=tables, foreign_keys=tuple(foreign_keys))


async def load_schema_from_database(workspace: Path, database_url: str | None) -> tuple[SchemaSnapshot, set[str]]:
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))
    from scripts import reset_test_data

    reset_test_data.load_server_env()
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    if str(reset_test_data.SERVER_ROOT) not in sys.path:
        sys.path.insert(0, str(reset_test_data.SERVER_ROOT))
    from app.db import get_engine, init_db, shutdown_db  # type: ignore

    await init_db(os.environ.get("DATABASE_URL"))
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            actual_tables = await reset_test_data.fetch_actual_tables(conn)
            foreign_keys = tuple(
                ForeignKeyRef(
                    child_table=fk.child_table,
                    parent_table=fk.parent_table,
                    delete_action=str(fk.delete_action).upper(),
                )
                for fk in await reset_test_data.fetch_foreign_keys(conn)
            )
        dynamic_cleanup = reset_test_data.build_clear_tables(actual_tables)
        return SchemaSnapshot(tables=actual_tables, foreign_keys=foreign_keys), set(dynamic_cleanup)
    finally:
        await shutdown_db()


def dynamic_cleanup_from_policy(actual_tables: Iterable[str]) -> set[str]:
    if str(WORKSPACE) not in sys.path:
        sys.path.insert(0, str(WORKSPACE))
    from scripts import reset_test_data

    return set(reset_test_data.build_clear_tables(actual_tables))


def audit_schema(
    schema: SchemaSnapshot,
    catalog: ClassificationCatalog,
    *,
    static_cleanup_tables: Iterable[str],
    dynamic_cleanup_tables: Iterable[str],
) -> SchemaAuditReport:
    actual_tables = set(schema.tables)
    static_cleanup = set(static_cleanup_tables)
    dynamic_cleanup = set(dynamic_cleanup_tables)

    table_classifications: dict[str, str] = {}
    unclassified: list[str] = []
    multiply_classified: dict[str, tuple[str, ...]] = {}
    for table in sorted(actual_tables):
        matches = catalog.matching_rules(table)
        if not matches:
            unclassified.append(table)
            continue
        if len(matches) > 1:
            multiply_classified[table] = tuple(rule.name for rule in matches)
            continue
        table_classifications[table] = matches[0].classification

    cleanup_covered = static_cleanup & actual_tables
    cleanup_not_required = {"special_cleanup"}
    ephemeral = {
        table
        for table, classification in table_classifications.items()
        if classification in CLEANUP_REQUIRED_CLASSIFICATIONS
    }
    special = {
        table
        for table, classification in table_classifications.items()
        if classification in cleanup_not_required
    }

    fk_risks = []
    for fk in schema.foreign_keys:
        if fk.parent_table not in cleanup_covered or fk.child_table in cleanup_covered:
            continue
        if fk.delete_action.upper() in CASCADE_SAFE_ACTIONS:
            continue
        if fk.child_table in special:
            continue
        fk_risks.append(f"{fk.child_table} -> {fk.parent_table} ({fk.delete_action.upper()})")

    return SchemaAuditReport(
        unclassified_tables=tuple(unclassified),
        multiply_classified_tables=multiply_classified,
        stale_catalog_tables=tuple(sorted(catalog.explicit_tables - actual_tables)),
        stale_static_cleanup_tables=tuple(sorted(static_cleanup - actual_tables)),
        stale_dynamic_cleanup_tables=tuple(sorted(dynamic_cleanup - actual_tables)),
        ephemeral_missing_from_static_cleanup=tuple(sorted(ephemeral - cleanup_covered)),
        dynamic_cleanup_missing_from_static=tuple(sorted((dynamic_cleanup & actual_tables) - cleanup_covered - special)),
        fk_cleanup_risks=tuple(sorted(fk_risks)),
    )


def _foreign_key_from_mapping(row: Mapping[str, Any]) -> ForeignKeyRef:
    return ForeignKeyRef(
        child_table=str(row["child_table"]),
        parent_table=str(row["parent_table"]),
        delete_action=str(row.get("delete_action") or "NO ACTION").upper(),
    )


def render_report(report: SchemaAuditReport) -> str:
    lines = ["DB cleanup schema audit"]
    counts = report.summary_counts()
    lines.append("Summary: " + ", ".join(f"{name}={count}" for name, count in counts.items()))
    for field_name in counts:
        value = getattr(report, field_name)
        if not value:
            continue
        lines.append("")
        lines.append(f"{field_name}:")
        if isinstance(value, dict):
            for table, rules in sorted(value.items()):
                lines.append(f"  - {table}: {', '.join(rules)}")
        else:
            for item in value:
                lines.append(f"  - {item}")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", type=Path, default=DEFAULT_CLASSIFICATION)
    parser.add_argument("--static-cleanup", type=Path, default=DEFAULT_STATIC_CLEANUP)
    parser.add_argument("--schema-json", type=Path)
    parser.add_argument("--schema-from-models", action="store_true")
    parser.add_argument("--database-url")
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text report.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when audit findings exist.")
    args = parser.parse_args(argv)

    catalog = load_classification_catalog(args.classification)
    static_cleanup_tables = load_static_cleanup_tables(args.static_cleanup)
    if args.schema_json and args.schema_from_models:
        parser.error("--schema-json and --schema-from-models are mutually exclusive")
    if args.schema_json:
        schema = load_schema_json(args.schema_json)
        dynamic_cleanup = dynamic_cleanup_from_policy(schema.tables)
    elif args.schema_from_models:
        schema = load_schema_from_models(args.workspace)
        dynamic_cleanup = dynamic_cleanup_from_policy(schema.tables)
    else:
        schema, dynamic_cleanup = asyncio.run(load_schema_from_database(args.workspace, args.database_url))

    report = audit_schema(
        schema,
        catalog,
        static_cleanup_tables=static_cleanup_tables,
        dynamic_cleanup_tables=dynamic_cleanup,
    )
    if args.json:
        payload = {
            "summary": report.summary_counts(),
            "has_failures": report.has_failures,
            **{
                field_name: getattr(report, field_name)
                for field_name in report.summary_counts()
                if field_name != "multiply_classified_tables"
            },
            "multiply_classified_tables": report.multiply_classified_tables,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_report(report), end="")
    return 1 if args.strict and report.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
