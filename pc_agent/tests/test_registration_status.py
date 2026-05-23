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

    async def json(self):
        return self.payload


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
async def test_registration_api_client_creates_confirmed_binding_session(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(
            payload={
                "status": "success",
                "data": {
                    "session": {"session_id": "server-session-1", "account_mode": "confirmed_binding"},
                    "session_token": "token-1",
                },
            }
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.create_confirmed_binding_account_session("binding-1")

    assert result["session"]["session_id"] == "server-session-1"
    assert fake_session.calls[0]["method"] == "POST"
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-sessions/confirmed-binding"
    assert fake_session.calls[0]["json"] == {"binding_id": "binding-1"}


@pytest.mark.asyncio
async def test_registration_api_client_requests_other_account_login(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(payload={"status": "success", "data": {"request_id": "request-1", "status": "pending_verification"}})
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.request_other_account_login({"full_name": "Other", "login": "other", "reason": "test"})

    assert result["request_id"] == "request-1"
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-login-requests"


@pytest.mark.asyncio
async def test_registration_api_client_validates_account_session(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(payload={"status": "success", "data": {"valid": True}}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.validate_account_session("session-1", session_token="token-1")

    assert result["valid"] is True
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-sessions/session-1/validate"
    assert fake_session.calls[0]["params"] == {"session_token": "token-1"}


@pytest.mark.asyncio
async def test_registration_api_client_creates_pending_session_and_logs_out(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(
        FakeResponse(
            payload={
                "status": "success",
                "data": {
                    "session": {"session_id": "pending-session-1", "account_mode": "registration_pending"},
                    "session_token": "pending-token",
                },
            }
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    pending = await client.create_registration_pending_account_session("claim-1")
    assert pending["session"]["session_id"] == "pending-session-1"
    assert fake_session.calls[0]["url"] == "http://localhost:8666/api/registry/agent/account-sessions/registration-pending"
    assert fake_session.calls[0]["json"] == {"claim_id": "claim-1"}

    fake_session.response = FakeResponse(payload={"status": "success", "data": {"session": {"verification_status": "revoked"}}})
    logged_out = await client.logout_account_session("pending-session-1", session_token="pending-token")
    assert logged_out["session"]["verification_status"] == "revoked"
    assert fake_session.calls[1]["url"] == "http://localhost:8666/api/registry/agent/account-sessions/pending-session-1/logout"
    assert fake_session.calls[1]["json"] == {"session_token": "pending-token"}


@pytest.mark.asyncio
async def test_registration_api_client_get_account_state_normalizes_auth_error(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="stale-token")
    fake_session = FakeSession(
        FakeResponse(
            status=401,
            payload={
                "status": "error",
                "error": "Требуется аутентификация",
                "error_code": "AUTH_REQUIRED",
            },
        )
    )

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    result = await client.get_account_state()

    assert result["status"] == "error"
    assert result["http_status"] == 401
    assert result["error_code"] == "AUTH_REQUIRED"
    assert "авторизация устройства" in result["error"]
    assert "\\u0442" not in result["error"]


@pytest.mark.asyncio
async def test_create_ticket_sends_only_requester_account_session_when_passed(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(payload={"status": "ok", "ticket": {"ticket_id": "ticket-1"}}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.create_ticket(
        description="Need help",
        requester_account={
            "account_session_id": "session-1",
            "session_token": "token-1",
            "account_mode": "verified_other_account",
            "display_name": "Other User",
            "created_from_other_account": True,
        },
    )

    assert fake_session.calls[0]["json"]["requester_account"] == {
        "session_id": "session-1",
        "session_token": "token-1",
    }
    assert fake_session.calls[0]["json"]["require_account_session"] is True


@pytest.mark.asyncio
async def test_preview_ticket_create_includes_account_session(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(payload={"status": "ok", "preview": {}}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)

    await client.preview_ticket_create(
        request_template_key="printer",
        account_session={"account_session_id": "session-1", "session_token": "token-1"},
    )

    call = fake_session.calls[0]
    assert call["json"]["requester_account"] == {"session_id": "session-1", "session_token": "token-1"}
    assert call["headers"]["X-Account-Session-Id"] == "session-1"
    assert call["headers"]["X-Account-Session-Token"] == "token-1"


@pytest.mark.asyncio
async def test_ticket_actions_include_account_session(monkeypatch):
    client = TicketApiClient("http://localhost:8666/api", "device-1", user_display_name="User", auth_token="token-123")
    fake_session = FakeSession(FakeResponse(payload={"status": "ok", "tickets": [], "ticket": {"ticket_id": "ticket-1"}}))

    async def fake_get_session():
        return fake_session

    monkeypatch.setattr(client, "_get_session", fake_get_session)
    account = {"account_session_id": "session-1", "session_token": "token-1"}

    await client.list_tickets(account_session=account)
    await client.get_ticket("ticket-1", account_session=account)
    await client.send_message("ticket-1", "hello", account_session=account)
    await client.mark_ticket_read("ticket-1", 10, account_session=account)

    assert fake_session.calls[0]["params"]["account_session_id"] == "session-1"
    assert fake_session.calls[1]["params"]["account_session_id"] == "session-1"
    assert fake_session.calls[2]["json"]["requester_account"] == {"session_id": "session-1", "session_token": "token-1"}
    assert fake_session.calls[2]["headers"]["X-Account-Session-Id"] == "session-1"
    assert fake_session.calls[3]["json"]["requester_account"] == {"session_id": "session-1", "session_token": "token-1"}
