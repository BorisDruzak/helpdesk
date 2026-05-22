from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
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
