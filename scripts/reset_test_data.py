#!/usr/bin/env python3
"""Reset test data while preserving request forms and admin/support users.

Default mode is an executable dry-run: the script opens a transaction, runs the
same DELETE plan as apply mode, reports counts, then rolls the transaction back.
Apply mode requires explicit confirmation flags.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import text

WORKSPACE = Path(os.environ.get("PC_CLIENT_WORKSPACE") or Path(__file__).resolve().parent.parent)
SERVER_ROOT = WORKSPACE / "server"
DEFAULT_OUTPUT_DIR = WORKSPACE / "artifacts" / "diagnostics"
PROFILE_NAME = "keep-forms-admin-support-clear-knowledge"
ADMIN_SUPPORT_ROLES = ("admin", "support")

FORM_CONSTRUCTOR_KEEP_TABLES = {
    "ticket_form_packs",
    "form_builder_drafts",
    "form_schemas",
    "form_fields",
    "form_conditions",
    "request_templates",
    "helpdesk_services",
    "helpdesk_service_offerings",
    "helpdesk_service_catalog_audit",
    "request_studio_publish_tokens",
}

HELPDESK_CONFIG_KEEP_TABLES = {
    "ticket_types",
    "ticket_queues",
    "ticket_queue_members",
    "ticket_queue_ola_targets",
    "ticket_categories",
    "ticket_business_calendars",
    "ticket_sla_policies",
    "ticket_sla_targets",
    "ticket_priority_matrix",
    "ticket_routing_rules",
    "ticket_resolution_codes",
    "priority_policies",
    "routing_policies",
    "sla_policies",
    "ola_policies",
    "approval_policies",
    "diagnostic_policies",
    "closure_policies",
    "visibility_policies",
    "notification_policies",
    "reporting_policies",
    "quality_policies",
    "change_policies",
    "problem_detection_rules",
    "problem_slo_policies",
}

RUNTIME_DEFINITION_KEEP_TABLES = {
    "server_config",
    "modules",
    "agent_builds",
    "agent_recipe_primitives",
    "agent_recipe_versions",
    "playbook",
    "playbook_version",
    "playbook_step",
    "diagnostic_providers",
    "diagnostic_capabilities",
    "diagnostic_capability_versions",
    "diagnostic_provider_configs",
    "diagnostic_provider_credential_refs",
    "ai_providers",
    "ai_model_profiles",
    "ai_policy_profiles",
    "tool_presentation_overrides",
}

RBAC_KEEP_TABLES = {
    "access_groups",
    "access_group_permissions",
    "access_group_queue_members",
}

SCHEMA_KEEP_TABLES = {
    "alembic_version",
}

KEEP_TABLES = (
    FORM_CONSTRUCTOR_KEEP_TABLES
    | HELPDESK_CONFIG_KEEP_TABLES
    | RUNTIME_DEFINITION_KEEP_TABLES
    | RBAC_KEEP_TABLES
    | SCHEMA_KEEP_TABLES
    | {"ui_users"}
)

TICKET_KEEP_TABLES = FORM_CONSTRUCTOR_KEEP_TABLES | {
    "ticket_types",
    "ticket_queues",
    "ticket_queue_members",
    "ticket_queue_ola_targets",
    "ticket_categories",
    "ticket_business_calendars",
    "ticket_sla_policies",
    "ticket_sla_targets",
    "ticket_priority_matrix",
    "ticket_routing_rules",
    "ticket_resolution_codes",
}

PROBLEM_KEEP_TABLES = {
    "problem_detection_rules",
    "problem_slo_policies",
}

CHANGE_KEEP_TABLES = {
    "change_policies",
}

EXPLICIT_CLEAR_TABLES = {
    "access_audit",
    "agent_build_download_audit",
    "agent_observer_events",
    "agent_recipe_test_runs",
    "agent_runtime_audit",
    "agent_tokens",
    "ai_request_audit",
    "artifacts",
    "auth_sessions",
    "changes",
    "connection_requests",
    "consent_decisions",
    "continuous_improvement_actions",
    "diagnostic_artifact_links",
    "diagnostic_bundles",
    "diagnostic_evidence",
    "diagnostic_findings",
    "diagnostic_provider_audit",
    "diagnostic_session_capabilities",
    "diagnostic_sessions",
    "diagnostic_steps",
    "dispatch_ready_devices",
    "download_audit",
    "helpdesk_policy_audit",
    "job_events",
    "operation_dependencies",
    "operations",
    "playbook_run",
    "playbook_step_run",
    "remote_access_events",
    "remote_access_sessions",
    "runner_rollout_events",
    "runner_rollout_plans",
    "runner_rollout_targets",
    "runner_rollout_waves",
    "server_runtime_snapshots",
    "service_quality_snapshots",
    "smart_views",
    "support_queue_saved_views",
    "ui_tokens",
    "ui_password_reset_requests",
    "ui_user_audit",
    "user_consent_requests",
}

SPECIAL_TABLES = {
    "access_group_members",
    "ui_users",
}


@dataclass(frozen=True)
class ForeignKeyRef:
    child_table: str
    parent_table: str
    delete_action: str


@dataclass(frozen=True)
class SpecialOperation:
    name: str
    table: str
    count_sql: str
    apply_sql: str
    kind: str = "delete"


SPECIAL_OPERATIONS = (
    SpecialOperation(
        name="prune_access_group_members_to_admin_support",
        table="access_group_members",
        count_sql=(
            "SELECT count(*) FROM access_group_members "
            "WHERE actor_id NOT IN ("
            "SELECT user_login FROM ui_users WHERE actor_role IN ('admin', 'support')"
            ")"
        ),
        apply_sql=(
            "DELETE FROM access_group_members "
            "WHERE actor_id NOT IN ("
            "SELECT user_login FROM ui_users WHERE actor_role IN ('admin', 'support')"
            ")"
        ),
    ),
    SpecialOperation(
        name="delete_non_admin_support_ui_users",
        table="ui_users",
        count_sql="SELECT count(*) FROM ui_users WHERE actor_role NOT IN ('admin', 'support')",
        apply_sql="DELETE FROM ui_users WHERE actor_role NOT IN ('admin', 'support')",
    ),
    SpecialOperation(
        name="reset_remaining_admin_support_runtime_fields",
        table="ui_users",
        count_sql=(
            "SELECT count(*) FROM ui_users "
            "WHERE actor_role IN ('admin', 'support') "
            "AND (failed_attempts <> 0 OR locked_until IS NOT NULL "
            "OR last_login_at IS NOT NULL OR last_ticket_assigned_at IS NOT NULL)"
        ),
        apply_sql=(
            "UPDATE ui_users SET failed_attempts = 0, locked_until = NULL, "
            "last_login_at = NULL, last_ticket_assigned_at = NULL, updated_at = now() "
            "WHERE actor_role IN ('admin', 'support') "
            "AND (failed_attempts <> 0 OR locked_until IS NOT NULL "
            "OR last_login_at IS NOT NULL OR last_ticket_assigned_at IS NOT NULL)"
        ),
        kind="update",
    ),
)


def load_server_env() -> None:
    env_path = SERVER_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass

    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def build_clear_tables(actual_tables: Iterable[str]) -> set[str]:
    actual = set(actual_tables)
    clear: set[str] = set()
    clear.update(table for table in actual if table.startswith("knowledge_"))
    clear.update(table for table in actual if table.startswith("registry_"))
    clear.update(table for table in actual if table.startswith("device_"))
    clear.update(table for table in actual if table.startswith("observer_"))
    clear.update(table for table in actual if table.startswith("ticket_") and table not in TICKET_KEEP_TABLES)
    clear.update(table for table in actual if table.startswith("problem_") and table not in PROBLEM_KEEP_TABLES)
    clear.update(table for table in actual if table.startswith("change_") and table not in CHANGE_KEEP_TABLES)
    clear.update(EXPLICIT_CLEAR_TABLES & actual)
    clear.add("devices") if "devices" in actual else None
    clear.add("tickets") if "tickets" in actual else None
    return (clear & actual) - KEEP_TABLES - SPECIAL_TABLES


def build_delete_order(clear_tables: Iterable[str], foreign_keys: Sequence[ForeignKeyRef]) -> list[str]:
    clear = set(clear_tables)
    successors: dict[str, set[str]] = {table: set() for table in clear}
    indegree: dict[str, int] = {table: 0 for table in clear}
    for fk in foreign_keys:
        child = fk.child_table
        parent = fk.parent_table
        if child == parent or child not in clear or parent not in clear:
            continue
        if parent not in successors[child]:
            successors[child].add(parent)
            indegree[parent] += 1

    queue = deque(sorted(table for table, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while queue:
        table = queue.popleft()
        order.append(table)
        for parent in sorted(successors[table]):
            indegree[parent] -= 1
            if indegree[parent] == 0:
                queue.append(parent)
    remaining = sorted(clear - set(order))
    return order + remaining


def build_protected_tables(actual_tables: Iterable[str], clear_tables: Iterable[str]) -> set[str]:
    actual = set(actual_tables)
    clear = set(clear_tables)
    protected = (KEEP_TABLES | SPECIAL_TABLES) & actual
    return protected - clear


async def fetch_actual_tables(conn: Any) -> set[str]:
    result = await conn.execute(
        text(
            "SELECT tablename FROM pg_tables "
            "WHERE schemaname = 'public' "
            "ORDER BY tablename"
        )
    )
    return {str(row[0]) for row in result.fetchall()}


async def fetch_foreign_keys(conn: Any) -> list[ForeignKeyRef]:
    result = await conn.execute(
        text(
            """
            SELECT child.relname AS child_table,
                   parent.relname AS parent_table,
                   CASE c.confdeltype
                       WHEN 'a' THEN 'NO ACTION'
                       WHEN 'r' THEN 'RESTRICT'
                       WHEN 'c' THEN 'CASCADE'
                       WHEN 'n' THEN 'SET NULL'
                       WHEN 'd' THEN 'SET DEFAULT'
                       ELSE c.confdeltype::text
                   END AS delete_action
            FROM pg_constraint c
            JOIN pg_class child ON child.oid = c.conrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            JOIN pg_class parent ON parent.oid = c.confrelid
            JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
            WHERE c.contype = 'f'
              AND child_ns.nspname = 'public'
              AND parent_ns.nspname = 'public'
            ORDER BY child.relname, parent.relname
            """
        )
    )
    return [
        ForeignKeyRef(
            child_table=str(row.child_table),
            parent_table=str(row.parent_table),
            delete_action=str(row.delete_action),
        )
        for row in result.fetchall()
    ]


async def scalar_int(conn: Any, sql: str) -> int:
    result = await conn.execute(text(sql))
    value = result.scalar_one()
    return int(value or 0)


async def count_table(conn: Any, table: str) -> int:
    return await scalar_int(conn, f"SELECT count(*) FROM {quote_ident(table)}")


async def count_tables(conn: Any, tables: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in sorted(tables):
        counts[table] = await count_table(conn, table)
    return counts


async def validate_protected_fk_blockers(
    conn: Any,
    *,
    clear_tables: set[str],
    protected_tables: set[str],
    foreign_keys: Sequence[ForeignKeyRef],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for fk in foreign_keys:
        if fk.parent_table not in clear_tables or fk.child_table not in protected_tables:
            continue
        child_count = await count_table(conn, fk.child_table)
        if child_count == 0:
            continue
        blockers.append(
            {
                "child_table": fk.child_table,
                "parent_table": fk.parent_table,
                "delete_action": fk.delete_action,
                "child_rows": child_count,
                "risk": "protected rows may be modified by FK action",
            }
        )
    return blockers


async def acquire_cleanup_lock(conn: Any) -> None:
    lock_key = 78120617
    result = await conn.execute(text("SELECT pg_try_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})
    if not bool(result.scalar_one()):
        raise RuntimeError("another reset_test_data run already holds the advisory lock")


async def set_local_timeouts(conn: Any, *, apply: bool) -> None:
    await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
    await conn.execute(text("SET LOCAL idle_in_transaction_session_timeout = '5min'"))
    statement_timeout = "10min" if apply else "5min"
    await conn.execute(text(f"SET LOCAL statement_timeout = '{statement_timeout}'"))


async def execute_plan(
    conn: Any,
    *,
    delete_order: Sequence[str],
    special_operations: Sequence[SpecialOperation],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    deleted_rows: dict[str, int] = {}
    for table in delete_order:
        result = await conn.execute(text(f"DELETE FROM {quote_ident(table)}"))
        deleted_rows[table] = int(result.rowcount if result.rowcount is not None else 0)

    special_results: list[dict[str, Any]] = []
    for operation in special_operations:
        before = await scalar_int(conn, operation.count_sql)
        result = await conn.execute(text(operation.apply_sql))
        affected = int(result.rowcount if result.rowcount is not None else 0)
        after = await scalar_int(conn, operation.count_sql)
        special_results.append(
            {
                "name": operation.name,
                "table": operation.table,
                "kind": operation.kind,
                "matching_before": before,
                "affected_rows": affected,
                "matching_after": after,
            }
        )
    return deleted_rows, special_results


async def collect_role_counts(conn: Any) -> list[dict[str, Any]]:
    if await count_table(conn, "ui_users") == 0:
        return []
    result = await conn.execute(
        text(
            "SELECT actor_role, is_active, count(*) AS count "
            "FROM ui_users "
            "GROUP BY actor_role, is_active "
            "ORDER BY actor_role, is_active DESC"
        )
    )
    return [
        {
            "actor_role": str(row.actor_role),
            "is_active": bool(row.is_active),
            "count": int(row.count),
        }
        for row in result.fetchall()
    ]


def summarize_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {table: count for table, count in sorted(counts.items()) if count}


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Test Data Reset Report",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Mode: `{report.get('mode')}`",
        f"- Profile: `{report.get('profile')}`",
        f"- Backup path: `{report.get('backup_path') or 'not-recorded'}`",
        f"- Clear tables: `{summary.get('clear_tables', 0)}`",
        f"- Rows planned before: `{summary.get('rows_before_clear', 0)}`",
        f"- Rows remaining after plan: `{summary.get('rows_after_clear', 0)}`",
        f"- Special rows affected: `{summary.get('special_affected_rows', 0)}`",
        "",
        "## Preserved Counts",
        "",
    ]
    protected_before = report.get("protected_counts_before") or {}
    protected_after = report.get("protected_counts_after") or {}
    for table in sorted(set(protected_before) | set(protected_after)):
        lines.append(f"- `{table}`: `{protected_before.get(table, 0)}` -> `{protected_after.get(table, 0)}`")

    lines.extend(["", "## Cleared Nonzero Counts", ""])
    cleared = report.get("clear_counts_before_nonzero") or {}
    if not cleared:
        lines.append("No rows were present in clear-target tables.")
    else:
        for table, count in cleared.items():
            lines.append(f"- `{table}`: `{count}`")

    lines.extend(["", "## Special Operations", ""])
    for item in report.get("special_results") or []:
        lines.append(
            f"- `{item.get('name')}` `{item.get('kind')}` "
            f"matching_before=`{item.get('matching_before')}` "
            f"affected=`{item.get('affected_rows')}` "
            f"matching_after=`{item.get('matching_after')}`"
        )
    return "\n".join(lines) + "\n"


def write_reports(report: Mapping[str, Any], output_dir: Path, *, timestamp: str) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"reset_test_data_{timestamp}.json"
    md_path = output_dir / f"reset_test_data_{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


async def run_reset(args: argparse.Namespace) -> dict[str, Any]:
    load_server_env()
    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url
    if str(SERVER_ROOT) not in sys.path:
        sys.path.insert(0, str(SERVER_ROOT))

    from app.db import get_engine, init_db, shutdown_db

    await init_db(os.environ.get("DATABASE_URL"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    transaction = None
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            transaction = await conn.begin()
            await acquire_cleanup_lock(conn)
            await set_local_timeouts(conn, apply=args.apply)

            actual_tables = await fetch_actual_tables(conn)
            foreign_keys = await fetch_foreign_keys(conn)
            clear_tables = build_clear_tables(actual_tables)
            protected_tables = build_protected_tables(actual_tables, clear_tables)
            protected_fk_warnings = await validate_protected_fk_blockers(
                conn,
                clear_tables=clear_tables,
                protected_tables=protected_tables,
                foreign_keys=foreign_keys,
            )

            delete_order = build_delete_order(clear_tables, foreign_keys)
            clear_counts_before = await count_tables(conn, clear_tables)
            protected_counts_before = await count_tables(conn, protected_tables)
            roles_before = await collect_role_counts(conn)

            deleted_rows, special_results = await execute_plan(
                conn,
                delete_order=delete_order,
                special_operations=SPECIAL_OPERATIONS,
            )

            clear_counts_after = await count_tables(conn, clear_tables)
            protected_counts_after = await count_tables(conn, protected_tables)
            roles_after = await collect_role_counts(conn)

            if args.apply:
                await transaction.commit()
                transaction = None
                mode = "apply"
            else:
                await transaction.rollback()
                transaction = None
                mode = "dry_run_rolled_back"

            rows_before_clear = sum(clear_counts_before.values())
            rows_after_clear = sum(clear_counts_after.values())
            special_affected = sum(int(item["affected_rows"]) for item in special_results)
            report: dict[str, Any] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                "profile": PROFILE_NAME,
                "backup_path": args.backup_path,
                "clear_tables": sorted(clear_tables),
                "delete_order": list(delete_order),
                "keep_tables": sorted(KEEP_TABLES & actual_tables),
                "protected_fk_warnings": protected_fk_warnings,
                "clear_counts_before_nonzero": summarize_counts(clear_counts_before),
                "clear_counts_after_nonzero": summarize_counts(clear_counts_after),
                "deleted_rows_nonzero": summarize_counts(deleted_rows),
                "protected_counts_before": protected_counts_before,
                "protected_counts_after": protected_counts_after,
                "ui_user_roles_before": roles_before,
                "ui_user_roles_after": roles_after,
                "special_results": special_results,
                "summary": {
                    "clear_tables": len(clear_tables),
                    "rows_before_clear": rows_before_clear,
                    "rows_after_clear": rows_after_clear,
                    "special_affected_rows": special_affected,
                    "protected_tables": len(protected_tables),
                    "protected_fk_warnings": len(protected_fk_warnings),
                },
            }
            json_path, md_path = write_reports(report, args.output_dir, timestamp=timestamp)
            report["report_json"] = str(json_path)
            report["report_md"] = str(md_path)
            return report
    finally:
        if transaction is not None:
            await transaction.rollback()
        await shutdown_db()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset test data while preserving forms and admin/support users.")
    parser.add_argument("--database-url", default=None, help="DATABASE_URL override. Defaults to server/.env.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--backup-path", default="", help="Backup path to record in the report.")
    parser.add_argument("--apply", action="store_true", help="Commit the cleanup transaction.")
    parser.add_argument("--yes", action="store_true", help="Required with --apply.")
    parser.add_argument("--confirm-services-stopped", action="store_true", help="Required with --apply.")
    args = parser.parse_args(argv)
    if args.apply and not args.yes:
        parser.error("--apply requires --yes")
    if args.apply and not args.confirm_services_stopped:
        parser.error("--apply requires --confirm-services-stopped")
    return args


async def amain(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = await run_reset(args)
    print(
        json.dumps(
            {
                "status": "ok",
                "mode": report["mode"],
                "profile": report["profile"],
                "summary": report["summary"],
                "report_json": report["report_json"],
                "report_md": report["report_md"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":
    main()
