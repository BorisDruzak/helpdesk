"""Pytest configuration and fixtures for Protocol V3 integration tests."""

import asyncio
import faulthandler
import importlib
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
from contextlib import asynccontextmanager
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

from server import create_app
from app_keys import OUTBOX_SENDER_APP_KEY, bind_app_value
from app.db import engine as db_engine_module
from tech.dismiss_store import clear_dismissed_alerts
from tech.log_buffer import clear_log_records

TEST_DATABASE_PREFIX = "pc_support_test_"
SHARED_TEST_DATABASE_NAME = "pc_support_test"
WINDOWS_TEST_DB_TUNNEL_PORT = int(os.getenv("PC_CLIENT_TEST_DB_TUNNEL_PORT", "55432"))
WINDOWS_TEST_DB_TUNNEL_HOST = os.getenv("PC_CLIENT_TEST_DB_TUNNEL_HOST", "127.0.0.1")
WINDOWS_TEST_DB_SSH_TARGET = os.getenv("PC_CLIENT_TEST_DB_SSH_TARGET", "altserver@192.168.100.17")
WINDOWS_TEST_DB_REMOTE_BIND = os.getenv("PC_CLIENT_TEST_DB_REMOTE_BIND", "127.0.0.1:5432")
WINDOWS_TEST_DB_SSH_KEY = os.getenv(
    "PC_CLIENT_TEST_DB_SSH_KEY",
    r"C:\Users\admin-2\.ssh\pc_client_altserver_ed25519",
)

TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"
TEST_UI_AUDITOR_TOKEN = "test-ui-auditor-token"
TEST_UI_USER_PREFIX = "test-ui-user:"

_WINDOWS_TEST_DB_TUNNEL_PROCESS = None
_WINDOWS_TEST_DB_TUNNEL_OWNED = False
_SHARED_TEST_DB_TERMINATE_UNAVAILABLE = False
_AGENT_WS_FIXTURES = {"test_agent"}


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


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        _apply_ci_layer_markers(item)


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


def _resolve_test_database_urls() -> tuple[str, str, bool]:
    explicit_test_url = os.getenv("TEST_DATABASE_URL")
    if _shared_test_db_allowed():
        shared_url = explicit_test_url or _default_test_database_url(SHARED_TEST_DATABASE_NAME)
        verify_test_database(shared_url, allow_shared=True)
        return shared_url, _resolve_admin_url(shared_url), True

    if (
        os.name == "nt"
        and explicit_test_url is None
        and os.getenv("TEST_DATABASE_ADMIN_URL") is None
    ):
        shared_url = _default_windows_shared_test_database_url()
        verify_test_database(shared_url, allow_shared=True)
        return shared_url, _resolve_admin_url(shared_url), True

    if explicit_test_url:
        verify_test_database(explicit_test_url, allow_shared=False)
        return explicit_test_url, _resolve_admin_url(explicit_test_url), False

    admin_url = os.getenv("TEST_DATABASE_ADMIN_URL", _default_test_database_url("postgres"))
    generated_name = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex[:10]}"
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
    asyncio.run(_probe_database(database_url))


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
            f"test DB {SHARED_TEST_DATABASE_NAME}. Set TEST_DATABASE_ADMIN_URL for isolated "
            "ephemeral DB runs.",
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
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _drop_test_database(admin_database_url: str, db_name: str) -> None:
    _validate_test_database_name(db_name)
    await _run_admin_sql(
        admin_database_url,
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = :db_name
          AND pid <> pg_backend_pid()
        """,
        db_name=db_name,
    )
    await _run_admin_sql(admin_database_url, f'DROP DATABASE IF EXISTS "{db_name}"')


async def _create_test_database(admin_database_url: str, db_name: str) -> None:
    _validate_test_database_name(db_name)
    await _run_admin_sql(admin_database_url, f'CREATE DATABASE "{db_name}"')


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
    verify_test_database(test_db_url, allow_shared=is_shared)
    original_test_url = os.environ.get("TEST_DATABASE_URL")
    original_admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    original_allow_shared = os.environ.get("PC_CLIENT_ALLOW_SHARED_TEST_DB")
    os.environ["TEST_DATABASE_URL"] = test_db_url
    os.environ["TEST_DATABASE_ADMIN_URL"] = admin_db_url
    if is_shared:
        os.environ["PC_CLIENT_ALLOW_SHARED_TEST_DB"] = "1"

    db_name = make_url(test_db_url).database or ""
    if not is_shared:
        asyncio.run(_drop_test_database(admin_db_url, db_name))
        asyncio.run(_create_test_database(admin_db_url, db_name))

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
        _close_windows_test_db_tunnel()
        if not is_shared:
            asyncio.run(_drop_test_database(admin_db_url, db_name))


@pytest.fixture(scope="session")
def run_migrations(test_database_url: str):
    """Apply Alembic migrations once per pytest session."""
    verify_test_database(test_database_url)

    from alembic import command
    from alembic.config import Config

    conftest_path = Path(__file__).resolve()
    server_root = conftest_path.parents[1]
    alembic_ini = server_root / "alembic.ini"

    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")

    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", test_database_url)
    script_path = server_root / "app" / "db" / "migrations"
    if script_path.exists():
        alembic_cfg.set_main_option("script_location", str(script_path))

    if os.name == "nt" and make_url(test_database_url).database == SHARED_TEST_DATABASE_NAME:
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


async def _cleanup_db_async(test_database_url: str, test_database_admin_url: str, test_engine) -> None:
    verify_test_database(test_database_url)
    clear_log_records()
    clear_dismissed_alerts()

    if _is_shared_test_database_url(test_database_url):
        await _terminate_other_test_database_backends(test_database_admin_url, test_database_url)

    async with test_engine.begin() as conn:
        await conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        await conn.execute(text("""
            TRUNCATE TABLE
                observer_error_occurrences,
                observer_error_signatures,
                observer_span_links,
                observer_spans,
                observer_traces,
                agent_observer_events,
                diagnostic_provider_audit,
                diagnostic_provider_credential_refs,
                diagnostic_provider_configs,
                diagnostic_capability_versions,
                diagnostic_capabilities,
                diagnostic_providers,
                diagnostic_bundles,
                diagnostic_findings,
                diagnostic_evidence,
                diagnostic_steps,
                diagnostic_sessions,
                remote_access_events,
                remote_access_sessions,
                artifacts,
                operations,
                device_outbox,
                ticket_events,
                device_events,
                device_toolset_snapshots,
                device_desired_modules,
                device_modules,
                device_config,
                registry_assets,
                registry_people,
                registry_services,
                registry_vendors,
                registry_locations,
                registry_departments,
                dispatch_ready_devices,
                devices,
                agent_tokens,
                connection_requests,
                agent_build_download_audit,
                agent_builds,
                agent_runtime_audit,
                server_config,
                ui_user_audit,
                access_audit,
                access_group_queue_members,
                access_group_permissions,
                access_group_members,
                access_groups,
                ticket_admin_audit,
                ticket_queue_ola_targets,
                ticket_queue_members,
                ticket_routing_rules,
                ticket_priority_matrix,
                ticket_sla_targets,
                ticket_sla_policies,
                ticket_business_calendars,
                ticket_resolution_codes,
                ticket_queues,
                playbook_step_run,
                playbook_step,
                playbook_run,
                playbook_version,
                playbook,
                ui_users,
                modules,
                tickets
            RESTART IDENTITY CASCADE
        """))


@pytest.fixture(autouse=True)
def cleanup_db(request):
    """Clean test data before each DB-backed test."""
    if request.node.get_closest_marker("no_db"):
        return
    test_database_url = request.getfixturevalue("test_database_url")
    test_database_admin_url = request.getfixturevalue("test_database_admin_url")
    test_engine = request.getfixturevalue("test_engine")
    asyncio.run(_cleanup_db_async(test_database_url, test_database_admin_url, test_engine))


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
        return AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="implicit-test-auth",
        )

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
        yield app


@pytest_asyncio.fixture
async def test_client(test_app):
    """aiohttp test client для HTTP запросов."""
    client = TestClient(TestServer(test_app))
    await client.start_server()
    try:
        yield client
    finally:
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
    import sys
    from pathlib import Path
    from unittest.mock import patch

    agent_db = tmp_path / "agent_test.db"
    test_modules_path = Path(__file__).parent / "test_modules"
    project_root = Path(__file__).resolve().parent.parent.parent
    pc_agent_dir = project_root / "pc_agent"
    server_dir = Path(__file__).resolve().parent.parent

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

            yield agent

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
        _clear_agent_runtime_modules()
        if not pc_agent_dir_in_path:
            while pc_agent_dir_str in sys.path:
                sys.path.remove(pc_agent_dir_str)
        if not project_root_in_path:
            while project_root_str in sys.path:
                sys.path.remove(project_root_str)
        if server_in_path and server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)
