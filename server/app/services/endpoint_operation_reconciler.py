"""Lease-based projection of Endpoint operations into local Helpdesk state."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from sqlalchemy import or_, select

from domain_ports.endpoint import (
    EndpointConflict,
    EndpointDeviceRef,
    EndpointDiagnosticParameters,
    EndpointDiagnosticResultProjection,
    EndpointForbidden,
    EndpointInvalidProjection,
    EndpointNotFound,
    EndpointOperationCorrelation,
    EndpointOperationCreateRequest,
    EndpointOperationProjection,
    EndpointOperationRef,
    EndpointPort,
    EndpointUnauthorized,
    EndpointUnavailable,
)

from app.services.endpoint_diagnostic_operation_service import (
    ENDPOINT_DIAGNOSTIC_CAPABILITY,
    ENDPOINT_DIAGNOSTIC_REASON,
)
from app.db.models import DiagnosticEvidence, DiagnosticSession, DiagnosticStep, EndpointOperationLink, Operation


_TERMINAL_LOCAL = frozenset({"succeeded", "failed", "timed_out", "canceled"})
_TERMINAL_REMOTE = frozenset({"succeeded", "failed", "canceled", "expired"})
_REMOTE_TO_LOCAL: dict[str, tuple[str, str]] = {
    "queued": ("queued", "endpoint_queued"),
    "delivered": ("sent", "endpoint_delivered"),
    "acknowledged": ("accepted", "endpoint_acknowledged"),
    "running": ("running", "endpoint_running"),
    "succeeded": ("succeeded", "endpoint_succeeded"),
    "failed": ("failed", "endpoint_failed"),
    "canceled": ("canceled", "endpoint_canceled"),
    "expired": ("timed_out", "endpoint_expired"),
}
_LOCAL_PROGRESS = {"queued": 0, "sent": 1, "accepted": 2, "running": 3}


@dataclass(frozen=True)
class EndpointReconcileClaim:
    operation_id: str
    ticket_id: str
    endpoint_device_ref: str
    endpoint_operation_ref: str | None
    attempt_count: int
    remote_status: str
    create_idempotency_key: str
    local_status: str = "queued"
    local_phase: str | None = "endpoint_create_pending"
    lease_token: str = ""


class EndpointOperationReconcileStore(Protocol):
    async def claim_ready(
        self, *, owner: str, now: datetime, limit: int, lease_seconds: int
    ) -> list[EndpointReconcileClaim]: ...

    async def commit(
        self,
        *,
        claim: EndpointReconcileClaim,
        endpoint_operation_ref: str | None,
        remote_status: str,
        operation_status: str,
        phase: str,
        error_code: str | None,
        safe_result_snapshot: dict[str, Any] | None,
        next_attempt_at: datetime,
    ) -> bool: ...


def endpoint_retry_delay_seconds(attempt_count: int, *, random: Callable[[], float]) -> float:
    """Bounded 2/5/15/30/60 second retry schedule with one-sided <=10% jitter."""

    index = max(attempt_count, 0)
    initial = (2, 5, 15, 30, 60)
    base = initial[index] if index < len(initial) else min(300, 60 * 2 ** (index - 4))
    return min(300.0, base * (1.0 + max(0.0, min(random(), 1.0)) * 0.1))


def endpoint_operation_correlation_ref(operation_id: str) -> str:
    """Non-reversible opaque trace ref; Helpdesk entity identifiers never cross the port."""

    return str(uuid5(NAMESPACE_URL, f"helpdesk-endpoint-correlation:{operation_id}"))


class EndpointOperationReconciler:
    """Performs one short claim, remote call and short commit for each link."""

    def __init__(
        self,
        *,
        endpoint_port: EndpointPort,
        store: EndpointOperationReconcileStore,
        mode: str,
        diagnostic_execution_mode: str,
        owner: str,
        now: Callable[[], datetime] | None = None,
        random: Callable[[], float] | None = None,
        publish_after_commit: Callable[[str], Awaitable[None] | None] | None = None,
        lease_seconds: int = 30,
    ) -> None:
        self._endpoint_port = endpoint_port
        self._store = store
        self._mode = mode
        self._diagnostic_execution_mode = diagnostic_execution_mode
        self._owner = owner
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._random = random or __import__("random").random
        self._publish_after_commit = publish_after_commit
        self._lease_seconds = lease_seconds

    @property
    def enabled(self) -> bool:
        return self._mode == "external" and self._diagnostic_execution_mode == "endpoint"

    async def reconcile_once(self, *, limit: int) -> int:
        if not self.enabled or limit < 1:
            return 0
        now = self._aware_now()
        claims = await self._store.claim_ready(
            owner=self._owner, now=now, limit=limit, lease_seconds=self._lease_seconds
        )
        for claim in claims:
            await self._reconcile_claim(claim)
        return len(claims)

    async def _reconcile_claim(self, claim: EndpointReconcileClaim) -> None:
        # There is intentionally no database session/transaction across this await.
        if claim.endpoint_operation_ref:
            outcome = await self._endpoint_port.read_operation(
                EndpointOperationRef(external_id=claim.endpoint_operation_ref)
            )
        else:
            request = EndpointOperationCreateRequest(
                parameters=EndpointDiagnosticParameters(reason=ENDPOINT_DIAGNOSTIC_REASON),
                correlation=EndpointOperationCorrelation(
                    source_entity_id=endpoint_operation_correlation_ref(claim.operation_id),
                    request_id=UUID(claim.operation_id),
                ),
            )
            outcome = await self._endpoint_port.create_operation(
                EndpointDeviceRef(external_id=claim.endpoint_device_ref),
                request,
                idempotency_key=claim.create_idempotency_key,
            )
        now = self._aware_now()
        if isinstance(outcome, EndpointUnavailable):
            if not outcome.retryable:
                await self._commit_and_publish(
                    claim=claim,
                    endpoint_operation_ref=None,
                    remote_status="failed",
                    operation_status="failed",
                    phase="endpoint_failed",
                    error_code=outcome.code,
                    safe_result_snapshot=None,
                    next_attempt_at=now,
                )
                return
            await self._commit_and_publish(
                claim=claim,
                endpoint_operation_ref=None,
                remote_status=claim.remote_status,
                operation_status=claim.local_status,
                phase=claim.local_phase or "endpoint_create_pending",
                error_code=outcome.code,
                safe_result_snapshot=None,
                next_attempt_at=now + timedelta(
                    seconds=endpoint_retry_delay_seconds(claim.attempt_count, random=self._random)
                ),
            )
            return
        if isinstance(
            outcome,
            (EndpointUnauthorized, EndpointForbidden, EndpointNotFound, EndpointConflict, EndpointInvalidProjection),
        ):
            await self._commit_and_publish(
                claim=claim,
                endpoint_operation_ref=None,
                remote_status="failed",
                operation_status="failed",
                phase="endpoint_failed",
                error_code=outcome.code,
                safe_result_snapshot=None,
                next_attempt_at=now,
            )
            return
        if not isinstance(outcome, EndpointOperationProjection):
            # EndpointPort's union is closed; unknown objects are not trusted.
            await self._commit_and_publish(
                claim=claim,
                endpoint_operation_ref=None,
                remote_status="failed",
                operation_status="failed",
                phase="endpoint_failed",
                error_code="endpoint_invalid_projection",
                safe_result_snapshot=None,
                next_attempt_at=now,
            )
            return
        status, phase = _REMOTE_TO_LOCAL[outcome.status]
        if (
            outcome.device.external_id != claim.endpoint_device_ref
            or outcome.correlation.source_entity_id != endpoint_operation_correlation_ref(claim.operation_id)
            or outcome.correlation.request_id != UUID(claim.operation_id)
        ):
            await self._commit_and_publish(
                claim=claim,
                endpoint_operation_ref=None,
                remote_status="failed",
                operation_status="failed",
                phase="endpoint_failed",
                error_code="endpoint_invalid_projection",
                safe_result_snapshot=None,
                next_attempt_at=now,
            )
            return
        safe_snapshot = _validated_safe_success_snapshot(outcome)
        await self._commit_and_publish(
            claim=claim,
            endpoint_operation_ref=outcome.operation.external_id,
            remote_status=outcome.status,
            operation_status=status,
            phase=phase,
            error_code=None,
            safe_result_snapshot=safe_snapshot,
            next_attempt_at=now if outcome.status in _TERMINAL_REMOTE else now + timedelta(seconds=5),
        )

    async def _commit_and_publish(self, **values: Any) -> None:
        committed = await self._store.commit(**values)
        if committed is not False and self._publish_after_commit is not None:
            published = self._publish_after_commit(values["claim"].operation_id)
            if published is not None:
                await published

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("endpoint reconciler clock must return an aware datetime")
        return value


class SqlAlchemyEndpointOperationReconcileStore:
    """PostgreSQL claim/commit adapter; remote calls stay in the reconciler."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def claim_ready(
        self, *, owner: str, now: datetime, limit: int, lease_seconds: int
    ) -> list[EndpointReconcileClaim]:
        async with self._session_factory() as session:
            async with session.begin():
                statement = (
                    select(EndpointOperationLink, Operation)
                    .join(Operation, Operation.operation_id == EndpointOperationLink.operation_id)
                    .where(
                        EndpointOperationLink.remote_status.notin_(tuple(_TERMINAL_REMOTE)),
                        EndpointOperationLink.next_attempt_at <= now,
                        or_(
                            EndpointOperationLink.lease_until.is_(None),
                            EndpointOperationLink.lease_until <= now,
                        ),
                        Operation.status.notin_(tuple(_TERMINAL_LOCAL)),
                    )
                    .order_by(EndpointOperationLink.next_attempt_at.asc(), EndpointOperationLink.link_id.asc())
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
                rows = list((await session.execute(statement)).all())
                claims: list[EndpointReconcileClaim] = []
                for link, operation in rows:
                    token = f"{owner}:{uuid4()}"
                    link.lease_owner = token
                    link.lease_until = now + timedelta(seconds=lease_seconds)
                    claims.append(
                        EndpointReconcileClaim(
                            operation_id=operation.operation_id,
                            ticket_id=str(operation.ticket_id),
                            endpoint_device_ref=link.endpoint_device_ref,
                            endpoint_operation_ref=link.endpoint_operation_ref,
                            attempt_count=link.attempt_count,
                            remote_status=link.remote_status,
                            create_idempotency_key=link.create_idempotency_key,
                            local_status=operation.status,
                            local_phase=operation.phase,
                            lease_token=token,
                        )
                    )
                await session.flush()
                return claims

    async def commit(
        self,
        *,
        claim: EndpointReconcileClaim,
        endpoint_operation_ref: str | None,
        remote_status: str,
        operation_status: str,
        phase: str,
        error_code: str | None,
        safe_result_snapshot: dict[str, Any] | None,
        next_attempt_at: datetime,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                link = (
                    await session.execute(
                        select(EndpointOperationLink)
                        .where(EndpointOperationLink.operation_id == claim.operation_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                operation = await session.get(Operation, claim.operation_id, with_for_update=True)
                if (
                    link is None
                    or operation is None
                    or operation.status in _TERMINAL_LOCAL
                    or link.lease_owner != claim.lease_token
                ):
                    return False
                if (
                    operation_status in _LOCAL_PROGRESS
                    and operation.status in _LOCAL_PROGRESS
                    and _LOCAL_PROGRESS[operation_status] < _LOCAL_PROGRESS[operation.status]
                ):
                    return False
                previous_endpoint_operation_ref = link.endpoint_operation_ref
                if endpoint_operation_ref is not None:
                    if link.endpoint_operation_ref not in (None, endpoint_operation_ref):
                        return False
                    link.endpoint_operation_ref = endpoint_operation_ref
                if safe_result_snapshot is not None:
                    if remote_status != "succeeded" or operation_status != "succeeded":
                        raise ValueError("safe Endpoint result may be stored only for succeeded operations")
                    safe_result_snapshot = EndpointDiagnosticResultProjection.model_validate(
                        safe_result_snapshot
                    ).model_dump(mode="json")
                state_changed = any(
                    (
                        link.remote_status != remote_status,
                        operation.status != operation_status,
                        operation.phase != phase,
                        previous_endpoint_operation_ref != endpoint_operation_ref
                        if endpoint_operation_ref is not None
                        else False,
                        link.safe_result_snapshot_json != safe_result_snapshot,
                        link.last_error_code != error_code,
                    )
                )
                link.remote_status = remote_status
                link.last_error_code = error_code
                link.safe_result_snapshot_json = safe_result_snapshot
                link.next_attempt_at = next_attempt_at
                link.last_synced_at = datetime.now(timezone.utc)
                link.lease_owner = None
                link.lease_until = None
                if (
                    error_code is not None
                    and remote_status == claim.remote_status
                    and operation_status == claim.local_status
                ):
                    link.attempt_count += 1
                operation.status = operation_status
                operation.phase = phase
                operation.error_code = error_code
                operation.error_message = None
                if operation_status in _TERMINAL_LOCAL:
                    operation.finished_at = datetime.now(timezone.utc)
                if link.diagnostic_step_id:
                    step = await session.get(DiagnosticStep, link.diagnostic_step_id, with_for_update=True)
                    if step is not None:
                        step.status = {
                            "queued": "pending",
                            "sent": "pending",
                            "accepted": "running",
                            "running": "running",
                            "succeeded": "completed",
                            "failed": "failed",
                            "timed_out": "failed",
                            "canceled": "canceled",
                        }[operation_status]
                        step.external_ref = link.endpoint_operation_ref
                        step.error_code = error_code
                        step.error_message = None
                        if operation_status in _TERMINAL_LOCAL:
                            step.finished_at = datetime.now(timezone.utc)
                if (
                    operation_status == "succeeded"
                    and safe_result_snapshot is not None
                    and link.endpoint_operation_ref
                ):
                    evidence = (
                        await session.execute(
                            select(DiagnosticEvidence).where(
                                DiagnosticEvidence.ticket_id == operation.ticket_id,
                                DiagnosticEvidence.source_type == "endpoint_platform",
                                DiagnosticEvidence.source_id == link.endpoint_operation_ref,
                                DiagnosticEvidence.kind == "diagnostic_result",
                            )
                        )
                    ).scalar_one_or_none()
                    if evidence is None:
                        evidence = DiagnosticEvidence(
                            id=str(uuid4()), ticket_id=operation.ticket_id,
                            session_id=link.diagnostic_session_id, step_id=link.diagnostic_step_id,
                            source_type="endpoint_platform", source_id=link.endpoint_operation_ref,
                            provider_id="endpoint_platform", capability_id=ENDPOINT_DIAGNOSTIC_CAPABILITY,
                            kind="diagnostic_result", domain="diagnostics", perspective="endpoint_platform",
                            title="Endpoint diagnostic collection", summary="Endpoint diagnostic collection completed",
                            status="succeeded", normalized_payload=safe_result_snapshot,
                            raw_ref=None, artifact_refs=[], trace_id=operation.trace_id,
                            redaction_level="endpoint_safe_projection", tags=[], passport_eligible=False,
                        )
                        session.add(evidence)
                        state_changed = True
                    if link.diagnostic_session_id:
                        diagnostic_session = await session.get(DiagnosticSession, link.diagnostic_session_id, with_for_update=True)
                        if diagnostic_session is not None and diagnostic_session.status != "completed":
                            diagnostic_session.status = "completed"
                            diagnostic_session.finished_at = datetime.now(timezone.utc)
                            state_changed = True
                await session.flush()
                return state_changed


def _validated_safe_success_snapshot(outcome: EndpointOperationProjection) -> dict[str, Any] | None:
    """Revalidate before persistence; never accept raw remote response fields."""

    if outcome.status != "succeeded" or outcome.safe_result is None:
        return None
    return EndpointDiagnosticResultProjection.model_validate(
        outcome.safe_result.model_dump(mode="json")
    ).model_dump(mode="json")


class EndpointOperationReconcilerRunner:
    """Explicit lifecycle seam; composition may call start/stop without daemon globals."""

    def __init__(
        self, reconciler: EndpointOperationReconciler, *, interval_seconds: int, batch_size: int
    ) -> None:
        self._reconciler = reconciler
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="endpoint-operation-reconciler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            await self._reconciler.reconcile_once(limit=self._batch_size)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_seconds)
            except TimeoutError:
                continue
