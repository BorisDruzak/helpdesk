from types import SimpleNamespace

import pytest

from tickets.account_access_service import TicketBindingAccessService


pytestmark = pytest.mark.no_db


def _ticket(**fields):
    values = {
        "device_id": "device-1",
        "requester_external_ref": None,
        "requester_snapshot_json": None,
        "requester_binding_id": None,
        "requester_person_id": None,
    }
    values.update(fields)
    return SimpleNamespace(**values)


def test_active_device_binding_limits_ticket_access_to_the_bound_requester():
    access = object.__new__(TicketBindingAccessService)
    binding = {"device_id": "device-1", "binding_id": "binding-1", "person_id": "person-1"}

    assert access._ticket_allowed(_ticket(requester_binding_id="binding-1"), binding) is True
    assert access._ticket_allowed(_ticket(requester_person_id="person-1"), binding) is True
    assert access._ticket_allowed(_ticket(requester_binding_id="binding-2", requester_person_id="person-2"), binding) is False
    assert access._ticket_allowed(_ticket(device_id="device-2", requester_binding_id="binding-1"), binding) is False


def test_active_device_binding_matches_valid_neutral_requester_reference_only():
    access = object.__new__(TicketBindingAccessService)
    binding = {"device_id": "device-1", "binding_id": "binding-1", "person_id": "person-1"}
    snapshot = {"person": {"external_id": "person-1"}, "display_name": "Bound User"}

    assert access._ticket_allowed(
        _ticket(requester_external_ref="person-1", requester_snapshot_json=snapshot), binding
    ) is True
    assert access._ticket_allowed(
        _ticket(requester_external_ref="person-2", requester_snapshot_json={**snapshot, "person": {"external_id": "person-2"}}), binding
    ) is False
