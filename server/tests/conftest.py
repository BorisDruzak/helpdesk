"""Pytest configuration and fixtures for Protocol V3 integration tests."""

import asyncio
import importlib
import os
import re
import sys
import types
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import text
from sqlalchemy.engine import make_url
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

DEFAULT_SHARED_TEST_DATABASE_URL = (
    "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test"
)
DEFAULT_TEST_DATABASE_ADMIN_URL = (
    "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/postgres"
)
TEST_DATABASE_PREFIX = "pc_support_test_"
SHARED_TEST_DATABASE_NAME = "pc_support_test"

TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"
TEST_UI_USER_PREFIX = "test-ui-user:"


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
        shared_url = explicit_test_url or DEFAULT_SHARED_TEST_DATABASE_URL
        verify_test_database(shared_url, allow_shared=True)
        return shared_url, _resolve_admin_url(shared_url), True

    if explicit_test_url:
        verify_test_database(explicit_test_url, allow_shared=False)
        return explicit_test_url, _resolve_admin_url(explicit_test_url), False

    admin_url = os.getenv("TEST_DATABASE_ADMIN_URL", DEFAULT_TEST_DATABASE_ADMIN_URL)
    generated_name = f"{TEST_DATABASE_PREFIX}{uuid.uuid4().hex[:10]}"
    test_url = _render_url(make_url(admin_url).set(database=generated_name))
    return test_url, admin_url, False


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


@pytest.fixture(scope="session")
def test_database_url() -> str:
    test_db_url, admin_db_url, is_shared = _resolve_test_database_urls()
    verify_test_database(test_db_url, allow_shared=is_shared)
    original_test_url = os.environ.get("TEST_DATABASE_URL")
    original_admin_url = os.environ.get("TEST_DATABASE_ADMIN_URL")
    os.environ["TEST_DATABASE_URL"] = test_db_url
    os.environ["TEST_DATABASE_ADMIN_URL"] = admin_db_url

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

    with patch.dict(os.environ, {"DATABASE_URL": test_database_url}):
        command.upgrade(alembic_cfg, "head")


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


@pytest.fixture(autouse=True)
async def cleanup_db(request):
    """Clean test data before each DB-backed test."""
    if request.node.get_closest_marker("no_db"):
        return

    test_database_url = request.getfixturevalue("test_database_url")
    test_engine = request.getfixturevalue("test_engine")
    verify_test_database(test_database_url)
    clear_log_records()
    clear_dismissed_alerts()

    async with test_engine.begin() as conn:
        await conn.execute(text("""
            TRUNCATE TABLE
                operations,
                device_outbox,
                ticket_events,
                device_events,
                device_toolset_snapshots,
                device_config,
                dispatch_ready_devices,
                devices,
                agent_tokens,
                connection_requests,
                agent_runtime_audit,
                ui_user_audit,
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
                ui_users,
                tickets
            RESTART IDENTITY CASCADE
        """))


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


@pytest.fixture
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
        sender.start()
        bind_app_value(app, key=OUTBOX_SENDER_APP_KEY, legacy_name="outbox_sender", value=sender)

        app.on_startup.clear()
        app.on_cleanup.clear()

        async def test_cleanup(app):
            if "outbox_sender" in app:
                app["outbox_sender"].stop()

        app.on_cleanup.append(test_cleanup)
        yield app


@pytest.fixture
async def test_client(test_app):
    """aiohttp test client для HTTP запросов."""
    async with TestClient(TestServer(test_app)) as client:
        yield client


@pytest.fixture
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
