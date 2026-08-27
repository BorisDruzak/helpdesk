"""Lease-driven HTTPS reconciliation for Helpdesk module operation links."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4
import logging

from sqlalchemy import or_, select

from domain_ports.endpoint_modules import (
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModulePort,
    EndpointModuleRef,
    EndpointModuleUnavailable,
    EndpointModuleVersionRef,
)
from app.db.models import DiagnosticEvidence, EndpointOperationLink, Operation


_LOGGER = logging.getLogger(__name__)
_TERMINAL_REMOTE_STATUSES = frozenset({"succeeded", "failed", "canceled", "expired"})
_TERMINAL_LOCAL_STATUSES = frozenset({"succeeded", "failed", "timed_out", "canceled"})
_REMOTE_PROGRESS = {"create_pending": 0, "queued": 1, "delivered": 2, "acknowledged": 3, "running": 4}
_REMOTE_TO_LOCAL = {
    "create_pending": ("queued", "endpoint_module_create_pending"),
    "queued": ("queued", "endpoint_module_queued"),
    "delivered": ("sent", "endpoint_module_delivered"),
    "acknowledged": ("accepted", "endpoint_module_acknowledged"),
    "running": ("running", "endpoint_module_running"),
    "succeeded": ("succeeded", "endpoint_module_succeeded"),
    "failed": ("failed", "endpoint_module_failed"),
    "canceled": ("canceled", "endpoint_module_canceled"),
    "expired": ("timed_out", "endpoint_module_expired"),
}


def _retry_delay_seconds(attempt_count: int) -> float:
    """Bound retries without holding an expired lease across remote I/O."""

    schedule = (2, 5, 15, 30, 60)
    index = max(attempt_count, 0)
    return float(schedule[index] if index < len(schedule) else min(300, 60 * 2 ** (index - 4)))


@dataclass(frozen=True)
class EndpointModuleReconcileClaim:
    operation_id: str
    endpoint_device_ref: str
    endpoint_operation_ref: str | None
    module_key: str
    module_version: str
    inputs: dict[str, str | int]
    create_idempotency_key: str
    remote_status: str = "create_pending"
    attempt_count: int = 0
    lease_token: str = ""


class EndpointModuleOperationReconcileStore(Protocol):
    async def claim_ready(self, *, owner: str, now: datetime, limit: int, lease_seconds: int) -> list[EndpointModuleReconcileClaim]: ...
    async def commit(self, **values: Any) -> bool: ...


class EndpointModuleOperationReconciler:
    """Calls only EndpointModulePort after a claim; never agent transports."""

    def __init__(
        self, *, endpoint_port: EndpointModulePort, store: EndpointModuleOperationReconcileStore,
        mode: str, execution_mode: str, owner: str, now: Callable[[], datetime] | None = None,
        lease_seconds: int = 30,
    ) -> None:
        self._endpoint_port = endpoint_port
        self._store = store
        self._mode = mode
        self._execution_mode = execution_mode
        self._owner = owner
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lease_seconds = lease_seconds

    async def reconcile_once(self, *, limit: int) -> int:
        if self._mode != "external" or self._execution_mode != "endpoint" or limit < 1:
            return 0
        processed = 0
        for _ in range(limit):
            claims = await self._store.claim_ready(
                owner=self._owner, now=self._aware_now(), limit=1, lease_seconds=self._lease_seconds,
            )
            if not claims:
                break
            claim = claims[0]
            try:
                await self._reconcile(claim)
            except Exception as error:
                await self._record_unexpected_failure(claim, error)
            processed += 1
        return processed

    async def _record_unexpected_failure(self, claim: EndpointModuleReconcileClaim, error: Exception) -> None:
        now = self._aware_now()
        retry_seconds = _retry_delay_seconds(claim.attempt_count)
        try:
            changed = await self._store.commit(
                claim=claim,
                endpoint_operation_ref=claim.endpoint_operation_ref,
                remote_status=claim.remote_status,
                safe_result_snapshot=None,
                error_code="endpoint_module_reconcile_unexpected",
                next_attempt_at=now + timedelta(seconds=retry_seconds),
            )
        except Exception as commit_error:
            _LOGGER.error(
                "endpoint_module_reconcile_failure_record_failed",
                extra={"operation_id": claim.operation_id, "error_type": type(commit_error).__name__},
            )
            return
        _LOGGER.warning(
            "endpoint_module_reconcile_unexpected" if changed else "endpoint_module_reconcile_stale",
            extra={
                "operation_id": claim.operation_id,
                "attempt": claim.attempt_count + 1,
                "retry_seconds": retry_seconds,
                "error_type": type(error).__name__,
            },
        )

    async def _reconcile(self, claim: EndpointModuleReconcileClaim) -> None:
        if claim.endpoint_operation_ref:
            outcome = await self._endpoint_port.read_operation(
                EndpointModuleOperationRef(external_id=claim.endpoint_operation_ref)
            )
        else:
            outcome = await self._endpoint_port.create_operation(
                EndpointModuleOperationCreateRequest(
                    module_version=EndpointModuleVersionRef(
                        module=EndpointModuleRef(module_key=claim.module_key), version=claim.module_version,
                    ), device_external_id=claim.endpoint_device_ref, inputs=claim.inputs,
                ), idempotency_key=claim.create_idempotency_key,
            )
        if isinstance(outcome, EndpointModuleOperationProjection):
            await self._store.commit(
                claim=claim, endpoint_operation_ref=outcome.operation.external_id,
                remote_status=outcome.status, safe_result_snapshot=self._safe_snapshot(outcome),
                error_code=None, next_attempt_at=self._aware_now(),
            )
            return
        error_code = getattr(outcome, "code", "endpoint_module_invalid_projection")
        retryable = isinstance(outcome, EndpointModuleUnavailable) and outcome.retryable
        await self._store.commit(
            claim=claim,
            endpoint_operation_ref=claim.endpoint_operation_ref,
            remote_status=claim.remote_status if retryable else "failed",
            safe_result_snapshot=None,
            error_code=error_code,
            next_attempt_at=(
                self._aware_now() + timedelta(seconds=_retry_delay_seconds(claim.attempt_count))
                if retryable
                else self._aware_now()
            ),
        )

    @staticmethod
    def _safe_snapshot(outcome: EndpointModuleOperationProjection) -> dict[str, object] | None:
        if outcome.status != "succeeded" or not outcome.result_available:
            return None
        return {"steps": [step.model_dump(mode="json") for step in outcome.safe_result]}

    def _aware_now(self) -> datetime:
        now = self._now()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("endpoint module reconciler clock must return an aware datetime")
        return now


class SqlAlchemyEndpointModuleOperationReconcileStore:
    """Short transaction lease store; it never calls the remote Endpoint service."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    async def claim_ready(self, *, owner: str, now: datetime, limit: int, lease_seconds: int) -> list[EndpointModuleReconcileClaim]:
        async with self._session_factory() as session:
            async with session.begin():
                rows = list((await session.execute(
                    select(EndpointOperationLink, Operation)
                    .join(Operation, Operation.operation_id == EndpointOperationLink.operation_id)
                    .where(
                        EndpointOperationLink.capability_code == "endpoint.module.recipe",
                        EndpointOperationLink.remote_status.notin_(("succeeded", "failed", "canceled", "expired")),
                        EndpointOperationLink.next_attempt_at <= now,
                        or_(EndpointOperationLink.lease_until.is_(None), EndpointOperationLink.lease_until <= now),
                        Operation.status.notin_(("succeeded", "failed", "timed_out", "canceled")),
                    ).order_by(EndpointOperationLink.next_attempt_at.asc(), EndpointOperationLink.link_id.asc())
                    .limit(limit).with_for_update(skip_locked=True)
                )).all())
                claims = []
                for link, operation in rows:
                    token = f"{owner}:{uuid4()}"
                    link.lease_owner = token
                    link.lease_until = now + timedelta(seconds=lease_seconds)
                    claims.append(EndpointModuleReconcileClaim(
                        operation_id=operation.operation_id, endpoint_device_ref=link.endpoint_device_ref,
                        endpoint_operation_ref=link.endpoint_operation_ref, module_key=link.module_key,
                        module_version=link.module_version, inputs=dict(link.module_inputs_snapshot_json or {}),
                        create_idempotency_key=link.create_idempotency_key, remote_status=link.remote_status,
                        attempt_count=link.attempt_count,
                        lease_token=token,
                    ))
                await session.flush()
                return claims

    async def commit(self, *, claim: EndpointModuleReconcileClaim, endpoint_operation_ref: str | None,
        remote_status: str, safe_result_snapshot: dict[str, object] | None, error_code: str | None,
        next_attempt_at: datetime) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                link = (await session.execute(select(EndpointOperationLink)
                    .where(EndpointOperationLink.operation_id == claim.operation_id).with_for_update()
                )).scalar_one_or_none()
                operation = await session.get(Operation, claim.operation_id, with_for_update=True)
                if (
                    link is None
                    or operation is None
                    or link.lease_owner != claim.lease_token
                    or link.remote_status in _TERMINAL_REMOTE_STATUSES
                    or operation.status in _TERMINAL_LOCAL_STATUSES
                ):
                    return False
                if (
                    remote_status in _REMOTE_PROGRESS
                    and link.remote_status in _REMOTE_PROGRESS
                    and _REMOTE_PROGRESS[remote_status] < _REMOTE_PROGRESS[link.remote_status]
                ):
                    return False
                if endpoint_operation_ref is not None:
                    if link.endpoint_operation_ref not in (None, endpoint_operation_ref):
                        return False
                    link.endpoint_operation_ref = endpoint_operation_ref
                if safe_result_snapshot is not None and remote_status != "succeeded":
                    raise ValueError("module safe result may be stored only for succeeded operations")
                link.remote_status = remote_status
                link.safe_result_snapshot_json = safe_result_snapshot
                link.last_error_code = error_code
                link.next_attempt_at = next_attempt_at
                link.last_synced_at = datetime.now(timezone.utc)
                link.lease_owner = None
                link.lease_until = None
                if error_code is not None and remote_status == claim.remote_status:
                    link.attempt_count += 1
                operation.status, operation.phase = _REMOTE_TO_LOCAL[remote_status]
                operation.error_code = error_code
                if operation.status in {"succeeded", "failed", "timed_out", "canceled"}:
                    operation.finished_at = datetime.now(timezone.utc)
                if (
                    remote_status == "succeeded" and safe_result_snapshot is not None
                    and link.endpoint_operation_ref and operation.ticket_id
                ):
                    evidence = (await session.execute(
                        select(DiagnosticEvidence).where(
                            DiagnosticEvidence.ticket_id == operation.ticket_id,
                            DiagnosticEvidence.source_type == "endpoint_platform",
                            DiagnosticEvidence.source_id == link.endpoint_operation_ref,
                            DiagnosticEvidence.kind == "endpoint.module.recipe",
                        )
                    )).scalar_one_or_none()
                    if evidence is None:
                        session.add(DiagnosticEvidence(
                            id=str(uuid4()), ticket_id=operation.ticket_id, session_id=None, step_id=None,
                            source_type="endpoint_platform", source_id=link.endpoint_operation_ref,
                            provider_id="endpoint_platform", capability_id="endpoint.module.recipe",
                            kind="endpoint.module.recipe", domain="diagnostics",
                            perspective="endpoint_platform", title="Endpoint module recipe",
                            summary=f"Endpoint module {link.module_key}@{link.module_version} completed",
                            status="succeeded", normalized_payload={
                                "module_key": link.module_key, "module_version": link.module_version,
                                "result": safe_result_snapshot,
                            }, raw_ref=None, artifact_refs=[], trace_id=operation.trace_id,
                            redaction_level="endpoint_safe_projection", tags=[], passport_eligible=False,
                        ))
                await session.flush()
                return True


class EndpointModuleOperationReconcilerRunner:
    """Lifecycle-owned polling loop, started only by explicit cutover composition."""

    def __init__(
        self, reconciler: EndpointModuleOperationReconciler, *, interval_seconds: int, batch_size: int
    ) -> None:
        self._reconciler = reconciler
        self._interval_seconds = interval_seconds
        self._batch_size = batch_size
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run(), name="endpoint-module-operation-reconciler")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self._reconciler.reconcile_once(limit=self._batch_size)
            except Exception as error:
                _LOGGER.error("endpoint_module_reconcile_runner_failed", extra={"error_type": type(error).__name__})
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=max(0.1, float(self._interval_seconds))
                )
            except TimeoutError:
                continue
