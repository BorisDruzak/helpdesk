"""Read-only Helpdesk retirement audit; never migrates or deletes historical data.

The remote program travels through SSH stdin and reads only the configured
Helpdesk environment. Private metadata exports stay in the caller's local,
ignored evidence directory. Standard output contains counts and hashes only.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TABLES = (
    "device_inventory_snapshots", "device_inventory_bindings",
    "device_inventory_binding_history", "device_inventory_refresh_policies",
    "device_inventory_refresh_runs", "device_inventory_bulk_operations",
    "device_inventory_bulk_operation_items", "device_binding_suggestions",
    "device_presence_snapshots", "device_presence_daily_summaries",
)
FIELDS = ("inventory_number", "building", "floor", "room", "department",
          "responsible_user", "responsible_user_login", "person_id", "asset_id",
          "source_binding_id", "registration_status", "status", "notes")
SECRET = re.compile(r"(?i)(password|passwd|secret|token|authorization|cookie|credential|api[_-]?key|access[_-]?key|private[_ -]?key|bearer\s|://[^\s/:]+:[^\s/]+@|eyJ[A-Za-z0-9_-]+\.)")


def safe_metadata(value):
    """Preserve ordinary notes/tags; redact an entire value suspected of secrets."""
    if isinstance(value, str):
        return "[REDACTED: possible credential]" if SECRET.search(value) else value
    if isinstance(value, list):
        return [safe_metadata(item) for item in value]
    if isinstance(value, dict):
        return {key: "[REDACTED: possible credential]" if SECRET.search(str(key)) else safe_metadata(item) for key, item in value.items()}
    return value


async def remote_audit(environment_file: str):
    import asyncpg
    from dotenv import dotenv_values

    values = dotenv_values(environment_file)
    dsn = values.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("missing_database_configuration")
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    connection = await asyncpg.connect(dsn, timeout=10, command_timeout=20)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "tables": {}, "foreign_keys": [], "migration": {"automatic_updates": 0}}
    exports = []
    try:
        async with connection.transaction(isolation="repeatable_read", readonly=True):
            await connection.execute("SET LOCAL statement_timeout = '15000ms'")
            columns = await connection.fetch("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema='public' AND table_name = ANY($1::text[])", list(TABLES))
            available = {}
            for row in columns:
                available.setdefault(row["table_name"], set()).add(row["column_name"])
            for table in TABLES:
                if table not in available:
                    report["tables"][table] = {"exists": False}
                    continue
                count = await connection.fetchval(f'SELECT count(*) FROM "{table}"')
                report["tables"][table] = {"exists": True, "rows": count}
                timestamps = [column for column in ("created_at", "updated_at", "changed_at", "collected_at", "observed_at", "requested_at") if column in available[table]]
                for column in timestamps:
                    row = await connection.fetchrow(f'SELECT min("{column}") AS first, max("{column}") AS last FROM "{table}"')
                    report["tables"][table][column] = dict(row)
            fks = await connection.fetch("SELECT conrelid::regclass::text AS source, confrelid::regclass::text AS target, conname AS name, pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE contype='f' AND (conrelid::regclass::text = ANY($1::text[]) OR confrelid::regclass::text = ANY($1::text[])) ORDER BY source, name", list(TABLES))
            report["foreign_keys"] = [dict(row) for row in fks]
            if "device_inventory_bindings" in available:
                fields = [field for field in FIELDS if field in available["device_inventory_bindings"]]
                expressions = [f"count(*) FILTER (WHERE nullif(trim(\"{field}\"::text), '') IS NOT NULL) AS \"{field}\"" for field in fields]
                if "tags" in available["device_inventory_bindings"]:
                    expressions.append("count(*) FILTER (WHERE tags IS NOT NULL AND tags::text NOT IN ('[]', '{}', 'null')) AS tags")
                report["nonempty_bindings"] = dict(await connection.fetchrow("SELECT " + ", ".join(expressions) + " FROM device_inventory_bindings"))
                rows = await connection.fetch("SELECT device_id, responsible_user, responsible_user_login, tags, notes FROM device_inventory_bindings WHERE nullif(trim(responsible_user),'') IS NOT NULL OR nullif(trim(responsible_user_login),'') IS NOT NULL OR nullif(trim(notes),'') IS NOT NULL OR (tags IS NOT NULL AND tags::text NOT IN ('[]', '{}', 'null')) ORDER BY device_id")
                exports = [safe_metadata(dict(row)) for row in rows]
                # Exact IDs only: no hostname, name or equal Endpoint UUID inference.
                report["migration"].update(dict(await connection.fetchrow("""
                    SELECT count(*) AS legacy_bindings,
                      count(*) FILTER (WHERE a.asset_id IS NOT NULL) AS exact_registry_assets,
                      count(*) FILTER (WHERE m.device_id IS NOT NULL) AS exact_endpoint_mappings,
                      count(*) FILTER (WHERE nullif(trim(b.inventory_number),'') IS NOT NULL AND a.asset_id IS NULL) AS inventory_without_destination,
                      count(*) FILTER (WHERE nullif(trim(b.inventory_number),'') IS NOT NULL AND nullif(trim(a.inventory_number),'') IS NULL AND a.asset_id IS NOT NULL) AS inventory_empty_destination,
                      count(*) FILTER (WHERE nullif(trim(b.inventory_number),'') IS NOT NULL AND nullif(trim(a.inventory_number),'') IS NOT NULL AND b.inventory_number <> a.inventory_number) AS inventory_conflicts,
                      count(*) FILTER (WHERE b.person_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM device_user_bindings u WHERE u.device_id=b.device_id AND u.person_id=b.person_id AND u.status='active' AND u.revoked_at IS NULL AND u.valid_from<=now() AND (u.valid_to IS NULL OR u.valid_to>now()))) AS person_without_active_exact_binding,
                      count(*) FILTER (WHERE (nullif(trim(b.building),'') IS NOT NULL OR nullif(trim(b.floor),'') IS NOT NULL OR nullif(trim(b.room),'') IS NOT NULL) AND (a.asset_id IS NULL OR a.location_id IS NULL)) AS location_requires_manual_review,
                      count(*) FILTER (WHERE nullif(trim(b.department),'') IS NOT NULL AND (a.asset_id IS NULL OR a.department_id IS NULL)) AS department_requires_manual_review
                    FROM device_inventory_bindings b
                    LEFT JOIN registry_assets a ON a.device_id=b.device_id
                    LEFT JOIN registry_endpoint_device_mappings m ON m.device_id=b.device_id
                """)))
                report["migration"]["tags_notes_destination"] = "private_export_only; no canonical destination; historical table retained"
                report["migration"]["free_text_responsible_destination"] = "none; only temporally active DeviceUserBinding is authoritative"
    finally:
        await connection.close()
    return {"report": report, "private_export": exports}


def validate_private_output(path: Path) -> Path:
    """Private export must resolve inside Git metadata or an ignored directory."""
    workspace = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()).resolve()
    target = path.resolve()
    git_dir = Path(subprocess.check_output(["git", "rev-parse", "--absolute-git-dir"], text=True).strip()).resolve()
    if target.is_relative_to(git_dir):
        return target
    if not target.is_relative_to(workspace):
        raise ValueError("Private export must stay in ignored workspace storage")
    relative = (target / "private-business-metadata.json").relative_to(workspace).as_posix()
    ignored = subprocess.run(["git", "check-ignore", "--quiet", "--no-index", relative], cwd=workspace).returncode == 0
    tracked = subprocess.check_output(["git", "ls-files", "--", relative], cwd=workspace, text=True).strip()
    if not ignored or tracked:
        raise ValueError("Private export destination must be ignored and untracked")
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote-environment")
    parser.add_argument("--output", type=Path, default=Path(".git/admin-cutover-retirement-audit"))
    args = parser.parse_args()
    if args.remote_environment:
        try:
            result = asyncio.run(remote_audit(args.remote_environment))
        except Exception:
            print(json.dumps({"error": "read_only_audit_failed"}))
            return 1
        print(json.dumps(result, default=str))
        return 0
    args.output = validate_private_output(args.output)
    from helpdesk_remote_profile import RemoteProfile
    profile = RemoteProfile.from_environment()
    remote_command = "sudo -n " + shlex.quote(profile.server_python) + " - --remote-environment " + shlex.quote(profile.environment_file)
    result = subprocess.run(["ssh", "-i", str(profile.ssh_key), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=8", profile.remote, remote_command], input=Path(__file__).read_text(encoding="utf-8"), text=True, encoding="utf-8", capture_output=True, timeout=180)
    if result.returncode:
        print("Read-only audit failed; remote diagnostics suppressed to protect configuration.")
        return 1
    payload = json.loads(result.stdout)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (("report.json", payload["report"]), ("private-business-metadata.json", payload["private_export"])):
        data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = args.output / name
        path.write_bytes(data)
        print(f"{name}: sha256={hashlib.sha256(data).hexdigest()}")
    print(json.dumps(payload["report"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
