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
    DeviceBrowserPairing,
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
from registry.browser_pairing_service import BrowserPairingService
from registry.account_session_service import AccountSessionService
from auth.service import AuthService
from registry.policy_service import RegistryPolicyService
from registry.registration_service import RegistrationService, RegistrationValidationError
from server import create_app
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_ADMIN_TOKEN, TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX


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
async def test_agent_gui_password_login_bound_user_creates_device_scoped_session(test_client, test_engine):
    reset_rate_limits()
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = f"gui-owner-{uuid.uuid4().hex[:8]}@example.test"
    async with session_maker() as session:
        session.add(_device(device_id))
        seeded = await _seed_bound_ui_user(session, device_id=device_id, login=login)
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/account-sessions/login",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"login": login, "password": seeded["password"]},
    )
    payload = await response.json()

    assert response.status == 200, payload
    data = payload["data"]
    assert data["session_token"]
    assert data["session"]["account_mode"] == "confirmed_binding"
    assert data["session"]["verification_method"] == "gui_password"
    assert data["session"]["device_id"] == device_id
    assert data["session"]["binding_id"] == seeded["binding"].binding_id
    assert data["session"]["person_id"] == seeded["person"].person_id
    assert data["session"]["login"] == login


@pytest.mark.asyncio
async def test_agent_gui_password_login_wrong_password_rejects_without_session(test_client, test_engine):
    reset_rate_limits()
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = f"gui-wrong-{uuid.uuid4().hex[:8]}@example.test"
    async with session_maker() as session:
        session.add(_device(device_id))
        await _seed_bound_ui_user(session, device_id=device_id, login=login)
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/account-sessions/login",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"login": login, "password": "WrongPassword123!"},
    )
    payload = await response.json()

    assert response.status == 401, payload
    assert payload["error_code"] == "INVALID_CREDENTIALS"
    assert "session" not in payload
    async with session_maker() as session:
        rows = (
            await session.execute(select(DeviceAccountSession).where(DeviceAccountSession.device_id == device_id))
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_agent_gui_password_login_valid_user_on_other_device_rejects_without_session(test_client, test_engine):
    reset_rate_limits()
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_device_id = str(uuid.uuid4())
    owner_device_id = str(uuid.uuid4())
    login = f"gui-mismatch-{uuid.uuid4().hex[:8]}@example.test"
    async with session_maker() as session:
        session.add_all([_device(actor_device_id), _device(owner_device_id)])
        seeded = await _seed_bound_ui_user(session, device_id=owner_device_id, login=login)
        await session.commit()

    response = await test_client.post(
        "/api/registry/agent/account-sessions/login",
        headers=_headers(f"{TEST_AGENT_PREFIX}{actor_device_id}"),
        json={"login": login, "password": seeded["password"]},
    )
    payload = await response.json()

    assert response.status == 403, payload
    assert payload["error_code"] == "ACCOUNT_SESSION_DEVICE_MISMATCH"
    async with session_maker() as session:
        rows = (
            await session.execute(select(DeviceAccountSession).where(DeviceAccountSession.device_id == actor_device_id))
        ).scalars().all()
    assert rows == []


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
async def test_agent_browser_pairing_rejects_different_device_id(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    actor_device_id = str(uuid.uuid4())
    other_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([_device(actor_device_id), _device(other_device_id)])
        await session.commit()

    forbidden = await test_client.post(
        "/api/registry/agent/browser-pairings",
        headers=_headers(f"{TEST_AGENT_PREFIX}{actor_device_id}"),
        json={"device_id": other_device_id, "purpose": "login"},
    )
    created = await test_client.post(
        "/api/registry/agent/browser-pairings",
        headers=_headers(f"{TEST_AGENT_PREFIX}{actor_device_id}"),
        json={"purpose": "login"},
    )
    payload = await created.json()

    assert forbidden.status == 403
    assert created.status == 200, payload
    assert payload["data"]["device_id"] == actor_device_id
    assert payload["data"]["purpose"] == "login"
    assert payload["data"]["pairing_token"]
    assert payload["data"]["pairing_code"]


@pytest.mark.asyncio
async def test_web_user_lookup_browser_pairing_code_returns_minimal_redirect_payload(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        pairing = await BrowserPairingService(session).create_pairing(
            device_id=device_id,
            purpose="registration",
            actor_id=device_id,
        )
        await session.commit()

    response = await test_client.post(
        "/api/web/registry/browser-pairings/lookup",
        headers=_headers(f"{TEST_UI_USER_PREFIX}manual-code@example.test"),
        json={"pairing_code": pairing["pairing_code"]},
    )
    payload = await response.json()

    assert response.status == 200, payload
    data = payload["data"]
    assert data == {
        "pairing_id": pairing["pairing_id"],
        "purpose": "registration",
        "expires_at": pairing["expires_at"],
        "next_url": f"/app/device/register?pairing_id={pairing['pairing_id']}",
    }
    assert "device_id" not in data
    assert "device" not in data
    assert "pairing_token" not in data
    assert "pairing_code" not in data


@pytest.mark.asyncio
async def test_web_user_lookup_browser_pairing_code_rejects_inactive_pairings(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    expired_device_id = str(uuid.uuid4())
    consumed_device_id = str(uuid.uuid4())
    superseded_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([
            _device(expired_device_id),
            _device(consumed_device_id),
            _device(superseded_device_id),
        ])
        service = BrowserPairingService(session)
        expired = await service.create_pairing(device_id=expired_device_id, purpose="login", actor_id=expired_device_id)
        expired_row = await session.get(DeviceBrowserPairing, expired["pairing_id"])
        expired_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        consumed = await service.create_pairing(device_id=consumed_device_id, purpose="login", actor_id=consumed_device_id)
        consumed_row = await session.get(DeviceBrowserPairing, consumed["pairing_id"])
        consumed_row.status = "consumed"
        consumed_row.completed_at = datetime.now(timezone.utc)
        superseded = await service.create_pairing(device_id=superseded_device_id, purpose="login", actor_id=superseded_device_id)
        await service.create_pairing(device_id=superseded_device_id, purpose="login", actor_id=superseded_device_id)
        await session.commit()

    for code in [expired["pairing_code"], consumed["pairing_code"], superseded["pairing_code"]]:
        response = await test_client.post(
            "/api/web/registry/browser-pairings/lookup",
            headers=_headers(f"{TEST_UI_USER_PREFIX}inactive-code@example.test"),
            json={"pairing_code": code},
        )
        payload = await response.json()

        assert response.status == 404, payload
        assert payload["error_code"] == "PAIRING_CODE_NOT_FOUND"


@pytest.mark.asyncio
async def test_browser_pairing_cleanup_expires_stale_pending_and_confirmed_rows(test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_maker() as session:
        expired_pending_device_id = str(uuid.uuid4())
        expired_confirmed_device_id = str(uuid.uuid4())
        fresh_device_id = str(uuid.uuid4())
        session.add_all([
            _device(expired_pending_device_id),
            _device(expired_confirmed_device_id),
            _device(fresh_device_id),
        ])
        service = BrowserPairingService(session)
        expired_pending = await service.create_pairing(device_id=expired_pending_device_id, purpose="login", actor_id="agent")
        expired_pending_row = await session.get(DeviceBrowserPairing, expired_pending["pairing_id"])
        assert expired_pending_row is not None
        expired_pending_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        expired_confirmed = await service.create_pairing(device_id=expired_confirmed_device_id, purpose="registration", actor_id="agent")
        expired_confirmed_row = await session.get(DeviceBrowserPairing, expired_confirmed["pairing_id"])
        assert expired_confirmed_row is not None
        expired_confirmed_row.status = "confirmed"
        expired_confirmed_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        fresh = await service.create_pairing(device_id=fresh_device_id, purpose="login", actor_id="agent")
        fresh_row = await session.get(DeviceBrowserPairing, fresh["pairing_id"])
        assert fresh_row is not None

        cleanup = await service.expire_stale_pairings(limit=10)
        await session.commit()

    assert cleanup["expired_count"] == 2
    async with session_maker() as session:
        pending_row = await session.get(DeviceBrowserPairing, expired_pending["pairing_id"])
        confirmed_row = await session.get(DeviceBrowserPairing, expired_confirmed["pairing_id"])
        fresh_row = await session.get(DeviceBrowserPairing, fresh["pairing_id"])
        assert pending_row is not None and pending_row.status == "expired"
        assert confirmed_row is not None and confirmed_row.status == "expired"
        assert fresh_row is not None and fresh_row.status == "pending"


@pytest.mark.asyncio
async def test_web_user_direct_pairing_get_rejects_inactive_pairings_without_device_facts(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    expired_device_id = str(uuid.uuid4())
    consumed_device_id = str(uuid.uuid4())
    superseded_device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add_all([
            _device(expired_device_id),
            _device(consumed_device_id),
            _device(superseded_device_id),
        ])
        service = BrowserPairingService(session)
        expired = await service.create_pairing(device_id=expired_device_id, purpose="login", actor_id=expired_device_id)
        expired_row = await session.get(DeviceBrowserPairing, expired["pairing_id"])
        expired_row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        consumed = await service.create_pairing(device_id=consumed_device_id, purpose="login", actor_id=consumed_device_id)
        consumed_row = await session.get(DeviceBrowserPairing, consumed["pairing_id"])
        consumed_row.status = "consumed"
        consumed_row.completed_at = datetime.now(timezone.utc)
        superseded = await service.create_pairing(device_id=superseded_device_id, purpose="login", actor_id=superseded_device_id)
        await service.create_pairing(device_id=superseded_device_id, purpose="login", actor_id=superseded_device_id)
        await session.commit()

    for pairing_id in [expired["pairing_id"], consumed["pairing_id"], superseded["pairing_id"], str(uuid.uuid4())]:
        response = await test_client.get(
            f"/api/web/registry/browser-pairings/{pairing_id}",
            headers=_headers(f"{TEST_UI_USER_PREFIX}inactive-direct@example.test"),
        )
        payload = await response.json()

        assert response.status == 404, payload
        assert payload["error_code"] == "NOT_FOUND"
        assert "device" not in payload
        assert "device_id" not in payload


@pytest.mark.asyncio
async def test_web_user_lookup_browser_pairing_code_rate_limits_invalid_attempts(test_client):
    reset_rate_limits()
    try:
        statuses = []
        for index in range(6):
            response = await test_client.post(
                "/api/web/registry/browser-pairings/lookup",
                headers=_headers(f"{TEST_UI_USER_PREFIX}rate-limited-code@example.test"),
                json={"pairing_code": f"BAD-{index}"},
            )
            statuses.append(response.status)

        assert statuses[:5] == [404, 404, 404, 404, 404]
        assert statuses[5] == 429
    finally:
        reset_rate_limits()


@pytest.mark.asyncio
async def test_web_user_confirms_login_pairing_and_agent_picks_up_token_once(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="owner@example.test",
            display_name="Owner User",
            profile={"full_name": "Owner User", "email": "owner@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        pairing = await BrowserPairingService(session).create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        await session.commit()

    confirmed = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/login/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}owner@example.test"),
        json={},
    )
    assert confirmed.status == 200, await confirmed.text()
    confirmed_payload = await confirmed.json()
    assert confirmed_payload["data"]["status"] == "confirmed"
    assert confirmed_payload["data"]["binding_id"] == approved["binding"]["binding_id"]
    assert "session_token" not in confirmed_payload["data"]

    picked_up = await test_client.get(
        f"/api/registry/agent/browser-pairings/{pairing['pairing_id']}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert picked_up.status == 200, await picked_up.text()
    pickup_payload = await picked_up.json()
    assert pickup_payload["data"]["status"] == "consumed"
    assert pickup_payload["data"]["session"]["account_mode"] == "confirmed_binding"
    assert pickup_payload["data"]["session_token"]

    repeated = await test_client.get(
        f"/api/registry/agent/browser-pairings/{pairing['pairing_id']}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    repeated_payload = await repeated.json()
    assert repeated.status == 200
    assert repeated_payload["data"]["status"] == "consumed"
    assert "session_token" not in repeated_payload["data"]


@pytest.mark.asyncio
async def test_admin_web_session_confirms_login_pairing_for_linked_registry_identity(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="owner@example.test",
            display_name="Owner User",
            profile={"full_name": "Owner User", "email": "owner@example.test", "user_confirmed": True},
        )
        approved = await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        session.add(
            RegistryPersonIdentity(
                person_id=approved["person"]["person_id"],
                provider="ui_login",
                identifier="admin-test",
                normalized_identifier="admin-test",
                verified=True,
                source="test",
            )
        )
        pairing = await BrowserPairingService(session).create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        await session.commit()

    page_response = await test_client.get(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    page_payload = await page_response.json()
    assert page_response.status == 200, page_payload
    assert page_payload["data"]["pairing_id"] == pairing["pairing_id"]

    confirmed = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/login/confirm",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={},
    )
    confirmed_payload = await confirmed.json()
    assert confirmed.status == 200, confirmed_payload
    assert confirmed_payload["data"]["status"] == "confirmed"
    assert confirmed_payload["data"]["binding_id"] == approved["binding"]["binding_id"]
    assert "session_token" not in confirmed_payload["data"]


@pytest.mark.asyncio
async def test_web_user_cannot_confirm_login_pairing_for_foreign_binding(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        claim = await service.submit_agent_profile_claim(
            device_id=device_id,
            requester_id="owner@example.test",
            display_name="Owner User",
            profile={"full_name": "Owner User", "email": "owner@example.test", "user_confirmed": True},
        )
        await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        pairing = await BrowserPairingService(session).create_pairing(device_id=device_id, purpose="login", actor_id=device_id)
        await session.commit()

    response = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/login/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}foreign@example.test"),
        json={},
    )
    payload = await response.json()

    assert response.status == 403
    assert payload["error_code"] == "PAIRING_FORBIDDEN"


@pytest.mark.asyncio
async def test_web_user_confirms_registration_pairing_for_pairing_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        pairing = await BrowserPairingService(session).create_pairing(device_id=device_id, purpose="registration", actor_id=device_id)
        await _completed_requester_profile(session, login="new-user@example.test")
        await session.commit()

    response = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/registration/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}new-user@example.test"),
        json={},
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["status"] == "confirmed"
    assert payload["data"]["claim_id"]
    assert payload["data"]["registration"]["device_id"] == device_id

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, payload["data"]["claim_id"])
    assert claim is not None
    assert claim.device_id == device_id
    assert claim.profile_snapshot["phone"] == "1001"


@pytest.mark.asyncio
async def test_registration_pairing_confirmation_links_account_only_user_by_default(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        pairing = await BrowserPairingService(session).create_pairing(device_id=device_id, purpose="registration", actor_id=device_id)
        await session.commit()

    response = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/registration/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}account-only@example.test"),
        json={},
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["status"] == "confirmed"
    assert payload["data"]["claim_id"]
    assert payload["data"]["registration"]["status"] == "approved"
    assert payload["data"]["binding"]["status"] == "active"

    async with session_maker() as session:
        row = await session.get(DeviceBrowserPairing, pairing["pairing_id"])
        claim = await session.get(DeviceRegistrationClaim, payload["data"]["claim_id"])
        binding = await session.get(DeviceUserBinding, payload["data"]["binding"]["binding_id"])
        person = await session.get(RegistryPerson, claim.person_id)

    assert row is not None
    assert row.status == "confirmed"
    assert claim is not None
    assert claim.status == "approved"
    assert binding is not None
    assert binding.status == "active"
    assert person is not None
    assert person.email == "account-only@example.test"

    picked_up = await test_client.get(
        f"/api/registry/agent/browser-pairings/{pairing['pairing_id']}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert picked_up.status == 200, await picked_up.text()
    picked_up_payload = await picked_up.json()
    assert picked_up_payload["data"]["status"] == "consumed"
    assert picked_up_payload["data"]["session"]["account_mode"] == "confirmed_binding"
    assert picked_up_payload["data"]["session_token"]
    assert picked_up_payload["data"]["resulting_account_session_id"] == picked_up_payload["data"]["session"]["session_id"]

    account_state = await test_client.get(
        "/api/registry/agent/account-state",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert account_state.status == 200, await account_state.text()
    account_payload = await account_state.json()
    assert account_payload["data"]["accounts"][0]["account_mode"] == "confirmed_binding"
    assert account_payload["data"]["accounts"][0]["email"] == "account-only@example.test"


@pytest.mark.asyncio
async def test_registration_pairing_approval_surfaces_confirmed_binding_to_agent(test_client, test_engine):
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
        await _completed_requester_profile(session, login="stage1-new-user@example.test")
        await session.commit()

    created = await test_client.post(
        "/api/registry/agent/browser-pairings",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"purpose": "registration"},
    )
    assert created.status == 200, await created.text()
    created_payload = await created.json()
    pairing = created_payload["data"]
    assert pairing["purpose"] == "registration"
    assert pairing["browser_url"] == f"/app/device/register?pairing_id={pairing['pairing_id']}"

    confirmed = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/registration/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}stage1-new-user@example.test"),
        json={},
    )
    assert confirmed.status == 200, await confirmed.text()
    confirmed_payload = await confirmed.json()
    claim_id = confirmed_payload["data"]["claim_id"]
    assert confirmed_payload["data"]["status"] == "confirmed"
    assert confirmed_payload["data"]["registration"]["status"] == "pending_admin_review"
    assert confirmed_payload["data"]["registration"]["device_id"] == device_id
    assert "session_token" not in confirmed_payload["data"]

    picked_up = await test_client.get(
        f"/api/registry/agent/browser-pairings/{pairing['pairing_id']}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert picked_up.status == 200, await picked_up.text()
    pickup_payload = await picked_up.json()
    assert pickup_payload["data"]["status"] == "consumed"
    assert pickup_payload["data"]["claim_id"] == claim_id
    assert "session_token" not in pickup_payload["data"]

    pending_state = await test_client.get(
        "/api/registry/agent/account-state",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert pending_state.status == 200, await pending_state.text()
    pending_payload = await pending_state.json()
    assert pending_payload["data"]["registration"]["requires_admin_action"] is True
    assert pending_payload["data"]["accounts"][0]["account_mode"] == "registration_pending"
    assert pending_payload["data"]["accounts"][0]["claim_id"] == claim_id

    approved = await test_client.post(
        f"/api/web/admin/registry/registrations/{claim_id}/approve",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={},
    )
    assert approved.status == 200, await approved.text()
    approved_payload = await approved.json()
    binding_id = approved_payload["data"]["binding"]["binding_id"]

    confirmed_state = await test_client.get(
        "/api/registry/agent/account-state",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert confirmed_state.status == 200, await confirmed_state.text()
    state_payload = await confirmed_state.json()
    account = state_payload["data"]["accounts"][0]
    assert account["account_mode"] == "confirmed_binding"
    assert account["binding_id"] == binding_id
    assert account["email"] == "stage1-new-user@example.test"
    assert account["registration_status"] == "admin_confirmed"
    assert account["can_login"] is True
    assert state_payload["data"]["can_login_confirmed_binding"] is True
    assert state_payload["data"]["can_register"] is False

    session_response = await test_client.post(
        "/api/registry/agent/account-sessions/confirmed-binding",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"binding_id": binding_id},
    )
    assert session_response.status == 200, await session_response.text()
    session_payload = await session_response.json()
    assert session_payload["data"]["session"]["account_mode"] == "confirmed_binding"
    assert session_payload["data"]["session"]["binding_id"] == binding_id
    assert session_payload["data"].get("session_token")

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, claim_id)
    assert claim is not None
    assert claim.status == "approved"


@pytest.mark.asyncio
async def test_registration_pairing_confirmation_accepts_required_registry_ids(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        service = RegistrationService(session)
        department = await service.registry_repo.get_or_create_department(
            name="Browser Strict Department",
            source="manual",
            status="active",
        )
        location = await service.registry_repo.get_or_create_location(
            building="Browser HQ",
            floor="7",
            room="701",
            source="manual",
            status="active",
        )
        await RegistryPolicyService(session).update_policies(
            {
                "registration": {
                    "department_mode": "required_existing",
                    "location_mode": "required_existing",
                }
            },
            actor_id="admin",
        )
        await _completed_requester_profile(
            session,
            login="strict-browser@example.test",
            department_id=department.department_id,
            location_id=location.location_id,
        )
        await session.commit()

    created = await test_client.post(
        "/api/registry/agent/browser-pairings",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"purpose": "registration"},
    )
    assert created.status == 200, await created.text()
    pairing = (await created.json())["data"]

    confirmed = await test_client.post(
        f"/api/web/registry/browser-pairings/{pairing['pairing_id']}/registration/confirm",
        headers=_headers(f"{TEST_UI_USER_PREFIX}strict-browser@example.test"),
        json={"department_id": department.department_id, "location_id": location.location_id},
    )
    payload = await confirmed.json()

    assert confirmed.status == 200, payload
    assert payload["data"]["status"] == "confirmed"
    assert payload["data"]["claim_id"]

    async with session_maker() as session:
        claim = await session.get(DeviceRegistrationClaim, payload["data"]["claim_id"])

    assert claim is not None
    assert claim.profile_snapshot["department_id"] == department.department_id
    assert claim.profile_snapshot["location_id"] == location.location_id


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
    assert approved_payload["data"].get("session_token")

    polled = await test_client.get(
        f"/api/registry/agent/account-login-requests/{request_id}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert polled.status == 200, await polled.text()
    polled_payload = await polled.json()
    session_id = polled_payload["data"]["session"]["session_id"]
    session_token = polled_payload["data"]["session_token"]
    assert session_token == approved_payload["data"]["session_token"]

    second_poll = await test_client.get(
        f"/api/registry/agent/account-login-requests/{request_id}",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert second_poll.status == 200, await second_poll.text()
    assert "session_token" not in (await second_poll.json())["data"]

    missing_token = await test_client.get(
        f"/api/registry/agent/account-sessions/{session_id}/validate",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert missing_token.status == 403
    missing_payload = await missing_token.json()
    assert missing_payload["error_code"] == "ACCOUNT_SESSION_TOKEN_REQUIRED"

    query_token = await test_client.get(
        f"/api/registry/agent/account-sessions/{session_id}/validate?session_token=wrong",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
    )
    assert query_token.status == 400
    assert (await query_token.json())["error_code"] == "SESSION_TOKEN_QUERY_DISABLED"

    wrong_token = await test_client.post(
        f"/api/registry/agent/account-sessions/{session_id}/validate",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"session_token": "wrong"},
    )
    assert wrong_token.status == 403
    wrong_payload = await wrong_token.json()
    assert wrong_payload["error_code"] == "ACCOUNT_SESSION_TOKEN_INVALID"

    valid = await test_client.post(
        f"/api/registry/agent/account-sessions/{session_id}/validate",
        headers={**_headers(f"{TEST_AGENT_PREFIX}{device_id}"), "X-Account-Session-Token": session_token},
    )
    assert valid.status == 200, await valid.text()
    assert (await valid.json())["data"]["valid"] is True


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
async def test_registration_pending_session_and_logout_endpoints(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="pending-api@example.test",
            display_name="Pending Api",
            profile={"full_name": "Pending Api", "email": "pending-api@example.test"},
        )
        await session.commit()

    created = await test_client.post(
        "/api/registry/agent/account-sessions/registration-pending",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"claim_id": claim["registration"]["claim_id"]},
    )
    assert created.status == 200, await created.text()
    created_payload = await created.json()
    session_id = created_payload["data"]["session"]["session_id"]
    session_token = created_payload["data"]["session_token"]
    assert created_payload["data"]["session"]["account_mode"] == "registration_pending"
    assert created_payload["data"]["session"]["verification_status"] == "pending_verification"

    state = await test_client.get(
        f"/api/registry/agent/account-state?device_id={device_id}",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    assert state.status == 200, await state.text()
    state_payload = await state.json()
    assert any(item["session_id"] == session_id for item in state_payload["data"]["server_sessions"])

    logged_out = await test_client.post(
        f"/api/registry/agent/account-sessions/{session_id}/logout",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"session_token": session_token},
    )
    assert logged_out.status == 200, await logged_out.text()
    assert (await logged_out.json())["data"]["session"]["verification_status"] == "revoked"

    invalid = await test_client.post(
        f"/api/registry/agent/account-sessions/{session_id}/validate",
        headers=_headers(f"{TEST_AGENT_PREFIX}{device_id}"),
        json={"session_token": session_token},
    )
    assert invalid.status == 403
    assert (await invalid.json())["error_code"] == "ACCOUNT_SESSION_REVOKED"


@pytest.mark.asyncio
async def test_admin_lists_and_revokes_device_account_sessions(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    async with session_maker() as session:
        session.add(_device(device_id))
        claim = await RegistrationService(session).submit_agent_profile_claim(
            device_id=device_id,
            requester_id="registered-admin-session@example.test",
            display_name="Registered Admin Session",
            profile={"full_name": "Registered Admin Session", "email": "registered-admin-session@example.test", "user_confirmed": True},
        )
        approved = await RegistrationService(session).approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")
        account = await AccountSessionService(session).create_confirmed_binding_session(
            device_id=device_id,
            binding_id=approved["binding"]["binding_id"],
        )
        await session.commit()

    listed = await test_client.get(
        f"/api/web/admin/registry/devices/{device_id}/account-sessions",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
    )
    assert listed.status == 200, await listed.text()
    listed_payload = await listed.json()
    assert any(item["session_id"] == account["session"]["session_id"] for item in listed_payload["data"]["items"])

    revoked = await test_client.post(
        f"/api/web/admin/registry/account-sessions/{account['session']['session_id']}/revoke",
        headers=_headers(TEST_UI_ADMIN_TOKEN),
        json={"reason": "test"},
    )
    assert revoked.status == 200, await revoked.text()
    assert (await revoked.json())["data"]["session"]["verification_status"] == "revoked"


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
