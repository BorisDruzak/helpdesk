import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_gui.server_api import TicketApiClient


class FakeResponse:
    def __init__(self, status=200, payload=None, text_payload=""):
        self.status = status
        self._payload = payload or {}
        self._text_payload = text_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text_payload

    async def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.response

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_get_service_catalog_current_reads_safe_catalog(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            text_payload='{"catalog_version":"v1","services":[{"service_code":"workplace","offerings":[]}]}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_service_catalog_current()

    assert result["catalog_version"] == "v1"
    call = fake_session.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "http://localhost:8666/api/service-catalog/current"
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_create_ticket_sends_service_catalog_selection(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={"status": "ok", "ticket": {"ticket_id": "ticket-1"}},
            text_payload='{"status":"ok","ticket":{"ticket_id":"ticket-1"}}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="Сломался ноутбук",
        request_template_key="laptop_incident",
        service_code="workplace",
        offering_code="laptop_broken",
        offering_full_code="workplace.laptop_broken",
    )

    payload = fake_session.calls[0]["json"]
    assert payload["service_code"] == "workplace"
    assert payload["offering_code"] == "laptop_broken"
    assert payload["offering_full_code"] == "workplace.laptop_broken"


@pytest.mark.asyncio
async def test_preview_ticket_create_sends_service_catalog_selection(monkeypatch):
    client = TicketApiClient(
        base_url="http://localhost:8666/api",
        device_id="device-1",
        user_display_name="User",
        auth_token="token-123",
    )
    fake_session = FakeSession(
        FakeResponse(
            status=200,
            payload={"status": "ok", "preview": {}},
            text_payload='{"status":"ok","preview":{}}',
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.preview_ticket_create(
        request_template_key="laptop_incident",
        service_code="workplace",
        offering_code="laptop_broken",
    )

    payload = fake_session.calls[0]["json"]
    assert payload["service_code"] == "workplace"
    assert payload["offering_code"] == "laptop_broken"
