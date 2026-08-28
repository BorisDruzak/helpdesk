import asyncio
import importlib.util
import inspect
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.registry_retirement_manifest import RETIRED_KNOWLEDGE_AI_TABLES


def _load_test_harness():
    path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("server_test_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


test_harness = _load_test_harness()


pytestmark = pytest.mark.no_db


@pytest.mark.asyncio
async def test_admin_sql_sets_bounded_timeouts_before_running_statement(monkeypatch):
    statements = []

    class FakeConnection:
        async def execute(self, statement, params=None):
            statements.append((str(statement), params))

    class FakeConnectionContext:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, *_args):
            return None

    class FakeEngine:
        def connect(self):
            return FakeConnectionContext()

        async def dispose(self):
            return None

    monkeypatch.setattr(test_harness, "create_async_engine", lambda *_args, **_kwargs: FakeEngine())

    await test_harness._run_admin_sql("postgresql+asyncpg://example/postgres", "DROP DATABASE test_db")

    assert statements == [
        ("SET lock_timeout = '5s'", None),
        ("SET statement_timeout = '30s'", None),
        ("DROP DATABASE test_db", {}),
    ]


@pytest.mark.asyncio
async def test_drop_test_database_reports_each_blocking_admin_phase(monkeypatch, capsys):
    run_admin_sql = AsyncMock()
    monkeypatch.setattr(test_harness, "_run_admin_sql", run_admin_sql)

    await test_harness._drop_test_database(
        "postgresql+asyncpg://example/postgres",
        "pc_support_test_unit",
    )

    stderr = capsys.readouterr().err
    assert "terminate stale connections" in stderr
    assert "drop database" in stderr


@pytest.mark.asyncio
async def test_admin_sql_times_out_while_opening_a_stalled_connection(monkeypatch):
    class SlowConnectionContext:
        async def __aenter__(self):
            await asyncio.sleep(0.01)
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, *_args, **_kwargs):
            return None

    class FakeEngine:
        def connect(self):
            return SlowConnectionContext()

        async def dispose(self):
            return None

    monkeypatch.setattr(test_harness, "create_async_engine", lambda *_args, **_kwargs: FakeEngine())
    monkeypatch.setattr(test_harness, "TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS", 0.001, raising=False)

    with pytest.raises(TimeoutError, match="test DB admin operation"):
        await test_harness._run_admin_sql("postgresql+asyncpg://example/postgres", "DROP DATABASE test_db")


@pytest.mark.asyncio
async def test_admin_sql_times_out_while_disposing_a_stalled_engine(monkeypatch):
    class FakeConnection:
        async def execute(self, *_args, **_kwargs):
            return None

    class FakeConnectionContext:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, *_args):
            return None

    class SlowDisposeEngine:
        def connect(self):
            return FakeConnectionContext()

        async def dispose(self):
            await asyncio.sleep(0.01)

    monkeypatch.setattr(test_harness, "create_async_engine", lambda *_args, **_kwargs: SlowDisposeEngine())
    monkeypatch.setattr(test_harness, "TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS", 0.001, raising=False)

    with pytest.raises(TimeoutError, match="test DB engine disposal"):
        await test_harness._run_admin_sql("postgresql+asyncpg://example/postgres", "DROP DATABASE test_db")


@pytest.mark.asyncio
async def test_admin_sql_preserves_operation_error_when_disposal_times_out(monkeypatch, capsys):
    class SlowConnectionContext:
        async def __aenter__(self):
            await asyncio.sleep(0.01)
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, *_args, **_kwargs):
            return None

    class SlowDisposeEngine:
        def connect(self):
            return SlowConnectionContext()

        async def dispose(self):
            await asyncio.sleep(0.01)

    monkeypatch.setattr(test_harness, "create_async_engine", lambda *_args, **_kwargs: SlowDisposeEngine())
    monkeypatch.setattr(test_harness, "TEST_DB_ADMIN_OPERATION_TIMEOUT_SECONDS", 0.001, raising=False)

    with pytest.raises(TimeoutError, match="test DB admin operation"):
        await test_harness._run_admin_sql("postgresql+asyncpg://example/postgres", "DROP DATABASE test_db")

    assert "preserving the prior admin-operation error" in capsys.readouterr().err


class _FakeNode:
    def __init__(self, *markers):
        self._markers = list(markers)

    def get_closest_marker(self, name):
        for marker_name, marker in reversed(self._markers):
            if marker_name == name:
                return marker
        return None

    def iter_markers(self, name=None):
        return [marker for marker_name, marker in self._markers if name is None or marker_name == name]


def _marker(*args):
    return SimpleNamespace(args=args, kwargs={})


class _FakeApp(dict):
    def __init__(self):
        super().__init__()
        self._state = self
        self["state"] = SimpleNamespace(name="test-state")
        self.on_startup = [object()]
        self.on_cleanup = [object()]


def _patch_fake_app_runtime(monkeypatch, *, fail_outbox: bool = False):
    events = []

    async def fake_recover_pending_commands(state):
        if fail_outbox:
            raise AssertionError("light app must not recover pending commands")
        events.append(("recover", state))

    class FakeSender:
        def __init__(self, state, *, poll_interval):
            if fail_outbox:
                raise AssertionError("light app must not construct DeviceOutboxSender")
            events.append(("sender_init", state, poll_interval))
            self.stopped = False

        async def start_async(self):
            events.append(("sender_start",))

        async def stop_async(self):
            self.stopped = True
            events.append(("sender_stop",))

    import websocket.device_outbox_sender as device_outbox_sender

    monkeypatch.setattr(test_harness, "create_app", _FakeApp)
    monkeypatch.setattr(test_harness, "verify_test_database", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(device_outbox_sender, "recover_pending_commands", fake_recover_pending_commands)
    monkeypatch.setattr(device_outbox_sender, "DeviceOutboxSender", FakeSender)
    return events


async def _yield_fixture_once(fixture_func):
    fixture = fixture_func(None, object(), "postgresql+asyncpg://example/test")
    app = await fixture.__anext__()
    with pytest.raises(StopAsyncIteration):
        await fixture.__anext__()
    return app


def test_auto_fallback_to_shared_db_when_admin_db_unavailable(monkeypatch):
    probed = []

    def fake_probe(url: str) -> None:
        probed.append(url)
        if url.endswith("/postgres"):
            raise ConnectionRefusedError("refused")

    monkeypatch.setattr(test_harness, "_probe_database_sync", fake_probe)
    monkeypatch.setattr(
        test_harness,
        "_default_test_database_url",
        lambda db_name: f"postgresql+asyncpg://chatbot:chatbot@example.test:5432/{db_name}",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        test_db_url, admin_db_url, is_shared = test_harness._maybe_fallback_to_shared_test_db(
            "postgresql+asyncpg://chatbot:chatbot@example.test:5432/pc_support_test_deadbeef",
            "postgresql+asyncpg://chatbot:chatbot@example.test:5432/postgres",
            False,
            allow_auto_shared_fallback=True,
        )

    assert is_shared is True
    assert test_db_url.endswith("/pc_support_test")
    assert admin_db_url.endswith("/postgres")
    assert any("falling back to shared test DB" in str(item.message) for item in caught)
    assert any("not valid for full DB/API gate" in str(item.message) for item in caught)
    assert probed == [
        "postgresql+asyncpg://chatbot:chatbot@example.test:5432/postgres",
        "postgresql+asyncpg://chatbot:chatbot@example.test:5432/pc_support_test",
    ]


@pytest.mark.asyncio
async def test_test_app_light_skips_outbox_runtime(monkeypatch):
    events = _patch_fake_app_runtime(monkeypatch, fail_outbox=True)

    app = await _yield_fixture_once(test_harness.test_app_light.__wrapped__)

    assert events == []
    assert "outbox_sender" not in app
    assert app.on_startup == []
    assert app.on_cleanup == []


@pytest.mark.asyncio
async def test_regular_test_app_still_starts_outbox_runtime(monkeypatch):
    events = _patch_fake_app_runtime(monkeypatch)

    fixture = test_harness.test_app.__wrapped__(None, object(), "postgresql+asyncpg://example/test")
    app = await fixture.__anext__()

    assert [event[0] for event in events] == ["recover", "sender_init", "sender_start"]
    assert app["outbox_sender"] is not None
    assert len(app.on_cleanup) == 1

    await app.on_cleanup[0](app)
    with pytest.raises(StopAsyncIteration):
        await fixture.__anext__()
    assert events[-1] == ("sender_stop",)


def test_test_client_light_depends_on_test_app_light():
    signature = inspect.signature(test_harness.test_client_light.__wrapped__)

    assert list(signature.parameters) == ["test_app_light"]


@pytest.mark.asyncio
async def test_test_app_light_timing_uses_distinct_fixture_name(monkeypatch):
    _patch_fake_app_runtime(monkeypatch, fail_outbox=True)
    records = []
    monkeypatch.setattr(test_harness, "_test_timing_start", lambda: 1.0)
    monkeypatch.setattr(
        test_harness,
        "_record_test_timing",
        lambda fixture, phase, started_at, **_kwargs: records.append((fixture, phase, started_at)),
    )

    await _yield_fixture_once(test_harness.test_app_light.__wrapped__)

    assert ("test_app_light", "setup", 1.0) in records
    assert ("test_app_light", "teardown", 1.0) in records
    assert all(record[0] != "test_app" for record in records)


def test_auto_fallback_is_not_used_when_disabled(monkeypatch):
    called = []

    def fake_probe(url: str) -> None:
        called.append(url)

    monkeypatch.setattr(test_harness, "_probe_database_sync", fake_probe)

    test_db_url, admin_db_url, is_shared = test_harness._maybe_fallback_to_shared_test_db(
        "postgresql+asyncpg://chatbot:chatbot@example.test:5432/pc_support_test_deadbeef",
        "postgresql+asyncpg://chatbot:chatbot@example.test:5432/postgres",
        False,
        allow_auto_shared_fallback=False,
    )

    assert test_db_url.endswith("/pc_support_test_deadbeef")
    assert admin_db_url.endswith("/postgres")
    assert is_shared is False
    assert called == []


def test_should_auto_fallback_only_for_default_windows_flow(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.delenv("PC_CLIENT_ALLOW_SHARED_TEST_DB", raising=False)
    monkeypatch.setattr(test_harness.os, "name", "nt", raising=False)

    assert test_harness._should_auto_fallback_to_shared_test_db() is True

    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://example/test")
    assert test_harness._should_auto_fallback_to_shared_test_db() is False


def test_windows_default_resolve_uses_isolated_test_db(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.delenv("PC_CLIENT_ALLOW_SHARED_TEST_DB", raising=False)
    monkeypatch.setattr(test_harness.os, "name", "nt", raising=False)
    monkeypatch.setattr(test_harness, "_ensure_windows_test_db_tunnel", lambda: None)
    monkeypatch.setattr(test_harness, "WINDOWS_TEST_DB_TUNNEL_HOST", "127.0.0.1")
    monkeypatch.setattr(test_harness, "WINDOWS_TEST_DB_TUNNEL_PORT", 55432)

    test_db_url, admin_db_url, is_shared = test_harness._resolve_test_database_urls()

    assert is_shared is False
    assert "/pc_support_test_nt_" in test_db_url or "/pc_support_test_server_" in test_db_url
    assert admin_db_url.endswith("/postgres")
    assert "127.0.0.1:55432" in test_db_url
    assert "127.0.0.1:55432" in admin_db_url


def test_windows_shared_debug_resolve_uses_tunnel(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.setenv("PC_CLIENT_ALLOW_SHARED_TEST_DB", "1")
    monkeypatch.setattr(test_harness.os, "name", "nt", raising=False)
    monkeypatch.setattr(test_harness, "_ensure_windows_test_db_tunnel", lambda: None)
    monkeypatch.setattr(test_harness, "WINDOWS_TEST_DB_TUNNEL_HOST", "127.0.0.1")
    monkeypatch.setattr(test_harness, "WINDOWS_TEST_DB_TUNNEL_PORT", 55432)

    test_db_url, admin_db_url, is_shared = test_harness._resolve_test_database_urls()

    assert is_shared is True
    assert test_db_url.endswith("/pc_support_test")
    assert admin_db_url.endswith("/postgres")
    assert "127.0.0.1:55432" in test_db_url
    assert "127.0.0.1:55432" in admin_db_url


def test_generated_test_database_name_includes_domain_worker_and_hash(monkeypatch):
    monkeypatch.setenv("PC_CLIENT_TEST_DB_DOMAIN", "knowledge")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_RUN_ID", "abcdef123456")
    monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")

    db_name = test_harness._generated_test_database_name()

    assert db_name.startswith("pc_support_test_knowledge_gw3_")
    assert len(db_name.rsplit("_", 1)[-1]) == 6


def test_keep_test_database_env_flag(monkeypatch):
    monkeypatch.delenv("PC_CLIENT_KEEP_TEST_DB", raising=False)
    assert test_harness._keep_test_database() is False

    monkeypatch.setenv("PC_CLIENT_KEEP_TEST_DB", "1")
    assert test_harness._keep_test_database() is True


def test_test_database_url_teardown_drops_database_before_closing_tunnel(monkeypatch):
    test_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_unit"
    admin_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres"
    events = []

    def fake_run_async_blocking(func, *args):
        events.append((func.__name__, args))

    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_ADMIN_URL", raising=False)
    monkeypatch.delenv("PC_CLIENT_ALLOW_SHARED_TEST_DB", raising=False)
    monkeypatch.delenv(test_harness.TEST_DB_TEMPLATE_CLONED_FROM_ENV, raising=False)
    monkeypatch.delenv(test_harness.TEST_DB_TEMPLATE_FINGERPRINT_ENV, raising=False)
    monkeypatch.setattr(test_harness, "_resolve_test_database_urls", lambda: (test_db_url, admin_db_url, False))
    monkeypatch.setattr(
        test_harness,
        "_maybe_fallback_to_shared_test_db",
        lambda test_url, admin_url, is_shared, *, allow_auto_shared_fallback: (test_url, admin_url, is_shared),
    )
    monkeypatch.setattr(test_harness, "_should_auto_fallback_to_shared_test_db", lambda: False)
    monkeypatch.setattr(test_harness, "verify_test_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(test_harness, "_test_db_template_enabled", lambda: False)
    monkeypatch.setattr(test_harness, "_keep_test_database", lambda: False)
    monkeypatch.setattr(test_harness, "_run_async_blocking", fake_run_async_blocking)
    monkeypatch.setattr(test_harness, "_close_windows_test_db_tunnel", lambda: events.append(("close_tunnel", ())))

    fixture = test_harness.test_database_url.__wrapped__()
    assert next(fixture) == test_db_url
    with pytest.raises(StopIteration):
        next(fixture)

    assert events == [
        ("_drop_test_database", (admin_db_url, "pc_support_test_unit")),
        ("_create_test_database", (admin_db_url, "pc_support_test_unit")),
        ("_drop_test_database", (admin_db_url, "pc_support_test_unit")),
        ("close_tunnel", ()),
    ]


def test_migration_clone_fixture_privately_provisions_and_drops_a_blank_database(monkeypatch):
    test_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_clone_unit"
    admin_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres"
    events = []

    def fake_run_async_blocking(func, *args):
        events.append((func.__name__, args))

    request = SimpleNamespace(node=_FakeNode(("migration_clone", _marker())))
    monkeypatch.setattr(test_harness, "_resolve_test_database_urls", lambda: (test_db_url, admin_db_url, False))
    monkeypatch.setattr(test_harness, "verify_test_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(test_harness, "_keep_test_database", lambda: False)
    monkeypatch.setattr(test_harness, "_run_async_blocking", fake_run_async_blocking)
    monkeypatch.setattr(test_harness, "_close_windows_test_db_tunnel", lambda: events.append(("close_tunnel", ())))

    fixture = test_harness.migration_clone_database_url.__wrapped__(request)
    assert next(fixture) == test_db_url
    with pytest.raises(StopIteration):
        next(fixture)

    assert events == [
        ("_drop_test_database", (admin_db_url, "pc_support_test_clone_unit")),
        ("_create_test_database", (admin_db_url, "pc_support_test_clone_unit")),
        ("_drop_test_database", (admin_db_url, "pc_support_test_clone_unit")),
        ("close_tunnel", ()),
    ]


@pytest.mark.parametrize("failing_operation", ("_drop_test_database", "_create_test_database"))
def test_migration_clone_fixture_cleans_up_private_database_and_tunnel_after_provisioning_failure(
    monkeypatch,
    failing_operation,
):
    """A provisioning error must not leak the clone database or an owned tunnel."""

    test_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_clone_unit"
    admin_db_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres"
    events = []

    def fake_run_async_blocking(func, *args):
        events.append((func.__name__, args))
        if func.__name__ == failing_operation and sum(name == failing_operation for name, _ in events) == 1:
            raise RuntimeError("provisioning failed")

    request = SimpleNamespace(node=_FakeNode(("migration_clone", _marker())))
    monkeypatch.setattr(test_harness, "_resolve_test_database_urls", lambda: (test_db_url, admin_db_url, False))
    monkeypatch.setattr(test_harness, "verify_test_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(test_harness, "_keep_test_database", lambda: False)
    monkeypatch.setattr(test_harness, "_run_async_blocking", fake_run_async_blocking)
    monkeypatch.setattr(test_harness, "_close_windows_test_db_tunnel", lambda: events.append(("close_tunnel", ())))

    fixture = test_harness.migration_clone_database_url.__wrapped__(request)
    with pytest.raises(RuntimeError, match="provisioning failed"):
        next(fixture)

    database_events = [event for event in events if event[0] != "close_tunnel"]
    assert all(args == (admin_db_url, "pc_support_test_clone_unit") for _, args in database_events)
    assert events[-1] == ("close_tunnel", ())
    assert database_events[-1] == ("_drop_test_database", (admin_db_url, "pc_support_test_clone_unit"))


def test_migration_clone_fixture_rejects_unmarked_test():
    request = SimpleNamespace(node=_FakeNode())

    with pytest.raises(RuntimeError, match="requires @pytest.mark.migration_clone"):
        next(test_harness.migration_clone_database_url.__wrapped__(request))


def test_pytest_configure_registers_migration_clone_marker():
    registered = []
    config = SimpleNamespace(addinivalue_line=lambda section, value: registered.append((section, value)))

    test_harness.pytest_configure(config)

    assert ("markers", "migration_clone: DB test owns a private blank Alembic lifecycle") in registered


def test_windows_isolated_alembic_upgrade_uses_subprocess(monkeypatch):
    calls = []

    monkeypatch.setattr(test_harness.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        test_harness.subprocess,
        "run",
        lambda command, **kwargs: calls.append((command, kwargs)),
    )
    monkeypatch.setattr(
        "alembic.command.upgrade",
        lambda *_args, **_kwargs: pytest.fail("Windows must not run isolated async Alembic in-process"),
    )

    test_harness._run_alembic_upgrade(
        "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_unit"
    )

    assert calls
    command, kwargs = calls[0]
    assert command[-2:] == ["upgrade", "head"]
    assert kwargs["check"] is True
    assert kwargs["env"]["DATABASE_URL"].endswith("/pc_support_test_unit")


def test_cleanup_profile_defaults_to_full_without_marker():
    assert test_harness._resolve_cleanup_profile(_FakeNode()) == "full"


def test_cleanup_profile_uses_explicit_marker():
    node = _FakeNode(("db_cleanup", _marker("tickets")))

    assert test_harness._resolve_cleanup_profile(node) == "tickets"


def test_cleanup_profile_returns_none_for_no_db_marker():
    node = _FakeNode(("no_db", _marker()))

    assert test_harness._resolve_cleanup_profile(node) is None


def test_cleanup_profile_rejects_unknown_profile():
    node = _FakeNode(("db_cleanup", _marker("unknown")))

    with pytest.raises(RuntimeError, match="Unknown db_cleanup profile"):
        test_harness._resolve_cleanup_profile(node)


def test_cleanup_profile_rejects_multiple_markers():
    node = _FakeNode(("db_cleanup", _marker("tickets")), ("db_cleanup", _marker("knowledge")))

    with pytest.raises(RuntimeError, match="Multiple db_cleanup markers"):
        test_harness._resolve_cleanup_profile(node)


def test_cleanup_profile_rejects_marker_without_single_string_argument():
    node = _FakeNode(("db_cleanup", _marker()))

    with pytest.raises(RuntimeError, match="requires exactly one profile"):
        test_harness._resolve_cleanup_profile(node)


def test_cleanup_profile_tables_use_safe_identifiers():
    for profile, tables in test_harness.CLEANUP_TABLES_BY_PROFILE.items():
        assert tables, profile
        for table in tables:
            test_harness._validate_cleanup_table_name(table)


def test_web_api_cleanup_profiles_are_bounded_subsets():
    full_tables = set(test_harness.CLEANUP_TABLES_BY_PROFILE["full"])
    registration_tables = set(test_harness.CLEANUP_TABLES_BY_PROFILE["registration"])
    web_support_tables = set(test_harness.CLEANUP_TABLES_BY_PROFILE["web_support"])

    assert registration_tables < full_tables
    assert web_support_tables < full_tables
    assert {"devices", "registry_people", "registry_departments", "registry_locations", "ui_users"} <= registration_tables
    assert {"tickets", "ticket_events", "operations", "device_outbox", "artifacts", "agent_builds"} <= web_support_tables
    assert {"observer_traces", "observer_spans", "playbook", "playbook_run"} <= web_support_tables


def test_cleanup_profiles_reject_the_retired_knowledge_schema():
    with pytest.raises(RuntimeError, match="Unknown db_cleanup profile 'knowledge'"):
        test_harness._cleanup_truncate_sql("knowledge")


def test_agent_runtime_cleanup_profile_covers_shared_runtime_catalogs():
    tables = set(test_harness.CLEANUP_TABLES_BY_PROFILE["agent_runtime"])

    assert {
        "diagnostic_providers",
        "diagnostic_capabilities",
        "tool_presentation_overrides",
        "agent_recipe_versions",
        "device_inventory_snapshots",
        "device_registration_claims",
        "registry_people",
        "registry_departments",
        "registry_locations",
        "server_config",
        "ticket_events",
        "tickets",
    } <= tables


def test_full_cleanup_profile_preserves_current_table_scope():
    full_tables = test_harness.CLEANUP_TABLES_BY_PROFILE["full"]

    assert len(full_tables) == 169
    assert full_tables[:4] == (
        "observer_integrity_check_runs",
        "observer_integrity_events",
        "observer_known_contamination",
        "observer_error_occurrences",
    )
    assert {
        "ticket_kb_links",
        "ticket_admin_audit_archive",
        "ticket_events_archive",
        "ticket_retention_runs",
    } <= set(full_tables)
    assert not RETIRED_KNOWLEDGE_AI_TABLES & set(full_tables)
    assert full_tables[-3:] == ("modules", "ticket_retention_runs", "tickets")


@pytest.mark.asyncio
async def test_cleanup_audit_fails_when_profile_table_keeps_rows(monkeypatch):
    class FakeResult:
        def __init__(self, value):
            self.value = value

        def scalar_one(self):
            return self.value

    class FakeConn:
        async def execute(self, statement):
            sql = str(statement)
            table = sql.split('FROM "', 1)[1].split('"', 1)[0]
            return FakeResult(2 if table == "knowledge_items" else 0)

    monkeypatch.setenv("PC_CLIENT_TEST_CLEANUP_AUDIT", "1")

    with pytest.raises(AssertionError, match="knowledge_items=2"):
        await test_harness._audit_cleanup_profile_empty(
            FakeConn(),
            "knowledge",
            ("knowledge_items", "knowledge_spaces"),
        )


def test_template_env_flags(monkeypatch):
    monkeypatch.delenv("PC_CLIENT_TEST_DB_TEMPLATE", raising=False)
    monkeypatch.delenv("PC_CLIENT_TEST_DB_TEMPLATE_KEEP", raising=False)
    monkeypatch.delenv("PC_CLIENT_TEST_DB_TEMPLATE_REBUILD", raising=False)

    assert test_harness._test_db_template_enabled() is False
    assert test_harness._keep_test_db_template() is False
    assert test_harness._rebuild_test_db_template() is False

    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE", "1")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE_KEEP", "1")
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE_REBUILD", "1")

    assert test_harness._test_db_template_enabled() is True
    assert test_harness._keep_test_db_template() is True
    assert test_harness._rebuild_test_db_template() is True


@pytest.mark.asyncio
async def test_run_async_blocking_works_from_running_event_loop():
    async def sample(value):
        await asyncio.sleep(0)
        return value

    assert test_harness._run_async_blocking(sample, "ok") == "ok"


def test_template_database_name_uses_safe_prefix_and_fingerprint(monkeypatch):
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE_PREFIX", "pc-support-test-template")

    name = test_harness._template_database_name_for_fingerprint("abcdef1234567890")

    assert name == "pc_support_test_template_abcdef123456"
    test_harness._validate_template_database_name(name)


def test_template_database_name_rejects_unsafe_prefix(monkeypatch):
    monkeypatch.setenv("PC_CLIENT_TEST_DB_TEMPLATE_PREFIX", "production")

    with pytest.raises(RuntimeError, match="pc_support_test_template"):
        test_harness._template_database_name_for_fingerprint("abcdef1234567890")


def test_validate_template_database_name_rejects_non_template_names():
    with pytest.raises(RuntimeError, match="Unsafe template database name"):
        test_harness._validate_template_database_name("pc_support_test_web_api_123456")

    with pytest.raises(RuntimeError, match="Unsafe template database name"):
        test_harness._validate_template_database_name('pc_support_test_template_bad";drop')


def test_migration_fingerprint_is_stable_and_changes_with_migration_content(tmp_path):
    server_root = tmp_path / "server"
    migrations = server_root / "app" / "db" / "migrations" / "versions"
    migrations.mkdir(parents=True)
    (server_root / "alembic.ini").write_text("[alembic]\nscript_location = app/db/migrations\n", encoding="utf-8")
    migration_path = migrations / "20260621_001_example.py"
    migration_path.write_text("revision = '001'\ndown_revision = None\n", encoding="utf-8")

    first = test_harness._migration_fingerprint(server_root)
    second = test_harness._migration_fingerprint(server_root)
    migration_path.write_text("revision = '001'\ndown_revision = None\n# changed\n", encoding="utf-8")
    changed = test_harness._migration_fingerprint(server_root)

    assert first == second
    assert first != changed
    assert len(first) == 40


@pytest.mark.asyncio
async def test_clone_test_database_from_template_uses_quoted_identifiers(monkeypatch):
    run_admin_sql = AsyncMock()
    monkeypatch.setattr(test_harness, "_run_admin_sql", run_admin_sql)

    await test_harness._clone_test_database_from_template(
        "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres",
        "pc_support_test_knowledge_123456",
        "pc_support_test_template_abcdef123456",
    )

    assert run_admin_sql.await_count == 1
    args, kwargs = run_admin_sql.await_args
    assert args[0] == "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres"
    assert args[1] == (
        'CREATE DATABASE "pc_support_test_knowledge_123456" '
        'TEMPLATE "pc_support_test_template_abcdef123456"'
    )
    assert kwargs == {}
