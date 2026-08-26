"""Lease-driven HTTPS reconciliation for Helpdesk module operation links."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import or_, select

from domain_ports.endpoint_modules import (
    EndpointModuleInvalidProjection,
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModulePort,
    EndpointModuleRef,
    EndpointModuleVersionRef,
)
from app.db.models import EndpointModuleOperationLink, Operation


@dataclass(frozen=True)
class EndpointModuleReconcileClaim:
    operation_id: str
    endpoint_device_ref: str
    endpoint_operation_ref: str | None
    module_key: str
    module_version: str
    inputs: dict[str, str | int]
    create_idempotency_key: str
    attempt_count: int = 0
    lease_token: str = ""


class EndpointModuleOperationReconcileStore(Protocol):
    async def claim_ready(self, *, owner: str, now: datetime, limit: int, lease_seconds: int) -> list[EndpointModuleReconcileClaim]: ...
    async def commit(self, **values: Any) -> bool: ...


class EndpointModuleOperationReconciler:
    """Calls only EndpointModulePort after a claim; never agent transports."""

    def __init__(
        self, *, endpoint_port: EndpointModulePort, store: EndpointModuleOperationReconcileStore,
        mode: str, owner: str, now: Callable[[], datetime] | None = None, lease_seconds: int = 30,
    ) -> None:
        self._endpoint_port = endpoint_port
        self._store = store
        self._mode = mode
        self._owner = owner
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._lease_seconds = lease_seconds

    async def reconcile_once(self, *, limit: int) -> int:
        if self._mode != "external" or limit < 1:
            return 0
        claims = await self._store.claim_ready(
            owner=self._owner, now=self._aware_now(), limit=limit, lease_seconds=self._lease_seconds,
        )
        for claim in claims:
            await self._reconcile(claim)
        return len(claims)

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
        await self._store.commit(
            claim=claim, endpoint_operation_ref=None, remote_status="failed"
            if isinstance(outcome, EndpointModuleInvalidProjection) else "create_pending",
            safe_result_snapshot=None, error_code=error_code, next_attempt_at=self._aware_now(),
        )

    @staticmethod
    def _safe_snapshot(outcome: EndpointModuleOperationProjection) -> dict[str, object] | None:
        if not outcome.result_available:
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
                    select(EndpointModuleOperationLink, Operation)
                    .join(Operation, Operation.operation_id == EndpointModuleOperationLink.operation_id)
                    .where(
                        EndpointModuleOperationLink.remote_status.notin_(("succeeded", "failed", "canceled", "expired")),
                        EndpointModuleOperationLink.next_attempt_at <= now,
                        or_(EndpointModuleOperationLink.lease_until.is_(None), EndpointModuleOperationLink.lease_until <= now),
                        Operation.status.notin_(("succeeded", "failed", "timed_out", "canceled")),
                    ).order_by(EndpointModuleOperationLink.next_attempt_at.asc(), EndpointModuleOperationLink.link_id.asc())
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
                        module_version=link.module_version, inputs=dict(link.inputs_snapshot_json or {}),
                        create_idempotency_key=link.create_idempotency_key, attempt_count=link.attempt_count,
                        lease_token=token,
                    ))
                await session.flush()
                return claims

    async def commit(self, *, claim: EndpointModuleReconcileClaim, endpoint_operation_ref: str | None,
        remote_status: str, safe_result_snapshot: dict[str, object] | None, error_code: str | None,
        next_attempt_at: datetime) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                link = (await session.execute(select(EndpointModuleOperationLink)
                    .where(EndpointModuleOperationLink.operation_id == claim.operation_id).with_for_update()
                )).scalar_one_or_none()
                operation = await session.get(Operation, claim.operation_id, with_for_update=True)
                if link is None or operation is None or link.lease_owner != claim.lease_token:
                    return False
                if endpoint_operation_ref is not None:
                    if link.endpoint_operation_ref not in (None, endpoint_operation_ref):
                        return False
                    link.endpoint_operation_ref = endpoint_operation_ref
                link.remote_status = remote_status
                link.safe_result_snapshot_json = safe_result_snapshot
                link.last_error_code = error_code
                link.next_attempt_at = next_attempt_at
                link.last_synced_at = datetime.now(timezone.utc)
                link.lease_owner = None
                link.lease_until = None
                operation.status = {"queued": "queued", "delivered": "sent", "acknowledged": "accepted", "running": "running", "succeeded": "succeeded", "failed": "failed", "canceled": "canceled", "expired": "timed_out"}[remote_status]
                operation.phase = f"endpoint_module_{remote_status}"
                operation.error_code = error_code
                if operation.status in {"succeeded", "failed", "timed_out", "canceled"}:
                    operation.finished_at = datetime.now(timezone.utc)
                await session.flush()
                return True
