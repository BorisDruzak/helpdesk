from __future__ import annotations

import asyncio

import pytest

from domain_ports import (
    ActiveBindingProjection,
    ActorRef,
    BindingRef,
    DeviceRef,
    PersonRef,
    RegistryObserverReadContext,
    RegistryReadActor,
    RequesterRef,
    RequesterSnapshot,
    RegistrationRequest,
    InventoryQualityProjection,
)
import domain_ports.registry_contracts as registry_contracts
from registry_adapter.http import ShadowReadRegistryPort


pytestmark = pytest.mark.no_db


def _local_binding() -> ActiveBindingProjection:
    return ActiveBindingProjection(
        device=DeviceRef(external_id="registry-ref-opaque-device-1"),
        binding=BindingRef(external_id="registry-ref-opaque-binding-1"),
        requester=RequesterRef(external_id="registry-ref-opaque-person-1"),
        requester_snapshot=RequesterSnapshot(
            person=PersonRef(external_id="registry-ref-opaque-person-1"),
            display_name="Requester One",
        ),
        relationship_type="primary_user",
        source="local_authoritative",
    )


class _LocalPort:
    async def active_binding(self, _device: DeviceRef) -> ActiveBindingProjection:
        return _local_binding()


class _ExternalPort:
    async def active_binding(self, _device: DeviceRef) -> ActiveBindingProjection:
        return _local_binding().model_copy(
            update={"relationship_type": "responsible", "source": "external_authoritative"}
        )


class _InventoryQualityLocalPort:
    async def inventory_quality(self) -> InventoryQualityProjection:
        return InventoryQualityProjection(
            active_pc_without_location_count=2,
            source="local_authoritative",
        )


class _InventoryQualityExternalPort:
    async def inventory_quality(self) -> InventoryQualityProjection:
        return InventoryQualityProjection(
            active_pc_without_location_count=3,
            source="external_authoritative",
        )


class _TicketParticipantLocalPort:
    async def ticket_participant(self, _person: PersonRef):
        return registry_contracts.TicketParticipantProjection(
            person=PersonRef(external_id="registry-ref-opaque-person-1"),
            display_name="Requester One",
            full_name="Requester One",
            email="local@example.test",
            source="local_authoritative",
        )


class _TicketParticipantExternalPort:
    async def ticket_participant(self, _person: PersonRef):
        return registry_contracts.TicketParticipantProjection(
            person=PersonRef(external_id="registry-ref-opaque-person-1"),
            display_name="Requester One",
            full_name="Requester One",
            email="external@example.test",
            source="external_authoritative",
        )


class _OnBehalfLocalPort:
    async def authorize_on_behalf(self, **_kwargs):
        return registry_contracts.OnBehalfAllowed(
            affected=RequesterRef(external_id="affected-person"),
            source="local_authoritative",
        )


class _OnBehalfExternalPort:
    async def authorize_on_behalf(self, **_kwargs):
        return registry_contracts.OnBehalfDenied(code="registry_on_behalf_scope_denied")


class _ProfileCompletionLocalPort:
    async def requester_profile_completion(self, _observer, person: RequesterRef):
        return registry_contracts.RequesterProfileCompletionProjection(
            person=person,
            complete=True,
            blocks=False,
            status="complete",
            missing_field_keys=(),
            source="local_authoritative",
        )


class _ProfileCompletionExternalPort:
    async def requester_profile_completion(self, _observer, person: RequesterRef):
        return registry_contracts.RequesterProfileCompletionProjection(
            person=person,
            complete=False,
            blocks=True,
            status="required",
            missing_field_keys=("phone",),
            source="external_authoritative",
        )


class _CommandLocalPort(_LocalPort):
    async def request_registration(self, request: RegistrationRequest):
        return {"local_operation_id": request.operation_id}


class _CommandExternalPort(_ExternalPort):
    def __init__(self) -> None:
        self.called = False

    async def request_registration(self, request: RegistrationRequest):
        self.called = True
        return {"external_operation_id": request.operation_id}


@pytest.mark.asyncio
async def test_shadow_mismatch_never_changes_authorization() -> None:
    evidence: list[dict[str, object]] = []
    shadow_port = ShadowReadRegistryPort(
        authoritative=_LocalPort(),
        shadow=_ExternalPort(),
        mismatch_reporter=evidence.append,
    )

    result = await shadow_port.active_binding(DeviceRef(external_id="registry-ref-opaque-device-1"))
    await asyncio.sleep(0)

    assert result.source == "local_authoritative"
    assert evidence == [
        {
            "operation": "active_binding",
            "outcome": "mismatch",
            "fields": ("relationship_type",),
        }
    ]


@pytest.mark.asyncio
async def test_shadow_registry_commands_never_call_external_port() -> None:
    external = _CommandExternalPort()
    shadow_port = ShadowReadRegistryPort(
        authoritative=_CommandLocalPort(),
        shadow=external,
    )

    result = await shadow_port.request_registration(
        RegistrationRequest(
            operation_id="registry-operation-1",
            device=DeviceRef(external_id="registry-ref-opaque-device-1"),
        )
    )

    assert result == {"local_operation_id": "registry-operation-1"}
    assert external.called is False


@pytest.mark.asyncio
async def test_shadow_inventory_quality_keeps_local_count_and_reports_redacted_mismatch() -> None:
    evidence: list[dict[str, object]] = []
    port = ShadowReadRegistryPort(
        authoritative=_InventoryQualityLocalPort(),
        shadow=_InventoryQualityExternalPort(),
        mismatch_reporter=evidence.append,
    )

    result = await port.inventory_quality()
    await asyncio.sleep(0)

    assert result.active_pc_without_location_count == 2
    assert result.source == "local_authoritative"
    assert evidence == [
        {
            "operation": "inventory_quality",
            "outcome": "mismatch",
            "fields": ("active_pc_without_location_count",),
        }
    ]


@pytest.mark.asyncio
async def test_shadow_ticket_participant_reports_only_purpose_bound_field_names() -> None:
    evidence: list[dict[str, object]] = []
    port = ShadowReadRegistryPort(
        authoritative=_TicketParticipantLocalPort(),
        shadow=_TicketParticipantExternalPort(),
        mismatch_reporter=evidence.append,
    )

    result = await port.ticket_participant(
        PersonRef(external_id="registry-ref-opaque-person-1")
    )
    await asyncio.sleep(0)

    assert result.email == "local@example.test"
    assert evidence == [
        {
            "operation": "ticket_participant",
            "outcome": "mismatch",
            "fields": ("email",),
        }
    ]


@pytest.mark.asyncio
async def test_shadow_on_behalf_authorization_never_changes_local_decision() -> None:
    evidence: list[dict[str, object]] = []
    port = ShadowReadRegistryPort(
        authoritative=_OnBehalfLocalPort(),
        shadow=_OnBehalfExternalPort(),
        mismatch_reporter=evidence.append,
    )
    actor = RegistryReadActor(
        actor=ActorRef(external_id="verified-ui-user"),
        role="user",
        requester=RequesterRef(external_id="creator-person"),
    )

    result = await port.authorize_on_behalf(
        actor=actor,
        creator=RequesterRef(external_id="creator-person"),
        affected=RequesterRef(external_id="affected-person"),
        policy=registry_contracts.OnBehalfPolicyProjection(scope="same_department"),
    )
    await asyncio.sleep(0)

    assert result.status == "allowed"
    assert result.source == "local_authoritative"
    assert evidence == [
        {
            "operation": "authorize_on_behalf",
            "outcome": "mismatch",
            "fields": ("outcome",),
        }
    ]


@pytest.mark.asyncio
async def test_shadow_profile_completion_keeps_local_authority_and_redacts_mismatch() -> None:
    evidence: list[dict[str, object]] = []
    port = ShadowReadRegistryPort(
        authoritative=_ProfileCompletionLocalPort(),
        shadow=_ProfileCompletionExternalPort(),
        mismatch_reporter=evidence.append,
    )

    result = await port.requester_profile_completion(
        RegistryObserverReadContext(source="observer.web_cabinet"),
        RequesterRef(external_id="person-1"),
    )
    await asyncio.sleep(0)

    assert result.source == "local_authoritative"
    assert evidence == [
        {
            "operation": "requester_profile_completion",
            "outcome": "mismatch",
            "fields": ("blocks", "complete", "missing_field_keys", "status"),
        }
    ]
