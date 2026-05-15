import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_gui.server_api import TicketApiClient


class FakeResponse:
    def __init__(self, status=200, text_payload=""):
        self.status = status
        self._text_payload = text_payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self._text_payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_agent_ticket_create_passes_safe_knowledge_attempts(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(status=200, text_payload='{"status":"ok","ticket":{"ticket_id":"ticket-1"}}'))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="VPN does not connect",
        knowledge_attempts=[
            {
                "item_id": "item-1",
                "version_id": "version-1",
                "result": "not_helpful",
                "surface": "agent_gui",
                "occurred_at": "2026-05-15T00:00:00Z",
            }
        ],
    )

    attempt = fake_session.calls[0]["json"]["knowledge_attempts"][0]
    assert attempt == {
        "item_id": "item-1",
        "version_id": "version-1",
        "result": "not_helpful",
        "surface": "agent_gui",
        "occurred_at": "2026-05-15T00:00:00Z",
    }
    assert "device_id" not in attempt
    assert "requester_id" not in attempt
