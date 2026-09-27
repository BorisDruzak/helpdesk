"""PostgreSQL durability at the Helpdesk-to-Endpoint dispatch boundary."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import DiagnosticSession, DiagnosticStep, EndpointOperationLink, Operation, Ticket
from app.repos.endpoint_operation_links_repo import EndpointOperationLinksRepo
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceResolution
from app.services.endpoint_diagnostic_operation_service import (
    EndpointDiagnosticOperationRequest,
    EndpointDiagnosticOperationService,
    SqlAlchemyEndpointDiagnosticOperationStore,
    deterministic_endpoint_operation_id,
)
from app.services.endpoint_operation_reconciler import (
    EndpointOperationReconciler,
    SqlAlchemyEndpointOperationReconcileStore,
)
from domain_ports.endpoint import EndpointDeviceRef, EndpointOperationProjection, EndpointOperationRef


pytestmark = pytest.mark.db_cleanup("full")


class _WorkerCrash(BaseException):
    """Bypass recovery exactly as a process exit would, without exiting pytest."""


class _IdempotentProvider:
    """Models the published provider key contract, without executing an agent."""

    def __init__(self, now):
        self.now = now
        self.calls = []
        self.operations = {}

    async def create_operation(self, device, request, *, idempotency_key):
        self.calls.append((device, request, idempotency_key))
        if idempotency_key not in self.operations:
            self.operations[idempotency_key] = EndpointOperationProjection(
                operation=EndpointOperationRef(external_id=str(uuid.uuid4())),
                device=device, status="queued", created_at=self.now,
                deadline_at=None, completed_at=None, correlation=None,
                result_available=False,
            )
        return self.operations[idempotency_key]


async def _setup(test_engine, *, actor_id="support-fixture"):
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    async with maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id=None, title="Durability regression",
                           description="Synthetic fixture", status="queued"))
        await session.commit()
    actor = SimpleNamespace(actor_id=actor_id, actor_role="support")
    device_ref = str(uuid.uuid4())
    key = "durability-" + uuid.uuid4().hex
    operation_id = deterministic_endpoint_operation_id(
        actor_id=actor.actor_id, ticket_id=ticket_id, endpoint_device_ref=device_ref,
        idempotency_key=key,
    )
    store = SqlAlchemyEndpointDiagnosticOperationStore(maker)
    service = EndpointDiagnosticOperationService(
        access_service=SimpleNamespace(require_ticket_operation_access=AsyncMock()),
        device_resolver=SimpleNamespace(resolve_ticket=AsyncMock(return_value=
            EndpointDeviceReferenceResolution(status="resolved", device_ref=device_ref))),
        store=store, now=lambda: now,
    )
    request = EndpointDiagnosticOperationRequest(ticket_id=ticket_id, idempotency_key=key)
    return maker, ticket_id, operation_id, actor, service, request, now


@pytest.mark.asyncio
async def test_diagnostic_operation_preserves_maximum_length_ui_actor(test_engine):
    actor_id = "support-" + "x" * 92  # UiUser.user_login permits 100 characters.
    maker, ticket_id, operation_id, actor, service, request, _ = await _setup(
        test_engine, actor_id=actor_id,
    )
    result = await service.create(actor=actor, request=request)
    assert result.operation_id == operation_id
    assert await _counts(maker, ticket_id, operation_id) == (1, 1, 1, 1)
    async with maker() as session:
        diagnostic = (await session.execute(select(DiagnosticSession).where(
            DiagnosticSession.ticket_id == ticket_id))).scalar_one()
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert diagnostic.started_by_user_id == actor_id
        assert link.caller_actor_id == actor_id


async def _counts(maker, ticket_id, operation_id):
    async with maker() as session:
        return tuple([await session.scalar(select(func.count()).select_from(model).where(predicate))
                     for model, predicate in (
                         (Operation, Operation.operation_id == operation_id),
                         (DiagnosticSession, DiagnosticSession.ticket_id == ticket_id),
                         (DiagnosticStep, DiagnosticStep.ticket_id == ticket_id),
                         (EndpointOperationLink, EndpointOperationLink.operation_id == operation_id),
                     )])


def _worker(maker, provider, now, owner):
    return EndpointOperationReconciler(
        endpoint_port=provider, store=SqlAlchemyEndpointOperationReconcileStore(maker),
        mode="external", diagnostic_execution_mode="endpoint", owner=owner,
        now=lambda: now, lease_seconds=30,
    )


@pytest.mark.asyncio
async def test_failed_local_operation_trace_prevents_remote_dispatch_and_allows_retry(test_engine, monkeypatch):
    maker, ticket_id, operation_id, actor, service, request, now = await _setup(test_engine)
    provider = _IdempotentProvider(now)
    original = EndpointOperationLinksRepo.create_pending

    async def fail_after_link_write(self, **values):
        await original(self, **values)
        raise RuntimeError("Synthetic local trace failure")

    with monkeypatch.context() as patch:
        patch.setattr(EndpointOperationLinksRepo, "create_pending", fail_after_link_write)
        with pytest.raises(RuntimeError, match="Synthetic local trace failure"):
            await service.create(actor=actor, request=request)

    assert await _counts(maker, ticket_id, operation_id) == (0, 0, 0, 0)
    assert await _worker(maker, provider, now, "failed-write-worker").reconcile_once(limit=1) == 0
    assert provider.calls == []

    result = await service.create(actor=actor, request=request)
    assert result.operation_id == operation_id
    assert await _counts(maker, ticket_id, operation_id) == (1, 1, 1, 1)
    assert await _worker(maker, provider, now, "retry-worker").reconcile_once(limit=1) == 1
    assert len(provider.calls) == 1
    assert isinstance(provider.calls[0][0], EndpointDeviceRef)
    async with maker() as session:
        operation = await session.get(Operation, operation_id)
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert operation.actor_role == actor.actor_role
        assert link.caller_actor_id == actor.actor_id
        assert link.endpoint_operation_ref is not None


@pytest.mark.asyncio
async def test_worker_crash_after_remote_create_replays_same_key_after_lease_expiry(test_engine, monkeypatch):
    maker, ticket_id, operation_id, actor, service, request, now = await _setup(test_engine)
    await service.create(actor=actor, request=request)
    provider = _IdempotentProvider(now)
    worker = _worker(maker, provider, now, "crashing-worker")

    async def crash_before_projection_commit(**_values):
        raise _WorkerCrash()

    monkeypatch.setattr(worker._store, "commit", crash_before_projection_commit)
    with pytest.raises(_WorkerCrash):
        await worker.reconcile_once(limit=1)
    assert len(provider.calls) == 1
    async with maker() as session:
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert link.endpoint_operation_ref is None
        assert link.lease_owner.startswith("crashing-worker:")
        assert link.lease_until == now + timedelta(seconds=30)
        persisted_key = link.create_idempotency_key

    # A separate worker/store reads only the persisted state after lease expiry.
    restarted = _worker(maker, provider, now + timedelta(seconds=31), "restarted-worker")
    assert await restarted.reconcile_once(limit=1) == 1
    assert [call[2] for call in provider.calls] == [persisted_key, persisted_key]
    assert len(provider.operations) == 1
    assert await _counts(maker, ticket_id, operation_id) == (1, 1, 1, 1)
    async with maker() as session:
        link = (await session.execute(select(EndpointOperationLink).where(
            EndpointOperationLink.operation_id == operation_id))).scalar_one()
        assert link.endpoint_operation_ref == provider.operations[persisted_key].operation.external_id
        assert link.lease_owner is None
