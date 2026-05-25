from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_housekeeping_does_not_start_inventory_runtime(monkeypatch):
    import server as server_module

    starts: list[object] = []

    class FakeInventoryRefreshRuntime:
        def __init__(self, *, state):
            self.state = state

        async def start(self):
            starts.append(self.state)

    sleep_calls = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError()

    monkeypatch.setattr("inventory.scheduler.InventoryRefreshRuntime", FakeInventoryRefreshRuntime)
    monkeypatch.setattr(server_module.asyncio, "sleep", fake_sleep)

    app = {
        "state": SimpleNamespace(
            sessions_by_ticket={},
            sessions_by_id={},
            ticket_seen_message_ids={},
        )
    }

    with pytest.raises(asyncio.CancelledError):
        await server_module.housekeeping_cleanup_task(app)

    assert starts == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_inventory_runtime_start_is_idempotent(monkeypatch):
    import server as server_module

    starts: list[object] = []

    class FakeInventoryRefreshRuntime:
        def __init__(self, *, state):
            self.state = state

        async def start(self):
            starts.append(self.state)

    monkeypatch.setattr("inventory.scheduler.InventoryRefreshRuntime", FakeInventoryRefreshRuntime)

    app = {
        "state": SimpleNamespace(),
    }

    await server_module.start_inventory_refresh_runtime(app)
    await server_module.start_inventory_refresh_runtime(app)

    assert starts == [app["state"]]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_strict_startup_raises_when_database_initialization_fails(monkeypatch):
    import server as server_module

    async def fail_init_db(_database_url):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(server_module, "ENABLE_DB_PERSISTENCE", True)
    monkeypatch.setattr(server_module, "validate_security_config", lambda: None)
    monkeypatch.setattr(server_module, "init_db", fail_init_db)
    monkeypatch.setattr(server_module, "is_strict_runtime_mode", lambda: True)

    app = {
        "state": SimpleNamespace(),
    }

    with pytest.raises(RuntimeError, match="database unavailable"):
        await server_module.on_startup(app)
