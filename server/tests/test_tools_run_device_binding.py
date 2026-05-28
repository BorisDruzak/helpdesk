import json
from types import SimpleNamespace

import pytest

from tools.handlers import _require_ticket_device_match


class _FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ticket_device_match_guard_rejects_mismatch(monkeypatch):
    class _FakeTicketEventsRepo:
        def __init__(self, _session):
            pass

        async def get_ticket(self, _ticket_id):
            return SimpleNamespace(device_id="device-a")

    monkeypatch.setattr("app.db.get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr("app.repos.ticket_events_repo.TicketEventsRepo", _FakeTicketEventsRepo)

    response = await _require_ticket_device_match(
        ticket_id="ticket-a",
        device_id="device-b",
    )

    assert response is not None
    assert response.status == 403
    payload = json.loads(response.text)
    assert payload["status"] == "error"
    assert payload["error_code"] == "DEVICE_MISMATCH"
    assert payload["ticket_id"] == "ticket-a"
    assert payload["device_id"] == "device-b"
    assert payload["bound_device_id"] == "device-a"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ticket_device_match_guard_rejects_unknown_ticket(monkeypatch):
    class _FakeTicketEventsRepo:
        def __init__(self, _session):
            pass

        async def get_ticket(self, _ticket_id):
            return None

    monkeypatch.setattr("app.db.get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr("app.repos.ticket_events_repo.TicketEventsRepo", _FakeTicketEventsRepo)

    response = await _require_ticket_device_match(
        ticket_id="missing-ticket",
        device_id="device-a",
    )

    assert response is not None
    assert response.status == 404
    payload = json.loads(response.text)
    assert payload["status"] == "error"
    assert payload["error_code"] == "UNKNOWN_TICKET"


@pytest.mark.asyncio
@pytest.mark.no_db
async def test_ticket_device_match_guard_allows_matching_ticket(monkeypatch):
    class _FakeTicketEventsRepo:
        def __init__(self, _session):
            pass

        async def get_ticket(self, _ticket_id):
            return SimpleNamespace(device_id="device-a")

    monkeypatch.setattr("app.db.get_session", lambda: _FakeSessionContext())
    monkeypatch.setattr("app.repos.ticket_events_repo.TicketEventsRepo", _FakeTicketEventsRepo)

    response = await _require_ticket_device_match(
        ticket_id="ticket-a",
        device_id="device-a",
    )

    assert response is None
