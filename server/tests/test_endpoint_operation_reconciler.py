from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import ast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import EndpointOperationLink, Operation
from app.services.endpoint_operation_reconciler import (
    EndpointOperationReconciler,
    EndpointReconcileClaim,
    SqlAlchemyEndpointOperationReconcileStore,
    _REMOTE_TO_LOCAL,
    endpoint_operation_correlation_ref,
    endpoint_retry_delay_seconds,
)
from domain_ports.endpoint import (
    EndpointDeviceRef,
    EndpointOperationCorrelation,
    EndpointOperationCreateRequest,
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

    async def claim_ready(self, *, owner: str, now: datetime, limit: int, lease_seconds: int):
        return self.claims[:limit]

    async def commit(self, **values):
        self.committed.append(values)
        return True


class _Port:
    def __init__(self, outcome):
        self.outcome = outcome
        self.create_calls: list[tuple] = []

    async def create_operation(self, device, request, *, idempotency_key):
        self.create_calls.append((device, request, idempotency_key))
        return self.outcome

    async def read_operation(self, operation):
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
async def test_reconcile_unavailable_schedules_retry_without_legacy_dispatch() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    store = _ClaimStore(claims=[_claim()], committed=[])
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
    assert len(port.create_calls) == 1
    assert port.create_calls[0][2] == "helpdesk-endpoint-operation:11111111-1111-1111-1111-111111111111"
    assert port.create_calls[0][1].correlation.source_entity_id == endpoint_operation_correlation_ref(
        "11111111-1111-1111-1111-111111111111"
    )
    assert port.create_calls[0][1].correlation.source_entity_id != "ticket-1"
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
async def test_retryable_unavailable_preserves_current_local_progress() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    claim = _claim()
    claim = EndpointReconcileClaim(**(claim.__dict__ | {"local_status": "running", "local_phase": "endpoint_running"}))
    store = _ClaimStore(claims=[claim], committed=[])
    reconciler = EndpointOperationReconciler(
        endpoint_port=_Port(EndpointUnavailable(retryable=True)), store=store,
        mode="external", diagnostic_execution_mode="endpoint", owner="test-worker", now=lambda: now,
    )

    await reconciler.reconcile_once(limit=1)

    assert store.committed[0]["operation_status"] == "running"
    assert store.committed[0]["phase"] == "endpoint_running"


@pytest.mark.asyncio
async def test_nonretryable_unavailable_is_terminal_and_does_not_publish_without_change() -> None:
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    store = _ClaimStore(claims=[_claim()], committed=[])
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
        correlation=EndpointOperationCorrelation(
            source_entity_id=endpoint_operation_correlation_ref(claim.operation_id),
            request_id="11111111-1111-1111-1111-111111111111",
        ),
        result_available=True,
        safe_result=EndpointDiagnosticResultProjection(
            collected_at=now,
            processes=(EndpointDiagnosticProcessProjection(name="safe-process", state="running"),),
        ),
    )
    store = _ClaimStore(claims=[claim], committed=[])
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
