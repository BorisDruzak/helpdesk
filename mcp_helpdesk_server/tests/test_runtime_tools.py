from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_runtime_snapshot_absent_returns_partial_not_crash() -> None:
    from observer.debug_facade import runtime_snapshot

    payload = await runtime_snapshot(object())

    assert payload["status"] == "partial"
    assert payload["runtime_snapshot_available"] is False


@pytest.mark.asyncio
async def test_presence_snapshot_absent_returns_partial_not_crash() -> None:
    from observer.debug_facade import agent_presence_snapshot

    class EmptyResult:
        def scalars(self):
            return self

        def all(self):
            return []

    class FakeSession:
        async def execute(self, stmt):
            return EmptyResult()

        async def get(self, model, key):
            return None

    payload = await agent_presence_snapshot(FakeSession(), limit=5)

    assert payload["status"] == "partial"
    assert payload["presence_snapshot_available"] is False
    assert payload["confidence"] == "unknown"


@pytest.mark.asyncio
async def test_presence_snapshot_available_returns_db_snapshot() -> None:
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from observer.debug_facade import agent_presence_snapshot

    now = datetime.now(timezone.utc)

    class Result:
        def __init__(self, rows):
            self.rows = rows

        def scalars(self):
            return self

        def all(self):
            return self.rows

    class FakeSession:
        async def execute(self, stmt):
            return Result(
                [
                    SimpleNamespace(
                        id="presence-1",
                        device_id="device-1",
                        collected_at=now,
                        received_at=now,
                        session_state="active",
                        current_user="user",
                        idle_seconds=3,
                        locked=False,
                        snapshot={"token": "secret"},
                    )
                ]
            )

        async def get(self, model, key):
            return None

    payload = await agent_presence_snapshot(FakeSession(), device_id="device-1", limit=5)

    assert payload["status"] == "ok"
    assert payload["presence_snapshot_available"] is True
    assert payload["snapshots"][0]["snapshot"]["token"] == "***REDACTED***"
