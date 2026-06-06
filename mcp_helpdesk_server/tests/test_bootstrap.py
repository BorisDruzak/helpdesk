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
