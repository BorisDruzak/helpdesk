from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DevicePresenceSnapshot, ServerRuntimeSnapshot
from observer.debug_facade import agent_presence_snapshot, runtime_snapshot
from observer.runtime_snapshot_writer import build_runtime_snapshot_payload, persist_runtime_snapshot


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
                    "service_health": {"api": "ok", "agent_ws_connections": 1},
                    "connected_agents": {
                        "device-1": {
                            "device_id": "device-1",
                            "live_ws_state": "online",
                            "agent_version": "3.1.61",
                        }
                    },
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
    assert payload["snapshot"]["service_health"]["agent_ws_connections"] == 1


@pytest.mark.asyncio
async def test_presence_snapshot_uses_fresh_runtime_ws_evidence_when_present(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    device_id = "device-live-1"

    async with session_maker() as session:
        session.add(
            Device(
                device_id=device_id,
                protocol_version="ws_ticket_v3",
                agent_version="3.1.61",
                hostname="live-device",
                os="ALT Linux",
                first_seen_at=now - timedelta(days=1),
                last_seen_at=now - timedelta(minutes=1),
                last_handshake_at=now - timedelta(minutes=1),
            )
        )
        session.add(
            ServerRuntimeSnapshot(
                process_kind="server",
                instance_id="test-instance",
                pid=12345,
                git_revision="abc1234",
                collected_at=now,
                expires_at=now + timedelta(minutes=2),
                status="ok",
                snapshot={
                    "connected_agents": {
                        device_id: {
                            "device_id": device_id,
                            "live_ws_state": "online",
                            "connected_at": now.isoformat(),
                            "agent_version": "3.1.61",
                        }
                    }
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        payload = await agent_presence_snapshot(session, device_id=device_id, limit=5)

    assert payload["status"] == "ok"
    assert payload["live_ws_state"] == "online"
    assert payload["live_ws_evidence"]["device_id"] == device_id
    assert payload["live_ws_evidence"]["agent_version"] == "3.1.61"
    assert payload["device_db_evidence"]["hostname"] == "live-device"


@pytest.mark.asyncio
async def test_presence_snapshot_without_device_id_reports_aggregate_live_ws_evidence(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async with session_maker() as session:
        await session.execute(delete(DevicePresenceSnapshot))
        session.add(
            ServerRuntimeSnapshot(
                process_kind="server",
                instance_id="test-instance",
                pid=12345,
                git_revision="abc1234",
                collected_at=now,
                expires_at=now + timedelta(minutes=2),
                status="ok",
                snapshot={
                    "connected_agents": {
                        "device-live-1": {
                            "device_id": "device-live-1",
                            "live_ws_state": "online",
                            "agent_version": "3.1.61",
                            "connection_id": "conn-1",
                        },
                        "device-live-2": {
                            "device_id": "device-live-2",
                            "live_ws_state": "online",
                            "agent_version": "3.1.62",
                            "connection_id": "conn-2",
                        },
                    }
                },
            )
        )
        await session.commit()

    async with session_maker() as session:
        payload = await agent_presence_snapshot(session, limit=5)

    assert payload["status"] == "ok"
    assert payload["presence_snapshot_available"] is False
    assert payload["confidence"] == "live_ws"
    assert payload["live_ws_state"] == "online"
    assert payload["live_ws_evidence"]["connected_count"] == 2
    assert payload["live_ws_evidence"]["returned"] == 2
    assert {agent["device_id"] for agent in payload["live_ws_evidence"]["agents"]} == {
        "device-live-1",
        "device-live-2",
    }


def test_build_runtime_snapshot_payload_excludes_raw_websocket_objects() -> None:
    class FakeState:
        ui_connections = {"ui-1": object()}
        connected_agents = {
            "device-1": {
                "ws": object(),
                "connected_at": "2026-06-06T10:00:00+00:00",
                "metadata": {
                    "connection_id": "conn-1",
                    "agent_version": "3.1.61",
                    "protocol_version": "ws_ticket_v3",
                    "token": "must-not-leak",
                },
            }
        }
        diagnostic_agent_connections = {"probe-1": object()}

    payload = build_runtime_snapshot_payload(
        app={"state": FakeState(), "operation_watchdog": object()},
        process_kind="server",
        git_revision="abc1234",
    )

    rendered = str(payload)
    assert payload["service_health"]["ui_ws_connections"] == 1
    assert payload["service_health"]["agent_ws_connections"] == 1
    assert payload["connected_agents"]["device-1"]["live_ws_state"] == "online"
    assert "ws" not in payload["connected_agents"]["device-1"]
    assert "must-not-leak" not in rendered


@pytest.mark.asyncio
async def test_persist_runtime_snapshot_writes_bounded_row(test_engine) -> None:
    session_maker = async_sessionmaker(test_engine)
    payload = {
        "process_kind": "server",
        "instance_id": "test-instance",
        "pid": 456,
        "git_revision": "def5678",
        "status": "ok",
        "connected_agents": {},
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
