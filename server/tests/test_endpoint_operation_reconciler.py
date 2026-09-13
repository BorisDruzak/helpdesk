from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    DiagnosticEvidence,
    DiagnosticSession,
    DiagnosticStep,
    EndpointOperationLink,
    Operation,
    Ticket,
)
from app.services.endpoint_operation_reconciler import (
    EndpointOperationReconciler,
    EndpointOperationReconcilerRunner,
    EndpointReconcileClaim,
    SqlAlchemyEndpointOperationReconcileStore,
    _REMOTE_TO_LOCAL,
    endpoint_operation_correlation_ref,
    endpoint_retry_delay_seconds,
)
from domain_ports.endpoint import (
    EndpointDeviceRef,
    EndpointOperationProjection,
    EndpointOperationRef,
    EndpointDiagnosticResultProjection,
    EndpointDiagnosticProcessProjection,
    EndpointUnavailable,
)


pytestmark = pytest.mark.db_cleanup("observer_diagnostics")


@dataclass
class _ClaimStore:
    claims: list[EndpointReconcileClaim]
    committed: list[dict]
    unexpected_failures: list[dict]
    terminal_session_repair_limits: list[int] = field(default_factory=list)

    async def claim_ready(self, *, owner: str, now: datetime, limit: int, lease_seconds: int):
        return [self.claims.pop(0)] if self.claims and limit == 1 else []

    async def commit(self, **values):
        self.committed.append(values)
        return True

    async def record_unexpected_failure(self, **values):
        self.unexpected_failures.append(values)
        return True

    async def complete_terminal_diagnostic_sessions(self, *, limit: int) -> int:
        self.terminal_session_repair_limits.append(limit)
        return 0


class _Port:
    def __init__(self, outcome):
        self.outcome = outcome
        self.create_calls: list[tuple] = []

    async def create_operation(self, device, request, *, idempotency_key):
        self.create_calls.append((device, request, idempotency_key))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def read_operation(self, operation):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _claim() -> EndpointReconcileClaim:
    return EndpointReconcileClaim(
        operation_id="11111111-1111-1111-1111-111111111111",
        ticket_id="ticket-1",
        endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref=None,
        attempt_count=0,
        remote_status="create_pending",
        create_idempotency_key="helpdesk-endpoint-operation:11111111-1111-1111-1111-111111111111",
        correlation_ref=endpoint_operation_correlation_ref("11111111-1111-1111-1111-111111111111"),
    )


def _pending_link(*, operation_id: str, now: datetime) -> EndpointOperationLink:
    return EndpointOperationLink(
        link_id="22222222-2222-2222-2222-222222222222",
        operation_id=operation_id,
        endpoint_device_ref="endpoint-device-1",
        capability_code="context.diagnostic.collect",
        create_idempotency_key="helpdesk-endpoint-operation:lease-test",
        correlation_ref=endpoint_operation_correlation_ref(operation_id),
        remote_status="create_pending",
        attempt_count=0,
        next_attempt_at=now,
    )


@pytest.mark.asyncio
async def test_sql_reconcile_store_claims_ready_link_once_across_sessions(test_engine) -> None:
    """The PostgreSQL lease must let just one worker claim the same ready link."""

    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    operation_id = "11111111-1111-1111-1111-111111111111"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Operation(
                operation_id=operation_id,
                device_id="local-ticket-device",
                ticket_id="33333333-3333-3333-3333-333333333333",
                kind="endpoint_diagnostic",
                actor_role="system",
                trace_id="44444444-4444-4444-4444-444444444444",
                status="queued",
                queued_at=now,
            )
        )
        await session.flush()
        session.add(_pending_link(operation_id=operation_id, now=now))
        await session.commit()

    first_store = SqlAlchemyEndpointOperationReconcileStore(session_maker)
    second_store = SqlAlchemyEndpointOperationReconcileStore(session_maker)
    start = asyncio.Barrier(2)

    async def claim(store: SqlAlchemyEndpointOperationReconcileStore, owner: str):
        await start.wait()
        return await store.claim_ready(owner=owner, now=now, limit=1, lease_seconds=30)

    first, second = await asyncio.gather(claim(first_store, "worker-a"), claim(second_store, "worker-b"))

    assert sorted(map(len, (first, second))) == [0, 1]
    claimed = (first or second)[0]
    assert claimed.operation_id == operation_id
    assert claimed.lease_token is not None
    assert claimed.lease_token.startswith(("worker-a:", "worker-b:"))


@pytest.mark.asyncio
async def test_sql_store_records_unexpected_failure_only_for_live_claim(test_engine) -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    operation_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            Operation(
                operation_id=operation_id,
                device_id="local-ticket-device",
                ticket_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                kind="endpoint_diagnostic",
                actor_role="system",
                trace_id="cccccccc-cccc-cccc-cccc-cccccccccccc",
                status="queued",
                queued_at=now,
                phase="endpoint_create_pending",
            )
        )
        await session.flush()
        session.add(_pending_link(operation_id=operation_id, now=now))
        await session.commit()

    store = SqlAlchemyEndpointOperationReconcileStore(session_maker)
    claim = (await store.claim_ready(owner="worker-a", now=now, limit=1, lease_seconds=30))[0]
    retry_at = now + timedelta(seconds=2)
    assert await store.record_unexpected_failure(
        claim=claim,
        error_code="endpoint_reconcile_unexpected",
        next_attempt_at=retry_at,
    )
    stale = EndpointReconcileClaim(**(claim.__dict__ | {"lease_token": "stale"}))
    assert not await store.record_unexpected_failure(
        claim=stale,
        error_code="endpoint_reconcile_unexpected",
        next_attempt_at=retry_at,
    )

    async with session_maker() as session:
        link = await session.get(EndpointOperationLink, "22222222-2222-2222-2222-222222222222")
        operation = await session.get(Operation, operation_id)

    assert link is not None and operation is not None
    assert link.attempt_count == 1
    assert link.last_error_code == "endpoint_reconcile_unexpected"
    assert link.next_attempt_at == retry_at
    assert link.lease_owner is None and link.lease_until is None
    assert operation.status == "queued"
    assert operation.phase == "endpoint_create_pending"
    assert operation.error_code == "endpoint_reconcile_unexpected"


@pytest.mark.asyncio
async def test_sql_store_persists_completed_session_with_autoflush_disabled(test_engine) -> None:
    """The production sessionmaker must not leave the operation session draft."""

    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    operation_id = "78787878-7878-7878-7878-787878787878"
    ticket_id = "89898989-8989-8989-8989-898989898989"
    session_id = "abababab-abab-abab-abab-abababababab"
    step_id = "cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="local-ticket-device",
                title="Endpoint diagnostic",
                description="Endpoint diagnostic",
                status="queued",
                requester_id="test-requester",
            )
        )
        await session.flush()
        operation = Operation(
            operation_id=operation_id,
            device_id="local-ticket-device",
            ticket_id=ticket_id,
            kind="endpoint_operation",
            actor_role="system",
            trace_id="efefefef-efef-efef-efef-efefefefefef",
            status="queued",
            phase="endpoint_create_pending",
            queued_at=now,
        )
        diagnostic_session = DiagnosticSession(
            id=session_id,
            ticket_id=ticket_id,
            status="draft",
            trigger_source="endpoint_platform",
        )
        step = DiagnosticStep(
            id=step_id,
            session_id=session_id,
            ticket_id=ticket_id,
            step_type="endpoint_operation",
            capability_id="context.diagnostic.collect",
            operation_id=operation_id,
            status="pending",
        )
        session.add_all((operation, diagnostic_session))
        await session.flush()
        session.add(step)
        await session.flush()
        link = EndpointOperationLink(
            link_id="dededede-dede-dede-dede-dededededede",
            operation_id=operation_id,
            endpoint_device_ref="endpoint-device-1",
            capability_code="context.diagnostic.collect",
            create_idempotency_key="helpdesk-endpoint-operation:db-session-complete",
            correlation_ref=endpoint_operation_correlation_ref(operation_id),
            remote_status="create_pending",
            attempt_count=0,
            next_attempt_at=now,
            diagnostic_session_id=session_id,
            diagnostic_step_id=step_id,
        )
        session.add(link)
        await session.commit()

    store = SqlAlchemyEndpointOperationReconcileStore(session_maker)
    claim = (await store.claim_ready(owner="worker-a", now=now, limit=1, lease_seconds=30))[0]
    safe_result = EndpointDiagnosticResultProjection(
        collected_at=now,
        processes=(EndpointDiagnosticProcessProjection(name="safe-process", state="running"),),
    ).model_dump(mode="json")

    assert await store.commit(
        claim=claim,
        endpoint_operation_ref="endpoint-operation-db-session-complete",
        remote_status="succeeded",
        operation_status="succeeded",
        phase="endpoint_succeeded",
        error_code=None,
        safe_result_snapshot=safe_result,
        next_attempt_at=now,
    )

    async with session_maker() as session:
        persisted_session = await session.get(DiagnosticSession, session_id)
        persisted_step = await session.get(DiagnosticStep, step_id)
        evidence = await session.scalar(
            select(DiagnosticEvidence).where(
                DiagnosticEvidence.ticket_id == ticket_id,
                DiagnosticEvidence.source_type == "endpoint_platform",
            )
        )

    assert persisted_session is not None and persisted_session.status == "completed"
    assert persisted_step is not None and persisted_step.status == "completed"
    assert evidence is not None


@pytest.mark.asyncio
async def test_sql_store_completes_previously_terminal_diagnostic_session(test_engine) -> None:
    """A completed operation repairs only its unfinished linked session."""

    now = datetime(2026, 8, 23, tzinfo=timezone.utc)
    operation_id = "78787878-7878-7878-7878-787878787879"
    ticket_id = "89898989-8989-8989-8989-898989898990"
    session_id = "abababab-abab-abab-abab-abababababac"
    step_id = "cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdce"
    remote_ref = "endpoint-operation-complete-repair"
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    async with session_maker() as session:
        session.add(
            Ticket(
                ticket_id=ticket_id,
                device_id="local-ticket-device",
                title="Endpoint diagnostic",
                description="Endpoint diagnostic",
                status="queued",
                requester_id="test-requester",
            )
        )
        await session.flush()
        operation = Operation(
            operation_id=operation_id,
            device_id="local-ticket-device",
            ticket_id=ticket_id,
            kind="endpoint_operation",
            actor_role="system",
            trace_id="efefefef-efef-efef-efef-efefefefeff0",
            status="succeeded",
            phase="endpoint_succeeded",
            queued_at=now,
            finished_at=now,
        )
        diagnostic_session = DiagnosticSession(
            id=session_id,
            ticket_id=ticket_id,
            status="draft",
            trigger_source="endpoint_platform",
        )
        step = DiagnosticStep(
            id=step_id,
            session_id=session_id,
            ticket_id=ticket_id,
            step_type="endpoint_operation",
            capability_id="context.diagnostic.collect",
            operation_id=operation_id,
            status="completed",
            finished_at=now,
        )
        session.add_all((operation, diagnostic_session))
        await session.flush()
        session.add(step)
        await session.flush()
        session.add_all(
            (
                EndpointOperationLink(
                    link_id="dededede-dede-dede-dede-dedededededf",
                    operation_id=operation_id,
                    endpoint_device_ref="endpoint-device-1",
                    endpoint_operation_ref=remote_ref,
                    capability_code="context.diagnostic.collect",
                    create_idempotency_key="helpdesk-endpoint-operation:db-session-repair",
                    correlation_ref=endpoint_operation_correlation_ref(operation_id),
                    remote_status="succeeded",
                    safe_result_snapshot_json={"kind": "safe_system_probe", "ok": True},
                    attempt_count=0,
                    next_attempt_at=now,
                    diagnostic_session_id=session_id,
                    diagnostic_step_id=step_id,
                ),
                DiagnosticEvidence(
                    id="edededed-eded-eded-eded-edededededed",
                    ticket_id=ticket_id,
                    session_id=session_id,
                    step_id=step_id,
                    source_type="endpoint_platform",
                    source_id=remote_ref,
                    provider_id="endpoint_platform",
                    capability_id="context.diagnostic.collect",
                    kind="diagnostic_result",
                    domain="diagnostics",
                    perspective="endpoint_platform",
                    title="Endpoint diagnostic collection",
                    summary="Endpoint diagnostic collection completed",
                    status="succeeded",
                    normalized_payload={"kind": "safe_system_probe", "ok": True},
                    redaction_level="endpoint_safe_projection",
                    tags=[],
                ),
            )
        )
        await session.commit()

    store = SqlAlchemyEndpointOperationReconcileStore(session_maker)
    assert await store.complete_terminal_diagnostic_sessions(limit=1) == 1

    async with session_maker() as session:
        diagnostic_session = await session.get(DiagnosticSession, session_id)
        evidence = (
            await session.execute(
                select(DiagnosticEvidence).where(DiagnosticEvidence.ticket_id == ticket_id)
            )
        ).scalars().all()

    assert diagnostic_session is not None
    assert diagnostic_session.status == "completed"
    assert diagnostic_session.finished_at is not None
    assert len(evidence) == 1


def test_retry_delay_has_bounded_jitter_and_caps_at_five_minutes() -> None:
    assert endpoint_retry_delay_seconds(0, random=lambda: 0.0) == 2.0
    assert endpoint_retry_delay_seconds(4, random=lambda: 1.0) == 66.0
    assert endpoint_retry_delay_seconds(100, random=lambda: 1.0) == 300.0


def test_remote_statuses_have_the_exact_local_operation_and_phase_projection() -> None:
    assert _REMOTE_TO_LOCAL == {
        "queued": ("queued", "endpoint_queued"),
        "delivered": ("sent", "endpoint_delivered"),
        "acknowledged": ("accepted", "endpoint_acknowledged"),
        "running": ("running", "endpoint_running"),
        "succeeded": ("succeeded", "endpoint_succeeded"),
        "failed": ("failed", "endpoint_failed"),
        "canceled": ("canceled", "endpoint_canceled"),
        "expired": ("timed_out", "endpoint_expired"),
    }


@pytest.mark.no_db
def test_endpoint_services_have_no_legacy_agent_runtime_imports() -> None:
    services = Path(__file__).parents[1] / "app" / "services"
    forbidden = {
        "websocket.protocol",
        "websocket.agent_handler",
        "state_manager",
        "device_outbox_repo",
        "tools.service",
        "pc_agent",
        "remote_assist",
        "auth.agent",
        "auth.token",
    }
    for path in (
        services / "endpoint_diagnostic_operation_service.py",
        services / "endpoint_operation_reconciler.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        } | {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert not any(
            imported == blocked or imported.startswith(f"{blocked}.")
            for imported in imports
            for blocked in forbidden
        )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_reconcile_unavailable_schedules_retry_without_legacy_dispatch() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    store = _ClaimStore(claims=[_claim()], committed=[], unexpected_failures=[])
    port = _Port(EndpointUnavailable())
    published: list[str] = []
    reconciler = EndpointOperationReconciler(
        endpoint_port=port,
        store=store,
        mode="external",
        diagnostic_execution_mode="endpoint",
        owner="test-worker",
        now=lambda: now,
        random=lambda: 0.0,
        publish_after_commit=published.append,
    )

    processed = await reconciler.reconcile_once(limit=1)

    assert processed == 1
    assert store.terminal_session_repair_limits == [1]
    assert len(port.create_calls) == 1
    assert port.create_calls[0][2] == "helpdesk-endpoint-operation:11111111-1111-1111-1111-111111111111"
    assert port.create_calls[0][1].correlation is None
    assert store.committed == [
        {
            "claim": _claim(),
            "endpoint_operation_ref": None,
            "remote_status": "create_pending",
            "operation_status": "queued",
            "phase": "endpoint_create_pending",
            "error_code": "endpoint_unavailable",
            "safe_result_snapshot": None,
            "next_attempt_at": now + timedelta(seconds=2),
        }
    ]
    assert published == ["11111111-1111-1111-1111-111111111111"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_retryable_unavailable_preserves_current_local_progress() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    claim = _claim()
    claim = EndpointReconcileClaim(**(claim.__dict__ | {"local_status": "running", "local_phase": "endpoint_running"}))
    store = _ClaimStore(claims=[claim], committed=[], unexpected_failures=[])
    reconciler = EndpointOperationReconciler(
        endpoint_port=_Port(EndpointUnavailable(retryable=True)), store=store,
        mode="external", diagnostic_execution_mode="endpoint", owner="test-worker", now=lambda: now,
    )

    await reconciler.reconcile_once(limit=1)

    assert store.committed[0]["operation_status"] == "running"
    assert store.committed[0]["phase"] == "endpoint_running"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_nonretryable_unavailable_is_terminal_and_does_not_publish_without_change() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    store = _ClaimStore(claims=[_claim()], committed=[], unexpected_failures=[])
    published: list[str] = []
    reconciler = EndpointOperationReconciler(
        endpoint_port=_Port(EndpointUnavailable(retryable=False)), store=store,
        mode="external", diagnostic_execution_mode="endpoint", owner="test-worker",
        now=lambda: now, publish_after_commit=published.append,
    )

    await reconciler.reconcile_once(limit=1)

    assert store.committed[0]["operation_status"] == "failed"
    assert store.committed[0]["phase"] == "endpoint_failed"
    assert published == ["11111111-1111-1111-1111-111111111111"]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ui_publication_failure_does_not_undo_committed_claim() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    store = _ClaimStore(claims=[_claim()], committed=[], unexpected_failures=[])

    async def fail_publication(_operation_id: str) -> None:
        raise RuntimeError("UI unavailable")

    reconciler = EndpointOperationReconciler(
        endpoint_port=_Port(EndpointUnavailable()),
        store=store,
        mode="external",
        diagnostic_execution_mode="endpoint",
        owner="test-worker",
        now=lambda: now,
        random=lambda: 0.0,
        publish_after_commit=fail_publication,
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert len(store.committed) == 1
    assert store.committed[0]["operation_status"] == "queued"
    assert store.unexpected_failures == []


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_success_persists_only_validated_safe_snapshot_and_remote_ref() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    claim = _claim()
    projection = EndpointOperationProjection(
        operation=EndpointOperationRef(external_id="endpoint-operation-1"),
        device=EndpointDeviceRef(external_id=claim.endpoint_device_ref),
        status="succeeded",
        created_at=now,
        deadline_at=None,
        completed_at=now,
        correlation=None,
        result_available=True,
        safe_result=EndpointDiagnosticResultProjection(
            collected_at=now,
            processes=(EndpointDiagnosticProcessProjection(name="safe-process", state="running"),),
        ),
    )
    store = _ClaimStore(claims=[claim], committed=[], unexpected_failures=[])
    reconciler = EndpointOperationReconciler(
        endpoint_port=_Port(projection),
        store=store,
        mode="external",
        diagnostic_execution_mode="endpoint",
        owner="test-worker",
        now=lambda: now,
    )

    await reconciler.reconcile_once(limit=1)

    committed = store.committed[0]
    assert committed["endpoint_operation_ref"] == "endpoint-operation-1"
    assert committed["remote_status"] == "succeeded"
    assert committed["operation_status"] == "succeeded"
    assert committed["safe_result_snapshot"] == {
        "profile": "diagnostic_v1",
        "collected_at": "2026-08-17T00:00:00Z",
        "reason": "Диагностика по обращению",
        "warnings": [],
        "processes": [{"name": "safe-process", "state": "running"}],
        "log_excerpt": None,
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_one_unexpected_claim_failure_does_not_stop_following_claims() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    first = _claim()
    second = EndpointReconcileClaim(**(first.__dict__ | {"operation_id": "22222222-2222-2222-2222-222222222222"}))
    store = _ClaimStore(claims=[first, second], committed=[], unexpected_failures=[])

    class FlakyPort(_Port):
        def __init__(self) -> None:
            super().__init__(EndpointUnavailable())
            self.calls = 0

        async def create_operation(self, device, request, *, idempotency_key):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("unexpected")
            return await super().create_operation(device, request, idempotency_key=idempotency_key)

    reconciler = EndpointOperationReconciler(endpoint_port=FlakyPort(), store=store, mode="external", diagnostic_execution_mode="endpoint", owner="test", now=lambda: now, random=lambda: 0.0)
    assert await reconciler.reconcile_once(limit=2) == 2
    assert store.unexpected_failures == [
        {
            "claim": first,
            "error_code": "endpoint_reconcile_unexpected",
            "next_attempt_at": now + timedelta(seconds=2),
        }
    ]
    assert [value["claim"].operation_id for value in store.committed] == [second.operation_id]


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_runner_survives_unexpected_reconcile_failure() -> None:
    completed = asyncio.Event()

    class FlakyReconciler:
        def __init__(self) -> None:
            self.calls = 0

        async def reconcile_once(self, *, limit: int) -> int:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("unexpected")
            completed.set()
            return 0

    reconciler = FlakyReconciler()
    runner = EndpointOperationReconcilerRunner(
        reconciler, interval_seconds=0.01, batch_size=1
    )
    runner.start()
    await asyncio.wait_for(completed.wait(), timeout=1)
    await runner.stop()
    assert reconciler.calls >= 2
