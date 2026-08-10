from __future__ import annotations

from types import SimpleNamespace

import pytest

from domain_ports import (
    AccountStatusProjection,
    ActiveBindingProjection,
    BindingRef,
    DeviceRef,
    PersonRef,
    RegistryUnavailable,
    RequesterRef,
    RequesterSnapshot,
)
from inventory.service import DeviceInventoryService
from tickets.create_flow import _read_registry_account_status
from tickets.ticket_context import TicketContextBuilder
from web_api.support_handlers import _build_support_registry_snapshot


pytestmark = pytest.mark.no_db


def _snapshot(person_id: str = "registry-ref-person-1") -> RequesterSnapshot:
    return RequesterSnapshot(
        person=PersonRef(external_id=person_id),
        display_name="Historical Requester",
    )


def _binding(device_id: str = "registry-ref-device-1") -> ActiveBindingProjection:
    snapshot = _snapshot()
    return ActiveBindingProjection(
        device=DeviceRef(external_id=device_id),
        binding=BindingRef(external_id="registry-ref-binding-1"),
        requester=RequesterRef(external_id=snapshot.person.external_id),
        requester_snapshot=snapshot,
        relationship_type="primary_user",
        source="external_authoritative",
    )


class _RegistryPortDouble:
    def __init__(
        self,
        *,
        requester_result: object | None = None,
        binding_result: object | None = None,
        account_result: object | None = None,
    ) -> None:
        self.requester_result = requester_result
        self.binding_result = binding_result
        self.account_result = account_result
        self.requester_refs: list[str] = []
        self.device_refs: list[str] = []

    async def requester_snapshot(self, person: PersonRef) -> object:
        self.requester_refs.append(person.external_id)
        return self.requester_result

    async def active_binding(self, device: DeviceRef) -> object:
        self.device_refs.append(device.external_id)
        return self.binding_result

    async def account_status(self, device: DeviceRef) -> object:
        self.device_refs.append(device.external_id)
        return self.account_result


class _NoRegistrySession:
    async def get(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("migrated Registry read must not use the caller session")

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("migrated Registry read must not use the caller session")


@pytest.mark.asyncio
async def test_ticket_snapshot_builder_uses_registry_port_for_verified_person() -> None:
    snapshot = _snapshot()
    port = _RegistryPortDouble(requester_result=snapshot)

    requester_ref, requester_snapshot = await TicketContextBuilder(
        _NoRegistrySession(),  # type: ignore[arg-type]
        registry_port=port,  # type: ignore[arg-type]
    ).requester_reference_snapshot(snapshot.person.external_id)

    assert requester_ref == RequesterRef(external_id="registry-ref-person-1")
    assert requester_snapshot == snapshot
    assert port.requester_refs == ["registry-ref-person-1"]


@pytest.mark.asyncio
async def test_ticket_snapshot_builder_fails_closed_when_registry_unavailable() -> None:
    port = _RegistryPortDouble(
        requester_result=RegistryUnavailable(code="registry_external_timeout")
    )

    with pytest.raises(ValueError, match="registry_external_timeout"):
        await TicketContextBuilder(
            _NoRegistrySession(),  # type: ignore[arg-type]
            registry_port=port,  # type: ignore[arg-type]
        ).requester_reference_snapshot("registry-ref-person-1")


@pytest.mark.asyncio
async def test_ticket_snapshot_builder_rejects_mismatched_requester_projection() -> None:
    port = _RegistryPortDouble(requester_result=_snapshot("different-registry-person"))

    with pytest.raises(ValueError, match="projection is invalid"):
        await TicketContextBuilder(
            _NoRegistrySession(),  # type: ignore[arg-type]
            registry_port=port,  # type: ignore[arg-type]
        ).requester_reference_snapshot("registry-ref-person-1")


@pytest.mark.asyncio
async def test_create_flow_account_status_uses_redacted_registry_projection() -> None:
    binding = _binding()
    port = _RegistryPortDouble(
        account_result=AccountStatusProjection(
            device=binding.device,
            status="admin_confirmed",
            active_binding=binding,
            source="external_authoritative",
        )
    )

    result = await _read_registry_account_status(port, binding.device.external_id)  # type: ignore[arg-type]

    assert result == {
        "status": "admin_confirmed",
        "active_binding": {
            "binding_id": "registry-ref-binding-1",
            "person_id": "registry-ref-person-1",
            "relationship_type": "primary_user",
        },
        "active_person": {
            "person_id": "registry-ref-person-1",
            "display_name": "Historical Requester",
        },
        "requires_user_action": False,
        "requires_admin_action": False,
        "conflict_reason": None,
        "registry_source": "external_authoritative",
    }
    assert port.device_refs == ["registry-ref-device-1"]


@pytest.mark.asyncio
async def test_create_flow_account_status_keeps_typed_unavailable_state() -> None:
    port = _RegistryPortDouble(
        account_result=RegistryUnavailable(code="registry_external_timeout")
    )

    result = await _read_registry_account_status(port, "registry-ref-device-1")  # type: ignore[arg-type]

    assert result == {
        "status": "registry_unavailable",
        "active_binding": None,
        "active_person": None,
        "requires_user_action": False,
        "requires_admin_action": False,
        "conflict_reason": "registry_external_timeout",
        "registry_source": "unavailable",
    }


@pytest.mark.asyncio
async def test_create_flow_rejects_invalid_registry_projection() -> None:
    port = _RegistryPortDouble(
        account_result=RegistryUnavailable(code="registry_projection_invalid")
    )

    with pytest.raises(ValueError, match="registry_projection_invalid"):
        await _read_registry_account_status(port, "registry-ref-device-1")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_flow_rejects_unexpected_registry_outcome() -> None:
    port = _RegistryPortDouble(account_result=object())

    with pytest.raises(ValueError, match="registry_projection_invalid"):
        await _read_registry_account_status(port, "registry-ref-device-1")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_flow_rejects_mismatched_account_device_projection() -> None:
    binding = _binding()
    port = _RegistryPortDouble(
        account_result=AccountStatusProjection(
            device=DeviceRef(external_id="different-registry-device"),
            status="admin_confirmed",
            active_binding=binding,
            source="external_authoritative",
        )
    )

    with pytest.raises(ValueError, match="registry_projection_invalid"):
        await _read_registry_account_status(port, binding.device.external_id)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_create_flow_rejects_mismatched_binding_requester_projection() -> None:
    binding = _binding()
    mismatched_binding = ActiveBindingProjection(
        device=binding.device,
        binding=binding.binding,
        requester=binding.requester,
        requester_snapshot=_snapshot("different-registry-person"),
        relationship_type=binding.relationship_type,
        source=binding.source,
    )
    port = _RegistryPortDouble(
        account_result=AccountStatusProjection(
            device=binding.device,
            status="admin_confirmed",
            active_binding=mismatched_binding,
            source="external_authoritative",
        )
    )

    with pytest.raises(ValueError, match="registry_projection_invalid"):
        await _read_registry_account_status(port, binding.device.external_id)  # type: ignore[arg-type]


class _InventoryServiceWithoutSuggestions(DeviceInventoryService):
    async def list_binding_suggestions(
        self,
        _device_id: str,
        *,
        include_reviewed: bool = False,
    ) -> list[object]:
        del include_reviewed
        return []


@pytest.mark.asyncio
async def test_inventory_profile_enrichment_uses_redacted_active_binding() -> None:
    binding = _binding()
    port = _RegistryPortDouble(binding_result=binding)
    service = _InventoryServiceWithoutSuggestions(
        _NoRegistrySession(),  # type: ignore[arg-type]
        registry_port=port,  # type: ignore[arg-type]
    )

    profiles = await service.list_device_profiles(binding.device.external_id)

    assert profiles == [
        {
            "requester_id": "registry-ref-person-1",
            "display_name": "Historical Requester",
            "full_name": None,
            "department": None,
            "building": None,
            "floor": None,
            "room": None,
            "phone": None,
            "email": None,
            "active": False,
            "last_seen_at": None,
            "source": "registry_port",
            "status": "active",
        }
    ]
    assert port.device_refs == ["registry-ref-device-1"]


@pytest.mark.asyncio
async def test_inventory_ignores_mismatched_active_binding_projection() -> None:
    binding = _binding("different-registry-device")
    port = _RegistryPortDouble(binding_result=binding)
    service = _InventoryServiceWithoutSuggestions(
        _NoRegistrySession(),  # type: ignore[arg-type]
        registry_port=port,  # type: ignore[arg-type]
    )

    profiles = await service.list_device_profiles("registry-ref-device-1")

    assert profiles == []
    assert port.device_refs == ["registry-ref-device-1"]


@pytest.mark.asyncio
async def test_support_uses_ticket_snapshot_when_registry_unavailable() -> None:
    port = _RegistryPortDouble(
        requester_result=RegistryUnavailable(code="registry_external_timeout")
    )
    ticket = SimpleNamespace(
        requester_external_ref="registry-ref-person-1",
        requester_snapshot_json=_snapshot().model_dump(mode="json"),
        requester_person_id="legacy-person-id-must-not-authorize-fallback",
    )

    result = await _build_support_registry_snapshot(ticket, registry_port=port)  # type: ignore[arg-type]

    assert result is not None
    assert result.model_dump(mode="json") == {
        "status": "unavailable",
        "source": "ticket_snapshot",
        "code": "registry_external_timeout",
        "person_id": "registry-ref-person-1",
        "person_display_name": "Historical Requester",
        "person_phone": None,
        "person_email": None,
        "person_source": None,
        "department_id": None,
        "department_name": None,
        "location_id": None,
        "location_display_name": None,
        "building": None,
        "floor": None,
        "room": None,
        "asset_id": None,
        "asset_name": None,
        "asset_type": None,
        "service_id": None,
        "service_name": None,
        "service_owner_queue_id": None,
        "service_owner_queue_name": None,
        "service_source": None,
    }
    assert port.requester_refs == ["registry-ref-person-1"]


@pytest.mark.asyncio
async def test_support_uses_active_binding_for_legacy_device_without_requester_ref() -> None:
    binding = _binding()
    port = _RegistryPortDouble(binding_result=binding)
    ticket = SimpleNamespace(
        device_id=binding.device.external_id,
        requester_external_ref=None,
        requester_snapshot_json=None,
        requester_person_id=None,
    )

    result = await _build_support_registry_snapshot(ticket, registry_port=port)  # type: ignore[arg-type]

    assert result is not None
    assert result.status == "available"
    assert result.source == "registry_port"
    assert result.person_id == "registry-ref-person-1"
    assert result.person_display_name == "Historical Requester"
    assert port.device_refs == ["registry-ref-device-1"]


@pytest.mark.asyncio
async def test_support_does_not_use_legacy_identity_when_neutral_snapshot_is_malformed() -> None:
    port = _RegistryPortDouble(
        requester_result=RegistryUnavailable(code="registry_external_timeout")
    )
    ticket = SimpleNamespace(
        requester_external_ref="registry-ref-person-1",
        requester_snapshot_json={
            "person": {"external_id": "different-registry-person"},
            "display_name": "Mismatched",
        },
        requester_person_id="legacy-person-id-must-not-authorize-fallback",
    )

    result = await _build_support_registry_snapshot(ticket, registry_port=port)  # type: ignore[arg-type]

    assert result is not None
    assert result.status == "unavailable"
    assert result.source == "registry_port"
    assert result.person_id is None
    assert result.person_display_name is None
    assert port.requester_refs == []


@pytest.mark.asyncio
async def test_support_rejects_mismatched_current_requester_projection() -> None:
    port = _RegistryPortDouble(requester_result=_snapshot("different-registry-person"))
    ticket = SimpleNamespace(
        requester_external_ref="registry-ref-person-1",
        requester_snapshot_json=_snapshot().model_dump(mode="json"),
        requester_person_id=None,
    )

    result = await _build_support_registry_snapshot(ticket, registry_port=port)  # type: ignore[arg-type]

    assert result is not None
    assert result.status == "unavailable"
    assert result.source == "ticket_snapshot"
    assert result.code == "registry_projection_invalid"
    assert result.person_id == "registry-ref-person-1"
    assert result.person_display_name == "Historical Requester"


@pytest.mark.asyncio
async def test_support_rejects_mismatched_active_binding_projection() -> None:
    port = _RegistryPortDouble(binding_result=_binding("different-registry-device"))
    ticket = SimpleNamespace(
        device_id="registry-ref-device-1",
        requester_external_ref=None,
        requester_snapshot_json=None,
        requester_person_id=None,
    )

    result = await _build_support_registry_snapshot(ticket, registry_port=port)  # type: ignore[arg-type]

    assert result is not None
    assert result.status == "unavailable"
    assert result.source == "registry_port"
    assert result.code == "registry_projection_invalid"
    assert result.person_id is None
