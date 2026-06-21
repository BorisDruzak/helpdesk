from app.db.models import Ticket, _ensure_ticket_requester_id
import pytest


pytestmark = pytest.mark.db_cleanup("tickets")

def _ticket(**overrides) -> Ticket:
    values = {
        "ticket_id": "ticket-1",
        "device_id": "device-1",
        "title": "title",
        "description": "description",
        "status": "new",
    }
    values.update(overrides)
    return Ticket(**values)


def test_ticket_model_backfills_requester_from_device_for_legacy_direct_insert() -> None:
    ticket = _ticket(requester_id=None)

    _ensure_ticket_requester_id(None, None, ticket)

    assert ticket.requester_id == "device:device-1"


def test_ticket_model_backfills_requester_from_ticket_when_device_missing() -> None:
    ticket = _ticket(device_id="", requester_id=" ")

    _ensure_ticket_requester_id(None, None, ticket)

    assert ticket.requester_id == "legacy:ticket-1"


def test_ticket_model_preserves_explicit_requester() -> None:
    ticket = _ticket(requester_id="user:alice")

    _ensure_ticket_requester_id(None, None, ticket)

    assert ticket.requester_id == "user:alice"
