from __future__ import annotations

import json
import pytest

from pc_agent.core.user_profile import UserProfileManager
from pc_agent.ui_gui.server_api import TicketApiClient


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return json.dumps(self.payload)


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return self.response


def apply_registration_status_for_test(manager: UserProfileManager, payload: dict) -> dict:
    profile = manager.load()
    registration = payload.get("registration")
    if isinstance(registration, dict):
        profile["registration_status"] = str(registration.get("status") or "unknown")
        if registration.get("pending_claim_id"):
            profile["last_claim_id"] = str(registration.get("pending_claim_id"))
    return manager.save(profile)


def test_handshake_registration_payload_updates_local_profile_status(tmp_path):
    manager = UserProfileManager(data_root=tmp_path)

    profile = apply_registration_status_for_test(
        manager,
        {"registration": {"status": "pending_admin_review", "pending_claim_id": "claim-1"}},
    )

    assert profile["registration_status"] == "pending_admin_review"
    assert profile["last_claim_id"] == "claim-1"
    assert manager.load()["registration_status"] == "pending_admin_review"


@pytest.mark.asyncio
async def test_registration_api_client_unwraps_success_data(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(payload={"status": "success", "data": {"registration": {"claim_id": "claim-1", "status": "pending_user_confirmation"}}})
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.submit_registration_profile({"full_name": "User"}, user_confirmed=False)

    assert result == {"registration": {"claim_id": "claim-1", "status": "pending_user_confirmation"}}
    assert fake_session.calls[0]["json"]["device_id"] == "device-1"


@pytest.mark.asyncio
async def test_registration_api_client_get_registration_form_unwraps_success_data(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(
            payload={
                "status": "success",
                "data": {
                    "form": {"key": "agent_device_registration", "fields": [{"key": "full_name"}]},
                    "registration": {"status": "unregistered"},
                    "registry_options": {},
                },
            }
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_registration_form()

    assert result["form"]["key"] == "agent_device_registration"
    assert result["registration"]["status"] == "unregistered"
    assert fake_session.calls[0]["method"] == "GET"
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/registration-form"


@pytest.mark.asyncio
async def test_registration_api_client_get_account_state_unwraps_success_data(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(
            payload={
                "status": "success",
                "data": {
                    "device_id": "device-1",
                    "accounts": [{"account_mode": "confirmed_binding", "binding_id": "binding-1"}],
                    "can_register": False,
                },
            }
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_account_state()

    assert result["device_id"] == "device-1"
    assert result["accounts"][0]["binding_id"] == "binding-1"
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-state"


@pytest.mark.asyncio
async def test_create_ticket_includes_requester_account_when_passed(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(payload={"status": "ok", "ticket": {"ticket_id": "ticket-1"}}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="Need help",
        requester_account={
            "account_session_id": "session-1",
            "account_mode": "other_account",
            "display_name": "Other User",
            "created_from_other_account": True,
        },
    )

    assert fake_session.calls[0]["json"]["requester_account"]["account_session_id"] == "session-1"
    assert fake_session.calls[0]["json"]["requester_account"]["created_from_other_account"] is True
