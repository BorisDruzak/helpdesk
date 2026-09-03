from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import (
    Device,
    DeviceAccountSession,
    DeviceRegistrationClaim,
    DeviceUserBinding,
    RegistryDepartment,
    RegistryLocation,
    RegistryPerson,
    RegistryPersonIdentity,
    UiUser,
)
from auth.password_service import hash_password
from auth.rate_limit import reset_rate_limits
from auth.service import AuthService
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationService, RegistrationValidationError
from server import create_app
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


pytestmark = pytest.mark.db_cleanup("registration")


@pytest.fixture
def test_client(test_client_light):
    return test_client_light


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


async def _completed_requester_profile(
    session,
    *,
    login: str,
    department_id: str | None = None,
    location_id: str | None = None,
) -> RegistryPerson:
    suffix = uuid.uuid4().hex[:8]
    if department_id is None:
        department_id = str(uuid.uuid4())
        session.add(
            RegistryDepartment(
                department_id=department_id,
                code=f"test-{suffix}",
                name=f"Test Department {suffix}",
                status="active",
                source="test",
                metadata_json={},
            )
        )
    if location_id is None:
        location_id = str(uuid.uuid4())
        session.add(
            RegistryLocation(
                location_id=location_id,
                building=f"Test Building {suffix}",
                floor="1",
                room="101",
                display_name=f"Test Building {suffix} / 101",
                status="active",
                source="test",
                metadata_json={},
            )
        )
    person = RegistryPerson(
        person_id=str(uuid.uuid4()),
        display_name=f"Requester {login}",
        full_name=f"Requester {login}",
        email=login if "@" in login else None,
        phone="1001",
        department_id=department_id,
        location_id=location_id,
        source="test",
        status="active",
    )
    session.add(person)
    session.add(
        RegistryPersonIdentity(
            person_id=person.person_id,
            provider="ui_login",
            identifier=login,
            normalized_identifier=login.lower(),
            verified=True,
            source="test",
        )
    )
    return person


async def _seed_bound_ui_user(
    session,
    *,
    device_id: str,
    login: str,
    password: str = "StrongGuiPassword123!",
) -> dict:
    person = await _completed_requester_profile(session, login=login)
    await session.flush()
    session.add(
        UiUser(
            user_login=login,
            password_hash=hash_password(password),
            actor_role="user",
            is_active=True,
        )
    )
    binding = DeviceUserBinding(
        binding_id=str(uuid.uuid4()),
        device_id=device_id,
        person_id=person.person_id,
        relationship_type="primary_user",
        status="active",
        source="test",
        confirmed_by_admin="test-admin",
        confirmed_at=datetime.now(timezone.utc),
    )
    session.add(binding)
    await session.flush()
    return {"person": person, "binding": binding, "password": password}


@pytest.mark.asyncio
async def test_submit_agent_profile_claim_rejects_archived_ui_identity(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = f"archived-registration-{uuid.uuid4().hex[:8]}@example.test"
    async with session_maker() as session:
        session.add(_device(device_id))
        person = await _completed_requester_profile(session, login=login)
        person.status = "archived"
        await session.flush()

        with pytest.raises(RegistrationValidationError, match="archived"):
            await RegistrationService(session).submit_agent_profile_claim(
                device_id=device_id,
                requester_id=login,
                display_name="Archived Requester",
                profile={
                    "full_name": "Archived Requester",
                    "email": login,
                    "login": login,
                    "user_confirmed": True,
                },
                actor_id=login,
                actor_role="user",
            )

        claims = (
            await session.execute(
                select(DeviceRegistrationClaim).where(DeviceRegistrationClaim.device_id == device_id)
            )
        ).scalars().all()
        await session.commit()

    assert claims == []




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
async def test_agent_cannot_assert_user_confirmed(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/profile",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={
            "profile": {"full_name": "Forged User", "email": "forged@example.test", "user_confirmed": True}
        },
    )
    payload = await response.json()

    assert response.status == 403
    assert payload["error_code"] == "USER_CONFIRMATION_FORBIDDEN"


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
        await RegistryPolicyService(session).update_policies(
            {
                "registration": {
                    "require_admin_confirmation": True,
                    "auto_approve_first_binding": False,
                }
            },
            actor_id="admin",
        )
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
