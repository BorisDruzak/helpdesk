from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repos.observer_integrity_repo import ObserverIntegrityEventInput, ObserverIntegrityRepo
from observer import integrity_service as integrity_module
from observer.checks.operation_lifecycle import SOURCE as OPERATION_SOURCE
from observer.checks.protocol_integrity import SOURCE as PROTOCOL_SOURCE
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
        return [_event(PROTOCOL_SOURCE, "protocol:complete")]

    async def empty_checker(*_args, **_kwargs):
        return []

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", incomplete_operation_checker)
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", complete_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", empty_checker)
    monkeypatch.setattr(integrity_module, "check_account_boundary", empty_checker)
    monkeypatch.setattr(integrity_module, "check_module_toolset", empty_checker)
    monkeypatch.setattr(integrity_module, "check_governance", empty_checker)
    monkeypatch.setattr(integrity_module, "check_web_cabinet", empty_checker)

    result = await service.run_scan(run_id="scan-scope-test")

    assert result.generated == 2
    assert OPERATION_SOURCE not in repo.resolved_sources
    assert PROTOCOL_SOURCE in repo.resolved_sources


@pytest.mark.asyncio
async def test_run_scan_isolates_failed_checker_and_does_not_resolve_its_source(monkeypatch):
    repo = _FakeIntegrityRepo()
    service = ObserverIntegrityService(session=_FakeSession())
    service.repo = repo

    async def failed_operation_checker(_session, *, run_id=None):
        raise RuntimeError("operation checker exploded")

    async def complete_protocol_checker(_session, *, run_id=None):
        return [_event(PROTOCOL_SOURCE, "protocol:complete")]

    async def empty_checker(*_args, **_kwargs):
        return []

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", failed_operation_checker)
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", complete_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", empty_checker)
    monkeypatch.setattr(integrity_module, "check_account_boundary", empty_checker)
    monkeypatch.setattr(integrity_module, "check_module_toolset", empty_checker)
    monkeypatch.setattr(integrity_module, "check_governance", empty_checker)
    monkeypatch.setattr(integrity_module, "check_web_cabinet", empty_checker)

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
