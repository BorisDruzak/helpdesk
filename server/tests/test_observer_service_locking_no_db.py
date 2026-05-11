from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import observer.service as observer_service_module
from observer.service import ObserverOverlayService, TraceOverlayFilters, _iter_postgres_payload_batches


class _AsyncSessionContext:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_postgres_payload_batches_respect_bind_parameter_limit() -> None:
    payloads = [{f"field_{field}": f"{row}-{field}" for field in range(4)} for row in range(7)]

    batches = list(_iter_postgres_payload_batches(payloads, bind_limit=10))

    assert [len(batch) for batch in batches] == [2, 2, 2, 1]


@pytest.mark.asyncio
async def test_store_span_payloads_chunks_large_postgres_bulk_insert() -> None:
    session = MagicMock()
    session.get_bind.return_value = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    session.execute = AsyncMock()
    service = ObserverOverlayService(session)
    now = datetime.now(timezone.utc)
    span_payloads = [
        {
            "span_id": f"span-{index}",
            "trace_id": "trace-1",
            "parent_span_id": None,
            "source_type": "ticket_event",
            "source_ref": str(index),
            "name": "ticket.event",
            "kind": "event",
            "component": "tickets",
            "event_type": "chat_message",
            "module_name": None,
            "tool_name": None,
            "status": "ok",
            "started_at": now,
            "finished_at": now,
            "duration_ms": 0,
            "attrs_json": {"index": index},
        }
        for index in range(2_000)
    ]

    await service._store_span_payloads(span_payloads)

    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_ensure_projected_commits_read_transaction_before_using_isolated_projection_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_session = MagicMock()
    main_session.in_transaction = MagicMock(return_value=True)
    main_session.new = set()
    main_session.dirty = set()
    main_session.deleted = set()
    main_session.commit = AsyncMock()

    projection_sessions = []
    for _ in range(2):
        session = MagicMock()
        session.commit = AsyncMock()
        projection_sessions.append(session)
    session_iter = iter(projection_sessions)

    async def _fake_candidate_trace_ids(self, filters, *, limit):
        assert isinstance(filters, TraceOverlayFilters)
        assert limit == 3
        return ["trace-a", "trace-b"]

    async def _fake_project_trace(self, trace_id: str, *, force: bool = False):
        return {"trace_id": trace_id, "session": id(self.session), "force": force}

    def _fake_get_session():
        return _AsyncSessionContext(next(session_iter))

    monkeypatch.setattr(ObserverOverlayService, "_candidate_trace_ids", _fake_candidate_trace_ids)
    monkeypatch.setattr(ObserverOverlayService, "project_trace", _fake_project_trace)
    monkeypatch.setattr(observer_service_module, "get_session", _fake_get_session)

    service = ObserverOverlayService(main_session)
    await service._ensure_projected(TraceOverlayFilters(ticket_id="ticket-1"), limit=3, force=False)

    main_session.commit.assert_awaited_once()
    assert [session.commit.await_count for session in projection_sessions] == [1, 1]


@pytest.mark.asyncio
async def test_rebuild_traces_uses_isolated_projection_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_session = MagicMock()
    main_session.in_transaction = MagicMock(return_value=True)
    main_session.new = set()
    main_session.dirty = set()
    main_session.deleted = set()
    main_session.commit = AsyncMock()

    projection_sessions = []
    for _ in range(2):
        session = MagicMock()
        session.commit = AsyncMock()
        projection_sessions.append(session)
    session_iter = iter(projection_sessions)

    async def _fake_candidate_trace_ids(self, filters, *, limit):
        assert limit == 2
        return ["trace-a", "trace-b"]

    async def _fake_project_trace(self, trace_id: str, *, force: bool = False):
        return {"trace_id": trace_id, "force": force}

    def _fake_get_session():
        return _AsyncSessionContext(next(session_iter))

    monkeypatch.setattr(ObserverOverlayService, "_candidate_trace_ids", _fake_candidate_trace_ids)
    monkeypatch.setattr(ObserverOverlayService, "project_trace", _fake_project_trace)
    monkeypatch.setattr(observer_service_module, "get_session", _fake_get_session)

    service = ObserverOverlayService(main_session)
    projected = await service.rebuild_traces(TraceOverlayFilters(ticket_id="ticket-2"), limit=2)

    assert projected == ["trace-a", "trace-b"]
    main_session.commit.assert_awaited_once()
    assert [session.commit.await_count for session in projection_sessions] == [1, 1]
