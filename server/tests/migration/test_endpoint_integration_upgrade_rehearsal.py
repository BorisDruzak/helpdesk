"""Disposable PostgreSQL rehearsal for the forward-only Endpoint integration migrations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url


SERVER_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = SERVER_ROOT.parent
_SAFE_DATABASE_NAME = re.compile(r"^pc_support_test_[a-z0-9_]+$")


def _upgrade(database_url: str, revision: str) -> None:
    environment = os.environ | {"DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(SERVER_ROOT / "alembic.ini"), "upgrade", revision],
        cwd=SERVER_ROOT,
        env=environment,
        check=True,
    )


def _admin_url(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql", database="postgres").render_as_string(
        hide_password=False
    )


async def _insert_representative_legacy_rows(database_url: str) -> dict[str, str]:
    ticket_id, operation_id, session_id, step_id = (str(uuid4()) for _ in range(4))
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql", 1))
    try:
        await connection.execute(
            """
            INSERT INTO tickets (
                ticket_id, device_id, title, description, status, requester_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, now(), now())
            """,
            ticket_id,
            "legacy-device-0001",
            "Endpoint migration rehearsal",
            "Representative legacy ticket without Endpoint mapping",
            "in_progress",
            "migration-rehearsal-requester",
        )
        await connection.execute(
            """
            INSERT INTO operations (operation_id, device_id, ticket_id, kind, actor_role, trace_id, status, queued_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, now())
            """,
            operation_id,
            "legacy-device-0001",
            ticket_id,
            "command",
            "support",
            str(uuid4()),
            "queued",
        )
        await connection.execute(
            "INSERT INTO diagnostic_sessions (id, ticket_id, status) VALUES ($1, $2, $3)",
            session_id,
            ticket_id,
            "draft",
        )
        await connection.execute(
            """
            INSERT INTO diagnostic_steps (id, session_id, ticket_id, step_type, operation_id, status)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            step_id,
            session_id,
            ticket_id,
            "legacy_command",
            operation_id,
            "pending",
        )
        await connection.execute(
            """
            INSERT INTO device_outbox (device_id, command_id, command, params, actor_role)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            "legacy-device-0001",
            str(uuid4()),
            "legacy.command",
            "{}",
            "support",
        )
    finally:
        await connection.close()
    return {
        "ticket_id": ticket_id,
        "operation_id": operation_id,
        "session_id": session_id,
        "step_id": step_id,
    }


async def _legacy_snapshot(
    database_url: str, identifiers: dict[str, str], *, include_endpoint_columns: bool
) -> dict[str, object]:
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql", 1))
    try:
        ticket_columns = "ticket_id, device_id, title, description, status, requester_id"
        if include_endpoint_columns:
            ticket_columns += ", endpoint_device_ref, endpoint_device_snapshot_json"
        ticket = await connection.fetchrow(
            f"SELECT {ticket_columns} FROM tickets WHERE ticket_id = $1", identifiers["ticket_id"]
        )
        operation = await connection.fetchrow(
            "SELECT operation_id, device_id, ticket_id, kind, actor_role, status FROM operations WHERE operation_id = $1",
            identifiers["operation_id"],
        )
        session = await connection.fetchrow(
            "SELECT id, ticket_id, status FROM diagnostic_sessions WHERE id = $1", identifiers["session_id"]
        )
        step = await connection.fetchrow(
            "SELECT id, session_id, ticket_id, step_type, operation_id, status FROM diagnostic_steps WHERE id = $1",
            identifiers["step_id"],
        )
        outbox_count = await connection.fetchval("SELECT count(*) FROM device_outbox WHERE device_id = $1", "legacy-device-0001")
    finally:
        await connection.close()
    assert ticket is not None and operation is not None and session is not None and step is not None
    return {
        "ticket": dict(ticket),
        "operation": dict(operation),
        "diagnostic_session": dict(session),
        "diagnostic_step": dict(step),
        "legacy_device_outbox_count": int(outbox_count),
    }


async def _schema_contract(database_url: str) -> tuple[set[str], set[str], set[str], set[str]]:
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql", 1))
    try:
        tables = {
            str(row["table_name"])
            for row in await connection.fetch(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        }
        columns = {
            f"{row['table_name']}.{row['column_name']}"
            for row in await connection.fetch(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"
            )
        }
        constraints = {
            str(row["conname"])
            for row in await connection.fetch(
                "SELECT conname FROM pg_constraint WHERE connamespace = 'public'::regnamespace"
            )
        }
        indexes = {
            str(row["indexname"])
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
            )
        }
    finally:
        await connection.close()
    return tables, columns, constraints, indexes


async def _endpoint_link_foreign_key_parents(database_url: str) -> set[str]:
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql", 1))
    try:
        rows = await connection.fetch(
            """
            SELECT DISTINCT parent.table_name AS foreign_table_name
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
              AND child.table_name = 'endpoint_operation_links'
            """
        )
    finally:
        await connection.close()
    return {str(row["foreign_table_name"]) for row in rows}


async def _assert_endpoint_link_constraints(database_url: str, identifiers: dict[str, str]) -> None:
    connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql", 1))
    link_id = str(uuid4())
    try:
        await connection.execute(
            """
            INSERT INTO endpoint_operation_links (
                link_id, operation_id, endpoint_operation_ref, endpoint_device_ref, capability_code,
                create_idempotency_key, remote_status, diagnostic_session_id, diagnostic_step_id,
                attempt_count, next_attempt_at, caller_actor_id, caller_idempotency_key
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now(), $11, $12)
            """,
            link_id, identifiers["operation_id"], "remote-operation-0001", "endpoint-device-0001",
            "context.diagnostic.collect", "migration-rehearsal-create-key", "queued",
            identifiers["session_id"], identifiers["step_id"], 0, "migration-actor", "migration-caller-key",
        )
        second_operation_id, third_operation_id, fourth_operation_id = (str(uuid4()) for _ in range(3))
        for operation_id in (second_operation_id, third_operation_id, fourth_operation_id):
            await connection.execute(
                """
                INSERT INTO operations (operation_id, device_id, ticket_id, kind, actor_role, trace_id, status, queued_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                """,
                operation_id,
                "legacy-device-0001",
                (await connection.fetchval("SELECT ticket_id FROM operations WHERE operation_id = $1", identifiers["operation_id"])),
                "command",
                "support",
                str(uuid4()),
                "queued",
            )
        with pytest.raises(asyncpg.UniqueViolationError):
            await connection.execute(
                """
                INSERT INTO endpoint_operation_links (
                    link_id, operation_id, endpoint_operation_ref, endpoint_device_ref, capability_code,
                    create_idempotency_key, remote_status, attempt_count, next_attempt_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
                """,
                str(uuid4()), second_operation_id, "remote-operation-0001", "endpoint-device-0002",
                "context.diagnostic.collect", "migration-rehearsal-create-key-2", "queued", 0,
            )
        with pytest.raises(asyncpg.UniqueViolationError):
            await connection.execute(
                """
                INSERT INTO endpoint_operation_links (
                    link_id, operation_id, endpoint_device_ref, capability_code, create_idempotency_key,
                    remote_status, attempt_count, next_attempt_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, now())
                """,
                str(uuid4()), third_operation_id, "endpoint-device-0003", "context.diagnostic.collect",
                "migration-rehearsal-create-key", "queued", 0,
            )
        with pytest.raises(asyncpg.UniqueViolationError):
            await connection.execute(
                """
                INSERT INTO endpoint_operation_links (
                    link_id, operation_id, endpoint_device_ref, capability_code, create_idempotency_key,
                    remote_status, attempt_count, next_attempt_at, caller_actor_id, caller_idempotency_key
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, now(), $8, $9)
                """,
                str(uuid4()), fourth_operation_id, "endpoint-device-0004", "context.diagnostic.collect",
                "migration-rehearsal-create-key-4", "queued", 0, "migration-actor", "migration-caller-key",
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await connection.execute(
                "UPDATE endpoint_operation_links SET attempt_count = -1 WHERE link_id = $1", link_id
            )
    finally:
        await connection.close()


async def _create_clean_database(database_url: str) -> str:
    source_url = make_url(database_url)
    source_name = source_url.database or ""
    assert _SAFE_DATABASE_NAME.fullmatch(source_name)
    fresh_name = f"{source_name}_fresh"
    admin_connection = await asyncpg.connect(_admin_url(database_url))
    try:
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{fresh_name}"')
        await admin_connection.execute(f'CREATE DATABASE "{fresh_name}"')
    finally:
        await admin_connection.close()
    return source_url.set(database=fresh_name).render_as_string(hide_password=False)


async def _drop_database(database_url: str) -> None:
    database_name = make_url(database_url).database or ""
    if not _SAFE_DATABASE_NAME.fullmatch(database_name):
        raise ValueError("refusing to drop a non-test migration rehearsal database")
    admin_connection = await asyncpg.connect(_admin_url(database_url))
    try:
        await admin_connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            database_name,
        )
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await admin_connection.close()


@pytest.mark.migration_clone
def test_endpoint_integration_upgrade_rehearsal(migration_clone_database_url: str) -> None:
    """Prove 134→137 preserves rows and adds only the governed local contract."""

    started = time.monotonic()
    fresh_database_url: str | None = None
    report_path = WORKSPACE_ROOT / "artifacts" / "migration" / "endpoint-integration-rehearsal.json"
    try:
        _upgrade(migration_clone_database_url, "134")
        before_tables, _, _, _ = asyncio.run(_schema_contract(migration_clone_database_url))
        identifiers = asyncio.run(_insert_representative_legacy_rows(migration_clone_database_url))
        legacy_before = asyncio.run(
            _legacy_snapshot(migration_clone_database_url, identifiers, include_endpoint_columns=False)
        )

        _upgrade(migration_clone_database_url, "137")
        after_tables, columns, constraints, indexes = asyncio.run(_schema_contract(migration_clone_database_url))
        legacy_after = asyncio.run(
            _legacy_snapshot(migration_clone_database_url, identifiers, include_endpoint_columns=True)
        )
        asyncio.run(_assert_endpoint_link_constraints(migration_clone_database_url, identifiers))
        foreign_key_parents = asyncio.run(_endpoint_link_foreign_key_parents(migration_clone_database_url))

        assert legacy_after["ticket"]["endpoint_device_ref"] is None
        assert legacy_after["ticket"]["endpoint_device_snapshot_json"] is None
        legacy_after_business = dict(legacy_after)
        legacy_after_business["ticket"] = {
            key: value
            for key, value in legacy_after["ticket"].items()
            if key not in {"endpoint_device_ref", "endpoint_device_snapshot_json"}
        }
        assert legacy_after_business == legacy_before
        assert before_tables <= after_tables
        assert {"endpoint_operation_links", "device_outbox"} <= after_tables
        assert {
            "tickets.endpoint_device_ref",
            "tickets.endpoint_device_snapshot_json",
            "endpoint_operation_links.correlation_ref",
            "endpoint_operation_links.caller_actor_id",
            "endpoint_operation_links.caller_idempotency_key",
        } <= columns
        assert {
            "uq_endpoint_operation_links_operation_id",
            "uq_endpoint_operation_links_endpoint_operation_ref",
            "uq_endpoint_operation_links_create_idempotency_key",
            "ck_endpoint_operation_links_remote_status",
            "ck_endpoint_operation_links_attempt_count",
        } <= constraints
        assert "uq_endpoint_operation_links_caller_key" in indexes
        assert foreign_key_parents == {"operations", "diagnostic_sessions", "diagnostic_steps"}

        fresh_database_url = asyncio.run(_create_clean_database(migration_clone_database_url))
        _upgrade(fresh_database_url, "head")
        fresh_tables, _, _, _ = asyncio.run(_schema_contract(fresh_database_url))
        assert "endpoint_operation_links" in fresh_tables

        report = {
            "starting_revision": "134",
            "ending_revision": "137",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "legacy_rows_before": legacy_before,
            "legacy_rows_after": legacy_after,
            "constraints_verified": True,
            "indexes_verified": True,
            "destructive_changes_detected": False,
            "success": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    finally:
        if fresh_database_url is not None:
            asyncio.run(_drop_database(fresh_database_url))
