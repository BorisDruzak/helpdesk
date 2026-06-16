from __future__ import annotations

import sys

import pytest

from mcp_helpdesk_server import bootstrap
from mcp_helpdesk_server.tools import db_tools


def test_configure_paths_adds_repo_and_server_roots() -> None:
    repo, server = bootstrap.configure_paths()

    assert str(repo) in sys.path
    assert str(server) in sys.path
    assert repo.name == "pc_client"
    assert server.name == "server"


@pytest.mark.asyncio
async def test_db_health_handles_init_failure_as_controlled_error(monkeypatch) -> None:
    async def fail_start() -> None:
        raise RuntimeError("postgresql+asyncpg://user:secret@host/db")

    monkeypatch.setattr(db_tools.bootstrap, "ensure_db_started", fail_start)

    payload = await db_tools.helpdesk_db_health({})

    assert payload["status"] == "error"
    assert payload["error_code"] == "DB_UNAVAILABLE"
    assert "secret" not in str(payload)


@pytest.mark.asyncio
async def test_ensure_db_started_reuses_existing_app_engine(monkeypatch) -> None:
    import app.db as app_db
    from app.db import engine as db_engine_module

    sentinel_engine = object()
    sentinel_session_maker = object()
    previous_engine = db_engine_module._engine
    previous_session_maker = db_engine_module._session_maker

    async def fail_init_db(_database_url: str) -> None:
        raise AssertionError("ensure_db_started must not reinitialize an existing app engine")

    async def fail_shutdown_db() -> None:
        raise AssertionError("shutdown_db_if_started must not close an externally owned app engine")

    monkeypatch.setattr(bootstrap, "_DB_STARTED", False)
    monkeypatch.setattr(bootstrap, "_DB_OWNED", False)
    monkeypatch.setattr(app_db, "init_db", fail_init_db)
    monkeypatch.setattr(app_db, "shutdown_db", fail_shutdown_db)
    db_engine_module._engine = sentinel_engine
    db_engine_module._session_maker = sentinel_session_maker

    try:
        payload = await bootstrap.ensure_db_started()

        assert payload == {"started": False, "already_started": True, "external": True}
        assert bootstrap.db_started() is True

        await bootstrap.shutdown_db_if_started()

        assert db_engine_module._engine is sentinel_engine
        assert db_engine_module._session_maker is sentinel_session_maker
        assert bootstrap.db_started() is False
    finally:
        db_engine_module._engine = previous_engine
        db_engine_module._session_maker = previous_session_maker
        monkeypatch.setattr(bootstrap, "_DB_STARTED", False)
        monkeypatch.setattr(bootstrap, "_DB_OWNED", False)
