"""Pytest configuration and fixtures for Protocol V3 integration tests."""

import asyncio
import faulthandler
import hashlib
import importlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import types
import uuid
import warnings
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
import asyncpg
from asyncpg import exceptions as asyncpg_exceptions
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError as SQLAlchemyDBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Add server directory to path
server_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(server_dir))

# The runtime default for admin config writes is fail-closed. Pytest enables the
# write surface explicitly so handler/RBAC/validation tests exercise it.
os.environ.setdefault("TICKET_ADMIN_CONFIG_WRITE_ENABLED", "true")

from server import create_app
from app_keys import OUTBOX_SENDER_APP_KEY, bind_app_value
from app.db import engine as db_engine_module
from tech.dismiss_store import clear_dismissed_alerts
from tech.log_buffer import clear_log_records

TEST_DATABASE_PREFIX = "pc_support_test_"
TEST_DATABASE_TEMPLATE_PREFIX = "pc_support_test_template"
SHARED_TEST_DATABASE_NAME = "pc_support_test"
TEST_DB_TEMPLATE_CLONED_FROM_ENV = "PC_CLIENT_TEST_DB_TEMPLATE_CLONED_FROM"
TEST_DB_TEMPLATE_FINGERPRINT_ENV = "PC_CLIENT_TEST_DB_TEMPLATE_FINGERPRINT"
WINDOWS_TEST_DB_TUNNEL_PORT = int(os.getenv("PC_CLIENT_TEST_DB_TUNNEL_PORT", "55432"))
WINDOWS_TEST_DB_TUNNEL_HOST = os.getenv("PC_CLIENT_TEST_DB_TUNNEL_HOST", "127.0.0.1")
WINDOWS_TEST_DB_SSH_TARGET = os.getenv("PC_CLIENT_TEST_DB_SSH_TARGET", "altserver@192.168.100.17")
WINDOWS_TEST_DB_REMOTE_BIND = os.getenv("PC_CLIENT_TEST_DB_REMOTE_BIND", "127.0.0.1:5432")
WINDOWS_TEST_DB_SSH_KEY = os.getenv(
    "PC_CLIENT_TEST_DB_SSH_KEY",
    r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519",
)
TEST_DB_ADMIN_LOCK_TIMEOUT_SECONDS = 5
TEST_DB_ADMIN_STATEMENT_TIMEOUT_SECONDS = 30
TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS = 35

TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"
TEST_UI_AUDITOR_TOKEN = "test-ui-auditor-token"
TEST_UI_USER_PREFIX = "test-ui-user:"
TEST_AGENT_PREFIX = "test-agent:"

_WINDOWS_TEST_DB_TUNNEL_PROCESS = None
_WINDOWS_TEST_DB_TUNNEL_OWNED = False
_SHARED_TEST_DB_TERMINATE_UNAVAILABLE = False
_AGENT_WS_FIXTURES = {"test_agent"}
_TEST_TIMING_WRITE_FAILED = False


class TestDbTemplateConfigError(RuntimeError):
    """Raised when the opt-in template DB configuration is unsafe."""


def _test_timing_enabled() -> bool:
    return os.getenv("PC_CLIENT_TEST_TIMING", "").strip() == "1"


def _test_timing_start() -> float | None:
    if not _test_timing_enabled():
        return None
    return time.perf_counter()


def _record_test_timing(
    fixture: str,
    phase: str,
    started_at: float | None,
    *,
    nodeid: str | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    if started_at is None:
        return
    path_raw = os.getenv("PC_CLIENT_TEST_TIMING_PATH", "").strip()
    if not path_raw:
        return
    duration_seconds = time.perf_counter() - started_at
    record = {
        "schema": "pc_client.fixture_timing.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "worker_id": os.getenv("PYTEST_XDIST_WORKER"),
        "nodeid": nodeid,
        "fixture": fixture,
        "phase": phase,
        "duration_seconds": round(duration_seconds, 6),
    }
    if extra:
        record.update(extra)
    path = Path(path_raw)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    except Exception as exc:
        global _TEST_TIMING_WRITE_FAILED
        if not _TEST_TIMING_WRITE_FAILED:
            _TEST_TIMING_WRITE_FAILED = True
            try:
                sys.stderr.write(
                    f"[fixture-timing] failed to write {path}: {type(exc).__name__}: {exc}\n"
                )
                sys.stderr.flush()
            except Exception:
                pass


@contextmanager
def _test_timing_span(fixture: str, phase: str, *, nodeid: str | None = None):
    started_at = _test_timing_start()
    try:
        yield
    finally:
        _record_test_timing(fixture, phase, started_at, nodeid=nodeid)


def _pytest_watchdog_seconds() -> float | None:
    raw = os.getenv("PC_CLIENT_PYTEST_WATCHDOG_SECONDS", "").strip()
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return seconds


def _apply_ci_layer_markers(item) -> None:
    fixture_names = set(getattr(item, "fixturenames", ()) or ())
    if fixture_names & _AGENT_WS_FIXTURES:
        item.add_marker("agent_ws")
        item.add_marker("integration")


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "agent_ws: tests that start the in-process WS agent fixture")
    config.addinivalue_line("markers", "db_cleanup(profile): select an explicit DB cleanup table profile")
    config.addinivalue_line("markers", "light_app: tests that opt into test_app_light/test_client_light")


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        _apply_ci_layer_markers(item)
        _resolve_cleanup_profile(item)


def pytest_runtest_setup(item) -> None:
    seconds = _pytest_watchdog_seconds()
    if seconds is None:
        return

    def _dump_current_test() -> None:
        sys.stderr.write(
            f"\n[pytest-watchdog] {item.nodeid} has been running longer than {seconds:.1f}s; "
            "dumping all Python thread stacks.\n"
        )
        sys.stderr.flush()
        faulthandler.dump_traceback(file=sys.stderr, all_threads=True)

    timer = threading.Timer(seconds, _dump_current_test)
    timer.daemon = True
    setattr(item, "_pc_client_watchdog_timer", timer)
    timer.start()


def pytest_runtest_teardown(item, nextitem) -> None:
    timer = getattr(item, "_pc_client_watchdog_timer", None)
    if timer is not None:
        timer.cancel()


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use selector policy on Windows to avoid Proactor-only websocket teardown noise in pytest."""
    if os.name == "nt":
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                message=r".*WindowsSelectorEventLoopPolicy.*",
            )
            selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
            if selector_policy is not None:
                return selector_policy()
    return asyncio.get_event_loop_policy()


def _run_sync_blocking(func, *args, **kwargs):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return func(*args, **kwargs)

    result: dict[str, object] = {}

    def run_in_thread() -> None:
        try:
            result["value"] = func(*args, **kwargs)
        except BaseException as exc:
            result["exception"] = exc

    thread = threading.Thread(target=run_in_thread, name="pc-client-test-sync-bridge")
    thread.start()
    thread.join()
    if "exception" in result:
        raise result["exception"]
    return result.get("value")


def _run_async_blocking(async_func, *args, **kwargs):
    def run() -> object:
        return asyncio.run(async_func(*args, **kwargs))

    return _run_sync_blocking(run)


def _default_runtime_database_url() -> str:
    runtime_url = os.getenv("DATABASE_URL")
    if runtime_url:
        return runtime_url
    if os.name == "nt":
        return "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_client"
    return "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:5432/pc_client"


def _default_test_database_url(database_name: str) -> str:
    return _render_url(make_url(_default_runtime_database_url()).set(database=database_name))


def _clear_agent_runtime_modules() -> None:
    prefixes = (
        "modules.",
        "config.",
        "pc_agent.",
        "ui_bridge",
        "ui_gui",
        "network.",
        "utils.",
        "core.",
    )
    exact = {
        "modules",
        "config",
        "pc_agent",
        "ws_agent",
        "network",
        "utils",
        "core",
    }
    for mod_name in list(sys.modules.keys()):
        if mod_name in exact or mod_name.startswith(prefixes):
            sys.modules.pop(mod_name, None)


def _snapshot_agent_shadowed_modules() -> dict[str, object]:
    prefixes = (
        "modules.",
        "config.",
        "utils.",
        "core.",
    )
    exact = {
        "modules",
        "config",
        "utils",
        "core",
    }
    return {
        mod_name: module
        for mod_name, module in sys.modules.items()
        if mod_name in exact or mod_name.startswith(prefixes)
    }


def _restore_module_snapshot(snapshot: dict[str, object]) -> None:
    for mod_name, module in snapshot.items():
        sys.modules[mod_name] = module


def _shared_test_db_allowed() -> bool:
    return os.getenv("PC_CLIENT_ALLOW_SHARED_TEST_DB") == "1"


def _render_url(url) -> str:
    return url.render_as_string(hide_password=False)


def _resolve_admin_url(test_db_url: str) -> str:
    explicit_admin = os.getenv("TEST_DATABASE_ADMIN_URL")
    if explicit_admin:
        return explicit_admin
    url = make_url(test_db_url)
    admin_db_name = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    return _render_url(url.set(database=admin_db_name))


def _is_shared_test_database_url(test_database_url: str) -> bool:
    return (make_url(test_database_url).database or "") == SHARED_TEST_DATABASE_NAME


def verify_test_database(test_database_url: str, *, allow_shared: bool | None = None) -> None:
    """Guard destructive test fixtures from touching non-test databases."""
    db_name = make_url(test_database_url).database or ""
    if allow_shared is None:
        allow_shared = _shared_test_db_allowed()
    if allow_shared:
        if db_name != SHARED_TEST_DATABASE_NAME:
            raise RuntimeError(
                "PC_CLIENT_ALLOW_SHARED_TEST_DB=1 requires TEST_DATABASE_URL to point to "
                f"{SHARED_TEST_DATABASE_NAME}, got: {db_name}"
            )
        return
    if not db_name.startswith(TEST_DATABASE_PREFIX):
        raise RuntimeError(
            "TEST_DATABASE_URL must point to an isolated test database named "
            f"{TEST_DATABASE_PREFIX}<runid>, got: {db_name}"
        )


def _validate_test_database_name(db_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise RuntimeError(f"Unsafe test database name: {db_name}")


def _validate_template_database_name(db_name: str) -> None:
    if not re.fullmatch(r"[a-z0-9_]+", db_name) or not db_name.startswith(
        f"{TEST_DATABASE_TEMPLATE_PREFIX}_"
    ):
        raise TestDbTemplateConfigError(
            "Unsafe template database name: expected "
            f"{TEST_DATABASE_TEMPLATE_PREFIX}_<fingerprint>, got: {db_name}"
        )


def _quote_database_identifier(db_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise RuntimeError(f"Unsafe database identifier: {db_name}")
    return f'"{db_name}"'


def _sanitize_test_database_part(value: str, *, fallback: str, max_length: int) -> str:
    sanitized = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return (sanitized or fallback)[:max_length]


def _generated_test_database_name() -> str:
    domain = _sanitize_test_database_part(
        os.getenv("PC_CLIENT_TEST_DB_DOMAIN", "server"),
        fallback="server",
        max_length=24,
    )
    worker = _sanitize_test_database_part(
        os.getenv("PYTEST_XDIST_WORKER") or str(os.getpid()),
        fallback=str(os.getpid()),
        max_length=16,
    )
    run_id = os.getenv("PC_CLIENT_TEST_DB_RUN_ID") or uuid.uuid4().hex
    short_hash = hashlib.sha1(
        f"{run_id}:{domain}:{worker}:{Path.cwd()}".encode("utf-8")
    ).hexdigest()[:6]
    return f"{TEST_DATABASE_PREFIX}{domain}_{worker}_{short_hash}"


def _keep_test_database() -> bool:
    return os.getenv("PC_CLIENT_KEEP_TEST_DB") == "1"


def _test_db_template_enabled() -> bool:
    return os.getenv("PC_CLIENT_TEST_DB_TEMPLATE") == "1"


def _keep_test_db_template() -> bool:
    return os.getenv("PC_CLIENT_TEST_DB_TEMPLATE_KEEP") == "1"


def _rebuild_test_db_template() -> bool:
    return os.getenv("PC_CLIENT_TEST_DB_TEMPLATE_REBUILD") == "1"


def _template_database_name_for_fingerprint(fingerprint: str) -> str:
    prefix_raw = os.getenv("PC_CLIENT_TEST_DB_TEMPLATE_PREFIX", TEST_DATABASE_TEMPLATE_PREFIX)
    prefix = _sanitize_test_database_part(
        prefix_raw,
        fallback=TEST_DATABASE_TEMPLATE_PREFIX,
        max_length=40,
    )
    if not prefix.startswith(TEST_DATABASE_TEMPLATE_PREFIX):
        raise TestDbTemplateConfigError(
            "PC_CLIENT_TEST_DB_TEMPLATE_PREFIX must resolve to a name starting with "
            f"{TEST_DATABASE_TEMPLATE_PREFIX}, got: {prefix_raw}"
        )
    fingerprint_short = re.sub(r"[^a-f0-9]+", "", fingerprint.lower())[:12]
    if len(fingerprint_short) != 12:
        raise TestDbTemplateConfigError(f"Migration fingerprint is too short for template DB name: {fingerprint}")
    db_name = f"{prefix}_{fingerprint_short}"
    _validate_template_database_name(db_name)
    return db_name


def _is_postgresql_database_url(database_url: str) -> bool:
    return make_url(database_url).drivername.startswith("postgresql")


def _migration_fingerprint(server_root: Path | None = None) -> str:
    server_root = server_root or Path(__file__).resolve().parents[1]
    hasher = hashlib.sha1()

    def _add_file(path: Path) -> None:
        rel_path = path.relative_to(server_root).as_posix()
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")

    alembic_ini = server_root / "alembic.ini"
    if alembic_ini.exists():
        _add_file(alembic_ini)

    migrations_root = server_root / "app" / "db" / "migrations"
    if migrations_root.exists():
        for path in sorted(item for item in migrations_root.rglob("*") if item.is_file()):
            _add_file(path)

    return hasher.hexdigest()


def _advisory_lock_key_for_template(template_name: str) -> int:
    digest = hashlib.sha1(template_name.encode("utf-8")).hexdigest()[:16]
    value = int(digest, 16)
    if value >= 2**63:
        value -= 2**64
    return value


def _resolve_test_database_urls() -> tuple[str, str, bool]:
    explicit_test_url = os.getenv("TEST_DATABASE_URL")
    if _shared_test_db_allowed():
        if explicit_test_url:
            shared_url = explicit_test_url
        elif os.name == "nt" and os.getenv("TEST_DATABASE_ADMIN_URL") is None:
            shared_url = _default_windows_shared_test_database_url()
        else:
            shared_url = _default_test_database_url(SHARED_TEST_DATABASE_NAME)
        verify_test_database(shared_url, allow_shared=True)
        return shared_url, _resolve_admin_url(shared_url), True

    if (
        os.name == "nt"
        and explicit_test_url is None
        and os.getenv("TEST_DATABASE_ADMIN_URL") is None
    ):
        admin_url = _default_windows_test_database_admin_url()
        generated_name = _generated_test_database_name()
        test_url = _render_url(make_url(admin_url).set(database=generated_name))
        verify_test_database(test_url, allow_shared=False)
        return test_url, admin_url, False

    if explicit_test_url:
        verify_test_database(explicit_test_url, allow_shared=False)
        return explicit_test_url, _resolve_admin_url(explicit_test_url), False

    admin_url = os.getenv("TEST_DATABASE_ADMIN_URL", _default_test_database_url("postgres"))
    generated_name = _generated_test_database_name()
    test_url = _render_url(make_url(admin_url).set(database=generated_name))
    return test_url, admin_url, False


def _is_tcp_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _default_windows_shared_test_database_url() -> str:
    _ensure_windows_test_db_tunnel()
    return (
        "postgresql+asyncpg://chatbot:chatbot@"
        f"{WINDOWS_TEST_DB_TUNNEL_HOST}:{WINDOWS_TEST_DB_TUNNEL_PORT}/{SHARED_TEST_DATABASE_NAME}"
    )


def _default_windows_test_database_admin_url() -> str:
    _ensure_windows_test_db_tunnel()
    return (
        "postgresql+asyncpg://chatbot:chatbot@"
        f"{WINDOWS_TEST_DB_TUNNEL_HOST}:{WINDOWS_TEST_DB_TUNNEL_PORT}/postgres"
    )


def _ensure_windows_test_db_tunnel() -> None:
    global _WINDOWS_TEST_DB_TUNNEL_PROCESS, _WINDOWS_TEST_DB_TUNNEL_OWNED

    if os.name != "nt":
        return
    if _is_tcp_port_open(WINDOWS_TEST_DB_TUNNEL_HOST, WINDOWS_TEST_DB_TUNNEL_PORT):
        return
    if _WINDOWS_TEST_DB_TUNNEL_PROCESS is not None and _WINDOWS_TEST_DB_TUNNEL_PROCESS.poll() is None:
        return

    cmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "IdentitiesOnly=yes",
        "-i",
        WINDOWS_TEST_DB_SSH_KEY,
        "-L",
        f"{WINDOWS_TEST_DB_TUNNEL_PORT}:{WINDOWS_TEST_DB_REMOTE_BIND}",
        WINDOWS_TEST_DB_SSH_TARGET,
        "-N",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.time() + 10.0
    while time.time() < deadline:
        if _is_tcp_port_open(WINDOWS_TEST_DB_TUNNEL_HOST, WINDOWS_TEST_DB_TUNNEL_PORT):
            _WINDOWS_TEST_DB_TUNNEL_PROCESS = proc
            _WINDOWS_TEST_DB_TUNNEL_OWNED = True
            return
        if proc.poll() is not None:
            stderr = (proc.stderr.read() if proc.stderr else "").strip()
            raise RuntimeError(f"Failed to start Windows test DB SSH tunnel: {stderr or proc.returncode}")
        time.sleep(0.2)

    proc.terminate()
    raise RuntimeError("Timed out waiting for Windows test DB SSH tunnel to open")


def _close_windows_test_db_tunnel() -> None:
    global _WINDOWS_TEST_DB_TUNNEL_PROCESS, _WINDOWS_TEST_DB_TUNNEL_OWNED

    proc = _WINDOWS_TEST_DB_TUNNEL_PROCESS
    if not _WINDOWS_TEST_DB_TUNNEL_OWNED or proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    _WINDOWS_TEST_DB_TUNNEL_PROCESS = None
    _WINDOWS_TEST_DB_TUNNEL_OWNED = False


def _should_auto_fallback_to_shared_test_db() -> bool:
    return (
        os.name == "nt"
        and os.getenv("TEST_DATABASE_URL") is None
        and os.getenv("TEST_DATABASE_ADMIN_URL") is None
        and not _shared_test_db_allowed()
    )


def _iter_exception_causes(exc: Exception):
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    while stack:
        current = stack.pop()
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)
        yield current
        for attr in ("orig", "__cause__", "__context__"):
            nested = getattr(current, attr, None)
            if isinstance(nested, BaseException):
                stack.append(nested)


def _is_admin_database_unavailable(exc: Exception) -> bool:
    handled_types = (
        ConnectionRefusedError,
        OSError,
        asyncpg_exceptions.InvalidAuthorizationSpecificationError,
        asyncpg_exceptions.InsufficientPrivilegeError,
        asyncpg_exceptions.InvalidPasswordError,
        asyncpg_exceptions.PostgresConnectionError,
    )
    if isinstance(exc, SQLAlchemyDBAPIError):
        return any(isinstance(nested, handled_types) for nested in _iter_exception_causes(exc))
    return isinstance(exc, handled_types)


async def _probe_database(database_url: str) -> None:
    sync_like_url = database_url.replace("+asyncpg", "")
    conn = None
    try:
        conn = await asyncpg.connect(sync_like_url)
        await conn.execute("SELECT 1")
    finally:
        if conn is not None:
            await conn.close()


def _probe_database_sync(database_url: str) -> None:
    _run_async_blocking(_probe_database, database_url)


def _maybe_fallback_to_shared_test_db(
    test_db_url: str,
    admin_db_url: str,
    is_shared: bool,
    *,
    allow_auto_shared_fallback: bool,
) -> tuple[str, str, bool]:
    if is_shared or not allow_auto_shared_fallback:
        return test_db_url, admin_db_url, is_shared

    try:
        _probe_database_sync(admin_db_url)
        return test_db_url, admin_db_url, is_shared
    except Exception as exc:
        if not _is_admin_database_unavailable(exc):
            raise

        shared_url = _default_test_database_url(SHARED_TEST_DATABASE_NAME)
        verify_test_database(shared_url, allow_shared=True)
        try:
            _probe_database_sync(shared_url)
        except Exception:
            raise exc

        warnings.warn(
            "Admin test database is unavailable from this client; falling back to shared "
            f"test DB {SHARED_TEST_DATABASE_NAME}. shared test DB fallback: not valid for "
            "full DB/API gate. Set TEST_DATABASE_ADMIN_URL for isolated ephemeral DB runs.",
            RuntimeWarning,
            stacklevel=2,
        )
        return shared_url, _resolve_admin_url(shared_url), True


async def _run_admin_sql(admin_database_url: str, sql: str, **params) -> None:
    engine = create_async_engine(
        admin_database_url,
        echo=False,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
        connect_args={
            "timeout": TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS,
            "command_timeout": TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS,
        },
    )
    operation_error: BaseException | None = None
    try:
        try:
            async with asyncio.timeout(TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS):
                async with engine.connect() as conn:
                    await conn.execute(text(f"SET lock_timeout = '{TEST_DB_ADMIN_LOCK_TIMEOUT_SECONDS}s'"))
                    await conn.execute(
                        text(f"SET statement_timeout = '{TEST_DB_ADMIN_STATEMENT_TIMEOUT_SECONDS}s'")
                    )
                    await conn.execute(text(sql), params)
        except TimeoutError as exc:
            raise TimeoutError(
                "test DB admin operation timed out after "
                f"{TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS}s"
            ) from exc
    except BaseException as exc:
        operation_error = exc
        raise
    finally:
        try:
            async with asyncio.timeout(TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS):
                await engine.dispose()
        except TimeoutError as exc:
            if operation_error is not None:
                sys.stderr.write(
                    "[test-db] engine disposal timed out while preserving the prior admin-operation error\n"
                )
                sys.stderr.flush()
            else:
                raise TimeoutError(
                    "test DB engine disposal timed out after "
                    f"{TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS}s"
                ) from exc


async def _run_admin_scalar(admin_database_url: str, sql: str, **params):
    engine = create_async_engine(
        admin_database_url,
        echo=False,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(sql), params)
            return result.scalar()
    finally:
        await engine.dispose()


async def _terminate_database_backends_on_connection(conn, db_name: str) -> None:
    await conn.execute(
        text(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = :db_name
              AND pid <> pg_backend_pid()
              AND usename = current_user
            """
        ),
        {"db_name": db_name},
    )


async def _database_exists_on_connection(conn, db_name: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
        {"db_name": db_name},
    )
    return result.scalar() == 1


async def _set_database_allow_connections_on_connection(
    conn,
    db_name: str,
    allow_connections: bool,
) -> None:
    allow_sql = "true" if allow_connections else "false"
    await conn.execute(
        text(f"ALTER DATABASE {_quote_database_identifier(db_name)} WITH ALLOW_CONNECTIONS {allow_sql}")
    )


def _report_test_database_admin_phase(phase: str, db_name: str) -> None:
    sys.stderr.write(f"[test-db] {phase}: {db_name}\n")
    sys.stderr.flush()


async def _drop_test_database(admin_database_url: str, db_name: str) -> None:
    _validate_test_database_name(db_name)
    _report_test_database_admin_phase("terminate stale connections", db_name)
    await _run_admin_sql(
        admin_database_url,
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = :db_name
          AND pid <> pg_backend_pid()
          AND usename = current_user
        """,
        db_name=db_name,
    )
    _report_test_database_admin_phase("drop database", db_name)
    await _run_admin_sql(admin_database_url, f'DROP DATABASE IF EXISTS "{db_name}"')


async def _create_test_database(admin_database_url: str, db_name: str) -> None:
    _validate_test_database_name(db_name)
    await _run_admin_sql(admin_database_url, f'CREATE DATABASE "{db_name}"')


async def _clone_test_database_from_template(
    admin_database_url: str,
    db_name: str,
    template_name: str,
) -> None:
    _validate_test_database_name(db_name)
    _validate_template_database_name(template_name)
    await _run_admin_sql(
        admin_database_url,
        f"CREATE DATABASE {_quote_database_identifier(db_name)} TEMPLATE {_quote_database_identifier(template_name)}",
    )


def _alembic_config_for_database_url(test_database_url: str, server_root: Path | None = None):
    from alembic.config import Config

    server_root = server_root or Path(__file__).resolve().parents[1]
    alembic_ini = server_root / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", test_database_url)
    script_path = server_root / "app" / "db" / "migrations"
    if script_path.exists():
        alembic_cfg.set_main_option("script_location", str(script_path))
    return alembic_cfg


def _alembic_head_revisions(server_root: Path | None = None) -> set[str]:
    from alembic.script import ScriptDirectory

    alembic_cfg = _alembic_config_for_database_url("postgresql+asyncpg://example/example", server_root)
    return set(ScriptDirectory.from_config(alembic_cfg).get_heads())


def _run_alembic_upgrade(test_database_url: str, server_root: Path | None = None) -> None:
    from alembic import command

    server_root = server_root or Path(__file__).resolve().parents[1]
    alembic_cfg = _alembic_config_for_database_url(test_database_url, server_root)
    alembic_ini = server_root / "alembic.ini"

    if os.name == "nt":
        env = os.environ.copy()
        env["DATABASE_URL"] = test_database_url
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
            cwd=str(server_root),
            env=env,
            check=True,
        )
        return

    with patch.dict(os.environ, {"DATABASE_URL": test_database_url}):
        command.upgrade(alembic_cfg, "head")


async def _database_alembic_revisions(test_database_url: str) -> set[str]:
    engine = create_async_engine(test_database_url, echo=False, pool_pre_ping=True, poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            return {str(row[0]) for row in result.fetchall()}
    finally:
        await engine.dispose()


def _ensure_database_at_alembic_head(test_database_url: str, server_root: Path | None = None) -> None:
    expected = _alembic_head_revisions(server_root)
    actual = _run_async_blocking(_database_alembic_revisions, test_database_url)
    if actual != expected:
        db_name = make_url(test_database_url).database or ""
        raise RuntimeError(
            f"Template-cloned test database {db_name} is not at Alembic head; "
            f"expected {sorted(expected)}, got {sorted(actual)}"
        )


async def _template_database_ready(
    template_database_url: str,
    server_root: Path | None = None,
) -> bool:
    try:
        expected = _alembic_head_revisions(server_root)
        actual = await _database_alembic_revisions(template_database_url)
    except Exception:
        return False
    return actual == expected


async def _asyncpg_database_exists(conn, db_name: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = $1)",
            db_name,
        )
    )


async def _asyncpg_set_database_allow_connections(
    conn,
    db_name: str,
    allow_connections: bool,
) -> None:
    allow_sql = "true" if allow_connections else "false"
    await conn.execute(
        f"ALTER DATABASE {_quote_database_identifier(db_name)} WITH ALLOW_CONNECTIONS {allow_sql}"
    )


async def _asyncpg_terminate_database_backends(conn, db_name: str) -> None:
    await conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1
          AND pid <> pg_backend_pid()
          AND usename = current_user
        """,
        db_name,
    )


async def _asyncpg_drop_database(conn, db_name: str) -> None:
    await conn.execute(f"DROP DATABASE IF EXISTS {_quote_database_identifier(db_name)}")


async def _template_database_pre_migration_setup(
    conn,
    template_name: str,
    template_url: str,
    server_root: Path,
) -> bool:
    exists = await _asyncpg_database_exists(conn, template_name)
    if exists:
        await _asyncpg_set_database_allow_connections(conn, template_name, True)
    if exists and not _rebuild_test_db_template():
        if await _template_database_ready(template_url, server_root):
            await _asyncpg_set_database_allow_connections(conn, template_name, False)
            return False

    if exists:
        await _asyncpg_terminate_database_backends(conn, template_name)
        await _asyncpg_drop_database(conn, template_name)

    await conn.execute(f"CREATE DATABASE {_quote_database_identifier(template_name)}")
    return True


async def _template_database_finalize_after_migration(
    conn,
    template_name: str,
    template_url: str,
    server_root: Path,
) -> None:
    if not await _template_database_ready(template_url, server_root):
        raise RuntimeError(f"Template DB {template_name} was migrated but did not reach Alembic head")
    await _asyncpg_set_database_allow_connections(conn, template_name, False)


async def _template_database_cleanup_after_failure(conn, template_name: str) -> None:
    try:
        if not await _asyncpg_database_exists(conn, template_name):
            return
        await _asyncpg_set_database_allow_connections(conn, template_name, True)
        await _asyncpg_terminate_database_backends(conn, template_name)
        await _asyncpg_drop_database(conn, template_name)
    except Exception:
        return


def _prepare_test_db_template_locked(
    admin_database_url: str,
    *,
    server_root: Path,
    template_name: str,
    template_url: str,
    lock_key: int,
) -> None:
    loop = asyncio.new_event_loop()
    previous_loop = None
    try:
        try:
            previous_loop = asyncio.get_event_loop()
        except RuntimeError:
            previous_loop = None
        asyncio.set_event_loop(loop)
        conn = loop.run_until_complete(asyncpg.connect(admin_database_url.replace("+asyncpg", "")))
        locked = False
        needs_cleanup_on_error = False
        try:
            loop.run_until_complete(conn.execute("SELECT pg_advisory_lock($1::bigint)", lock_key))
            locked = True
            needs_migration = loop.run_until_complete(
                _template_database_pre_migration_setup(conn, template_name, template_url, server_root)
            )
            if needs_migration:
                needs_cleanup_on_error = True
                _run_alembic_upgrade(template_url, server_root)
                loop.run_until_complete(
                    _template_database_finalize_after_migration(conn, template_name, template_url, server_root)
                )
                needs_cleanup_on_error = False
        except Exception:
            if needs_cleanup_on_error:
                loop.run_until_complete(_template_database_cleanup_after_failure(conn, template_name))
            raise
        finally:
            if locked:
                loop.run_until_complete(conn.execute("SELECT pg_advisory_unlock($1::bigint)", lock_key))
            loop.run_until_complete(conn.close())
    finally:
        asyncio.set_event_loop(previous_loop)
        loop.close()


def _prepare_test_db_template(
    admin_database_url: str,
    *,
    server_root: Path | None = None,
) -> tuple[str, str]:
    server_root = server_root or Path(__file__).resolve().parents[1]
    fingerprint = _migration_fingerprint(server_root)
    template_name = _template_database_name_for_fingerprint(fingerprint)
    template_url = _render_url(make_url(admin_database_url).set(database=template_name))
    lock_key = _advisory_lock_key_for_template(template_name)
    _record_test_timing(
        "db_template_fingerprint",
        "info",
        _test_timing_start(),
        extra={"fingerprint": fingerprint, "template_db": template_name},
    )

    prepare_started = _test_timing_start()
    try:
        _run_sync_blocking(
            _prepare_test_db_template_locked,
            admin_database_url,
            server_root=server_root,
            template_name=template_name,
            template_url=template_url,
            lock_key=lock_key,
        )
        return template_name, fingerprint
    finally:
        _record_test_timing(
            "db_template_prepare",
            "prepare",
            prepare_started,
            extra={"template_db": template_name, "fingerprint": fingerprint},
        )


async def _clone_test_database_from_template_with_retry(
    admin_database_url: str,
    db_name: str,
    template_name: str,
) -> None:
    clone_started = _test_timing_start()
    try:
        try:
            await _clone_test_database_from_template(admin_database_url, db_name, template_name)
        except Exception:
            engine = create_async_engine(
                admin_database_url,
                echo=False,
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True,
            )
            try:
                async with engine.connect() as conn:
                    await _terminate_database_backends_on_connection(conn, template_name)
            finally:
                await engine.dispose()
            await _clone_test_database_from_template(admin_database_url, db_name, template_name)
    finally:
        _record_test_timing(
            "db_template_clone",
            "clone",
            clone_started,
            extra={"template_db": template_name, "test_db": db_name},
        )


async def _terminate_other_test_database_backends(
    admin_database_url: str,
    test_database_url: str,
) -> None:
    global _SHARED_TEST_DB_TERMINATE_UNAVAILABLE

    db_name = make_url(test_database_url).database or ""
    if db_name != SHARED_TEST_DATABASE_NAME:
        return
    if _SHARED_TEST_DB_TERMINATE_UNAVAILABLE:
        return
    _validate_test_database_name(db_name)
    try:
        await _run_admin_sql(
            admin_database_url,
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = :db_name
              AND pid <> pg_backend_pid()
              AND usename = current_user
            """,
            db_name=db_name,
        )
    except Exception as exc:
        if _is_admin_database_unavailable(exc):
            _SHARED_TEST_DB_TERMINATE_UNAVAILABLE = True
            warnings.warn(
                "Shared test DB cleanup could not terminate other backends; continuing without "
                "pg_terminate_backend because admin privileges are unavailable.",
                RuntimeWarning,
                stacklevel=2,
            )
            return
        raise


@pytest.fixture(scope="session")
def test_database_url() -> str:
    test_db_url, admin_db_url, is_shared = _resolve_test_database_urls()
    test_db_url, admin_db_url, is_shared = _maybe_fallback_to_shared_test_db(
        test_db_url,
        admin_db_url,
        is_shared,
        allow_auto_shared_fallback=_should_auto_fallback_to_shared_test_db(),
    )
    if is_shared and _test_db_template_enabled():
        raise RuntimeError(
            "template DB requires isolated admin database access; shared fallback is not valid "
            "for full DB/API gate"
        )
    verify_test_database(test_db_url, allow_shared=is_shared)
    original_test_url = os.environ.get("TEST_DATABASE_URL")
    original_admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    original_allow_shared = os.environ.get("PC_CLIENT_ALLOW_SHARED_TEST_DB")
    original_template_cloned_from = os.environ.get(TEST_DB_TEMPLATE_CLONED_FROM_ENV)
    original_template_fingerprint = os.environ.get(TEST_DB_TEMPLATE_FINGERPRINT_ENV)
    os.environ["TEST_DATABASE_URL"] = test_db_url
    os.environ["TEST_DATABASE_ADMIN_URL"] = admin_db_url
    if is_shared:
        os.environ["PC_CLIENT_ALLOW_SHARED_TEST_DB"] = "1"

    db_name = make_url(test_db_url).database or ""
    template_name: str | None = None
    if not is_shared:
        _run_async_blocking(_drop_test_database, admin_db_url, db_name)
        if _test_db_template_enabled() and _is_postgresql_database_url(test_db_url):
            try:
                template_name, template_fingerprint = _prepare_test_db_template(admin_db_url)
                _run_async_blocking(
                    _clone_test_database_from_template_with_retry,
                    admin_db_url,
                    db_name,
                    template_name,
                )
                os.environ[TEST_DB_TEMPLATE_CLONED_FROM_ENV] = template_name
                os.environ[TEST_DB_TEMPLATE_FINGERPRINT_ENV] = template_fingerprint
            except TestDbTemplateConfigError:
                raise
            except Exception as exc:
                _record_test_timing(
                    "db_template_fallback",
                    "fallback",
                    _test_timing_start(),
                    extra={"reason": f"{type(exc).__name__}: {exc}", "test_db": db_name},
                )
                warnings.warn(
                    "PostgreSQL test DB template is unavailable; falling back to direct "
                    f"Alembic migration path for {db_name}: {type(exc).__name__}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                _run_async_blocking(_create_test_database, admin_db_url, db_name)
        else:
            _run_async_blocking(_create_test_database, admin_db_url, db_name)

    try:
        yield test_db_url
    finally:
        if original_test_url is None:
            os.environ.pop("TEST_DATABASE_URL", None)
        else:
            os.environ["TEST_DATABASE_URL"] = original_test_url
        if original_admin_url is None:
            os.environ.pop("TEST_DATABASE_ADMIN_URL", None)
        else:
            os.environ["TEST_DATABASE_ADMIN_URL"] = original_admin_url
        if original_allow_shared is None:
            os.environ.pop("PC_CLIENT_ALLOW_SHARED_TEST_DB", None)
        else:
            os.environ["PC_CLIENT_ALLOW_SHARED_TEST_DB"] = original_allow_shared
        if original_template_cloned_from is None:
            os.environ.pop(TEST_DB_TEMPLATE_CLONED_FROM_ENV, None)
        else:
            os.environ[TEST_DB_TEMPLATE_CLONED_FROM_ENV] = original_template_cloned_from
        if original_template_fingerprint is None:
            os.environ.pop(TEST_DB_TEMPLATE_FINGERPRINT_ENV, None)
        else:
            os.environ[TEST_DB_TEMPLATE_FINGERPRINT_ENV] = original_template_fingerprint
        if not is_shared and not _keep_test_database():
            _run_async_blocking(_drop_test_database, admin_db_url, db_name)
        if template_name and not _keep_test_db_template():
            try:
                _validate_template_database_name(template_name)
                _run_async_blocking(_drop_test_database, admin_db_url, template_name)
            except Exception as exc:
                warnings.warn(
                    "Could not drop PostgreSQL test DB template "
                    f"{template_name}: {type(exc).__name__}: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
        _close_windows_test_db_tunnel()


@pytest.fixture(scope="session")
def run_migrations(test_database_url: str):
    """Apply Alembic migrations once per pytest session."""
    timing_started = _test_timing_start()
    timing_phase = "setup"
    timing_extra: dict[str, object] | None = None
    try:
        verify_test_database(test_database_url)
        cloned_from = os.getenv(TEST_DB_TEMPLATE_CLONED_FROM_ENV)
        if _test_db_template_enabled() and cloned_from:
            _ensure_database_at_alembic_head(test_database_url)
            timing_phase = "skipped_template"
            timing_extra = {
                "template_db": cloned_from,
                "fingerprint": os.getenv(TEST_DB_TEMPLATE_FINGERPRINT_ENV),
            }
            return

        _run_alembic_upgrade(test_database_url)
    finally:
        _record_test_timing("run_migrations", timing_phase, timing_started, extra=timing_extra)


@pytest.fixture(scope="session")
def test_database_admin_url(test_database_url: str) -> str:
    return _resolve_admin_url(test_database_url)


@pytest.fixture(scope="session")
def test_engine(test_database_url: str, run_migrations):
    """Single async engine shared across the full server pytest session."""
    verify_test_database(test_database_url)
    engine = create_async_engine(
        test_database_url,
        echo=False,
        pool_pre_ping=True,
        poolclass=NullPool,
    )
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    previous_engine = db_engine_module._engine
    previous_session_maker = db_engine_module._session_maker
    db_engine_module._engine = engine
    db_engine_module._session_maker = session_maker

    try:
        yield engine
    finally:
        db_engine_module._engine = previous_engine
        db_engine_module._session_maker = previous_session_maker
        asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
def ensure_db_ready(request):
    """Ensure migrations are applied before DB-backed tests run."""
    if request.node.get_closest_marker("no_db"):
        return
    request.getfixturevalue("run_migrations")


FULL_CLEANUP_TABLES = (
    "observer_integrity_check_runs",
    "observer_integrity_events",
    "observer_known_contamination",
    "observer_error_occurrences",
    "observer_error_signatures",
    "observer_span_links",
    "observer_spans",
    "observer_traces",
    "agent_observer_events",
    "diagnostic_provider_audit",
    "diagnostic_provider_credential_refs",
    "diagnostic_provider_configs",
    "diagnostic_artifact_links",
    "diagnostic_session_capabilities",
    "tool_presentation_overrides",
    "agent_recipe_test_runs",
    "agent_recipe_primitives",
    "agent_recipe_versions",
    "diagnostic_capability_versions",
    "diagnostic_capabilities",
    "diagnostic_providers",
    "diagnostic_bundles",
    "diagnostic_findings",
    "diagnostic_evidence",
    "diagnostic_steps",
    "diagnostic_sessions",
    "knowledge_chunk_embeddings",
    "knowledge_index_jobs",
    "ai_request_audit",
    "ai_policy_profiles",
    "ai_model_profiles",
    "ai_providers",
    "knowledge_search_settings",
    "knowledge_search_events",
    "knowledge_gap_findings",
    "knowledge_quality_snapshots",
    "knowledge_audience_rules",
    "knowledge_review_comments",
    "knowledge_review_tasks",
    "knowledge_content_pack_items",
    "knowledge_content_packs",
    "knowledge_rollout_policies",
    "knowledge_taxonomy_terms",
    "knowledge_property_definitions",
    "knowledge_item_properties",
    "knowledge_item_taxonomy_terms",
    "knowledge_applicability_rules",
    "knowledge_quality_models",
    "knowledge_graph_layouts",
    "knowledge_ai_proposals",
    "knowledge_entity_mentions",
    "knowledge_feedback_events",
    "knowledge_article_segments",
    "knowledge_article_views",
    "knowledge_user_bookmarks",
    "knowledge_correction_requests",
    "knowledge_article_subscriptions",
    "knowledge_article_editor_events",
    "knowledge_version_diff_cache",
    "knowledge_segmentation_jobs",
    "knowledge_segmentation_profiles",
    "knowledge_ingestion_jobs",
    "continuous_improvement_actions",
    "changes",
    "change_risk_assessments",
    "change_plans",
    "change_approvals",
    "change_windows",
    "change_affected_objects",
    "change_tasks",
    "change_pir_records",
    "change_activity_events",
    "problem_scanner_runs",
    "problem_activity_events",
    "problem_known_error_links",
    "problem_affected_objects",
    "problem_rca_records",
    "problem_candidates",
    "problem_detection_rules",
    "problem_slo_policies",
    "problem_ticket_links",
    "problems",
    "knowledge_edges",
    "knowledge_nodes",
    "knowledge_bindings",
    "knowledge_chunks",
    "knowledge_item_versions",
    "knowledge_items",
    "knowledge_spaces",
    "ticket_quality_review_comments",
    "ticket_quality_reviews",
    "ticket_reopen_events",
    "ticket_waits",
    "ticket_resolution_passports",
    "ticket_evidence_items",
    "ticket_action_log",
    "ticket_approvals",
    "ticket_related_objects",
    "ticket_watchers",
    "ticket_links",
    "ticket_kb_links",
    "ticket_knowledge_links",
    "ticket_worklogs",
    "ticket_notifications",
    "ticket_notification_prefs",
    "ticket_public_sessions",
    "ticket_feedback",
    "service_quality_snapshots",
    "quality_policies",
    "remote_access_events",
    "remote_access_sessions",
    "artifacts",
    "operation_dependencies",
    "operations",
    "device_outbox",
    "ticket_events",
    "ticket_events_archive",
    "device_events",
    "device_toolset_snapshots",
    "device_registration_claims",
    "device_user_bindings",
    "device_registration_events",
    "device_account_sessions",
    "device_account_login_requests",
    "device_browser_pairings",
    "device_account_events",
    "device_inventory_snapshots",
    "device_inventory_bindings",
    "device_inventory_binding_history",
    "device_inventory_refresh_policies",
    "device_inventory_refresh_runs",
    "device_inventory_bulk_operations",
    "device_inventory_bulk_operation_items",
    "device_binding_suggestions",
    "device_presence_snapshots",
    "device_presence_daily_summaries",
    "device_desired_modules",
    "device_modules",
    "device_config",
    "registry_quality_issue_overrides",
    "registry_admin_events",
    "registry_admin_policies",
    "registry_person_department_memberships",
    "registry_audience_group_members",
    "registry_audience_groups",
    "registry_assets",
    "registry_person_identities",
    "registry_people",
    "registry_services",
    "registry_vendors",
    "registry_locations",
    "registry_departments",
    "dispatch_ready_devices",
    "devices",
    "agent_tokens",
    "connection_requests",
    "auth_sessions",
    "consent_decisions",
    "user_consent_requests",
    "ui_tokens",
    "ui_password_reset_requests",
    "download_audit",
    "job_events",
    "server_runtime_snapshots",
    "runner_rollout_plans",
    "runner_rollout_waves",
    "runner_rollout_targets",
    "runner_rollout_events",
    "agent_build_download_audit",
    "agent_builds",
    "agent_runtime_audit",
    "server_config",
    "ui_user_audit",
    "access_audit",
    "access_group_queue_members",
    "access_group_permissions",
    "access_group_members",
    "access_groups",
    "helpdesk_policy_audit",
    "request_templates",
    "priority_policies",
    "sla_policies",
    "ola_policies",
    "routing_policies",
    "approval_policies",
    "closure_policies",
    "diagnostic_policies",
    "notification_policies",
    "visibility_policies",
    "reporting_policies",
    "smart_views",
    "support_queue_saved_views",
    "ticket_admin_audit",
    "ticket_admin_audit_archive",
    "ticket_change_links",
    "ticket_queue_ola_targets",
    "ticket_queue_members",
    "ticket_routing_rules",
    "ticket_priority_matrix",
    "ticket_sla_targets",
    "ticket_sla_policies",
    "ticket_business_calendars",
    "ticket_resolution_codes",
    "ticket_queues",
    "playbook_step_run",
    "playbook_step",
    "playbook_run",
    "playbook_version",
    "playbook",
    "ui_users",
    "modules",
    "ticket_retention_runs",
    "tickets",
)


def _cleanup_profile_subset(*tables: str) -> tuple[str, ...]:
    requested = set(tables)
    unknown = requested - set(FULL_CLEANUP_TABLES)
    if unknown:
        raise RuntimeError(f"Cleanup profile references unknown tables: {sorted(unknown)}")
    return tuple(table for table in FULL_CLEANUP_TABLES if table in requested)


CLEANUP_TABLES_BY_PROFILE = {
    "full": FULL_CLEANUP_TABLES,
    "knowledge": _cleanup_profile_subset(
        "knowledge_chunk_embeddings",
        "knowledge_index_jobs",
        "ai_request_audit",
        "ai_policy_profiles",
        "ai_model_profiles",
        "ai_providers",
        "knowledge_search_settings",
        "knowledge_search_events",
        "knowledge_gap_findings",
        "knowledge_quality_snapshots",
        "knowledge_audience_rules",
        "knowledge_review_comments",
        "knowledge_review_tasks",
        "knowledge_content_pack_items",
        "knowledge_content_packs",
        "knowledge_rollout_policies",
        "continuous_improvement_actions",
        "problem_scanner_runs",
        "problem_activity_events",
        "problem_known_error_links",
        "problem_affected_objects",
        "problem_rca_records",
        "problem_candidates",
        "problem_detection_rules",
        "problem_slo_policies",
        "problem_ticket_links",
        "problems",
        "knowledge_edges",
        "knowledge_nodes",
        "knowledge_bindings",
        "knowledge_chunks",
        "knowledge_item_versions",
        "knowledge_items",
        "knowledge_spaces",
        "registry_departments",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_people",
        "agent_runtime_audit",
        "ticket_events",
        "artifacts",
        "ui_users",
        "tickets",
    ),
    "observer_diagnostics": _cleanup_profile_subset(
        "observer_integrity_check_runs",
        "observer_integrity_events",
        "observer_known_contamination",
        "observer_error_occurrences",
        "observer_error_signatures",
        "observer_span_links",
        "observer_spans",
        "observer_traces",
        "agent_observer_events",
        "diagnostic_provider_audit",
        "diagnostic_provider_credential_refs",
        "diagnostic_provider_configs",
        "tool_presentation_overrides",
        "agent_recipe_test_runs",
        "agent_recipe_primitives",
        "agent_recipe_versions",
        "diagnostic_capability_versions",
        "diagnostic_capabilities",
        "diagnostic_providers",
        "diagnostic_bundles",
        "diagnostic_findings",
        "diagnostic_evidence",
        "diagnostic_steps",
        "diagnostic_sessions",
        "problem_scanner_runs",
        "problem_activity_events",
        "problem_known_error_links",
        "problem_affected_objects",
        "problem_rca_records",
        "problem_candidates",
        "problem_detection_rules",
        "problem_slo_policies",
        "problem_ticket_links",
        "problems",
        "operations",
        "device_outbox",
        "ticket_events",
        "device_events",
        "device_toolset_snapshots",
        "device_modules",
        "device_config",
        "dispatch_ready_devices",
        "devices",
        "agent_runtime_audit",
        "modules",
        "tickets",
    ),
    "tickets": _cleanup_profile_subset(
        "ticket_quality_review_comments",
        "ticket_quality_reviews",
        "ticket_reopen_events",
        "ticket_feedback",
        "service_quality_snapshots",
        "quality_policies",
        "remote_access_events",
        "remote_access_sessions",
        "artifacts",
        "operation_dependencies",
        "operations",
        "device_outbox",
        "ticket_events",
        "device_events",
        "device_toolset_snapshots",
        "device_desired_modules",
        "device_modules",
        "device_config",
        "registry_quality_issue_overrides",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_assets",
        "registry_people",
        "registry_services",
        "registry_vendors",
        "registry_locations",
        "registry_departments",
        "dispatch_ready_devices",
        "devices",
        "agent_tokens",
        "connection_requests",
        "server_config",
        "ui_user_audit",
        "access_audit",
        "access_group_queue_members",
        "access_group_permissions",
        "access_group_members",
        "access_groups",
        "helpdesk_policy_audit",
        "request_templates",
        "priority_policies",
        "sla_policies",
        "ola_policies",
        "routing_policies",
        "approval_policies",
        "closure_policies",
        "diagnostic_policies",
        "notification_policies",
        "visibility_policies",
        "reporting_policies",
        "smart_views",
        "ticket_admin_audit",
        "ticket_queue_ola_targets",
        "ticket_queue_members",
        "ticket_routing_rules",
        "ticket_priority_matrix",
        "ticket_sla_targets",
        "ticket_sla_policies",
        "ticket_business_calendars",
        "ticket_resolution_codes",
        "ticket_queues",
        "playbook_step_run",
        "playbook_step",
        "playbook_run",
        "playbook_version",
        "playbook",
        "ui_users",
        "modules",
        "tickets",
    ),
    "agent_runtime": _cleanup_profile_subset(
        "diagnostic_provider_audit",
        "diagnostic_provider_credential_refs",
        "diagnostic_provider_configs",
        "diagnostic_artifact_links",
        "diagnostic_session_capabilities",
        "tool_presentation_overrides",
        "agent_recipe_test_runs",
        "agent_recipe_primitives",
        "agent_recipe_versions",
        "diagnostic_capability_versions",
        "diagnostic_capabilities",
        "diagnostic_providers",
        "remote_access_events",
        "remote_access_sessions",
        "artifacts",
        "operation_dependencies",
        "operations",
        "device_outbox",
        "ticket_events",
        "device_events",
        "device_toolset_snapshots",
        "device_registration_claims",
        "device_user_bindings",
        "device_registration_events",
        "device_inventory_snapshots",
        "device_inventory_bindings",
        "device_inventory_binding_history",
        "device_inventory_refresh_policies",
        "device_inventory_refresh_runs",
        "device_inventory_bulk_operations",
        "device_inventory_bulk_operation_items",
        "device_binding_suggestions",
        "device_desired_modules",
        "device_modules",
        "device_config",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_assets",
        "registry_person_identities",
        "registry_people",
        "registry_services",
        "registry_vendors",
        "registry_locations",
        "registry_departments",
        "dispatch_ready_devices",
        "devices",
        "agent_tokens",
        "connection_requests",
        "agent_build_download_audit",
        "agent_builds",
        "agent_runtime_audit",
        "server_config",
        "modules",
        "tickets",
    ),
    "registration": _cleanup_profile_subset(
        "registry_admin_events",
        "registry_admin_policies",
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_assets",
        "registry_people",
        "registry_services",
        "registry_vendors",
        "registry_locations",
        "registry_departments",
        "dispatch_ready_devices",
        "devices",
        "agent_tokens",
        "connection_requests",
        "ui_user_audit",
        "access_audit",
        "ui_users",
    ),
    "web_support": _cleanup_profile_subset(
        "observer_integrity_check_runs",
        "observer_integrity_events",
        "observer_known_contamination",
        "observer_error_occurrences",
        "observer_error_signatures",
        "observer_span_links",
        "observer_spans",
        "observer_traces",
        "agent_observer_events",
        "tool_presentation_overrides",
        "agent_recipe_test_runs",
        "agent_recipe_primitives",
        "agent_recipe_versions",
        "knowledge_audience_rules",
        "ticket_quality_review_comments",
        "ticket_quality_reviews",
        "ticket_reopen_events",
        "ticket_feedback",
        "service_quality_snapshots",
        "quality_policies",
        "remote_access_events",
        "remote_access_sessions",
        "artifacts",
        "operation_dependencies",
        "operations",
        "device_outbox",
        "ticket_events",
        "device_events",
        "device_toolset_snapshots",
        "device_desired_modules",
        "device_modules",
        "device_config",
        "registry_quality_issue_overrides",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_assets",
        "registry_people",
        "registry_services",
        "registry_vendors",
        "registry_locations",
        "registry_departments",
        "dispatch_ready_devices",
        "devices",
        "agent_tokens",
        "connection_requests",
        "agent_build_download_audit",
        "agent_builds",
        "agent_runtime_audit",
        "server_config",
        "ui_user_audit",
        "access_audit",
        "access_group_queue_members",
        "access_group_permissions",
        "access_group_members",
        "access_groups",
        "helpdesk_policy_audit",
        "request_templates",
        "priority_policies",
        "sla_policies",
        "ola_policies",
        "routing_policies",
        "approval_policies",
        "closure_policies",
        "diagnostic_policies",
        "notification_policies",
        "visibility_policies",
        "reporting_policies",
        "smart_views",
        "ticket_admin_audit",
        "ticket_queue_ola_targets",
        "ticket_queue_members",
        "ticket_routing_rules",
        "ticket_priority_matrix",
        "ticket_sla_targets",
        "ticket_sla_policies",
        "ticket_business_calendars",
        "ticket_resolution_codes",
        "ticket_queues",
        "playbook_step_run",
        "playbook_step",
        "playbook_run",
        "playbook_version",
        "playbook",
        "ui_users",
        "modules",
        "tickets",
    ),
    "registry_access": _cleanup_profile_subset(
        "registry_quality_issue_overrides",
        "registry_admin_events",
        "registry_admin_policies",
        "registry_person_department_memberships",
        "registry_audience_group_members",
        "registry_audience_groups",
        "registry_assets",
        "registry_people",
        "registry_services",
        "registry_vendors",
        "registry_locations",
        "registry_departments",
        "ui_user_audit",
        "access_audit",
        "access_group_queue_members",
        "access_group_permissions",
        "access_group_members",
        "access_groups",
        "ui_users",
    ),
    "policies_config": _cleanup_profile_subset(
        "server_config",
        "helpdesk_policy_audit",
        "request_templates",
        "priority_policies",
        "sla_policies",
        "ola_policies",
        "routing_policies",
        "approval_policies",
        "closure_policies",
        "diagnostic_policies",
        "notification_policies",
        "visibility_policies",
        "reporting_policies",
        "smart_views",
        "ticket_admin_audit",
        "ticket_queue_ola_targets",
        "ticket_queue_members",
        "ticket_routing_rules",
        "ticket_priority_matrix",
        "ticket_sla_targets",
        "ticket_sla_policies",
        "ticket_business_calendars",
        "ticket_resolution_codes",
        "ticket_queues",
        "ui_users",
        "tickets",
    ),
}


def _validate_cleanup_table_name(table_name: str) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", table_name):
        raise RuntimeError(f"Unsafe cleanup table name: {table_name}")


def _cleanup_tables_for_profile(profile: str) -> tuple[str, ...]:
    try:
        tables = CLEANUP_TABLES_BY_PROFILE[profile]
    except KeyError as exc:
        raise RuntimeError(
            f"Unknown db_cleanup profile {profile!r}; expected one of {sorted(CLEANUP_TABLES_BY_PROFILE)}"
        ) from exc
    for table_name in tables:
        _validate_cleanup_table_name(table_name)
    return tables


def _cleanup_truncate_sql(profile: str) -> str:
    tables = _cleanup_tables_for_profile(profile)
    table_list = ",\n                    ".join(tables)
    return f"""
                TRUNCATE TABLE
                    {table_list}
                RESTART IDENTITY CASCADE
            """


def _resolve_cleanup_profile(node) -> str | None:
    if node.get_closest_marker("no_db"):
        return None
    markers = list(node.iter_markers("db_cleanup"))
    if not markers:
        return "full"
    if len(markers) > 1:
        raise RuntimeError("Multiple db_cleanup markers are not allowed on one test")
    marker = markers[0]
    if len(marker.args) != 1 or not isinstance(marker.args[0], str) or marker.kwargs:
        raise RuntimeError("db_cleanup marker requires exactly one profile string argument")
    profile = marker.args[0]
    _cleanup_tables_for_profile(profile)
    return profile


def _cleanup_audit_enabled() -> bool:
    return os.getenv("PC_CLIENT_TEST_CLEANUP_AUDIT") == "1"


async def _audit_cleanup_profile_empty(conn, profile: str, tables: tuple[str, ...]) -> None:
    if not _cleanup_audit_enabled():
        return
    dirty: list[str] = []
    for table_name in tables:
        _validate_cleanup_table_name(table_name)
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {_quote_database_identifier(table_name)}"))
        count = int(result.scalar_one())
        if count:
            dirty.append(f"{table_name}={count}")
    if dirty:
        raise AssertionError(f"db_cleanup({profile!r}) left rows after cleanup: {', '.join(dirty)}")


def _cleanup_timing_extra(profile: str) -> dict[str, object]:
    return {
        "profile": profile,
        "table_count": len(_cleanup_tables_for_profile(profile)),
        "cleanup_strategy": "truncate_profile",
    }


async def _cleanup_db_async(
    test_database_url: str,
    test_database_admin_url: str,
    test_engine,
    *,
    profile: str = "full",
) -> None:
    timing_started = _test_timing_start()
    timing_extra = _cleanup_timing_extra(profile)
    try:
        verify_test_database(test_database_url)
        clear_log_records()
        clear_dismissed_alerts()

        if _is_shared_test_database_url(test_database_url):
            await _terminate_other_test_database_backends(test_database_admin_url, test_database_url)

        async with test_engine.begin() as conn:
            await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            tables = _cleanup_tables_for_profile(profile)
            await conn.execute(text(_cleanup_truncate_sql(profile)))
            await _audit_cleanup_profile_empty(conn, profile, tables)
    finally:
        _record_test_timing("_cleanup_db_async", "call", timing_started, extra=timing_extra)


@pytest.fixture(autouse=True)
def cleanup_db(request):
    """Clean test data before each DB-backed test."""
    profile = _resolve_cleanup_profile(request.node)
    if profile is None:
        return
    timing_started = _test_timing_start()
    timing_extra = _cleanup_timing_extra(profile)
    test_database_url = request.getfixturevalue("test_database_url")
    test_database_admin_url = request.getfixturevalue("test_database_admin_url")
    test_engine = request.getfixturevalue("test_engine")
    try:
        asyncio.run(_cleanup_db_async(test_database_url, test_database_admin_url, test_engine, profile=profile))
    finally:
        _record_test_timing(
            "cleanup_db",
            "setup",
            timing_started,
            nodeid=request.node.nodeid,
            extra=timing_extra,
        )


@pytest.fixture
def patched_get_session(test_engine):
    """Compatibility fixture for tests that still depend on patched_get_session."""
    session_maker = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    with patch("app.db.get_session", test_get_session), \
         patch("app.db.engine.get_session", test_get_session):
        yield


@pytest_asyncio.fixture
async def test_app(patched_get_session, test_engine, test_database_url: str):
    """Создаёт aiohttp app через create_app() с session-scoped test engine."""
    setup_timing_started = _test_timing_start()
    setup_timing_recorded = False
    teardown_timing_started = None
    from auth import middleware as auth_middleware_module
    from auth.context import AuthContext, AuthType
    from auth.service import AuthService
    import config as server_config
    import tools.service as tools_service_module
    from websocket.device_outbox_sender import DeviceOutboxSender, recover_pending_commands

    test_builtin_modules = set(server_config.AGENT_BUILTIN_MODULES) | {
        "test_echo",
        "test_fail",
        "test_slow_echo",
    }

    async def fake_verify_ui_token(self, token: str):
        if token == TEST_UI_SUPPORT_TOKEN:
            return {
                "user_login": "support-test",
                "actor_role": "support",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token == TEST_UI_ADMIN_TOKEN:
            return {
                "user_login": "admin-test",
                "actor_role": "admin",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token == TEST_UI_AUDITOR_TOKEN:
            return {
                "user_login": "auditor-test",
                "actor_role": "auditor",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token.startswith(TEST_UI_USER_PREFIX):
            return {
                "user_login": token.split(":", 1)[1],
                "actor_role": "user",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token.startswith(TEST_AGENT_PREFIX):
            return {
                "user_login": token.split(":", 1)[1],
                "actor_role": "agent",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "agent",
            }
        return None

    async def fake_extract_auth_context(request):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header:
            parts = auth_header.split(" ", 1)
            if len(parts) == 2:
                token = parts[1].strip()
        if token == TEST_UI_SUPPORT_TOKEN:
            return AuthContext(
                actor_id="support-test",
                actor_role="support",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token == TEST_UI_ADMIN_TOKEN:
            return AuthContext(
                actor_id="admin-test",
                actor_role="admin",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token == TEST_UI_AUDITOR_TOKEN:
            return AuthContext(
                actor_id="auditor-test",
                actor_role="auditor",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token and token.startswith(TEST_UI_USER_PREFIX):
            return AuthContext(
                actor_id=token.split(":", 1)[1],
                actor_role="user",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token and token.startswith(TEST_AGENT_PREFIX):
            return AuthContext(
                actor_id=token.split(":", 1)[1],
                actor_role="agent",
                auth_type=AuthType.AGENT_TOKEN,
                token=token,
            )
        return AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="implicit-test-auth",
        )

    try:
        with patch.object(AuthService, "verify_ui_token", fake_verify_ui_token), \
             patch.object(auth_middleware_module, "extract_auth_context", fake_extract_auth_context), \
             patch.object(server_config, "AGENT_BUILTIN_MODULES", test_builtin_modules), \
             patch.object(tools_service_module, "AGENT_BUILTIN_MODULES", test_builtin_modules):
            app = create_app()
            verify_test_database(test_database_url)

            state = app["state"]
            await recover_pending_commands(state)

            sender = DeviceOutboxSender(state, poll_interval=0.5)
            await sender.start_async()
            bind_app_value(app, key=OUTBOX_SENDER_APP_KEY, legacy_name="outbox_sender", value=sender)

            app.on_startup.clear()
            app.on_cleanup.clear()

            async def test_cleanup(app):
                if "outbox_sender" in app:
                    await app["outbox_sender"].stop_async()

            app.on_cleanup.append(test_cleanup)
            _record_test_timing("test_app", "setup", setup_timing_started)
            setup_timing_recorded = True
            try:
                yield app
            finally:
                teardown_timing_started = _test_timing_start()
    finally:
        if not setup_timing_recorded:
            _record_test_timing("test_app", "setup", setup_timing_started)
        _record_test_timing("test_app", "teardown", teardown_timing_started)


@pytest_asyncio.fixture
async def test_app_light(patched_get_session, test_engine, test_database_url: str):
    """Create aiohttp app for HTTP/API tests without runtime sender startup."""
    setup_timing_started = _test_timing_start()
    setup_timing_recorded = False
    teardown_timing_started = None
    from auth import middleware as auth_middleware_module
    from auth.context import AuthContext, AuthType
    from auth.service import AuthService
    import config as server_config
    import tools.service as tools_service_module

    test_builtin_modules = set(server_config.AGENT_BUILTIN_MODULES) | {
        "test_echo",
        "test_fail",
        "test_slow_echo",
    }

    async def fake_verify_ui_token(self, token: str):
        if token == TEST_UI_SUPPORT_TOKEN:
            return {
                "user_login": "support-test",
                "actor_role": "support",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token == TEST_UI_ADMIN_TOKEN:
            return {
                "user_login": "admin-test",
                "actor_role": "admin",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token == TEST_UI_AUDITOR_TOKEN:
            return {
                "user_login": "auditor-test",
                "actor_role": "auditor",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token.startswith(TEST_UI_USER_PREFIX):
            return {
                "user_login": token.split(":", 1)[1],
                "actor_role": "user",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "ui",
            }
        if token.startswith(TEST_AGENT_PREFIX):
            return {
                "user_login": token.split(":", 1)[1],
                "actor_role": "agent",
                "created_at": "2026-01-01T00:00:00+00:00",
                "type": "agent",
            }
        return None

    async def fake_extract_auth_context(request):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header:
            parts = auth_header.split(" ", 1)
            if len(parts) == 2:
                token = parts[1].strip()
        if token == TEST_UI_SUPPORT_TOKEN:
            return AuthContext(
                actor_id="support-test",
                actor_role="support",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token == TEST_UI_ADMIN_TOKEN:
            return AuthContext(
                actor_id="admin-test",
                actor_role="admin",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token == TEST_UI_AUDITOR_TOKEN:
            return AuthContext(
                actor_id="auditor-test",
                actor_role="auditor",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token and token.startswith(TEST_UI_USER_PREFIX):
            return AuthContext(
                actor_id=token.split(":", 1)[1],
                actor_role="user",
                auth_type=AuthType.UI_TOKEN,
                token=token,
            )
        if token and token.startswith(TEST_AGENT_PREFIX):
            return AuthContext(
                actor_id=token.split(":", 1)[1],
                actor_role="agent",
                auth_type=AuthType.AGENT_TOKEN,
                token=token,
            )
        return AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="implicit-test-auth",
        )

    try:
        with patch.object(AuthService, "verify_ui_token", fake_verify_ui_token), \
             patch.object(auth_middleware_module, "extract_auth_context", fake_extract_auth_context), \
             patch.object(server_config, "AGENT_BUILTIN_MODULES", test_builtin_modules), \
             patch.object(tools_service_module, "AGENT_BUILTIN_MODULES", test_builtin_modules):
            app = create_app()
            verify_test_database(test_database_url)

            app.on_startup.clear()
            app.on_cleanup.clear()

            _record_test_timing("test_app_light", "setup", setup_timing_started)
            setup_timing_recorded = True
            try:
                yield app
            finally:
                teardown_timing_started = _test_timing_start()
    finally:
        if not setup_timing_recorded:
            _record_test_timing("test_app_light", "setup", setup_timing_started)
        _record_test_timing("test_app_light", "teardown", teardown_timing_started)


@pytest_asyncio.fixture
async def test_client(test_app):
    """aiohttp test client для HTTP запросов."""
    with _test_timing_span("test_client", "setup"):
        client = TestClient(TestServer(test_app))
        await client.start_server()
    try:
        yield client
    finally:
        with _test_timing_span("test_client", "teardown"):
            if not getattr(client, "_closed", False):
                for ws in list(getattr(client, "_websockets", ())):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    response = getattr(ws, "_response", None)
                    wait_for_close = getattr(response, "wait_for_close", None)
                    if callable(wait_for_close):
                        try:
                            await wait_for_close()
                        except Exception:
                            pass
                await client.close()


@pytest_asyncio.fixture
async def test_client_light(test_app_light):
    """aiohttp test client backed by test_app_light for HTTP/API tests."""
    with _test_timing_span("test_client_light", "setup"):
        client = TestClient(TestServer(test_app_light))
        await client.start_server()
    try:
        yield client
    finally:
        with _test_timing_span("test_client_light", "teardown"):
            if not getattr(client, "_closed", False):
                for ws in list(getattr(client, "_websockets", ())):
                    try:
                        await ws.close()
                    except Exception:
                        pass
                    response = getattr(ws, "_response", None)
                    wait_for_close = getattr(response, "wait_for_close", None)
                    if callable(wait_for_close):
                        try:
                            await wait_for_close()
                        except Exception:
                            pass
                await client.close()


@pytest_asyncio.fixture
async def test_agent(tmp_path, test_client):
    """Запускает WSAgent in-process с временным SQLite."""
    setup_timing_started = _test_timing_start()
    setup_timing_recorded = False
    import sys
    from pathlib import Path
    from unittest.mock import patch

    agent_db = tmp_path / "agent_test.db"
    test_modules_path = Path(__file__).parent / "test_modules"
    project_root = Path(__file__).resolve().parent.parent.parent
    pc_agent_dir = project_root / "pc_agent"
    server_dir = Path(__file__).resolve().parent.parent
    shadowed_modules = _snapshot_agent_shadowed_modules()

    server_path_str = str(server_dir)
    server_in_path = server_path_str in sys.path
    project_root_str = str(project_root)
    project_root_in_path = project_root_str in sys.path
    pc_agent_dir_str = str(pc_agent_dir)
    pc_agent_dir_in_path = pc_agent_dir_str in sys.path
    if server_in_path:
        sys.path.remove(server_path_str)

    import importlib

    _clear_agent_runtime_modules()

    try:
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)
        if pc_agent_dir_str not in sys.path:
            sys.path.insert(0, pc_agent_dir_str)

        sys.modules.pop("core", None)
        for mod_name in [name for name in list(sys.modules.keys()) if name.startswith("core.")]:
            sys.modules.pop(mod_name, None)
        core_namespace = types.ModuleType("core")
        core_namespace.__path__ = [str(pc_agent_dir / "core")]
        core_namespace.__package__ = "core"
        core_namespace.__spec__ = importlib.machinery.ModuleSpec("core", loader=None, is_package=True)
        sys.modules["core"] = core_namespace
        server_config_path = server_dir / "config.py"
        config_spec = importlib.util.spec_from_file_location("config", server_config_path)
        if config_spec and config_spec.loader:
            config_module = importlib.util.module_from_spec(config_spec)
            config_spec.loader.exec_module(config_module)
            sys.modules["config"] = config_module

        test_api_url = str(test_client.make_url("/api")).rstrip("/")
        test_ws_url = str(test_client.make_url("/ws")).replace("http://", "ws://", 1).replace("https://", "wss://", 1)

        import pc_agent.config.config_loader as config_loader_module

        config_loader_module.ConfigLoader._instance = None
        config_loader_module.ConfigLoader._config = None

        from auth.service import AuthService
        from ws_agent import WSAgent
        from pc_agent.config.config_loader import ConfigLoader, init_config

        original_load = ConfigLoader.load

        def patched_load(self, config_path, create_dirs=True):
            """Return config overridden for the in-process test agent."""
            config = original_load(self, config_path, create_dirs=create_dirs)
            config.paths.data_dir = str(tmp_path)
            config.enabled_modules = ["echo", "fail", "slow_echo"]
            if not hasattr(config, "modules"):
                from types import SimpleNamespace

                config.modules = SimpleNamespace()
            config.modules.extra_paths = [str(test_modules_path)]
            config.ui.port = 0
            config.server.ws_url = test_ws_url
            config.server.api_url = test_api_url
            return config

        with patch.dict(
            os.environ,
            {
                "PC_AGENT_WS_URL": test_ws_url,
                "PC_AGENT_API_URL": test_api_url,
                "PC_AGENT_UI_PORT": "0",
                "PC_AGENT_DATA_DIR": str(tmp_path),
            },
        ), patch.object(ConfigLoader, "load", patched_load):
            loader = ConfigLoader()
            if loader._config is None:
                init_config(tmp_path)
            cfg = loader._config
            if cfg is not None:
                cfg.server.ws_url = test_ws_url
                cfg.server.api_url = test_api_url
                cfg.paths.data_dir = str(tmp_path)
                cfg.enabled_modules = ["echo", "fail", "slow_echo"]
                if not hasattr(cfg, "modules"):
                    from types import SimpleNamespace

                    cfg.modules = SimpleNamespace()
                cfg.modules.extra_paths = [str(test_modules_path)]
                cfg.ui.port = 0

            if cfg is not None and not hasattr(cfg, "modules"):
                from types import SimpleNamespace

                cfg.modules = SimpleNamespace()
            if cfg is not None:
                cfg.modules.extra_paths = [str(test_modules_path)]

            from pc_agent.core.database import DatabaseManager

            DatabaseManager._instance = None

            agent = WSAgent(data_root=tmp_path)
            await agent.initialize()

            auth_service = AuthService(test_client.app["state"])
            agent_token = await auth_service.generate_agent_token(device_id=agent.device_id, expires_hours=24)
            os.environ["AUTH_TOKEN"] = agent_token

            if agent.db_manager:
                expected_db_path = Path(tmp_path) / "storage.db"
                if agent.db_manager._db_path != expected_db_path:
                    agent.db_manager._db_path = expected_db_path
                    agent.db_manager._initialized = False
                    await agent.db_manager.init_db()
                await agent.db_manager.save_auth_token(agent_token, agent.device_id)

            if hasattr(agent, "http") and agent.http:
                agent.http.base_url = test_api_url

            agent_task = asyncio.create_task(agent.run())

            from loguru import logger

            max_wait = 10
            waited = 0
            while waited < max_wait:
                if agent._agent_ws and not agent._agent_ws.closed:
                    logger.info(f"Agent connected to test server after {waited:.1f}s")
                    break
                await asyncio.sleep(0.5)
                waited += 0.5
            else:
                logger.warning(f"Agent did not connect within {max_wait}s, continuing test")

            _record_test_timing("test_agent", "setup", setup_timing_started)
            setup_timing_recorded = True
            try:
                yield agent
            finally:
                with _test_timing_span("test_agent", "teardown"):
                    close_agent_ws = getattr(agent, "_close_agent_ws", None)
                    if callable(close_agent_ws):
                        try:
                            await close_agent_ws(reason="test_fixture_shutdown", message=b"test_shutdown")
                            await asyncio.sleep(0)
                        except Exception:
                            pass

                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    await agent.cleanup()
                    _clear_agent_runtime_modules()
    finally:
        if not setup_timing_recorded:
            _record_test_timing("test_agent", "setup", setup_timing_started)
        _clear_agent_runtime_modules()
        _restore_module_snapshot(shadowed_modules)
        if not pc_agent_dir_in_path:
            while pc_agent_dir_str in sys.path:
                sys.path.remove(pc_agent_dir_str)
        if not project_root_in_path:
            while project_root_str in sys.path:
                sys.path.remove(project_root_str)
        if server_in_path and server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)
