from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from domain_ports import ActiveBindingProjection, ActorRef, DeviceRef, RegistryReadActor, RequesterRef, RequesterSnapshot
from domain_ports.registry_contracts import BindingRef
from domain_ports.registry_contracts import RequesterProfileProjection, RegistryUnavailable
from registry_adapter.local import LocalRegistryAdapter
from web_api.support_handlers import _build_support_registry_snapshot, _build_support_sla_ola_payload, _ticket_timer_payload

pytestmark = pytest.mark.no_db
NOW = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)


def timer_ticket(**changes):
    values = dict(created_at=NOW - timedelta(minutes=10), first_response_due_at=NOW + timedelta(minutes=5),
                  first_response_at=None, sla_paused_at=None, sla_paused_seconds=0)
    return SimpleNamespace(**(values | changes))


def timer(ticket, now=NOW):
    return _ticket_timer_payload(ticket, due_attr="first_response_due_at", completed_attr="first_response_at",
                                 paused_attr="sla_paused_at", paused_seconds_attr="sla_paused_seconds", now=now)


def test_completed_first_response_is_distinct_from_missing_deadline():
    result = timer(timer_ticket(first_response_at=NOW - timedelta(minutes=1)))
    assert result.status == "completed"
    assert result.completed_at == (NOW - timedelta(minutes=1)).isoformat()
    assert result.completed_within_target is True
    assert result.remaining_seconds is None


def test_completed_late_reply_preserves_breach():
    result = timer(timer_ticket(first_response_at=NOW, first_response_due_at=NOW - timedelta(minutes=1)))
    assert result.status == "completed"
    assert result.completed_within_target is False


def test_recorded_breach_remains_after_completion_and_later_pauses():
    ticket = timer_ticket(first_response_at=NOW, first_response_breached_at=NOW - timedelta(minutes=1), sla_paused_seconds=3600)
    result = _ticket_timer_payload(ticket, due_attr="first_response_due_at", completed_attr="first_response_at",
                                  breached_attr="first_response_breached_at", paused_seconds_attr="sla_paused_seconds", now=NOW)
    assert result.completed_within_target is False


def test_resolved_ticket_uses_canonical_sla_stop_timestamp():
    ticket = timer_ticket(status="resolved", resolution_at=NOW - timedelta(minutes=1), resolution_due_at=NOW + timedelta(hours=1))
    result = _build_support_sla_ola_payload(ticket, now=NOW).resolution
    assert result.status == "completed"
    assert result.completed_at == ticket.resolution_at.isoformat()
    assert result.remaining_seconds is None


def test_paused_countdown_does_not_decrease_or_go_negative_while_waiting():
    ticket = timer_ticket(sla_paused_at=NOW - timedelta(minutes=1))
    before, after = timer(ticket), timer(ticket, NOW + timedelta(hours=1))
    assert before.status == after.status == "paused"
    assert before.remaining_seconds == after.remaining_seconds == 360


def test_local_profile_projection_includes_only_contact_fields_and_labels():
    person = SimpleNamespace(person_id="person-1", display_name="Заявитель", status="active",
                             email="person@example.test", phone="1234", metadata_json={"private": "omit"})
    profile = LocalRegistryAdapter._requester_profile_from_person(
        person=person, department_label="Отдел", location_label="Кабинет 1")
    assert profile.email == "person@example.test"
    assert profile.phone == "1234"
    assert "metadata_json" not in profile.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatched", [False, True])
async def test_support_profile_enrichment_checks_identity_and_actor(mismatched):
    actor = RegistryReadActor(actor=ActorRef(external_id="operator"), role="support")
    profile = RequesterProfileProjection(
        requester=RequesterRef(external_id="other" if mismatched else "person-1"), display_name="Заявитель",
        department_label="Отдел", location_label="Кабинет 1", status="active", source="local_authoritative",
    ).model_copy(update={"email": "person@example.test", "phone": "1234"})
    calls = []
    class Port:
        async def requester_snapshot(self, person):
            return RequesterSnapshot(person=person, display_name="Заявитель")
        async def requester_profile(self, person, *, actor):
            calls.append((person.external_id, actor))
            return profile
    ticket = SimpleNamespace(requester_person_id="person-1", requester_external_ref=None, requester_snapshot_json=None)
    result = await _build_support_registry_snapshot(ticket, registry_port=Port(), actor=actor)
    assert calls == [("person-1", actor)]
    assert result.person_email == (None if mismatched else "person@example.test")
    assert result.person_phone == (None if mismatched else "1234")
    assert result.location_display_name == (None if mismatched else "Кабинет 1")


@pytest.mark.asyncio
async def test_registry_unavailable_does_not_load_contact_data():
    actor = RegistryReadActor(actor=ActorRef(external_id="operator"), role="support")
    class Port:
        async def requester_snapshot(self, person):
            return RegistryUnavailable(code="registry_read_unavailable")
        async def requester_profile(self, *args, **kwargs):
            raise AssertionError("Unavailable identity must not expose contacts")
    ticket = SimpleNamespace(requester_person_id="person-1", requester_external_ref=None, requester_snapshot_json=None)
    result = await _build_support_registry_snapshot(ticket, registry_port=Port(), actor=actor)
    assert result.person_email is None


@pytest.mark.asyncio
async def test_device_owner_fallback_does_not_load_requester_contacts():
    actor = RegistryReadActor(actor=ActorRef(external_id="operator"), role="support")
    calls = []
    class Port:
        async def active_binding(self, device):
            return ActiveBindingProjection(device=device, binding=BindingRef(external_id="binding-1"),
                requester=RequesterRef(external_id="device-owner"),
                requester_snapshot=RequesterSnapshot(person={"external_id": "device-owner"}, display_name="Владелец устройства"),
                relationship_type="assigned", source="local_authoritative")
        async def requester_profile(self, *args, **kwargs):
            calls.append(args)
            return RequesterProfileProjection(requester=RequesterRef(external_id="device-owner"),
                display_name="Владелец устройства", email="owner@example.test", phone="1234",
                status="active", source="local_authoritative")
    ticket = SimpleNamespace(device_id="device-1", requester_person_id=None, requester_external_ref=None, requester_snapshot_json=None)
    result = await _build_support_registry_snapshot(ticket, registry_port=Port(), actor=actor)
    assert result.person_display_name == "Владелец устройства"
    assert calls == []
    assert result.person_email is None
