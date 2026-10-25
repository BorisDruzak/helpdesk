#!/usr/bin/env python3
"""Run a command against a disposable, loopback-only PostgreSQL cluster."""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit, urlunsplit

if __package__ in (None, ""):
    from owned_child_process import run_child
else:
    from .owned_child_process import run_child

WORKSPACE = Path(__file__).resolve().parents[1]
RUN_ROOT = WORKSPACE / ".run" / "postgres-test-runs"
DEFAULT_BIN = WORKSPACE / ".run" / "isolated-postgres" / "pgsql" / "bin"


def redact(text: str, secret: str) -> str:
    return text.replace(secret, "[REDACTED]") if secret else text


def child_environment(base: dict[str, str], admin_url: str) -> dict[str, str]:
    url = urlsplit(admin_url)
    if (url.scheme != "postgresql+asyncpg" or url.hostname != "127.0.0.1"
            or not url.port or url.path != "/postgres" or url.query or url.fragment):
        raise ValueError("Only an explicit loopback PostgreSQL admin URL is allowed")
    env = dict(base)
    for key in ("TEST_DATABASE_URL", "PC_CLIENT_ALLOW_SHARED_TEST_DB",
                "PC_CLIENT_TEST_DB_TEMPLATE_CLONED_FROM", "PC_CLIENT_TEST_DB_TEMPLATE_FINGERPRINT"):
        env.pop(key, None)
    env.update({
        "TEST_DATABASE_ADMIN_URL": admin_url,
        "DATABASE_URL": urlunsplit(url._replace(path="/pc_support_test_runtime")),
        "PC_CLIENT_TEST_DB_TEMPLATE": "0",
        "PC_CLIENT_TEST_DB_TEMPLATE_KEEP": "0",
        "PC_CLIENT_KEEP_TEST_DB": "0",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
    })
    return env


def validate_cluster_path(path: Path, root: Path) -> Path:
    resolved, parent = path.resolve(), root.resolve()
    if resolved == parent or not resolved.is_relative_to(parent):
        raise ValueError("Cluster cleanup must stay inside the dedicated run directory")
    return resolved


def _control(argv: list[str], secret: str) -> None:
    # A detached Windows server may retain inherited pipe handles after pg_ctl
    # exits. A file lets us wait for the control process, not for pipe EOF.
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(argv, stdout=output, stderr=subprocess.STDOUT, timeout=90,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            output.seek(0)
            raise RuntimeError(redact(output.read().decode("utf-8", errors="replace"), secret))


def _grant_cluster_owner_access(cluster: Path) -> None:
    if os.name != "nt":
        return
    # Python's private temporary directory grants OWNER RIGHTS. An elevated
    # token may own it as Administrators, which PostgreSQL deliberately drops.
    # Grant the actual current user on this one disposable directory only.
    result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                            capture_output=True, text=True, encoding="utf-8", check=True)
    sid = next(csv.reader(result.stdout.splitlines()))[1]
    if not sid.startswith("S-1-") or not all(part.isdecimal() for part in sid[2:].split("-")):
        raise RuntimeError("Cannot determine current Windows user SID")
    _control(["icacls", str(cluster), "/grant", f"*{sid}:(OI)(CI)F"], "")


async def _verify_cluster(admin_url: str, data: Path) -> None:
    import asyncpg
    connection = await asyncpg.connect(admin_url.replace("postgresql+asyncpg://", "postgresql://", 1), timeout=10)
    try:
        actual = await connection.fetchval("SHOW data_directory")
        if Path(actual).resolve() != data.resolve():
            raise RuntimeError("Connected PostgreSQL is not the owned disposable cluster")
    finally:
        await connection.close()


def run(command: list[str], bin_dir: Path) -> int:
    suffix = ".exe" if os.name == "nt" else ""
    binaries = {name: bin_dir.resolve() / (name + suffix) for name in ("initdb", "pg_ctl", "postgres")}
    if not all(path.is_file() for path in binaries.values()):
        raise ValueError("PostgreSQL binaries missing; pass --bin-dir (see docs/TESTING_RULES.md)")
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    if not RUN_ROOT.resolve().is_relative_to(WORKSPACE.resolve()):
        raise ValueError("Runtime directory must remain inside this workspace")
    cluster = validate_cluster_path(Path(tempfile.mkdtemp(prefix="pg-test-", dir=RUN_ROOT)), RUN_ROOT)
    data = cluster / "data"
    secret = secrets.token_hex(32)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    admin_url = f"postgresql+asyncpg://pc_client_test_admin:{secret}@127.0.0.1:{port}/postgres"
    pg_ctl = str(binaries["pg_ctl"])
    start_attempted = False
    stopped = True
    try:
        _grant_cluster_owner_access(cluster)
        # The transient password file lives outside the repository and is removed
        # immediately after initdb; no raw credentials enter config or evidence.
        with tempfile.NamedTemporaryFile(mode="w", encoding="ascii", delete=False) as password_file:
            password_file.write(secret + "\n")
            password_path = Path(password_file.name)
        try:
            _control([str(binaries["initdb"]), "-D", str(data), "-U", "pc_client_test_admin",
                      "--auth=scram-sha-256", "--encoding=UTF8", "--locale=C",
                      "--pwfile=" + str(password_path), "--no-instructions"], secret)
        finally:
            password_path.unlink(missing_ok=True)
        with (data / "postgresql.conf").open("a", encoding="utf-8") as config:
            # Every run owns a fresh, disposable cluster. These tests exercise
            # transaction/locking semantics, not crash or power-loss recovery.
            config.write(f"\nlisten_addresses = '127.0.0.1'\nport = {port}\n"
                         "unix_socket_directories = ''\nmax_connections = 40\n"
                         "fsync = off\nfull_page_writes = off\nsynchronous_commit = off\n"
                         "timezone = 'UTC'\nlog_statement = 'none'\n")
        start_attempted, stopped = True, False
        _control([pg_ctl, "-D", str(data), "-l", str(cluster / "postgres.log"),
                  "-w", "-t", "30", "start"], secret)
        asyncio.run(_verify_cluster(admin_url, data))
        print(f"[local-postgres] isolated cluster ready at 127.0.0.1:{port}; SCRAM; no shared fallback", flush=True)
        print("[local-postgres] disposable nondurable cluster; no crash-durability guarantees", flush=True)
        return run_child(command, WORKSPACE, child_environment(os.environ, admin_url), secret)
    finally:
        if start_attempted:
            try:
                _control([pg_ctl, "-D", str(data), "-w", "-t", "30", "stop", "-m", "fast"], secret)
                stopped = True
                print("[local-postgres] owned cluster stopped", flush=True)
            except Exception:
                # Never recursively remove files while their server may be alive.
                print(f"[local-postgres] stop failed; retained owned cluster at {cluster}", file=sys.stderr)
                raise
        if stopped:
            shutil.rmtree(validate_cluster_path(cluster, RUN_ROOT))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path, default=DEFAULT_BIN)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("supply a command after --")
    try:
        return run(command, args.bin_dir)
    except Exception as exc:
        print(f"[local-postgres] {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
