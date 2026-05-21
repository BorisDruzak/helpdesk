import importlib.util
import warnings
from pathlib import Path

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
