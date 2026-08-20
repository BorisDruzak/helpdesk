from __future__ import annotations

from datetime import datetime, timezone
import json
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
        self.added: list[object] = []

    async def __aenter__(self) -> "_Session":
        self._factory.open_sessions += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        self._factory.open_sessions -= 1
        return False

    async def get(self, model, ticket_id: str, **_kwargs):
        assert model.__name__ == "Ticket"
        return self._ticket if ticket_id == self._ticket.ticket_id else None

    async def flush(self) -> None:
        self.flush_count += 1

    async def commit(self) -> None:
        self.commit_count += 1

    def add(self, value: object) -> None:
        self.added.append(value)


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
    audit = sessions.sessions[0].added[0]
    assert audit.action == "created"
    assert audit.before_json is None
    assert audit.after_json["endpoint_device_ref"] == "legacy-device"


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
async def test_admin_mapping_rejects_retired_provider_device_without_persistence():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket()
    sessions = _SessionFactory(ticket)
    retired = _device_projection()
    retired = retired.model_copy(update={"retired": True})

    result = await EndpointDeviceReferenceService(
        _EndpointPort(sessions, retired), sessions
    ).assign_verified_mapping(ticket_id="ticket-1", endpoint_device_ref="legacy-device")

    assert result.status == "unresolved"
    assert result.code == "ENDPOINT_DEVICE_RETIRED"
    assert ticket.endpoint_device_ref is None
    assert ticket.endpoint_device_snapshot_json is None
    assert all(session.flush_count == 0 for session in sessions.sessions)


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_mapping_replacement_requires_exact_prior_ref_and_replay_is_noop():
    from app.services.endpoint_device_reference_service import EndpointDeviceReferenceService

    ticket = _ticket(endpoint_device_ref="endpoint-device-1")
    ticket.endpoint_device_snapshot_json = {
        "schema_version": "endpoint_device_snapshot_v1",
        "device_ref": "endpoint-device-1",
        "display_name": "Endpoint workstation",
        "retired": False,
        "last_seen_at": None,
        "captured_at": "2026-08-17T09:00:00Z",
        "source": "endpoint_platform",
    }
    sessions = _SessionFactory(ticket)
    service = EndpointDeviceReferenceService(
        _EndpointPort(sessions, _device_projection("endpoint-device-2")), sessions
    )

    rejected = await service.assign_verified_mapping(
        ticket_id="ticket-1",
        endpoint_device_ref="endpoint-device-2",
        replace=True,
        expected_previous_ref="different-device",
        reason="Endpoint device was replaced after hardware service.",
    )
    assert rejected.status == "unresolved"
    assert ticket.endpoint_device_ref == "endpoint-device-1"

    replaced = await service.assign_verified_mapping(
        ticket_id="ticket-1",
        endpoint_device_ref="endpoint-device-2",
        replace=True,
        expected_previous_ref="endpoint-device-1",
        reason="Endpoint device was replaced after hardware service.",
        actor_id="admin-42",
        actor_role="admin",
        request_correlation="mapping-42",
    )
    assert replaced.status == "resolved" and replaced.persisted is True
    audit = sessions.sessions[-1].added[0]
    assert audit.action == "replaced"
    assert audit.actor_id == "admin-42"
    assert audit.before_json == {"endpoint_device_ref": "endpoint-device-1"}
    assert audit.after_json == {
        "endpoint_device_ref": "endpoint-device-2",
        "reason": "Endpoint device was replaced after hardware service.",
        "request_correlation": "mapping-42",
    }
    replay = await service.assign_verified_mapping(
        ticket_id="ticket-1",
        endpoint_device_ref="endpoint-device-2",
    )
    assert replay.status == "resolved" and replay.persisted is False
    assert sessions.sessions[-1].added == []


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


def test_mapping_request_requires_explicit_safe_replacement_intent():
    from app.services.endpoint_device_reference_service import EndpointDeviceMappingRequestV1

    initial = EndpointDeviceMappingRequestV1.model_validate(
        {
            "schema_version": "endpoint_device_mapping_request_v1",
            "endpoint_device_ref": "endpoint-device-1",
            "replace": False,
            "expected_previous_ref": None,
            "reason": None,
        }
    )
    assert initial.endpoint_device_ref == "endpoint-device-1"

    replacement = EndpointDeviceMappingRequestV1.model_validate(
        {
            "schema_version": "endpoint_device_mapping_request_v1",
            "endpoint_device_ref": "endpoint-device-2",
            "replace": True,
            "expected_previous_ref": "endpoint-device-1",
            "reason": "Endpoint device was replaced after hardware service.",
        }
    )
    assert replacement.replace is True

    for invalid in (
        {**initial.model_dump(), "unexpected": True},
        {**replacement.model_dump(), "expected_previous_ref": None},
        {**replacement.model_dump(), "reason": "short"},
        {**replacement.model_dump(), "reason": "see https://unsafe.example"},
        {**initial.model_dump(), "reason": "unneeded reason"},
    ):
        with pytest.raises(ValidationError):
            EndpointDeviceMappingRequestV1.model_validate(invalid)


class _MappingHandlerRequest(dict):
    def __init__(self, *, payload: object, actor_role: str) -> None:
        super().__init__(
            auth_context=SimpleNamespace(actor_id="admin-42", actor_role=actor_role)
        )
        self.match_info = {"ticket_id": "ticket-1"}
        self.headers = {"X-Correlation-ID": "mapping-42"}
        self.path = "/api/admin/tickets/ticket-1/endpoint-device-mapping"
        self._payload = payload

    async def json(self) -> object:
        return self._payload


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_admin_mapping_handler_rejects_schema_drift_before_provider_access(monkeypatch):
    import diagnostics.handlers as handlers

    class _BombContainer:
        @classmethod
        def from_config(cls):
            raise AssertionError("invalid request must not access Endpoint provider")

    monkeypatch.setattr(handlers, "DomainPortContainer", _BombContainer)
    response = await handlers.handle_admin_ticket_endpoint_device_mapping(
        _MappingHandlerRequest(
            actor_role="admin",
            payload={
                "schema_version": "endpoint_device_mapping_request_v1",
                "endpoint_device_ref": "endpoint-device-1",
                "replace": False,
                "expected_previous_ref": None,
                "reason": None,
                "unexpected": True,
            },
        )
    )

    assert response.status == 400
    assert json.loads(response.text) == {
        "status": "error",
        "error_code": "ENDPOINT_DEVICE_MAPPING_REQUEST_INVALID",
    }


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_endpoint_mapping_handler_remains_admin_only(monkeypatch):
    import diagnostics.handlers as handlers
    import auth.middleware as auth_middleware

    async def _no_audit(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(auth_middleware, "_write_web_auth_audit", _no_audit)

    response = await handlers.handle_admin_ticket_endpoint_device_mapping(
        _MappingHandlerRequest(actor_role="support", payload={})
    )

    assert response.status == 403
    assert json.loads(response.text)["error_code"] == "FORBIDDEN"
