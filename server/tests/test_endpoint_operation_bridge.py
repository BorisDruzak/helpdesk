from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from app.services.endpoint_diagnostic_operation_service import (
    EndpointDiagnosticOperationService,
    EndpointDiagnosticOperationConflict,
    EndpointDiagnosticOperationRequest,
    validate_endpoint_operation_idempotency_key,
    remote_endpoint_idempotency_key,
)
from app.services.endpoint_device_reference_service import EndpointDeviceReferenceResolution


pytestmark = pytest.mark.no_db


@dataclass
class _Actor:
    actor_id: str = "support-42"
    actor_role: str = "support"


class _Access:
    def __init__(self) -> None:
        self.calls: list[tuple[object, str]] = []

    async def require_ticket_operation_access(self, *, actor: object, ticket_id: str) -> None:
        self.calls.append((actor, ticket_id))


class _Resolver:
    async def resolve_ticket(self, ticket_id: str) -> EndpointDeviceReferenceResolution:
        assert ticket_id == "ticket-1"
        return EndpointDeviceReferenceResolution(status="resolved", device_ref="endpoint-device-1")


class _Store:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.existing: dict[str, object] = {}

    async def get_by_operation_id(self, operation_id: str):
        return self.existing.get(operation_id)

    async def create_pending(self, **values):
        self.created.append(values)
        return values


@pytest.mark.asyncio
async def test_create_uses_server_generated_deterministic_identity_and_never_remote_ref() -> None:
    access = _Access()
    store = _Store()
    service = EndpointDiagnosticOperationService(
        access_service=access,
        device_resolver=_Resolver(),
        store=store,
        now=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )
    request = EndpointDiagnosticOperationRequest(
        ticket_id="ticket-1",
        idempotency_key="caller-key-0001",
    )

    result = await service.create(actor=_Actor(), request=request)

    expected = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "helpdesk:ticket-1:endpoint-device-1:context.diagnostic.collect:caller-key-0001",
        )
    )
    assert result.operation_id == expected
    assert result.status == "queued"
    assert result.endpoint_operation_ref is None
    assert access.calls == [(_Actor(), "ticket-1")]
    created = store.created[0]
    assert created | {"trace_id": None} == {
        "operation_id": expected,
        "ticket_id": "ticket-1",
        "actor_id": "support-42",
        "actor_role": "support",
        "endpoint_device_ref": "endpoint-device-1",
        "idempotency_key": remote_endpoint_idempotency_key(expected),
        "trace_id": None,
        "created_at": datetime(2026, 8, 17, tzinfo=timezone.utc),
    }
    assert uuid.UUID(created["trace_id"])


@pytest.mark.parametrize(
    "value",
    ["short", " x-caller-key-0001", "x-caller-key-0001 ", "ключ-восемь"],
)
def test_idempotency_key_must_be_ascii_bounded_and_untrimmed(value: str) -> None:
    with pytest.raises(ValueError, match="idempotency"):
        validate_endpoint_operation_idempotency_key(value)


@pytest.mark.asyncio
async def test_create_rejects_reused_key_with_different_immutable_identity() -> None:
    store = _Store()
    store.existing[str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            "helpdesk:ticket-1:endpoint-device-1:context.diagnostic.collect:caller-key-0001",
        )
    )] = {
        "operation_id": "different-operation",
        "ticket_id": "ticket-1",
        "endpoint_device_ref": "endpoint-device-1",
    }
    service = EndpointDiagnosticOperationService(
        access_service=_Access(),
        device_resolver=_Resolver(),
        store=store,
    )

    with pytest.raises(EndpointDiagnosticOperationConflict):
        await service.create(
            actor=_Actor(),
            request=EndpointDiagnosticOperationRequest(
                ticket_id="ticket-1", idempotency_key="caller-key-0001"
            ),
        )


@pytest.mark.asyncio
async def test_exact_repeat_returns_existing_local_operation_without_another_create() -> None:
    store = _Store()
    service = EndpointDiagnosticOperationService(
        access_service=_Access(), device_resolver=_Resolver(), store=store
    )
    request = EndpointDiagnosticOperationRequest(
        ticket_id="ticket-1", idempotency_key="caller-key-0001"
    )

    first = await service.create(actor=_Actor(), request=request)
    store.existing[first.operation_id] = store.created[0] | {"status": "queued"}
    second = await service.create(actor=_Actor(), request=request)

    assert second == first
    assert len(store.created) == 1


def test_remote_idempotency_is_derived_from_the_local_operation_not_caller_key() -> None:
    assert remote_endpoint_idempotency_key("11111111-1111-1111-1111-111111111111") == (
        "helpdesk-endpoint-operation:11111111-1111-1111-1111-111111111111"
    )
