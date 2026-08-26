"""Lease-driven HTTPS reconciliation for Helpdesk module operation links."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from domain_ports.endpoint_modules import (
    EndpointModuleInvalidProjection,
    EndpointModuleOperationCreateRequest,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModulePort,
    EndpointModuleRef,
    EndpointModuleVersionRef,
)


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
