from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa

from app.db import get_session
from app.repos.agent_observer_events_repo import AgentObserverEventsRepo
from observer.service import ObserverOverlayService, TraceOverlayFilters


@pytest.mark.asyncio
async def test_agent_observer_event_projects_as_runtime_trace_and_signature() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000af01"

    async with get_session() as session:
        repo = AgentObserverEventsRepo(session)
        events = await repo.ingest_batch(
            device_id=device_id,
            events=[
                {
                    "event_id": "projection-agent-event-1",
                    "event_type": "agent.crash_detected",
                    "severity": "error",
                    "root_kind": "agent_runtime",
                    "component": "launcher",
                    "stage": "startup",
                    "status": "failed",
                    "created_at": now.isoformat(),
                    "attrs_json": {
                        "reason": "new version exited during startup",
                        "exception_type": "RuntimeError",
                    },
                }
            ],
        )
        trace_id = events[0].trace_id
        assert trace_id
        await session.commit()

    async with get_session() as session:
        trace = await ObserverOverlayService(session).project_trace(trace_id, force=True)
        await session.commit()

    assert trace is not None
    assert trace.root_kind == "agent_runtime"
    assert trace.device_id == device_id
    assert trace.status == "error"

    async with get_session() as session:
        spans = (
            await session.execute(
                sa.text(
                    "SELECT source_type, component, event_type, status "
                    "FROM observer_spans WHERE trace_id = :trace_id"
                ),
                {"trace_id": trace_id},
            )
        ).mappings().all()
        assert any(row["source_type"] == "agent_observer_event" for row in spans)
        assert any(row["component"] == "launcher" and row["event_type"] == "agent.crash_detected" for row in spans)

        occurrences = (
            await session.execute(
                sa.text(
                    "SELECT component, error_kind, failure_stage, severity "
                    "FROM observer_error_occurrences WHERE trace_id = :trace_id"
                ),
                {"trace_id": trace_id},
            )
        ).mappings().all()
        assert occurrences
        assert occurrences[0]["component"] == "launcher"
        assert occurrences[0]["error_kind"] == "agent.crash_detected"
        assert occurrences[0]["failure_stage"] == "startup"
        assert occurrences[0]["severity"] == "error"


@pytest.mark.asyncio
async def test_agent_observer_event_is_searchable_by_device_and_text() -> None:
    now = datetime.now(timezone.utc)
    device_id = "00000000-0000-0000-0000-00000000af11"

    async with get_session() as session:
        await AgentObserverEventsRepo(session).ingest_batch(
            device_id=device_id,
            events=[
                {
                    "event_id": "search-agent-event-1",
                    "event_type": "agent.update.launcher",
                    "severity": "warning",
                    "root_kind": "agent_update",
                    "component": "launcher",
                    "stage": "rollback",
                    "created_at": now.isoformat(),
                    "attrs_json": {"reason": "launcher rollback after failed canary"},
                }
            ],
        )
        await session.commit()

    async with get_session() as session:
        service = ObserverOverlayService(session)
        candidates = await service._candidate_trace_ids(
            TraceOverlayFilters(device_id=device_id, query="rollback", root_kind="agent_update"),
            limit=10,
        )

    assert candidates
