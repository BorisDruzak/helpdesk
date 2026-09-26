"""Verified PostgreSQL backup and disposable restore drill; no secrets in argv."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit


def libpq_environment(url: str) -> dict[str, str]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg"} or not parsed.hostname or parsed.query:
        raise ValueError("PostgreSQL URL must have explicit host/database and no query")
    database = unquote(parsed.path.lstrip("/"))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
        raise ValueError("PostgreSQL database identifier is invalid")
    env = os.environ.copy()
    # Avoid ambient libpq service/options silently changing the destination.
    for name in tuple(env):
        if name.startswith("PG"):
            env.pop(name)
    env.update(PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432), PGDATABASE=database,
               PGUSER=unquote(parsed.username or ""), PGPASSWORD=unquote(parsed.password or ""),
               PGCONNECT_TIMEOUT="10")
    return env


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _marker(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _call(run, argv: list[str], env: dict[str, str]) -> str:
    result = run(argv, env=env, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _revision(run, env: dict[str, str]) -> str:
    exists = _call(run, ["psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-c",
                        "SELECT to_regclass('public.alembic_version') IS NOT NULL"], env)
    if exists == "f":
        return "empty"
    return _call(run, ["psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-c",
                       "SELECT version_num FROM alembic_version ORDER BY version_num"], env)


def create_verified_backup(url: str, directory: Path, marker: Path, source_release: str, *, run=subprocess.run) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}", source_release):
        raise ValueError("backup requires exact source release SHA")
    env = libpq_environment(url)
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    archive = directory / f"helpdesk-{uuid.uuid4().hex}.dump"
    payload = dict(status="failed", database=env["PGDATABASE"], target=env["PGDATABASE"],
                   created_at=_now(), source_release=source_release, format="postgres-custom")
    _marker(marker, payload)  # Invalidate any previous successful marker first.
    try:
        revision = _revision(run, env)
        # Reserve privately before pg_dump opens the output; umask independent.
        with archive.open("xb"):
            pass
        archive.chmod(0o600)
        _call(run, ["pg_dump", "--format=custom", "--file", str(archive)], env)
        if archive.stat().st_size == 0:
            raise ValueError("empty archive")
        _call(run, ["pg_restore", "--list", str(archive)], env)
        with archive.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        payload.update(status="success", sha256=digest, size_bytes=archive.stat().st_size,
                       pre_migration_revision=revision, artifact=str(archive), finished_at=_now())
        _marker(marker, payload)
        return payload
    except (OSError, ValueError, subprocess.CalledProcessError):
        payload["finished_at"] = _now()
        _marker(marker, payload)
        raise RuntimeError("PostgreSQL backup failed; migration must not start") from None


def restore_drill(admin_url: str, backup_marker: Path, output: Path, *, run=subprocess.run) -> dict:
    env = libpq_environment(admin_url)
    payload = dict(status="failed", target="isolated-helpdesk-restore", finished_at=_now())
    _marker(output, payload)
    created = False
    name = "helpdesk_restore_" + uuid.uuid4().hex
    try:
        backup = json.loads(backup_marker.read_text(encoding="utf-8"))
        archive = Path(backup["artifact"])
        with archive.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        if backup.get("status") != "success" or digest != backup.get("sha256") or archive.stat().st_size != backup.get("size_bytes"):
            raise ValueError("backup verification failed")
        _call(run, ["pg_restore", "--list", str(archive)], env)
        _call(run, ["createdb", "--template=template0", name], env)
        created = True
        restore_env = dict(env, PGDATABASE=name)
        _call(run, ["pg_restore", "--exit-on-error", "--no-owner", "--no-privileges", "--dbname", name, str(archive)], restore_env)
        revision = _revision(run, restore_env)
        if revision != backup["pre_migration_revision"]:
            raise ValueError("restored migration revision differs")
        count = _call(run, ["psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-c",
                           "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"], restore_env)
        if revision != "empty" and int(count) < 1:
            raise ValueError("restored schema is empty")
        _call(run, ["psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-c", "BEGIN; SELECT 1; ROLLBACK;"], restore_env)
        payload.update(backup_sha256=digest, source_release=backup["source_release"], schema_revision=revision)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        raise RuntimeError("PostgreSQL restore drill failed") from None
    finally:
        if created:
            try:
                _call(run, ["dropdb", name], env)
            except (OSError, subprocess.CalledProcessError):
                _marker(output, payload)
                raise RuntimeError("Restore drill cleanup failed; isolated database retained") from None
    payload.update(status="success", finished_at=_now())
    _marker(output, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-drill", action="store_true")
    parser.add_argument("--backup-marker", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.restore_drill or not args.output:
        parser.error("use --restore-drill --output; migration entrypoint creates backups automatically")
    try:
        restore_drill(os.environ["HELPDESK_RESTORE_ADMIN_URL"], args.backup_marker, args.output)
    except (RuntimeError, ValueError, KeyError):
        raise SystemExit("Restore drill failed; inspect protected operational state") from None
    print("Isolated restore drill passed and temporary database removed")


if __name__ == "__main__":
    main()
