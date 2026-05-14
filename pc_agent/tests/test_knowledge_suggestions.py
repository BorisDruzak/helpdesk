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

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_agent_fetches_knowledge_suggestions_with_service_context(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(status=200, text_payload='{"status":"ok","suggestions":[{"item_id":"item-1","title":"VPN"}]}')
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_knowledge_suggestions(
        service_code="network",
        offering_code="network.vpn_issue",
        request_template_key="vpn_issue",
        query="VPN не подключается",
    )

    assert result["suggestions"][0]["item_id"] == "item-1"
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/knowledge/suggest"
    assert call["json"]["service_code"] == "network"
    assert call["json"]["surface"] == "agent_gui"
    assert call["headers"]["Authorization"] == "Bearer token-123"


@pytest.mark.asyncio
async def test_agent_records_knowledge_feedback(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(status=200, text_payload='{"status":"ok","event":{"event_type":"helpful"}}'))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.record_knowledge_feedback(
        item_id="item-1",
        version_id="version-1",
        event_type="helpful",
        service_code="network",
        offering_code="network.vpn_issue",
    )

    assert result["event"]["event_type"] == "helpful"
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/knowledge/feedback"
    assert call["json"]["surface"] == "agent_gui"


@pytest.mark.asyncio
async def test_agent_create_ticket_sends_knowledge_attempts(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(status=200, text_payload='{"status":"ok","ticket":{"ticket_id":"ticket-1"}}')
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="VPN не подключается",
        knowledge_attempts=[{"item_id": "item-1", "version_id": "version-1", "result": "not_helpful"}],
    )

    assert fake_session.calls[0]["json"]["knowledge_attempts"][0]["item_id"] == "item-1"
