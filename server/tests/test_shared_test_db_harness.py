from unittest.mock import AsyncMock

import pytest

from tests import conftest as harness


@pytest.mark.no_db
def test_is_shared_test_database_url_detects_shared_name():
    shared_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test"
    isolated_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_abcd1234"

    assert harness._is_shared_test_database_url(shared_url) is True
    assert harness._is_shared_test_database_url(isolated_url) is False


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_terminate_other_test_database_backends_skips_non_shared_db(monkeypatch):
    run_admin_sql = AsyncMock()
    monkeypatch.setattr(harness, "_run_admin_sql", run_admin_sql)

    await harness._terminate_other_test_database_backends(
        "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres",
        "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test_abcd1234",
    )

    run_admin_sql.assert_not_awaited()


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_terminate_other_test_database_backends_terminates_shared_db_sessions(monkeypatch):
    run_admin_sql = AsyncMock()
    monkeypatch.setattr(harness, "_run_admin_sql", run_admin_sql)
    shared_url = "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/pc_support_test"

    await harness._terminate_other_test_database_backends(
        "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres",
        shared_url,
    )

    run_admin_sql.assert_awaited_once()
    args, kwargs = run_admin_sql.await_args
    assert args[0] == "postgresql+asyncpg://chatbot:chatbot@127.0.0.1:55432/postgres"
    assert "pg_terminate_backend" in args[1]
    assert kwargs == {"db_name": "pc_support_test"}
