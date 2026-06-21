import asyncio
import importlib.util
import warnings
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _load_test_harness():
    path = Path(__file__).resolve().parent / "conftest.py"
    spec = importlib.util.spec_from_file_location("server_test_harness", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


test_harness = _load_test_harness()


pytestmark = pytest.mark.no_db


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
        lambda db_name: f"postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/{db_name}",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        test_db_url, admin_db_url, is_shared = test_harness._maybe_fallback_to_shared_test_db(
            "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test_deadbeef",
            "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/postgres",
            False,
            allow_auto_shared_fallback=True,
        )

    assert is_shared is True
    assert test_db_url.endswith("/pc_support_test")
    assert admin_db_url.endswith("/postgres")
    assert any("falling back to shared test DB" in str(item.message) for item in caught)
    assert any("not valid for full DB/API gate" in str(item.message) for item in caught)
    assert probed == [
        "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/postgres",
        "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test",
    ]


def test_auto_fallback_is_not_used_when_disabled(monkeypatch):
    called = []

    def fake_probe(url: str) -> None:
        called.append(url)

    monkeypatch.setattr(test_harness, "_probe_database_sync", fake_probe)

    test_db_url, admin_db_url, is_shared = test_harness._maybe_fallback_to_shared_test_db(
        "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/pc_support_test_deadbeef",
        "postgresql+asyncpg://chatbot:chatbot@192.168.100.17:5432/postgres",
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


def test_cleanup_truncate_sql_uses_selected_profile_tables_only():
    sql = test_harness._cleanup_truncate_sql("knowledge")
    tables = test_harness.CLEANUP_TABLES_BY_PROFILE["knowledge"]

    assert "knowledge_items" in tables
    assert "knowledge_items" in sql
    assert "ticket_queues" not in tables
    assert "ticket_queues" not in sql
    assert sql.strip().endswith("RESTART IDENTITY CASCADE")


def test_full_cleanup_profile_preserves_current_table_scope():
    full_tables = test_harness.CLEANUP_TABLES_BY_PROFILE["full"]

    assert len(full_tables) == 132
    assert full_tables[:3] == (
        "observer_integrity_events",
        "observer_known_contamination",
        "observer_error_occurrences",
    )
    assert full_tables[-3:] == ("ui_users", "modules", "tickets")


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
