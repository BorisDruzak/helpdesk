from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, DeviceRegistrationClaim
from registry.account_session_service import AccountSessionService
from auth.service import AuthService
from registry.registration_service import RegistrationService
from server import create_app
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _device(device_id: str) -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.59",
        hostname="api-reg",
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


@pytest.mark.asyncio
async def test_agent_cannot_submit_profile_for_different_device_id(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_device_id = str(uuid.uuid4())
    other_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([_device(actor_device_id), _device(other_device_id)])
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers(f"{TEST_AGENT_PREFIX}{actor_device_id}"),
        json={"device_id": other_device_id, "profile": {"full_name": "Agent User"}},
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_real_generated_agent_token_can_submit_own_registration_profile(test_engine):
    import app.db as app_db
    import app.db.engine as app_db_engine
    import auth.service as auth_service_module
    import web_api.registry_handlers as registry_handlers_module

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    with patch.object(app_db, "get_session", test_get_session), \
        patch.object(app_db_engine, "get_session", test_get_session), \
        patch.object(auth_service_module, "get_session", test_get_session), \
        patch.object(registry_handlers_module, "get_session", test_get_session):
        app = create_app()
        app.on_startup.clear()
        app.on_cleanup.clear()
        device_id = str(uuid.uuid4())
        token = await AuthService(app["state"]).generate_agent_token(device_id=device_id, expires_hours=1)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post(
                "/api/registry/agent/profile",
                headers=_headers(token),
                json={"profile": {"full_name": "Real Agent", "email": "real-agent@example.test"}},
            )
            status = response.status
            text = await response.text()
            payload = await response.json() if response.content_type == "application/json" else {}
        finally:
            await client.close()

    assert status == 200, text
    assert payload["data"]["registration"]["status"] == "pending_user_confirmation"
    assert payload["data"]["asset"]["device_id"] == device_id


@pytest.mark.asyncio
async def test_user_cannot_submit_profile_for_arbitrary_device_id(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers("test-ui-user:ordinary-user"),
        json={"device_id": device_id, "profile": {"full_name": "Ordinary User"}},
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_submit_profile_validates_device_id_and_missing_device(test_client):
    bad = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={"device_id": "not-a-uuid", "profile": {"full_name": "Bad"}},
    )
    missing = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={"device_id": str(uuid.uuid4()), "profile": {"full_name": "Missing"}},
    )
    empty = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers(TEST_UI_SUPPORT_TOKEN),
        json={"profile": {"full_name": "Missing"}},
    )

    assert bad.status == 400
    assert missing.status == 404
    assert empty.status == 400


@pytest.mark.asyncio
async def test_user_cannot_confirm_unrelated_claim(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        result = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="claim-owner",
            display_name="Claim Owner",
            profile={"full_name": "Claim Owner", "email": "owner@example.test"},
        )
        await session.commit()

    response = await test_client.post(
        f"/api/registry/agent/claims/{result['registration']['claim_id']}/confirm",
        headers=_headers("test-ui-user:other-user"),
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_user_can_confirm_own_claim_by_email_identity(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        result = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="owner@example.test",
            display_name="Claim Owner",
            profile={"full_name": "Claim Owner", "email": "Owner@Example.Test"},
        )
        await session.commit()

    response = await test_client.post(
        f"/api/registry/agent/claims/{result['registration']['claim_id']}/confirm",
        headers=_headers("test-ui-user:owner@example.test"),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["registration"]["status"] == "pending_admin_review"


@pytest.mark.asyncio
async def test_user_cannot_confirm_same_display_name_with_different_identity(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        result = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="alice@example.test",
            display_name="Shared Display",
            profile={"full_name": "Shared Display", "email": "alice@example.test"},
        )
        await session.commit()

    response = await test_client.post(
        f"/api/registry/agent/claims/{result['registration']['claim_id']}/confirm",
        headers=_headers("test-ui-user:bob@example.test"),
    )

    assert response.status == 403


@pytest.mark.asyncio
async def test_user_confirm_claim_normalizes_windows_login(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        result = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="DOMAIN\\User",
            display_name="Domain User",
            profile={"full_name": "Domain User", "login": "DOMAIN\\User"},
        )
        await session.commit()

    response = await test_client.post(
        f"/api/registry/agent/claims/{result['registration']['claim_id']}/confirm",
        headers=_headers("test-ui-user:domain\\user"),
    )

    assert response.status == 200, await response.text()


@pytest.mark.asyncio
async def test_registration_status_missing_device_returns_404_for_admin_and_agent(test_client):
    missing_device_id = str(uuid.uuid4())

    admin_response = await test_client.get(
        f"/api/registry/agent/registration-status?device_id={missing_device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    agent_response = await test_client.get(
        "/api/registry/agent/registration-status",
        headers=_headers(f"{TEST_AGENT_PREFIX}{missing_device_id}"),
    )

    assert admin_response.status == 404
    assert (await admin_response.json())["error_code"] == "DEVICE_NOT_FOUND"
    assert agent_response.status == 404
    assert (await agent_response.json())["error_code"] == "DEVICE_NOT_FOUND"


@pytest.mark.asyncio
async def test_agent_registration_form_works_for_real_token_and_is_side_effect_free(test_engine):
    import app.db as app_db
    import app.db.engine as app_db_engine
    import auth.service as auth_service_module
    import web_api.registry_handlers as registry_handlers_module

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    with patch.object(app_db, "get_session", test_get_session), \
        patch.object(app_db_engine, "get_session", test_get_session), \
        patch.object(auth_service_module, "get_session", test_get_session), \
        patch.object(registry_handlers_module, "get_session", test_get_session):
        app = create_app()
        app.on_startup.clear()
        app.on_cleanup.clear()
        device_id = str(uuid.uuid4())
        token = await AuthService(app["state"]).generate_agent_token(device_id=device_id, expires_hours=1)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.get(
                "/api/registry/agent/registration-form",
                headers=_headers(token),
            )
            status = response.status
            text = await response.text()
            payload = await response.json() if response.content_type == "application/json" else {}
        finally:
            await client.close()

    assert status == 200, text
    assert payload["data"]["form"]["key"] == "agent_device_registration"
    assert payload["data"]["registration"]["status"] == "unregistered"
    assert {field["key"] for field in payload["data"]["form"]["fields"]} >= {"full_name", "login", "relationship_type"}
    async with session_maker() as session:
        rows = (await session.execute(
            DeviceRegistrationClaim.__table__.select().where(DeviceRegistrationClaim.device_id == device_id)
        )).all()
    assert rows == []


@pytest.mark.asyncio
async def test_registration_form_forbids_user_and_validates_admin_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    user_response = await test_client.get(
        f"/api/registry/agent/registration-form?device_id={device_id}",
        headers=_headers("test-ui-user:ordinary-user"),
    )
    missing_admin_device = await test_client.get(
        "/api/registry/agent/registration-form",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    bad_admin_device = await test_client.get(
        "/api/registry/agent/registration-form?device_id=not-a-uuid",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    existing_admin_device = await test_client.get(
        f"/api/registry/agent/registration-form?device_id={device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )

    assert user_response.status == 403
    assert missing_admin_device.status == 400
    assert bad_admin_device.status == 400
    assert existing_admin_device.status == 200
    payload = await existing_admin_device.json()
    assert payload["data"]["registration"]["device_id"] == device_id


@pytest.mark.asyncio
async def test_account_state_real_agent_token_is_side_effect_free(test_engine):
    import app.db as app_db
    import app.db.engine as app_db_engine
    import auth.service as auth_service_module
    import web_api.registry_handlers as registry_handlers_module

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    with patch.object(app_db, "get_session", test_get_session), \
        patch.object(app_db_engine, "get_session", test_get_session), \
        patch.object(auth_service_module, "get_session", test_get_session), \
        patch.object(registry_handlers_module, "get_session", test_get_session):
        app = create_app()
        app.on_startup.clear()
        app.on_cleanup.clear()
        device_id = str(uuid.uuid4())
        token = await AuthService(app["state"]).generate_agent_token(device_id=device_id, expires_hours=1)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.get("/api/registry/agent/account-state", headers=_headers(token))
            status = response.status
            text = await response.text()
            payload = await response.json() if response.content_type == "application/json" else {}
        finally:
            await client.close()

    assert status == 200, text
    assert payload["data"]["device_id"] == device_id
    assert payload["data"]["accounts"] == []
    assert payload["data"]["can_register"] is True
    async with session_maker() as session:
        rows = (await session.execute(
            DeviceRegistrationClaim.__table__.select().where(DeviceRegistrationClaim.device_id == device_id)
        )).all()
    assert rows == []


@pytest.mark.asyncio
async def test_account_state_forbids_user_and_validates_admin_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    user_response = await test_client.get(
        f"/api/registry/agent/account-state?device_id={device_id}",
        headers=_headers("test-ui-user:ordinary-user"),
    )
    missing_admin_device = await test_client.get(
        "/api/registry/agent/account-state",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    unknown_admin_device = await test_client.get(
        f"/api/registry/agent/account-state?device_id={uuid.uuid4()}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    existing_admin_device = await test_client.get(
        f"/api/registry/agent/account-state?device_id={device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )

    assert user_response.status == 403
    assert missing_admin_device.status == 400
    assert unknown_admin_device.status == 404
    assert (await unknown_admin_device.json())["error_code"] == "DEVICE_NOT_FOUND"
    assert existing_admin_device.status == 200
    payload = await existing_admin_device.json()
    assert payload["data"]["device_id"] == device_id
    assert payload["data"]["can_register"] is True


@pytest.mark.asyncio
async def test_account_state_active_binding_returns_confirmed_account(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered@example.test",
            display_name="Registered User",
            profile={"full_name": "Registered User", "email": "registered@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        await session.commit()

    response = await test_client.get(
        f"/api/registry/agent/account-state?device_id={device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    account = payload["data"]["accounts"][0]
    assert account["account_mode"] == "confirmed_binding"
    assert account["binding_id"] == approved["binding"]["binding_id"]
    assert account["person_id"] == approved["binding"]["person_id"]
    assert account["display_name"] == "Registered User"
    assert account["email"] == "registered@example.test"
    assert account["registration_status"] == "admin_confirmed"
    assert account["can_login"] is True
    assert payload["data"]["can_register"] is False


@pytest.mark.asyncio
async def test_confirmed_binding_session_endpoint_real_agent_token(test_engine):
    import app.db as app_db
    import app.db.engine as app_db_engine
    import auth.service as auth_service_module
    import web_api.registry_handlers as registry_handlers_module

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)

    @asynccontextmanager
    async def test_get_session():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    with patch.object(app_db, "get_session", test_get_session), \
        patch.object(app_db_engine, "get_session", test_get_session), \
        patch.object(auth_service_module, "get_session", test_get_session), \
        patch.object(registry_handlers_module, "get_session", test_get_session):
        app = create_app()
        app.on_startup.clear()
        app.on_cleanup.clear()
        device_id = str(uuid.uuid4())
        token = await AuthService(app["state"]).generate_agent_token(device_id=device_id, expires_hours=1)
        async with session_maker() as session:
            session.add(_device(device_id))
            claim = await RegistrationService(session).submit_agent_profile_claim(
                device_id=device_id,
                requester_id="registered@example.test",
                display_name="Registered User",
                profile={"full_name": "Registered User", "email": "registered@example.test", "user_confirmed": True},
            )
            approved = await RegistrationService(session).approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
            await session.commit()
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            response = await client.post(
                "/api/registry/agent/account-sessions/confirmed-binding",
                headers=_headers(token),
                json={"binding_id": approved["binding"]["binding_id"]},
            )
            status = response.status
            text = await response.text()
            payload = await response.json() if response.content_type == "application/json" else {}
        finally:
            await client.close()

    assert status == 200, text
    assert payload["data"]["session"]["account_mode"] == "confirmed_binding"
    assert payload["data"]["session"]["binding_id"] == approved["binding"]["binding_id"]
    assert payload["data"]["session"]["display_name"] == "Registered User"
    assert payload["data"]["session"]["email"] == "registered@example.test"
    assert payload["data"]["session"]["person"]["display_name"] == "Registered User"
    assert payload["data"].get("session_token")


@pytest.mark.asyncio
async def test_other_account_login_request_and_admin_approval_endpoints(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered@example.test",
            display_name="Registered User",
            profile={"full_name": "Registered User", "email": "registered-api@example.test", "user_confirmed": True},
        )
        await RegistrationService(session).approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        await session.commit()

    requested = await test_client.post(
        "/api/registry/agent/account-login-requests",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={
            "full_name": "Other User",
            "login": "other",
            "email": "other@example.test",
            "phone": "+15551234567",
            "reason": "Temporary replacement",
        },
    )
    assert requested.status == 200, await requested.text()
    request_payload = await requested.json()
    request_id = request_payload["data"]["request_id"]

    listed = await test_client.get(
        "/api/web/admin/registry/account-login-requests",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    approved = await test_client.post(
        f"/api/web/admin/registry/account-login-requests/{request_id}/approve",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={},
    )

    assert listed.status == 200, await listed.text()
    assert any(item["request_id"] == request_id for item in (await listed.json())["data"]["items"])
    assert approved.status == 200, await approved.text()
    approved_payload = await approved.json()
    assert approved_payload["data"]["session"]["account_mode"] == "verified_other_account"
    assert approved_payload["data"]["session"]["declared_account"]["phone"] == "+15551234567"


@pytest.mark.asyncio
async def test_account_state_includes_server_sessions_and_pending_login_requests(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered@example.test",
            display_name="Registered User",
            profile={"full_name": "Registered User", "email": "registered-state@example.test", "user_confirmed": True},
        )
        approved = await RegistrationService(session).approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        request = await AccountSessionService(session).create_other_account_login_request(
            device_id=device_id,
            requested_account={"full_name": "Other User", "login": "other", "reason": "Temporary replacement"},
        )
        await session.commit()

    response = await test_client.get(
        f"/api/registry/agent/account-state?device_id={device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["server_sessions"]
    assert payload["data"]["pending_login_requests"][0]["request_id"] == request["request_id"]
    assert payload["data"]["can_request_other_account_login"] is True


@pytest.mark.asyncio
async def test_admin_approve_and_reject_registration_claim(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    approve_device_id = str(uuid.uuid4())
    reject_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([_device(approve_device_id), _device(reject_device_id)])
        service = RegistrationService(session)
        approve_claim = await service.submit_agent_profile_claim(
            device_id=approve_device_id,
            requester_id="approve-owner",
            display_name="Approve Owner",
            profile={"full_name": "Approve Owner", "email": "approve@example.test", "user_confirmed": True},
        )
        reject_claim = await service.submit_agent_profile_claim(
            device_id=reject_device_id,
            requester_id="reject-owner",
            display_name="Reject Owner",
            profile={"full_name": "Reject Owner", "email": "reject-api@example.test"},
        )
        await session.commit()

    approved = await test_client.post(
        f"/api/web/admin/registry/registrations/{approve_claim['registration']['claim_id']}/approve",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={},
    )
    rejected = await test_client.post(
        f"/api/web/admin/registry/registrations/{reject_claim['registration']['claim_id']}/reject",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={"reason": "wrong user"},
    )

    assert approved.status == 200, await approved.text()
    assert rejected.status == 200, await rejected.text()
