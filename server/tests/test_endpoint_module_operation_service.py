from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.services.endpoint_module_operation_service import (
    EndpointModuleOperationRequest,
    EndpointModuleOperationService,
)
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceResolution


pytestmark = pytest.mark.no_db


@dataclass(frozen=True)
class _Actor:
    actor_id: str = "support-1"
    actor_role: str = "support"


class _Access:
    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        assert actor == _Actor()
        assert ticket_id == "ticket-1"


class _Resolver:
    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution:
        assert ticket_id == "ticket-1"
        return EndpointDeviceReferenceResolution(status="resolved", device_ref="endpoint-device-1")


class _Store:
    def __init__(self) -> None:
        self.record: dict[str, object] | None = None

    async def get_by_operation_id(self, operation_id: str) -> dict[str, object] | None:
        if self.record and self.record["operation_id"] == operation_id:
            return self.record
        return None

    async def create_pending(self, **values: object) -> dict[str, object]:
        self.record = dict(values)
        return self.record


@pytest.mark.asyncio
async def test_module_facade_creates_one_local_typed_operation_without_dispatching_agent_work() -> None:
    store = _Store()
    service = EndpointModuleOperationService(
        access_service=_Access(),
        device_resolver=_Resolver(),
        store=store,
        now=lambda: datetime(2026, 8, 26, tzinfo=timezone.utc),
        new_trace_id=lambda: "trace-1",
    )
    request = EndpointModuleOperationRequest(
        ticket_id="ticket-1",
        module_key="network.basic.check",
        module_version="1.0.0",
        inputs={"target": "example.test"},
        idempotency_key="module-request-key-1",
    )

    result = await service.create(actor=_Actor(), request=request)
    replay = await service.create(actor=_Actor(), request=request)

    assert result.operation_id == replay.operation_id
    assert result.status == "queued"
    assert store.record is not None
    assert store.record["endpoint_device_ref"] == "endpoint-device-1"
    assert store.record["module_key"] == "network.basic.check"
    assert store.record["module_version"] == "1.0.0"
    assert store.record["inputs"] == {"target": "example.test"}
    assert not {"recipe", "command", "tool_name", "device_outbox"} & set(store.record)
