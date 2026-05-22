from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device
from registry.registration_service import RegistrationService
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
