from __future__ import annotations

import json

import pytest

from pc_agent.ui_gui import main as gui_main


class FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return json.dumps(self.payload)


class FakeClientSession:
    calls: list[dict] = []
    response: FakeResponse

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_verify_token_on_server_rejects_auth_required(monkeypatch):
    FakeClientSession.calls = []
    FakeClientSession.response = FakeResponse(
        401,
        {"status": "error", "error": "Authentication required", "error_code": "AUTH_REQUIRED"},
    )
    monkeypatch.setattr(gui_main.aiohttp, "ClientSession", FakeClientSession)

    assert await gui_main.verify_token_on_server("http://localhost:8666/api", "stale-token") is False

    assert FakeClientSession.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-state"
    assert FakeClientSession.calls[0]["headers"]["Authorization"] == "Bearer stale-token"


@pytest.mark.asyncio
async def test_verify_token_on_server_accepts_account_state_success(monkeypatch):
    FakeClientSession.calls = []
    FakeClientSession.response = FakeResponse(
        200,
        {"status": "success", "data": {"device_id": "device-1", "accounts": []}},
    )
    monkeypatch.setattr(gui_main.aiohttp, "ClientSession", FakeClientSession)

    assert await gui_main.verify_token_on_server("http://localhost:8666/api", "valid-token") is True
