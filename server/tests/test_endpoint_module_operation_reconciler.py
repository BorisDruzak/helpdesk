from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.services.endpoint_module_operation_reconciler import (
    EndpointModuleReconcileClaim,
    EndpointModuleOperationReconciler,
)
from domain_ports.endpoint_modules import (
    EndpointModuleOperationProjection,
    EndpointModuleOperationRef,
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
