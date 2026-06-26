from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AgentRuntimeAudit, Device, ObserverIntegrityCheckRun, Operation, Ticket, TicketEvent
from app.repos.observer_integrity_repo import ObserverIntegrityEventInput, ObserverIntegrityRepo
from observer import integrity_service as integrity_module
from observer.checks.operation_lifecycle import QUERY_LIMIT as OPERATION_QUERY_LIMIT
from observer.checks.operation_lifecycle import SOURCE as OPERATION_SOURCE
from observer.checks.operation_lifecycle import check_operation_lifecycle
from observer.checks.protocol_integrity import SOURCE as PROTOCOL_SOURCE
from observer.checks.protocol_integrity import QUERY_LIMIT as PROTOCOL_QUERY_LIMIT
from observer.checks.protocol_integrity import check_protocol_integrity
from observer.checks.runtime_presence import check_runtime_presence
from observer.checks.types import ObserverIntegrityCheckResult
from observer.checks.web_cabinet import check_web_cabinet
from observer.integrity_service import ObserverIntegrityService


pytestmark = pytest.mark.db_cleanup("full")


class _OnlineState:
    def is_agent_online(self, _device_id: str) -> bool:
        return True


def _integrity_event(source: str, dedupe_key: str) -> ObserverIntegrityEventInput:
    return ObserverIntegrityEventInput(
        event_type="observer_test_event",
        severity="warning",
        source=source,
        dedupe_key=dedupe_key,
        expected="expected",
        actual="actual",
        evidence={},
    )


async def _complete_empty(source: str) -> ObserverIntegrityCheckResult:
    return ObserverIntegrityCheckResult(source=source, events=[], complete=True)


@pytest.mark.asyncio
async def test_operation_lifecycle_marks_incomplete_when_limit_plus_one_rows_are_filtered(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for index in range(OPERATION_QUERY_LIMIT + 1):
            operation_id = f"obs-limit-op-{index:03d}"
            ticket_id = f"obs-limit-ticket-{index:03d}"
            finished_at = now - timedelta(seconds=index)
            session.add(
                Operation(
                    operation_id=operation_id,
                    device_id=f"obs-device-{index:03d}",
                    ticket_id=ticket_id,
                    kind="tool_call",
                    tool_name="diagnose",
                    actor_role="support",
                    trace_id=f"obs-trace-{index:03d}",
                    status="succeeded",
                    queued_at=finished_at - timedelta(seconds=5),
                    finished_at=finished_at,
                )
            )
            if index < OPERATION_QUERY_LIMIT:
                session.add(
                    TicketEvent(
                        ticket_id=ticket_id,
                        device_id=f"obs-device-{index:03d}",
                        event_type="tool_call_result",
                        payload={},
                        operation_id=operation_id,
                        created_at=finished_at,
                    )
                )
        await session.commit()

    async with session_maker() as session:
        result = await check_operation_lifecycle(session, run_id="operation-limit-plus-one")

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert result.events == []


@pytest.mark.asyncio
async def test_web_cabinet_marks_incomplete_at_ticket_limit_plus_one(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with session_maker() as session:
        for index in range(301):
            session.add(
                Ticket(
                    ticket_id=f"obs-web-ticket-{index:03d}",
                    title=f"Observer web ticket {index}",
                    description="Observer completeness fixture",
                    status="new",
                    requester_id=f"requester-{index:03d}",
                    requester_account_mode="browser_no_device",
                    custom_fields={"request_context": "requester_portal"},
                    created_at=now - timedelta(seconds=index),
                    updated_at=now - timedelta(seconds=index),
                )
            )
        await session.commit()

    async with session_maker() as session:
        result = await check_web_cabinet(session, run_id="web-limit-plus-one", limit=300)

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert len(result.events) >= 300


@pytest.mark.asyncio
async def test_runtime_presence_marks_incomplete_at_device_limit_plus_one(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    stale = now - timedelta(hours=1)
    async with session_maker() as session:
        for index in range(501):
            session.add(
                Device(
                    device_id=f"obs-runtime-device-{index:03d}",
                    first_seen_at=stale,
                    last_seen_at=stale,
                    last_handshake_at=stale,
                    protocol_version="ws_ticket_v3",
                    agent_version="test",
                    capabilities={},
                )
            )
        await session.commit()

    async with session_maker() as session:
        result = await check_runtime_presence(
            session,
            state=_OnlineState(),
            run_id="runtime-limit-plus-one",
            stale_after=timedelta(minutes=15),
        )

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is False
    assert len(result.events) == 500


@pytest.mark.asyncio
async def test_protocol_integrity_scans_all_ack_pages_before_marking_complete(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    async with session_maker() as session:
        for index in range(PROTOCOL_QUERY_LIMIT + 1):
            session.add(
                AgentRuntimeAudit(
                    device_id=f"obs-protocol-device-{index:03d}",
                    event_type="outbox_ack_persisted",
                    severity="info",
                    source="observer_test",
                    details_json={
                        "audit_contract_version": 2,
                        "outbox_id": f"obs-protocol-outbox-{index:03d}",
                        "trace_id": f"obs-protocol-trace-{index:03d}",
                        "event_type": "tool_call_result",
                        "persisted_event_id": index + 1,
                        "duplicate": False,
                    },
                    created_at=now - timedelta(milliseconds=index),
                )
            )
        await session.commit()

    async with session_maker() as session:
        result = await check_protocol_integrity(session, run_id="protocol-paginated-ack")

    assert isinstance(result, ObserverIntegrityCheckResult)
    assert result.complete is True
    assert result.events == []
    assert result.scanned_count == PROTOCOL_QUERY_LIMIT + 1


@pytest.mark.asyncio
async def test_run_scan_resolves_only_current_missing_event_after_complete_db_scan(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    visible_key = "operation:fixed-visible-finding"
    outside_key = "operation:still-broken-outside-window"

    async with session_maker() as session:
        repo = ObserverIntegrityRepo(session)
        await repo.upsert_event(_integrity_event(OPERATION_SOURCE, visible_key))
        await repo.upsert_event(_integrity_event(OPERATION_SOURCE, outside_key))
        await session.commit()

    async def incomplete_operation_checker(_session, *, run_id=None):
        return ObserverIntegrityCheckResult(
            source=OPERATION_SOURCE,
            events=[],
            complete=False,
            scanned_count=OPERATION_QUERY_LIMIT + 1,
            limit=OPERATION_QUERY_LIMIT,
        )

    async def complete_operation_checker(_session, *, run_id=None):
        return ObserverIntegrityCheckResult(
            source=OPERATION_SOURCE,
            events=[_integrity_event(OPERATION_SOURCE, outside_key)],
            complete=True,
            scanned_count=1,
            limit=OPERATION_QUERY_LIMIT,
        )

    monkeypatch.setattr(
        integrity_module,
        "check_protocol_integrity",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.PROTOCOL_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_runtime_presence",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.RUNTIME_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_account_boundary",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.ACCOUNT_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_module_toolset",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.MODULE_TOOLSET_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_governance",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.GOVERNANCE_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_web_cabinet",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.WEB_CABINET_SOURCE),
    )

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", incomplete_operation_checker)
    async with session_maker() as session:
        incomplete_result = await ObserverIntegrityService(session).run_scan(run_id="resolve-window-incomplete")
        repo = ObserverIntegrityRepo(session)
        visible = await repo.get_by_dedupe_key(visible_key)
        outside = await repo.get_by_dedupe_key(outside_key)
        assert incomplete_result.resolved == 0
        assert OPERATION_SOURCE in incomplete_result.incomplete_sources
        assert visible is not None and visible.status == "active"
        assert outside is not None and outside.status == "active"
        await session.commit()

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", complete_operation_checker)
    async with session_maker() as session:
        complete_result = await ObserverIntegrityService(session).run_scan(run_id="resolve-window-complete")
        repo = ObserverIntegrityRepo(session)
        visible = await repo.get_by_dedupe_key(visible_key)
        outside = await repo.get_by_dedupe_key(outside_key)
        assert complete_result.resolved == 1
        assert OPERATION_SOURCE not in complete_result.incomplete_sources
        assert visible is not None and visible.status == "resolved"
        assert outside is not None and outside.status == "active"


@pytest.mark.asyncio
async def test_run_scan_persists_per_checker_reports(test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    async def complete_operation_checker(_session, *, run_id=None):
        return ObserverIntegrityCheckResult(
            source=OPERATION_SOURCE,
            events=[_integrity_event(OPERATION_SOURCE, "operation:report-visible")],
            complete=True,
            scanned_count=7,
            limit=OPERATION_QUERY_LIMIT,
        )

    async def degraded_runtime_checker(_session, *, state=None, run_id=None):
        return ObserverIntegrityCheckResult(
            source=integrity_module.RUNTIME_SOURCE,
            events=[],
            complete=False,
            scanned_count=501,
            limit=500,
        )

    async def failed_protocol_checker(_session, *, run_id=None):
        raise RuntimeError("protocol report failure")

    monkeypatch.setattr(integrity_module, "check_operation_lifecycle", complete_operation_checker)
    monkeypatch.setattr(integrity_module, "check_protocol_integrity", failed_protocol_checker)
    monkeypatch.setattr(integrity_module, "check_runtime_presence", degraded_runtime_checker)
    monkeypatch.setattr(
        integrity_module,
        "check_account_boundary",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.ACCOUNT_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_module_toolset",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.MODULE_TOOLSET_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_governance",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.GOVERNANCE_SOURCE),
    )
    monkeypatch.setattr(
        integrity_module,
        "check_web_cabinet",
        lambda *_args, **_kwargs: _complete_empty(integrity_module.WEB_CABINET_SOURCE),
    )

    async with session_maker() as session:
        result = await ObserverIntegrityService(session).run_scan(run_id="checker-report-db")
        rows = list(
            (
                await session.execute(
                    select(ObserverIntegrityCheckRun).where(
                        ObserverIntegrityCheckRun.scan_id == result.scan_id
                    )
                )
            )
            .scalars()
            .all()
        )

    reports = {row.source: row for row in rows}
    assert len(rows) == 7
    assert reports[OPERATION_SOURCE].status == "passed"
    assert reports[OPERATION_SOURCE].complete is True
    assert reports[OPERATION_SOURCE].generated_count == 1
    assert reports[OPERATION_SOURCE].active_count == 1
    assert reports[OPERATION_SOURCE].scanned_count == 7
    assert reports[OPERATION_SOURCE].limit_value == OPERATION_QUERY_LIMIT
    assert reports[integrity_module.RUNTIME_SOURCE].status == "degraded"
    assert reports[integrity_module.RUNTIME_SOURCE].complete is False
    assert reports[integrity_module.RUNTIME_SOURCE].scanned_count == 501
    assert reports[PROTOCOL_SOURCE].status == "failed"
    assert reports[PROTOCOL_SOURCE].error_type == "RuntimeError"
