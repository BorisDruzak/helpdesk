from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.services.endpoint_module_operation_reconciler import (
    EndpointModuleReconcileClaim,
    EndpointModuleOperationReconciler,
)
from domain_ports.endpoint_modules import (
    EndpointModuleInvalidProjection,
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
    EndpointModuleOperationStepProjection,
)


pytestmark = pytest.mark.no_db


@dataclass
class _Store:
    claim: EndpointModuleReconcileClaim
    committed: dict[str, object] | None = None

    async def claim_ready(self, **_kwargs: object) -> list[EndpointModuleReconcileClaim]:
        return [self.claim]

    async def commit(self, **values: object) -> bool:
        self.committed = values
        return True


class _Port:
    async def create_operation(self, request, *, idempotency_key: str):
        now = datetime(2026, 8, 26, tzinfo=timezone.utc)
        assert request.module_version.version == "1.0.0"
        assert idempotency_key == "remote-module-key"
        return EndpointModuleOperationProjection(
            operation=EndpointModuleOperationRef(external_id="remote-operation-1"),
            module_version=request.module_version,
            device_external_id=request.device_external_id,
            status="queued", created_at=now, deadline_at=now, completed_at=None,
        )

    async def read_operation(self, _operation):
        raise AssertionError("create path must not read before the remote ref exists")


class _OneAtATimeStore:
    def __init__(self, claims: list[EndpointModuleReconcileClaim]) -> None:
        self._claims = list(claims)
        self.claim_limits: list[int] = []
        self.commits: list[dict[str, object]] = []

    async def claim_ready(self, *, limit: int, **_kwargs: object) -> list[EndpointModuleReconcileClaim]:
        self.claim_limits.append(limit)
        if not self._claims:
            return []
        return [self._claims.pop(0)]

    async def commit(self, **values: object) -> bool:
        self.commits.append(values)
        return True


class _UnavailablePort:
    async def create_operation(self, _request, *, idempotency_key: str):
        assert idempotency_key
        raise RuntimeError("simulated transport interruption")

    async def read_operation(self, _operation):
        raise RuntimeError("simulated transport interruption")


class _AcceptingPort:
    async def create_operation(self, request, *, idempotency_key: str):
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        assert request.module_version.version == "1.0.0"
        assert idempotency_key.startswith("remote-module-key-")
        return EndpointModuleOperationProjection(
            operation=EndpointModuleOperationRef(external_id=f"remote-{idempotency_key}"),
            module_version=request.module_version,
            device_external_id=request.device_external_id,
            status="queued",
            created_at=now,
            deadline_at=now,
            completed_at=None,
        )

    async def read_operation(self, _operation):
        raise AssertionError("create path must not read before the remote ref exists")


class _FailedOperationPort:
    async def create_operation(self, request, *, idempotency_key: str):
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        assert idempotency_key == "remote-module-key"
        return EndpointModuleOperationProjection(
            operation=EndpointModuleOperationRef(external_id="remote-operation-1"),
            module_version=request.module_version,
            device_external_id=request.device_external_id,
            status="failed",
            created_at=now,
            deadline_at=now,
            completed_at=now,
            result_available=True,
            safe_result=(
                EndpointModuleOperationStepProjection(
                    sequence=0,
                    capability="dns.resolve",
                    status="failed",
                    error_code="endpoint_module_invalid_projection",
                ),
            ),
        )

    async def read_operation(self, _operation):
        raise AssertionError("create path must not read before the remote ref exists")


class _InvalidReadPort:
    async def create_operation(self, _request, *, idempotency_key: str):
        raise AssertionError("existing remote operation must be read, not created")

    async def read_operation(self, operation):
        assert operation.external_id == "remote-operation-1"
        return EndpointModuleInvalidProjection()


@pytest.mark.asyncio
async def test_reconciler_creates_remote_typed_operation_outside_local_store() -> None:
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref=None, module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key",
    )
    store = _Store(claim)
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_Port(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: datetime(2026, 8, 26, tzinfo=timezone.utc),
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert store.committed is not None
    assert store.committed["endpoint_operation_ref"] == "remote-operation-1"
    assert store.committed["remote_status"] == "queued"


@pytest.mark.asyncio
async def test_reconciler_is_fail_closed_until_endpoint_execution_is_enabled() -> None:
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref=None, module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key",
    )
    store = _Store(claim)
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_Port(), store=store, mode="external", execution_mode="disabled", owner="test-owner",
    )

    assert await reconciler.reconcile_once(limit=1) == 0
    assert store.committed is None


@pytest.mark.asyncio
async def test_reconciler_claims_one_operation_immediately_before_each_remote_call() -> None:
    claims = [
        EndpointModuleReconcileClaim(
            operation_id=f"local-operation-{number}", endpoint_device_ref="endpoint-device-1",
            endpoint_operation_ref=None, module_key="network.basic.check", module_version="1.0.0",
            inputs={"target": "example.test"}, create_idempotency_key=f"remote-module-key-{number}",
        )
        for number in (1, 2)
    ]
    store = _OneAtATimeStore(claims)
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_AcceptingPort(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: datetime(2026, 8, 27, tzinfo=timezone.utc),
    )

    assert await reconciler.reconcile_once(limit=2) == 2
    assert store.claim_limits == [1, 1]
    assert [commit["claim"].operation_id for commit in store.commits] == [
        "local-operation-1",
        "local-operation-2",
    ]


@pytest.mark.asyncio
async def test_reconciler_records_unexpected_transport_failure_for_safe_retry() -> None:
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref=None, module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key",
    )
    store = _OneAtATimeStore([claim])
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_UnavailablePort(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: datetime(2026, 8, 27, tzinfo=timezone.utc),
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert len(store.commits) == 1
    assert store.commits[0]["error_code"] == "endpoint_module_reconcile_unexpected"
    assert store.commits[0]["remote_status"] == "create_pending"


@pytest.mark.asyncio
async def test_reconciler_never_projects_failed_remote_step_values_as_safe_evidence() -> None:
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref=None, module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key",
    )
    store = _OneAtATimeStore([claim])
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_FailedOperationPort(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: datetime(2026, 8, 27, tzinfo=timezone.utc),
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert store.commits[0]["remote_status"] == "failed"
    assert store.commits[0]["safe_result_snapshot"] is None


@pytest.mark.asyncio
async def test_reconciler_retries_one_invalid_read_after_remote_parent_exists() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref="remote-operation-1", module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key", remote_status="queued",
    )
    store = _OneAtATimeStore([claim])
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_InvalidReadPort(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: now,
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert store.commits[0]["endpoint_operation_ref"] == "remote-operation-1"
    assert store.commits[0]["remote_status"] == "queued"
    assert store.commits[0]["error_code"] == "endpoint_module_invalid_projection"
    assert store.commits[0]["next_attempt_at"] == datetime(2026, 8, 28, 0, 0, 2, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_reconciler_fails_closed_after_the_retry_for_an_invalid_read() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    claim = EndpointModuleReconcileClaim(
        operation_id="local-operation-1", endpoint_device_ref="endpoint-device-1",
        endpoint_operation_ref="remote-operation-1", module_key="network.basic.check", module_version="1.0.0",
        inputs={"target": "example.test"}, create_idempotency_key="remote-module-key", remote_status="queued",
        attempt_count=1,
    )
    store = _OneAtATimeStore([claim])
    reconciler = EndpointModuleOperationReconciler(
        endpoint_port=_InvalidReadPort(), store=store, mode="external", execution_mode="endpoint", owner="test-owner",
        now=lambda: now,
    )

    assert await reconciler.reconcile_once(limit=1) == 1
    assert store.commits[0]["remote_status"] == "failed"
    assert store.commits[0]["next_attempt_at"] == now
