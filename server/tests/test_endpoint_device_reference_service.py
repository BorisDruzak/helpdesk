from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from domain_ports.endpoint import (
    EndpointDeviceProjection,
    EndpointDeviceRef,
    EndpointNotFound,
    EndpointUnavailable,
)


class _Session:
    def __init__(self, factory: "_SessionFactory", ticket: SimpleNamespace) -> None:
        self._factory = factory
        self._ticket = ticket
        self.flush_count = 0
        self.commit_count = 0

    async def __aenter__(self) -> "_Session":
        self._factory.open_sessions += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._factory.open_sessions -= 1
        return False

    async def get(self, model, ticket_id: str):
        assert model.__name__ == "Ticket"
        return self._ticket if ticket_id == self._ticket.ticket_id else None

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1


class _SessionFactory:
    def __init__(self, ticket: SimpleNamespace) -> None:
        self.ticket = ticket
        self.open_sessions = 0
        self.sessions: list[_Session] = []

    def __call__(self) -> _Session:
        session = _Session(self, self.ticket)
        self.sessions.append(session)
        return session


class _EndpointPort:
    def __init__(self, factory: _SessionFactory, outcome) -> None:
        self.factory = factory
        self.outcome = outcome
        self.calls: list[str] = []

    async def read_device(self, device: EndpointDeviceRef):
        assert self.factory.open_sessions == 0, "Endpoint read must happen outside a DB session"
        self.calls.append(device.external_id)
        return self.outcome


def _ticket(*, endpoint_device_ref: str | None = None, device_id: str | None = "legacy-device"):
    return SimpleNamespace(
        ticket_id="ticket-1",
        device_id=device_id,
        endpoint_device_ref=endpoint_device_ref,
        endpoint_device_snapshot_json=None,
    )


def _device_projection(ref: str = "legacy-device") -> EndpointDeviceProjection:
    return EndpointDeviceProjection(
        device=EndpointDeviceRef(external_id=ref),
        display_name="Endpoint workstation",
        retired=False,
        last_seen_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_admin_mapping_persists_only_exact_verified_device_ref_after_port_read():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket()
    sessions = _SessionFactory(ticket)
    port = _EndpointPort(sessions, _device_projection())

    result = await EndpointDeviceReferenceService(port, sessions).assign_verified_mapping(
        ticket_id="ticket-1", endpoint_device_ref="legacy-device"
    )

    assert result.status == "resolved"
    assert result.code is None
    assert result.persisted is True
    assert port.calls == ["legacy-device"]
    assert ticket.endpoint_device_ref == "legacy-device"
    assert ticket.endpoint_device_snapshot_json == {
        "schema_version": "endpoint_device_snapshot_v1",
        "device_ref": "legacy-device",
        "display_name": "Endpoint workstation",
        "retired": False,
        "last_seen_at": "2026-08-17T09:00:00Z",
        "captured_at": ticket.endpoint_device_snapshot_json["captured_at"],
        "source": "endpoint_platform",
    }
    assert ticket.endpoint_device_snapshot_json["captured_at"].endswith("Z")
    assert len(sessions.sessions) == 1
    assert sessions.sessions[0].flush_count == 1
    assert sessions.sessions[0].commit_count == 1


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_resolver_preserves_existing_validated_endpoint_ref_without_port_lookup():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket(endpoint_device_ref="already-verified", device_id="different-legacy-device")
    ticket.endpoint_device_snapshot_json = {
        "schema_version": "endpoint_device_snapshot_v1",
        "device_ref": "already-verified",
        "display_name": "Endpoint workstation",
        "retired": False,
        "last_seen_at": None,
        "captured_at": "2026-08-17T09:00:00Z",
        "source": "endpoint_platform",
    }
    sessions = _SessionFactory(ticket)
    port = _EndpointPort(sessions, _device_projection("different-legacy-device"))

    result = await EndpointDeviceReferenceService(port, sessions).resolve_ticket("ticket-1")

    assert result.status == "resolved"
    assert result.persisted is False
    assert result.device_ref == "already-verified"
    assert port.calls == []
    assert ticket.endpoint_device_ref == "already-verified"


@pytest.mark.asyncio
@pytest.mark.no_db
@pytest.mark.parametrize(
    ("outcome", "expected_code"),
    [
        (EndpointNotFound(), "ENDPOINT_DEVICE_MAPPING_MISSING"),
        (EndpointUnavailable(), "ENDPOINT_UNAVAILABLE"),
    ],
)
async def test_admin_mapping_does_not_persist_failed_endpoint_lookup(outcome, expected_code: str):
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket()
    sessions = _SessionFactory(ticket)
    port = _EndpointPort(sessions, outcome)

    result = await EndpointDeviceReferenceService(port, sessions).assign_verified_mapping(
        ticket_id="ticket-1", endpoint_device_ref="legacy-device"
    )

    assert result.status == "unresolved"
    assert result.code == expected_code
    assert result.persisted is False
    assert ticket.endpoint_device_ref is None
    assert ticket.endpoint_device_snapshot_json is None
    assert all(session.flush_count == 0 for session in sessions.sessions)


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_admin_mapping_rejects_mismatched_endpoint_ref_without_persistence():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket()
    sessions = _SessionFactory(ticket)
    port = _EndpointPort(sessions, _device_projection("different-device"))

    result = await EndpointDeviceReferenceService(port, sessions).assign_verified_mapping(
        ticket_id="ticket-1", endpoint_device_ref="legacy-device"
    )

    assert result.status == "unresolved"
    assert result.code == "ENDPOINT_DEVICE_MAPPING_INVALID"
    assert ticket.endpoint_device_ref is None
    assert ticket.endpoint_device_snapshot_json is None
    assert all(session.flush_count == 0 for session in sessions.sessions)


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_resolver_never_uses_legacy_ticket_device_id_as_endpoint_mapping():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket(device_id="legacy-device")
    sessions = _SessionFactory(ticket)
    port = _EndpointPort(sessions, _device_projection())

    result = await EndpointDeviceReferenceService(port, sessions).resolve_ticket("ticket-1")

    assert result.status == "unresolved"
    assert result.code == "ENDPOINT_DEVICE_MAPPING_MISSING"
    assert port.calls == []


@pytest.mark.no_db
def test_endpoint_device_snapshot_rejects_extra_or_raw_endpoint_fields():
    from app.services.endpoint_device_reference_service import EndpointDeviceSnapshotV1

    snapshot = EndpointDeviceSnapshotV1(
        device_ref="endpoint-device-1",
        display_name="Endpoint workstation",
        retired=False,
        last_seen_at=None,
        captured_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
    )
    with pytest.raises(ValidationError):
        snapshot.display_name = "replacement"

    with pytest.raises(ValidationError):
        EndpointDeviceSnapshotV1(
            device_ref="endpoint-device-1",
            display_name="Endpoint workstation",
            retired=False,
            last_seen_at=None,
            captured_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            mac_address="00:11:22:33:44:55",
        )
