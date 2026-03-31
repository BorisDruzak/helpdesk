"""
Pytest configuration and fixtures for Protocol V3 integration tests.
"""
import os
import sys
import pytest
import asyncio
import importlib
import types
from pathlib import Path
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from unittest.mock import patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from aiohttp.test_utils import TestClient, TestServer

# Add server directory to path
server_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(server_dir))

from server import create_app
from app.db.engine import get_engine, get_session, init_db
from tech.dismiss_store import clear_dismissed_alerts
from tech.log_buffer import clear_log_records

# Test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test"
)
TEST_UI_SUPPORT_TOKEN = "test-ui-support-token"
TEST_UI_ADMIN_TOKEN = "test-ui-admin-token"
TEST_UI_USER_PREFIX = "test-ui-user:"


def verify_test_database():
    """Проверка что БД == pc_support_test перед destructive операциями."""
    parsed = urlparse(TEST_DATABASE_URL)
    db_name = parsed.path.lstrip('/')
    if db_name != "pc_support_test":
        raise RuntimeError(
            f"TEST_DATABASE_URL must point to pc_support_test, got: {db_name}"
        )

@pytest.fixture(scope="session")
def run_migrations():
    """Применяет Alembic миграции один раз на сессию (sync fixture)."""
    verify_test_database()
    
    from alembic.config import Config
    from alembic import command
    
    # Вычисляем путь относительно файла conftest.py
    conftest_path = Path(__file__).resolve()
    server_dir = conftest_path.parents[1]  # server/tests -> server
    alembic_ini = server_dir / "alembic.ini"
    
    if not alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {alembic_ini}")
    
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    # Resolve script_location relative to server dir (alembic resolves relative to CWD otherwise)
    script_path = server_dir / "app" / "db" / "migrations"
    if script_path.exists():
        alembic_cfg.set_main_option("script_location", str(script_path))
    
    # Alembic env.py prefers DATABASE_URL from process environment.
    # create_app/server import can preload server/.env with the production URL,
    # so pin DATABASE_URL to the test DSN for the whole migration run.
    with patch.dict(os.environ, {"DATABASE_URL": TEST_DATABASE_URL}):
        command.upgrade(alembic_cfg, "head")


@pytest.fixture
def test_engine():
    """Создает тестовый engine для патчинга get_session."""
    verify_test_database()
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(autouse=True)
def ensure_db_ready(request):
    """Ensure migrations are applied before DB-backed tests run."""
    if request.node.get_closest_marker("no_db"):
        return

    verify_test_database()
    request.getfixturevalue("run_migrations")


@pytest.fixture(autouse=True)
async def cleanup_db(request, test_engine):
    """Clean test data before each DB-backed test."""
    if request.node.get_closest_marker("no_db"):
        return

    verify_test_database()
    clear_log_records()
    clear_dismissed_alerts()

    async with test_engine.begin() as conn:
        # Один statement TRUNCATE с RESTART IDENTITY CASCADE
        # RESTART IDENTITY критично - иначе автоинкремент id "уплывает"
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
    """Патчит app.db.get_session и app.db.engine.get_session для использования тестового engine."""
    session_maker = async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
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
    
    # Патчим оба пути импорта
    with patch('app.db.get_session', test_get_session), \
         patch('app.db.engine.get_session', test_get_session):
        yield


@pytest.fixture
async def test_app(patched_get_session, test_engine):
    """Создает aiohttp app через create_app() с патченным get_session."""
    from app.db.engine import init_db
    from websocket.device_outbox_sender import DeviceOutboxSender, recover_pending_commands
    from auth.context import AuthContext, AuthType
    from auth.service import AuthService
    from auth import middleware as auth_middleware_module

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
        # Legacy интеграционные тесты не передают токен; считаем их support-сценариями.
        return AuthContext(
            actor_id="support-test",
            actor_role="support",
            auth_type=AuthType.UI_TOKEN,
            token="implicit-test-auth",
        )
    
    with patch.object(AuthService, "verify_ui_token", fake_verify_ui_token), \
         patch.object(auth_middleware_module, "extract_auth_context", fake_extract_auth_context):
        app = create_app()
        # Инициализируем БД вручную для тестов
        await init_db(TEST_DATABASE_URL)

        # КРИТИЧНО: Запускаем DeviceOutboxSender вручную для тестов
        # (startup hooks очищаются, но sender нужен для доставки команд)
        state = app['state']

        # Recover pending commands
        await recover_pending_commands(state)

        # Start device outbox sender
        sender = DeviceOutboxSender(state, poll_interval=0.5)  # Более частый polling для тестов
        sender.start()
        app['outbox_sender'] = sender

        # Disable startup hooks that require real DB (уже инициализировали выше)
        app.on_startup.clear()
        app.on_cleanup.clear()

        # Но сохраняем cleanup для остановки sender
        async def test_cleanup(app):
            if 'outbox_sender' in app:
                app['outbox_sender'].stop()
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
    
    # Временный SQLite
    agent_db = tmp_path / "agent_test.db"
    
    # Путь к тестовым tools
    test_modules_path = Path(__file__).parent / "test_modules"
    
    # Add pc_agent to path (в начало, чтобы приоритет был у pc_agent)
    # Важно: удаляем server из пути, чтобы не было конфликта с server/modules
    project_root = Path(__file__).resolve().parent.parent.parent
    pc_agent_dir = project_root / "pc_agent"
    server_dir = Path(__file__).resolve().parent.parent
    
    # Временно удаляем server из пути и очищаем кэш модулей
    server_path_str = str(server_dir)
    server_in_path = server_path_str in sys.path
    if server_in_path:
        sys.path.remove(server_path_str)
    
    # Очищаем кэш модулей, чтобы избежать конфликтов
    import importlib
    # Очищаем все модули, которые могут конфликтовать
    modules_to_clear = [k for k in list(sys.modules.keys()) if k.startswith(('modules.', 'config.', 'pc_agent.')) or k in ('modules', 'config', 'pc_agent')]
    for mod_name in modules_to_clear:
        del sys.modules[mod_name]
    
    try:
        # Добавляем родительский каталог проекта в начало для абсолютных импортов pc_agent.*
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        # Также добавляем pc_agent_dir для относительных импортов
        if str(pc_agent_dir) not in sys.path:
            sys.path.insert(0, str(pc_agent_dir))

        # Алиасим top-level package `core` на `pc_agent/core`, иначе его затмевает `server/core`.
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
        
        # КРИТИЧНО: Получаем URL тестового сервера
        test_api_url = str(test_client.make_url("/api")).rstrip("/")
        test_ws_url = str(test_client.make_url("/ws")).replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        
        # КРИТИЧНО: Патчим config в модуле config_loader ДО импорта ws_agent
        # Это необходимо, потому что ws_agent импортирует config напрямую при импорте
        import pc_agent.config.config_loader as config_loader_module
        config_loader = config_loader_module.ConfigLoader()
        # Если config уже загружен, обновляем его
        if config_loader._config:
            config_loader._config.server.ws_url = test_ws_url
            config_loader._config.server.api_url = test_api_url
            config_loader._config.paths.data_dir = str(tmp_path)
            config_loader._config.enabled_modules = ["echo", "fail"]
            if not hasattr(config_loader._config, 'modules'):
                from types import SimpleNamespace
                config_loader._config.modules = SimpleNamespace()
            config_loader._config.modules.extra_paths = [str(test_modules_path)]
            config_loader._config.ui.port = 0
        
        # Создаем WSAgent с переопределенными путями
        from ws_agent import WSAgent
        from pc_agent.config.config_loader import ConfigLoader, init_config

        # Точечный патч config: загружаем реальный config и переопределяем поля
        original_load = ConfigLoader.load
        
        def patched_load(self, config_path, create_dirs=True):
            """Патч ConfigLoader.load() для возврата модифицированного config."""
            config = original_load(self, config_path, create_dirs=create_dirs)
            # Переопределяем только нужные поля
            config.paths.data_dir = str(tmp_path)
            # ВАЖНО: ModuleFactory добавляет префикс "test_" к имени модуля при загрузке из extra_paths
            # Поэтому указываем имена без префикса: "echo", "fail"
            config.enabled_modules = ["echo", "fail", "slow_echo"]  # тестовые tools
            if not hasattr(config, 'modules'):
                # Создаем объект modules если его нет
                from types import SimpleNamespace
                config.modules = SimpleNamespace()
            config.modules.extra_paths = [str(test_modules_path)]
            config.ui.port = 0  # Случайный порт для UiApiServer
            # Используем правильный URL тестового сервера
            config.server.ws_url = test_ws_url
            config.server.api_url = test_api_url
            return config
        
        with patch.object(ConfigLoader, 'load', patched_load):
            loader = ConfigLoader()
            if loader._config is None:
                init_config(tmp_path)
            cfg = loader._config
            if cfg is not None:
                cfg.server.ws_url = test_ws_url
                cfg.server.api_url = test_api_url
                cfg.paths.data_dir = str(tmp_path)
                cfg.enabled_modules = ["echo", "fail", "slow_echo"]
                if not hasattr(cfg, 'modules'):
                    from types import SimpleNamespace
                    cfg.modules = SimpleNamespace()
                cfg.modules.extra_paths = [str(test_modules_path)]
                cfg.ui.port = 0

            # КРИТИЧНО: Обновляем cached config перед созданием агента
            if cfg is not None and not hasattr(cfg, 'modules'):
                from types import SimpleNamespace
                cfg.modules = SimpleNamespace()
            if cfg is not None:
                cfg.modules.extra_paths = [str(test_modules_path)]
            
            # КРИТИЧНО: Сбрасываем singleton DatabaseManager перед созданием агента
            # чтобы использовать правильный путь к БД
            from pc_agent.core.database import DatabaseManager
            DatabaseManager._instance = None
            
            agent = WSAgent()
            
            # Инициализация (db_manager создается в initialize() с путем из config.paths.data_dir)
            await agent.initialize()
            
            # Проверяем, что БД создана по правильному пути
            if agent.db_manager:
                expected_db_path = Path(tmp_path) / "storage.db"
                if agent.db_manager._db_path != expected_db_path:
                    # Если путь не совпадает, переинициализируем
                    agent.db_manager._db_path = expected_db_path
                    agent.db_manager._initialized = False
                    await agent.db_manager.init_db()
            
            # Также обновляем HTTP клиент если он уже создан
            if hasattr(agent, 'http') and agent.http:
                agent.http.base_url = test_api_url

            # Запуск в фоне
            agent_task = asyncio.create_task(agent.run())
            
            # Ждем подключения агента к серверу (до 10 секунд)
            from loguru import logger
            max_wait = 10
            waited = 0
            while waited < max_wait:
                if agent._agent_ws and not agent._agent_ws.closed:
                    logger.info(f"✅ Агент подключен к серверу после {waited:.1f}s")
                    break
                await asyncio.sleep(0.5)
                waited += 0.5
            else:
                logger.warning(f"⚠️ Агент не подключился за {max_wait}s, продолжаем тест")
            
            yield agent
            
            # Cleanup
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                pass
            await agent.cleanup()
    finally:
        # Восстанавливаем server в пути
        if server_in_path and server_path_str not in sys.path:
            sys.path.insert(0, server_path_str)
