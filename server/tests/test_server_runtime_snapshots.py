from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import ServerRuntimeSnapshot
from observer.debug_facade import runtime_snapshot
from observer.runtime_snapshot_writer import build_runtime_snapshot_payload, persist_runtime_snapshot

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
async def test_runtime_snapshot_returns_fresh_persisted_server_snapshot(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    collected_at = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        session.add(
            ServerRuntimeSnapshot(
                process_kind="server",
                instance_id="test-instance",
                pid=12345,
                git_revision="abc1234",
                collected_at=collected_at,
                expires_at=collected_at + timedelta(minutes=2),
                status="ok",
                snapshot={
                    "service_health": {"api": "ok", "ui_ws_connections": 1},
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        payload = await runtime_snapshot(session, process_kind="server", include_details=True)

    assert payload["status"] == "ok"
    assert payload["runtime_snapshot_available"] is True
    assert payload["process_kind"] == "server"
    assert payload["snapshot"]["git_revision"] == "abc1234"
    assert payload["snapshot"]["service_health"]["ui_ws_connections"] == 1


def test_build_runtime_snapshot_payload_excludes_raw_websocket_objects() -> None:
    class FakeState:
        ui_connections = {"ui-1": object()}

    payload = build_runtime_snapshot_payload(
        app={"state": FakeState(), "operation_watchdog": object()},
        process_kind="server",
        git_revision="abc1234",
    )

    assert payload["service_health"]["ui_ws_connections"] == 1
    assert "agent_ws_connections" not in payload["service_health"]
    assert "connected_agents" not in payload


@pytest.mark.asyncio
async def test_persist_runtime_snapshot_writes_bounded_row(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    payload = {
        "process_kind": "server",
        "instance_id": "test-instance",
        "pid": 456,
        "git_revision": "def5678",
        "status": "ok",
        "service_health": {"api": "ok"},
    }

    async with session_maker() as session:
        row = await persist_runtime_snapshot(session, payload, ttl_seconds=120)
        await session.commit()

    async with session_maker() as session:
        stored = await session.get(ServerRuntimeSnapshot, row.id)

    assert stored is not None
    assert stored.process_kind == "server"
    assert stored.git_revision == "def5678"
    assert stored.snapshot["service_health"]["api"] == "ok"
    assert stored.expires_at > stored.collected_at
