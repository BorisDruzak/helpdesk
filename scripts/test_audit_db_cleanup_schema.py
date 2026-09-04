import importlib
import json
from pathlib import Path


def test_retired_local_knowledge_tables_are_not_synthesized_into_post_134_schema_audit():
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")

    expected = {
        "ai_providers",
        "knowledge_items",
        "knowledge_article_views",
        "knowledge_graph_layouts",
        "knowledge_audience_rules",
        "problem_known_error_links",
        "ticket_knowledge_links",
    }

    assert expected <= audit.RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES
    assert audit.RETIRED_LOCAL_KNOWLEDGE_MIGRATION_TABLES.isdisjoint(audit.MIGRATION_ONLY_TABLES)


def test_retired_agent_control_plane_tables_are_explicit_migration_residue():
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")

    expected = {
        "agent_tokens",
        "connection_requests",
        "device_outbox",
        "device_modules",
        "runner_rollout_plans",
    }

    assert expected <= audit.RETIRED_AGENT_CONTROL_PLANE_MIGRATION_TABLES
    assert audit.RETIRED_AGENT_CONTROL_PLANE_MIGRATION_TABLES <= audit.MIGRATION_ONLY_TABLES


def _catalog(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "db_table_classification.toml"
    path.write_text(content, encoding="utf-8")
    return path


def test_schema_audit_reports_unclassified_stale_and_missing_cleanup(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")
    catalog_path = _catalog(
        tmp_path,
        """
[[rules]]
name = "ticket runtime"
classification = "ephemeral_test_data"
tables = ["tickets"]
reason = "Runtime ticket rows are test data."

[[rules]]
name = "knowledge runtime"
classification = "ephemeral_test_data"
patterns = ["knowledge_*"]
reason = "Knowledge runtime rows are test data."

[[rules]]
name = "migration metadata"
classification = "migration_metadata"
tables = ["alembic_version", "removed_table"]
reason = "Alembic metadata."
""",
    )
    schema = audit.SchemaSnapshot(
        tables={"alembic_version", "knowledge_items", "new_feature_events", "tickets"},
        foreign_keys=(),
    )
    report = audit.audit_schema(
        schema,
        audit.load_classification_catalog(catalog_path),
        static_cleanup_tables={"tickets", "stale_cleanup_table"},
        dynamic_cleanup_tables={"knowledge_items", "tickets"},
    )

    assert report.unclassified_tables == ("new_feature_events",)
    assert report.stale_static_cleanup_tables == ("stale_cleanup_table",)
    assert report.stale_catalog_tables == ("removed_table",)
    assert report.ephemeral_missing_from_static_cleanup == ("knowledge_items",)
    assert report.dynamic_cleanup_missing_from_static == ("knowledge_items",)
    assert report.has_failures is True


def test_schema_audit_flags_overlapping_classification_rules(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")
    catalog_path = _catalog(
        tmp_path,
        """
[[rules]]
name = "all ticket tables"
classification = "ephemeral_test_data"
patterns = ["ticket_*"]
reason = "Ticket runtime rows are test data."

[[rules]]
name = "ticket waits"
classification = "persistent_reference_fixture"
tables = ["ticket_waits"]
reason = "Bad overlap for test coverage."
""",
    )

    report = audit.audit_schema(
        audit.SchemaSnapshot(tables={"ticket_waits"}, foreign_keys=()),
        audit.load_classification_catalog(catalog_path),
        static_cleanup_tables={"ticket_waits"},
        dynamic_cleanup_tables={"ticket_waits"},
    )

    assert report.multiply_classified_tables == {"ticket_waits": ("all ticket tables", "ticket waits")}
    assert report.has_failures is True


def test_schema_audit_flags_fk_children_missing_from_cleanup(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")
    catalog_path = _catalog(
        tmp_path,
        """
[[rules]]
name = "runtime tables"
classification = "ephemeral_test_data"
tables = ["parent_rows", "child_rows"]
reason = "Runtime rows are test data."
""",
    )
    schema = audit.SchemaSnapshot(
        tables={"child_rows", "parent_rows"},
        foreign_keys=(audit.ForeignKeyRef(child_table="child_rows", parent_table="parent_rows", delete_action="NO ACTION"),),
    )

    report = audit.audit_schema(
        schema,
        audit.load_classification_catalog(catalog_path),
        static_cleanup_tables={"parent_rows"},
        dynamic_cleanup_tables={"parent_rows"},
    )

    assert report.fk_cleanup_risks == ("child_rows -> parent_rows (NO ACTION)",)


def test_load_static_cleanup_tables_from_conftest_uses_ast(tmp_path):
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")
    conftest = tmp_path / "conftest.py"
    conftest.write_text(
        'FULL_CLEANUP_TABLES = (\n    "tickets",\n    "operations",\n)\n',
        encoding="utf-8",
    )

    assert audit.load_static_cleanup_tables(conftest) == {"operations", "tickets"}


def test_main_accepts_schema_json_and_strict_failure(tmp_path, capsys):
    audit = importlib.import_module("scripts.audit_db_cleanup_schema")
    catalog_path = _catalog(
        tmp_path,
        """
[[rules]]
name = "ticket runtime"
classification = "ephemeral_test_data"
tables = ["tickets"]
reason = "Runtime ticket rows are test data."
""",
    )
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({"tables": ["tickets", "unknown_table"], "foreign_keys": []}), encoding="utf-8")
    cleanup_path = tmp_path / "conftest.py"
    cleanup_path.write_text('FULL_CLEANUP_TABLES = ("tickets",)\n', encoding="utf-8")

    exit_code = audit.main(
        [
            "--classification",
            str(catalog_path),
            "--schema-json",
            str(schema_path),
            "--static-cleanup",
            str(cleanup_path),
            "--strict",
        ]
    )

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "unknown_table" in output
    assert "unclassified_tables=1" in output
