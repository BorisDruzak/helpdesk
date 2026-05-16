import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pc_agent.ui_gui.server_api import TicketApiClient


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
async def test_agent_treats_rollout_disabled_as_empty_suggestions(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(status=200, text_payload='{"status":"ok","suggestions":[],"known_errors":[],"workarounds":[]}'))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_knowledge_suggestions(
        service_code="network",
        offering_code="network.vpn_issue",
        request_template_key="vpn_issue",
        query="VPN does not connect",
    )

    assert result["suggestions"] == []
    call = fake_session.calls[0]
    assert call["url"] == "http://localhost:8666/api/knowledge/suggest"
    assert call["json"]["surface"] == "agent_gui"
    assert "rollout_policy_id" not in result
