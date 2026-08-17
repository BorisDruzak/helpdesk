from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
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


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_endpoint_reconciler_ui_publisher_reads_committed_operation_before_push(monkeypatch):
    import server as server_module

    operation = SimpleNamespace(operation_id="operation-1")
    calls: list[object] = []

    class FakeRepo:
        def __init__(self, session):
            calls.append(("repo", session))

        async def get_by_operation_id(self, operation_id):
            calls.append(("read", operation_id))
            return operation

    class FakePublisher:
        def __init__(self, state):
            calls.append(("publisher", state))

        async def push_operation_updated(self, value):
            calls.append(("push", value))

    @asynccontextmanager
    async def fake_session():
        yield "committed-session"

    monkeypatch.setattr(server_module, "get_session", fake_session)
    monkeypatch.setattr(server_module, "OperationsRepo", FakeRepo)
    monkeypatch.setattr(server_module, "UiPublisherImpl", FakePublisher)

    publish = server_module._endpoint_operation_ui_publisher(SimpleNamespace())
    await publish("operation-1")

    assert calls[0][0] == "publisher"
    assert calls[1:] == [
        ("repo", "committed-session"),
        ("read", "operation-1"),
        ("push", operation),
    ]
