from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest


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
