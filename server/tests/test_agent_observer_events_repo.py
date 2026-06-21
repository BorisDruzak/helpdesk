from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.db import get_session
from app.db.models import AgentObserverEvent
from app.repos.agent_observer_events_repo import AgentObserverEventsRepo


pytestmark = pytest.mark.db_cleanup("agent_runtime")

@pytest.mark.asyncio
async def test_agent_observer_events_repo_ingests_idempotently_redacts_and_lists() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000ae01"
    trace_id = "00000000-0000-0000-0000-00000000ae02"

    async with get_session() as session:
        repo = AgentObserverEventsRepo(session)
        first = await repo.ingest_batch(
            device_id=device_id,
            events=[
                {
                    "event_id": "agent-event-1",
                    "event_type": "agent.ws.reconnect",
                    "severity": "warning",
                    "root_kind": "agent_runtime",
                    "component": "websocket",
                    "stage": "connect",
                    "status": "retrying",
                    "trace_id": trace_id,
                    "created_at": now.isoformat(),
                    "attrs_json": {
                        "reason": "connection_lost",
                        "token": "secret-token-value",
                        "nested": {"password": "secret-password"},
                    },
                }
            ],
        )
        second = await repo.ingest_batch(
            device_id=device_id,
            events=[
                {
                    "event_id": "agent-event-1",
                    "event_type": "agent.ws.reconnect",
                    "severity": "critical",
                    "root_kind": "agent_runtime",
                    "component": "websocket",
                    "created_at": (now + timedelta(seconds=1)).isoformat(),
                    "attrs_json": {"reason": "duplicate_should_not_overwrite"},
                }
            ],
        )
        await session.commit()

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].id == first[0].id

    async with get_session() as session:
        stored = await session.get(AgentObserverEvent, first[0].id)
        assert stored is not None
        assert stored.event_id == "agent-event-1"
        assert stored.device_id == device_id
        assert stored.trace_id == trace_id
        assert stored.severity == "warning"
        assert stored.attrs_json["token"] != "secret-token-value"
        assert stored.attrs_json["nested"]["password"] != "secret-password"

        repo = AgentObserverEventsRepo(session)
        by_device = await repo.list_recent(device_id=device_id)
        by_trace = await repo.list_recent(trace_id=trace_id)
        assert [item.event_id for item in by_device] == ["agent-event-1"]
        assert [item.event_id for item in by_trace] == ["agent-event-1"]


@pytest.mark.asyncio
async def test_agent_observer_events_repo_normalizes_invalid_values_and_caps_batch() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000ae11"
    events = [
        {
            "event_id": f"cap-event-{idx}",
            "event_type": "agent.update.apply",
            "severity": "loud",
            "root_kind": "unknown_root",
            "component": "launcher",
            "created_at": (now + timedelta(seconds=idx)).isoformat(),
            "attrs_json": {"idx": idx},
        }
        for idx in range(105)
    ]

    async with get_session() as session:
        repo = AgentObserverEventsRepo(session)
        stored = await repo.ingest_batch(device_id=device_id, events=events)
        await session.commit()

    assert len(stored) == 100
    assert {item.severity for item in stored} == {"info"}
    assert {item.root_kind for item in stored} == {"agent_runtime"}
