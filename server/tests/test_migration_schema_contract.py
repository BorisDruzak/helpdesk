from __future__ import annotations

import asyncio
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from scripts import audit_db_cleanup_schema
from scripts.registry_retirement_manifest import RETIRED_KNOWLEDGE_AI_TABLES


pytestmark = pytest.mark.db_cleanup("full")

SERVER_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = SERVER_ROOT.parent


def _load_test_harness():
    path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("server_test_harness_migration_schema", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


test_harness = _load_test_harness()


# These Helpdesk, auth/RBAC and Registry tables are intentionally literal
# rather than derived from the retirement migration under test.
PROTECTED_KNOWLEDGE_RETIREMENT_TABLES = frozenset(
    {
        "tickets", "ticket_kb_links", "ticket_resolution_passports", "problems", "ui_users",
        "auth_sessions", "ui_tokens", "ui_user_audit", "ui_password_reset_requests",
        "ticket_public_sessions", "access_groups", "access_group_members",
        "access_group_permissions", "access_group_queue_members", "access_audit", "ticket_queues",
        "ticket_queue_members", "ticket_queue_ola_targets", "user_consent_requests",
        "device_account_events", "device_account_login_requests", "device_account_sessions",
        "device_browser_pairings", "device_registration_claims", "device_registration_events",
        "device_user_bindings", "registry_admin_events", "registry_admin_policies", "registry_assets",
        "registry_audience_group_members", "registry_audience_groups", "registry_departments",
        "registry_locations", "registry_people", "registry_person_department_memberships",
        "registry_person_identities", "registry_quality_issue_overrides", "registry_services",
        "registry_vendors",
    }
)


def _load_historical_retirement_migration():
    path = SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260810_134_retire_local_knowledge_ai_schema.py"
    spec = importlib.util.spec_from_file_location("historical_knowledge_retirement_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _historical_migration_foreign_key_edges(path: Path) -> tuple[set[str], set[tuple[str, str]]]:
    """Extract literal ``create_table`` FK edges without importing a historical revision."""

    source = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    tables: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for node in ast.walk(source):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "create_table":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or not isinstance(node.args[0].value, str):
            continue
        table_name = node.args[0].value
        tables.add(table_name)
        for descendant in ast.walk(node):
            if (
                not isinstance(descendant, ast.Call)
                or not isinstance(descendant.func, ast.Attribute)
                or descendant.func.attr != "ForeignKeyConstraint"
                or len(descendant.args) < 2
            ):
                continue
            parent_columns = descendant.args[1]
            if not isinstance(parent_columns, (ast.List, ast.Tuple)) or not parent_columns.elts:
                continue
            parent_column = parent_columns.elts[0]
            if not isinstance(parent_column, ast.Constant) or not isinstance(parent_column.value, str):
                continue
            parent_table = parent_column.value.partition(".")[0]
            edges.add((table_name, parent_table))
    return tables, edges


@pytest.mark.no_db
def test_declared_historical_graph_matches_migration_118_non_self_fk_contract() -> None:
    """A later static drop graph must not silently omit a historical FK edge."""

    migration = _load_historical_retirement_migration()
    migration_118 = SERVER_ROOT / "app" / "db" / "migrations" / "versions" / "20260612_118_knowledge_metadata_model.py"
    migration_tables, source_edges = _historical_migration_foreign_key_edges(migration_118)
    declared_edges = set(migration.HISTORICAL_KNOWLEDGE_AI_FK_EDGES)
    documented_self_edges = set(migration.HISTORICAL_SELF_REFERENTIAL_FK_EDGE_EXCLUSIONS)

    assert {edge for edge in source_edges if edge[0] == edge[1]} == documented_self_edges
    assert {
        edge for edge in declared_edges if edge[0] in migration_tables
    } == source_edges - documented_self_edges


async def _fetch_schema_snapshot(database_url: str) -> audit_db_cleanup_schema.SchemaSnapshot:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            tables = {
                str(row[0])
                for row in (
                    await conn.execute(
                        text(
                            """
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                              AND table_type = 'BASE TABLE'
                            """
                        )
                    )
                ).all()
            }
            fk_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT
                            child.table_name AS child_table,
                            parent.table_name AS parent_table,
                            refs.delete_rule AS delete_action
                        FROM information_schema.referential_constraints refs
                        JOIN information_schema.table_constraints child
                          ON child.constraint_catalog = refs.constraint_catalog
                         AND child.constraint_schema = refs.constraint_schema
                         AND child.constraint_name = refs.constraint_name
                        JOIN information_schema.table_constraints parent
                          ON parent.constraint_catalog = refs.unique_constraint_catalog
                         AND parent.constraint_schema = refs.unique_constraint_schema
                         AND parent.constraint_name = refs.unique_constraint_name
                        WHERE child.table_schema = 'public'
                          AND parent.table_schema = 'public'
                        """
                    )
                )
            ).mappings().all()
    finally:
        await engine.dispose()

    foreign_keys = tuple(
        audit_db_cleanup_schema.ForeignKeyRef(
            child_table=str(row["child_table"]),
            parent_table=str(row["parent_table"]),
            delete_action=str(row["delete_action"]).upper(),
        )
        for row in fk_rows
    )
    return audit_db_cleanup_schema.SchemaSnapshot(tables=tables, foreign_keys=foreign_keys)


async def _catalog_tables(database_url: str) -> set[str]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    """
                )
            )
            return {str(row[0]) for row in result.all()}
    finally:
        await engine.dispose()


async def _protected_knowledge_retirement_tables_are_selectable(database_url: str) -> None:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            for table_name in sorted(PROTECTED_KNOWLEDGE_RETIREMENT_TABLES):
                # Literal test-owned table names, never request input.
                await connection.execute(text(f'SELECT count(*) FROM "{table_name}"'))
    finally:
        await engine.dispose()


def _run_alembic_upgrade_to_revision(database_url: str, revision: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(SERVER_ROOT / "alembic.ini"), "upgrade", revision],
        cwd=str(SERVER_ROOT),
        env=environment,
        check=True,
    )


async def _schema_signature(database_url: str) -> dict[str, tuple[tuple[Any, ...], ...]]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            columns = (
                await conn.execute(
                    text(
                        """
                        SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position
                        """
                    )
                )
            ).all()
            constraints = (
                await conn.execute(
                    text(
                        """
                        SELECT conrelid::regclass::text AS table_name,
                               conname,
                               contype,
                               pg_get_constraintdef(oid, true) AS definition
                        FROM pg_constraint
                        WHERE connamespace = 'public'::regnamespace
                        ORDER BY table_name, conname
                        """
                    )
                )
            ).all()
            indexes = (
                await conn.execute(
                    text(
                        """
                        SELECT tablename, indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = 'public'
                        ORDER BY tablename, indexname
                        """
                    )
                )
            ).all()
    finally:
        await engine.dispose()

    return {
        "columns": tuple(tuple(row) for row in columns),
        "constraints": tuple(tuple(row) for row in constraints),
        "indexes": tuple(tuple(row) for row in indexes),
    }


async def _fetch_catalog_objects(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            constraints = {
                str(row[0])
                for row in (
                    await conn.execute(
                        text(
                            """
                            SELECT conname
                            FROM pg_constraint
                            WHERE connamespace = 'public'::regnamespace
                            """
                        )
                    )
                ).all()
            }
            indexes = {
                str(row[0])
                for row in (
                    await conn.execute(
                        text(
                            """
                            SELECT indexname
                            FROM pg_indexes
                            WHERE schemaname = 'public'
                            """
                        )
                    )
                ).all()
            }
            columns = {
                (str(row["table_name"]), str(row["column_name"])): {
                    "nullable": str(row["is_nullable"]),
                    "default": None if row["column_default"] is None else str(row["column_default"]),
                }
                for row in (
                    await conn.execute(
                        text(
                            """
                            SELECT table_name, column_name, is_nullable, column_default
                            FROM information_schema.columns
                            WHERE table_schema = 'public'
                            """
                        )
                    )
                ).mappings().all()
            }
    finally:
        await engine.dispose()

    return {"constraints": constraints, "indexes": indexes, "columns": columns}


async def _smoke_recent_runtime_tables(database_url: str) -> dict[str, Any]:
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO observer_integrity_events (
                        event_id,
                        event_type,
                        severity,
                        source,
                        status,
                        detected_at,
                        first_seen_at,
                        last_seen_at,
                        dedupe_key,
                        occurrence_count,
                        expected,
                        actual,
                        evidence_json,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        'migration-smoke-observer',
                        'migration_schema_smoke',
                        'info',
                        'migration_schema',
                        'active',
                        now(),
                        now(),
                        now(),
                        'migration-schema-smoke-observer',
                        1,
                        'insert',
                        'insert',
                        '{}'::jsonb,
                        now(),
                        now()
                    )
                    """
                )
            )
            observer_count = (
                await conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM observer_integrity_events
                        WHERE event_id = 'migration-smoke-observer'
                        """
                    )
                )
            ).scalar_one()

            await conn.execute(
                text(
                    """
                    INSERT INTO user_consent_requests (
                        consent_id,
                        subject_type,
                        subject_id,
                        title
                    )
                    VALUES (
                        'migration-smoke-consent',
                        'operation',
                        'migration-smoke-operation',
                        'Migration smoke consent'
                    )
                    """
                )
            )
            consent_row = (
                await conn.execute(
                    text(
                        """
                        SELECT status, policy_snapshot, requested_action_payload_redacted, metadata_json
                        FROM user_consent_requests
                        WHERE consent_id = 'migration-smoke-consent'
                        """
                    )
                )
            ).mappings().one()

            await conn.execute(
                text("DELETE FROM user_consent_requests WHERE consent_id = 'migration-smoke-consent'")
            )
            await conn.execute(
                text("DELETE FROM observer_integrity_events WHERE event_id = 'migration-smoke-observer'")
            )
    finally:
        await engine.dispose()

    return {
        "observer_count": int(observer_count),
        "consent_status": str(consent_row["status"]),
        "policy_snapshot": consent_row["policy_snapshot"],
        "requested_action_payload_redacted": consent_row["requested_action_payload_redacted"],
        "metadata_json": consent_row["metadata_json"],
    }


def _assert_direct_fresh_migration_path() -> None:
    cloned_from = os.getenv(test_harness.TEST_DB_TEMPLATE_CLONED_FROM_ENV)
    assert not cloned_from, (
        "migration_schema must exercise the direct empty-DB Alembic path; "
        f"got template clone {cloned_from!r}"
    )
    assert os.getenv("PC_CLIENT_TEST_DB_TEMPLATE") != "1", (
        "migration_schema must run with PC_CLIENT_TEST_DB_TEMPLATE=0 so a migrated template "
        "cannot hide fresh-upgrade failures"
    )


@pytest.mark.no_db
def test_direct_migration_schema_guard_rejects_template_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE", "1")

    with pytest.raises(AssertionError, match="PC_CLIENT_TEST_DB_TEMPLATE=0"):
        _assert_direct_fresh_migration_path()


@pytest.mark.migration_clone
def test_clone_upgrade_from_133_retires_only_historical_knowledge_ai_schema(
    migration_clone_database_url: str,
) -> None:
    """Own the isolated 133->134 lifecycle without any pre-applied head/template."""

    _assert_direct_fresh_migration_path()
    database_name = make_url(migration_clone_database_url).database or ""
    assert database_name.startswith("pc_support_test_")
    assert database_name != "pc_support_test"
    assert len(RETIRED_KNOWLEDGE_AI_TABLES) == 45

    blank = asyncio.run(_catalog_tables(migration_clone_database_url))
    assert not blank, "migration_clone must start from a blank private database"

    _run_alembic_upgrade_to_revision(migration_clone_database_url, "133")
    before = asyncio.run(_catalog_tables(migration_clone_database_url))
    assert RETIRED_KNOWLEDGE_AI_TABLES <= before
    assert PROTECTED_KNOWLEDGE_RETIREMENT_TABLES <= before

    _run_alembic_upgrade_to_revision(migration_clone_database_url, "134")
    after = asyncio.run(_catalog_tables(migration_clone_database_url))
    assert not RETIRED_KNOWLEDGE_AI_TABLES & after
    assert before - after == RETIRED_KNOWLEDGE_AI_TABLES
    assert PROTECTED_KNOWLEDGE_RETIREMENT_TABLES <= after
    asyncio.run(_protected_knowledge_retirement_tables_are_selectable(migration_clone_database_url))

    _run_alembic_upgrade_to_revision(migration_clone_database_url, "head")
    head = asyncio.run(_catalog_tables(migration_clone_database_url))
    assert head - after == {"endpoint_operation_links"}


def _format_schema_audit_failure(report: audit_db_cleanup_schema.SchemaAuditReport) -> str:
    details = report.summary_counts()
    return (
        "actual migrated DB schema failed cleanup classification audit: "
        + ", ".join(f"{key}={value}" for key, value in details.items())
    )


def test_fresh_alembic_upgrade_reaches_exact_heads_and_is_idempotent(test_database_url: str, run_migrations) -> None:
    _assert_direct_fresh_migration_path()
    expected_heads = test_harness._alembic_head_revisions(SERVER_ROOT)
    actual_heads = test_harness._run_async_blocking(test_harness._database_alembic_revisions, test_database_url)

    assert actual_heads == expected_heads

    before = test_harness._run_async_blocking(_schema_signature, test_database_url)
    test_harness._run_alembic_upgrade(test_database_url, SERVER_ROOT)
    after = test_harness._run_async_blocking(_schema_signature, test_database_url)

    assert after == before


def test_migrated_schema_matches_models_and_cleanup_catalog(test_database_url: str, run_migrations) -> None:
    schema = test_harness._run_async_blocking(_fetch_schema_snapshot, test_database_url)
    model_schema = audit_db_cleanup_schema.load_schema_from_models(WORKSPACE)

    assert model_schema.tables - schema.tables == set()
    assert schema.tables - model_schema.tables <= audit_db_cleanup_schema.MIGRATION_ONLY_TABLES

    catalog = audit_db_cleanup_schema.load_classification_catalog(
        WORKSPACE / "quality" / "db_table_classification.toml"
    )
    static_cleanup_tables = audit_db_cleanup_schema.load_static_cleanup_tables(
        WORKSPACE / "server" / "tests" / "conftest.py"
    )
    dynamic_cleanup_tables = audit_db_cleanup_schema.dynamic_cleanup_from_policy(schema.tables)
    report = audit_db_cleanup_schema.audit_schema(
        schema,
        catalog,
        static_cleanup_tables=static_cleanup_tables,
        dynamic_cleanup_tables=dynamic_cleanup_tables,
    )

    assert not report.has_failures, _format_schema_audit_failure(report)


def test_required_constraints_indexes_defaults_and_nullable_migration_contracts(
    test_database_url: str,
    run_migrations,
) -> None:
    catalog = test_harness._run_async_blocking(_fetch_catalog_objects, test_database_url)

    assert {
        "ck_tickets_status_canonical",
        "ck_tickets_requester_id_non_empty",
        "ck_user_consent_requests_subject_type",
        "ck_user_consent_requests_status",
        "ck_device_browser_pairings_purpose",
        "ck_device_browser_pairings_status",
        "uq_observer_integrity_events_dedupe_key",
    } <= catalog["constraints"]
    assert {
        "ix_tickets_device_account_session",
        "ix_tickets_requester_external_ref",
        "ix_observer_integrity_status_severity",
        "ix_device_browser_pairings_token_hash",
        "ix_user_consent_requests_requester_external_ref",
        "ix_user_consent_requests_status_expires",
        "ux_user_consent_requests_pending_subject",
    } <= catalog["indexes"]

    columns = catalog["columns"]
    assert columns[("tickets", "device_id")]["nullable"] == "YES"
    assert columns[("tickets", "requester_external_ref")]["nullable"] == "YES"
    assert columns[("tickets", "requester_snapshot_json")]["nullable"] == "YES"
    assert columns[("ticket_events", "device_id")]["nullable"] == "YES"
    assert columns[("user_consent_requests", "status")]["nullable"] == "NO"
    assert columns[("user_consent_requests", "requester_external_ref")]["nullable"] == "YES"
    assert columns[("user_consent_requests", "requester_snapshot_json")]["nullable"] == "YES"
    assert "'pending'" in str(columns[("user_consent_requests", "status")]["default"])
    assert "'{}'::jsonb" in str(columns[("user_consent_requests", "policy_snapshot")]["default"])
    assert "'{}'::jsonb" in str(columns[("device_browser_pairings", "metadata_json")]["default"])


def test_recent_runtime_tables_support_smoke_insert_select_delete(test_database_url: str, run_migrations) -> None:
    result = test_harness._run_async_blocking(_smoke_recent_runtime_tables, test_database_url)

    assert result == {
        "observer_count": 1,
        "consent_status": "pending",
        "policy_snapshot": {},
        "requested_action_payload_redacted": {},
        "metadata_json": {},
    }
