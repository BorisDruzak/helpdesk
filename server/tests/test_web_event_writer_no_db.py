from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.dialects import postgresql

from app.db.models import ObserverErrorOccurrence, ObserverErrorSignature, ObserverSpan, ObserverTrace
from observer.checks.web_cabinet import _has_create_observer_trace
from observer.web_event_writer import write_web_cabinet_observer_event


pytestmark = pytest.mark.no_db


class _FakeResult:
    def __init__(self, *, scalar=None, row=None) -> None:
        self._scalar = scalar
        self._row = row

    def scalar_one_or_none(self):
        return self._scalar

    def one(self):
        return self._row


class _FakeSession:
    def __init__(self) -> None:
        self.traces: dict[str, ObserverTrace] = {}
        self.spans_by_source_ref: dict[tuple[str, str], ObserverSpan] = {}
        self.signatures: dict[str, ObserverErrorSignature] = {}
        self.occurrences: list[ObserverErrorOccurrence] = []

    async def get(self, model, key):
        if model is ObserverTrace:
            return self.traces.get(str(key))
        if model is ObserverErrorSignature:
            return self.signatures.get(str(key))
        return None

    def add(self, row) -> None:
        if isinstance(row, ObserverTrace):
            self.traces[row.trace_id] = row
        elif isinstance(row, ObserverSpan):
            self.spans_by_source_ref[(row.trace_id, row.source_ref)] = row
        elif isinstance(row, ObserverErrorSignature):
            self.signatures[row.error_signature] = row
        elif isinstance(row, ObserverErrorOccurrence):
            self.occurrences.append(row)

    async def flush(self) -> None:
        return None

    async def execute(self, stmt):
        descriptions = getattr(stmt, "column_descriptions", ())
        if descriptions and descriptions[0].get("entity") is ObserverSpan:
            params = stmt.compile().params
            trace_id = params.get("trace_id_1")
            source_ref = params.get("source_ref_1")
            return _FakeResult(scalar=self.spans_by_source_ref.get((trace_id, source_ref)))
        count = len(self.occurrences)
        first = min((row.created_at for row in self.occurrences), default=datetime.now(timezone.utc))
        last = max((row.created_at for row in self.occurrences), default=first)
        affected_devices = len({row.device_id for row in self.occurrences if row.device_id})
        return _FakeResult(row=(count, first, last, affected_devices))


async def _write(session: _FakeSession, *, correlation_id: str, result: str, error_code: str | None = None) -> str:
    return await write_web_cabinet_observer_event(
        session,
        source="requester",
        event_type="ticket_create",
        severity="error" if error_code else "info",
        route="/app/requester/create",
        actor_context={"actor_role": "requester", "correlation_id": correlation_id},
        result=result,
        ticket_id="ticket-same",
        error_code=error_code,
        payload={"field": "value"},
    )


@pytest.mark.asyncio
async def test_web_trace_identity_prefers_execution_correlation_over_ticket_entity():
    session = _FakeSession()

    first_trace_id = await _write(session, correlation_id="request-one", result="created")
    second_trace_id = await _write(session, correlation_id="request-two", result="created")

    assert first_trace_id != second_trace_id
    assert len(session.traces) == 2


@pytest.mark.asyncio
async def test_web_trace_error_then_success_keeps_error_history_on_same_execution():
    session = _FakeSession()

    failed_trace_id = await _write(session, correlation_id="retry-request", result="failed", error_code="VALIDATION")
    succeeded_trace_id = await _write(session, correlation_id="retry-request", result="created")

    trace = session.traces[failed_trace_id]
    spans = [span for span in session.spans_by_source_ref.values() if span.trace_id == failed_trace_id]

    assert succeeded_trace_id == failed_trace_id
    assert trace.status == "succeeded"
    assert trace.error_count == 1
    assert trace.span_count == 2
    assert {span.status for span in spans} == {"error", "ok"}


@pytest.mark.asyncio
async def test_successful_create_trace_predicate_requires_successful_requester_create():
    seen: dict[str, str] = {}

    class PredicateSession:
        async def scalar(self, stmt):
            seen["sql"] = str(
                stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
            ).lower()
            return 0

    assert await _has_create_observer_trace(PredicateSession(), "ticket-predicate") is False

    sql = seen["sql"]
    assert "observer_traces.status = 'succeeded'" in sql
    assert "requester_ticket_create" in sql
    assert "ticket_create_succeeded" in sql
    assert "ticket_create_created" in sql
    assert "created" in sql
    assert " or " not in sql
