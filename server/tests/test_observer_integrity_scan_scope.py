from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.repos.observer_integrity_repo import ObserverIntegrityEventInput, ObserverIntegrityRepo
from observer import integrity_service as integrity_module
from observer.checks.operation_lifecycle import QUERY_LIMIT as OPERATION_QUERY_LIMIT
from observer.checks.operation_lifecycle import SOURCE as OPERATION_SOURCE
from observer.checks.operation_lifecycle import check_operation_lifecycle
from observer.checks.protocol_integrity import SOURCE as PROTOCOL_SOURCE
from observer.checks.runtime_presence import QUERY_LIMIT as RUNTIME_QUERY_LIMIT
from observer.checks.runtime_presence import SOURCE as RUNTIME_SOURCE
from observer.checks.runtime_presence import check_runtime_presence
from observer.checks.web_cabinet import check_web_cabinet
from observer.integrity_service import ObserverIntegrityService


pytestmark = pytest.mark.no_db


class _FakeIntegrityRepo:
    def __init__(self) -> None:
        self.resolved_sources: list[str] = []
        self.upserted_events: list[ObserverIntegrityEventInput] = []

    async def ensure_contamination(self, *, rows):
        return 0

    async def find_contamination(self, event):
        return None

    async def upsert_event(self, event, *, suppression_reason=None):
        self.upserted_events.append(event)
        return type("Row", (), {"event_id": event.dedupe_key, "status": "active"})()

    async def resolve_missing(self, *, source, active_dedupe_keys, run_id=None):
        self.resolved_sources.append(source)
        return 1


class _FakeSession:
    async def flush(self) -> None:
        return None


class _FakeScalarResult:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _FakeExecuteResult:
    def __init__(self, rows) -> None:
        self._rows = list(rows)

    def all(self):
        return list(self._rows)

    def scalars(self):
        return _FakeScalarResult(self._rows)


def _statement_limit(stmt, default: int) -> int:
    clause = getattr(stmt, "_limit_clause", None)
    value = getattr(clause, "value", None)
    return int(value if value is not None else default)


def _event(source: str, dedupe_key: str) -> ObserverIntegrityEventInput:
    return ObserverIntegrityEventInput(
        event_type="observer_test_event",
        severity="warning",
        source=source,
        dedupe_key=dedupe_key,
        expected="expected",
        actual="actual",
        evidence={},
    )


def test_known_contamination_manifest_seed_rows_are_time_boxed():
    rows = integrity_module.load_known_contamination_manifest()

    assert rows
    assert all(row.get("expires_at") is not None for row in rows)


@pytest.mark.asyncio
async def test_run_scan_skips_resolve_for_incomplete_checker_scope(monkeypatch):
    repo = _FakeIntegrityRepo()
    service = ObserverIntegrityService(session=_FakeSession())
    service.repo = repo

    async def incomplete_operation_checker(_session, *, run_id=None):
        return integrity_module.ObserverIntegrityCheckResult(
            source=OPERATION_SOURCE,
            events=[_event(OPERATION_SOURCE, "operation:visible-page")],
            complete=False,
        )

    async def complete_protocol_checker(_session, *, run_id=None):
        return integrity_module.ObserverIntegrityCheckResult(
            source=PROTOCOL_SOURCE,
            events=[_event(PROTOCOL_SOURCE, "protocol:complete")],
            complete=True,
        )

    async def empty_checker(source):
        return integrity_module.ObserverIntegrityCheckResult(source=source, events=[], complete=True)

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", incomplete_operation_checker)
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", complete_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", lambda *_args, **_kwargs: empty_checker(RUNTIME_SOURCE))
    monkeypatch.setattr(integrity_module, "check_account_boundary", lambda *_args, **_kwargs: empty_checker(integrity_module.ACCOUNT_SOURCE))
    monkeypatch.setattr(integrity_module, "check_module_toolset", lambda *_args, **_kwargs: empty_checker(integrity_module.MODULE_TOOLSET_SOURCE))
    monkeypatch.setattr(integrity_module, "check_governance", lambda *_args, **_kwargs: empty_checker(integrity_module.GOVERNANCE_SOURCE))
    monkeypatch.setattr(integrity_module, "check_web_cabinet", lambda *_args, **_kwargs: empty_checker(integrity_module.WEB_CABINET_SOURCE))

    result = await service.run_scan(run_id="scan-scope-test")

    assert result.generated == 2
    assert OPERATION_SOURCE not in repo.resolved_sources
    assert PROTOCOL_SOURCE in repo.resolved_sources


@pytest.mark.asyncio
async def test_operation_lifecycle_limit_plus_one_is_complete_false_even_when_page_rows_filter_out():
    now = datetime.now(timezone.utc)
    operations = [
        SimpleNamespace(
            operation_id=f"op-{index:03d}",
            device_id=f"device-{index:03d}",
            ticket_id=f"ticket-{index:03d}",
            status="succeeded",
            kind="tool_call",
            tool_name="diagnose",
            trace_id=f"trace-{index:03d}",
            actor_role="support",
            queued_at=now,
            finished_at=now,
            canceled_at=None,
            result_event_id=None,
        )
        for index in range(OPERATION_QUERY_LIMIT + 1)
    ]

    class Session:
        def __init__(self) -> None:
            self.execute_calls = 0

        async def execute(self, stmt):
            self.execute_calls += 1
            limit = _statement_limit(stmt, OPERATION_QUERY_LIMIT)
            if self.execute_calls < 3:
                return _FakeExecuteResult([])
            return _FakeExecuteResult(operations[:limit])

        async def scalar(self, _stmt):
            return 1

    result = await check_operation_lifecycle(Session(), run_id="operation-limit-no-db")

    assert result.complete is False
    assert result.scanned_count == OPERATION_QUERY_LIMIT + 1
    assert result.events == []


@pytest.mark.asyncio
async def test_web_cabinet_limit_plus_one_is_complete_false_for_301_ticket_window():
    now = datetime.now(timezone.utc)
    tickets = [
        SimpleNamespace(
            ticket_id=f"web-ticket-{index:03d}",
            device_id=None,
            requester_account_mode="browser_no_device",
            custom_fields={"request_context": "requester_portal"},
            created_at=now,
        )
        for index in range(301)
    ]

    class Session:
        async def execute(self, stmt):
            limit = _statement_limit(stmt, 300)
            return _FakeExecuteResult(tickets[:limit])

        async def scalar(self, _stmt):
            return 1

    result = await check_web_cabinet(Session(), run_id="web-limit-no-db", limit=300)

    assert result.complete is False
    assert result.scanned_count == 301
    assert len(result.events) == 300


@pytest.mark.asyncio
async def test_runtime_presence_limit_plus_one_is_complete_false_for_501_devices():
    stale = datetime.now(timezone.utc) - timedelta(hours=1)
    devices = [
        SimpleNamespace(device_id=f"runtime-device-{index:03d}", last_seen_at=stale)
        for index in range(RUNTIME_QUERY_LIMIT + 1)
    ]

    class Session:
        async def execute(self, stmt):
            limit = _statement_limit(stmt, RUNTIME_QUERY_LIMIT)
            return _FakeExecuteResult(devices[:limit])

    class State:
        def is_agent_online(self, _device_id: str) -> bool:
            return True

    result = await check_runtime_presence(
        Session(),
        state=State(),
        run_id="runtime-limit-no-db",
        stale_after=timedelta(minutes=15),
    )

    assert result.complete is False
    assert result.scanned_count == RUNTIME_QUERY_LIMIT + 1
    assert len(result.events) == RUNTIME_QUERY_LIMIT


@pytest.mark.asyncio
async def test_run_scan_fails_closed_for_checker_without_completion_status(monkeypatch):
    repo = _FakeIntegrityRepo()
    service = ObserverIntegrityService(session=_FakeSession())
    service.repo = repo

    async def legacy_protocol_checker(_session, *, run_id=None):
        return [_event(PROTOCOL_SOURCE, "protocol:legacy-list")]

    async def complete_checker(source):
        return integrity_module.ObserverIntegrityCheckResult(source=source, events=[], complete=True)

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", lambda *_args, **_kwargs: complete_checker(OPERATION_SOURCE))
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", legacy_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", lambda *_args, **_kwargs: complete_checker(RUNTIME_SOURCE))
    monkeypatch.setattr(integrity_module, "check_account_boundary", lambda *_args, **_kwargs: complete_checker(integrity_module.ACCOUNT_SOURCE))
    monkeypatch.setattr(integrity_module, "check_module_toolset", lambda *_args, **_kwargs: complete_checker(integrity_module.MODULE_TOOLSET_SOURCE))
    monkeypatch.setattr(integrity_module, "check_governance", lambda *_args, **_kwargs: complete_checker(integrity_module.GOVERNANCE_SOURCE))
    monkeypatch.setattr(integrity_module, "check_web_cabinet", lambda *_args, **_kwargs: complete_checker(integrity_module.WEB_CABINET_SOURCE))

    result = await service.run_scan(run_id="legacy-list-checker-test")

    assert result.generated == 1
    assert PROTOCOL_SOURCE in result.incomplete_sources
    assert PROTOCOL_SOURCE not in repo.resolved_sources


@pytest.mark.asyncio
async def test_run_scan_isolates_failed_checker_and_does_not_resolve_its_source(monkeypatch):
    repo = _FakeIntegrityRepo()
    service = ObserverIntegrityService(session=_FakeSession())
    service.repo = repo

    async def failed_operation_checker(_session, *, run_id=None):
        raise RuntimeError("operation checker exploded")

    async def complete_protocol_checker(_session, *, run_id=None):
        return integrity_module.ObserverIntegrityCheckResult(
            source=PROTOCOL_SOURCE,
            events=[_event(PROTOCOL_SOURCE, "protocol:complete")],
            complete=True,
        )

    async def empty_checker(source):
        return integrity_module.ObserverIntegrityCheckResult(source=source, events=[], complete=True)

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", failed_operation_checker)
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", complete_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", lambda *_args, **_kwargs: empty_checker(RUNTIME_SOURCE))
    monkeypatch.setattr(integrity_module, "check_account_boundary", lambda *_args, **_kwargs: empty_checker(integrity_module.ACCOUNT_SOURCE))
    monkeypatch.setattr(integrity_module, "check_module_toolset", lambda *_args, **_kwargs: empty_checker(integrity_module.MODULE_TOOLSET_SOURCE))
    monkeypatch.setattr(integrity_module, "check_governance", lambda *_args, **_kwargs: empty_checker(integrity_module.GOVERNANCE_SOURCE))
    monkeypatch.setattr(integrity_module, "check_web_cabinet", lambda *_args, **_kwargs: empty_checker(integrity_module.WEB_CABINET_SOURCE))

    result = await service.run_scan(run_id="failed-checker-test")

    assert result.generated == 2
    assert result.failed_sources == [OPERATION_SOURCE]
    assert OPERATION_SOURCE in result.incomplete_sources
    assert OPERATION_SOURCE not in repo.resolved_sources
    assert PROTOCOL_SOURCE in repo.resolved_sources
    assert any(event.event_type == "observer_integrity_checker_failed" for event in repo.upserted_events)


@pytest.mark.asyncio
async def test_upsert_event_preserves_acknowledged_status_when_condition_persists():
    existing = SimpleNamespace(
        event_type="observer_test_event",
        severity="warning",
        source=PROTOCOL_SOURCE,
        status="acknowledged",
        detected_at=None,
        last_seen_at=None,
        resolved_at=None,
        occurrence_count=1,
        device_id=None,
        ticket_id=None,
        operation_id=None,
        command_id=None,
        device_outbox_id=None,
        outbox_id=None,
        trace_id=None,
        actor_role=None,
        expected="old expected",
        actual="old actual",
        evidence_json={},
        runbook=None,
        suppression_reason=None,
        run_id=None,
        updated_at=None,
    )
    repo = ObserverIntegrityRepo(_FakeSession())

    async def fake_get_by_dedupe_key(_dedupe_key):
        return existing

    repo.get_by_dedupe_key = fake_get_by_dedupe_key

    row = await repo.upsert_event(_event(PROTOCOL_SOURCE, "protocol:acknowledged"))

    assert row.status == "acknowledged"
    assert row.occurrence_count == 2
