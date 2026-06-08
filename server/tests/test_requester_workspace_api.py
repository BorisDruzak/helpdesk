from __future__ import annotations

from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Device, Ticket, TicketEvent
from registry.registration_service import RegistrationService
from tests.conftest import TEST_AGENT_PREFIX, TEST_UI_USER_PREFIX
from tickets.create_flow import build_default_priority_payload, create_ticket_with_side_effects


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _device(device_id: str, hostname: str = "requester-device") -> Device:
    now = datetime.now(timezone.utc)
    return Device(
        device_id=device_id,
        protocol_version="ws_ticket_v3",
        agent_version="3.1.61",
        hostname=hostname,
        os="Windows",
        capabilities={},
        device_metadata={},
        first_seen_at=now,
        last_seen_at=now,
        last_handshake_at=now,
    )


async def _approved_binding(session, *, device_id: str, login: str):
    service = RegistrationService(session)
    claim = await service.submit_agent_profile_claim(
        device_id=device_id,
        requester_id=login,
        display_name=f"Requester {login}",
        profile={"full_name": f"Requester {login}", "email": login, "login": login, "user_confirmed": True},
    )
    return await service.approve_claim(claim["registration"]["claim_id"], reviewed_by="admin")


@pytest.mark.asyncio
async def test_requester_workspace_bootstrap_lists_owned_device_and_ticket(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = str(uuid.uuid4())
    login = "requester-owner@example.test"
    async with session_maker() as session:
        session.add(_device(device_id))
        approved = await _approved_binding(session, device_id=device_id, login=login)
        session_payload = await create_ticket_with_side_effects(
            session,
            device_id=device_id,
            requester_id=login,
            title="Existing requester ticket",
            description="Visible through requester workspace",
            user_display_name="Requester Owner",
            requester_profile={"full_name": "Requester Owner", "email": login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        await session.commit()

    response = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    payload = await response.json()

    assert response.status == 200, payload
    assert payload["data"]["profile"]["person_id"] == approved["person"]["person_id"]
    assert payload["data"]["devices"][0]["device_id"] == device_id
    assert payload["data"]["open_ticket_count"] >= 1

    tickets = await test_client.get(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
    )
    tickets_payload = await tickets.json()
    assert tickets.status == 200, tickets_payload
    assert session_payload["ticket_id"] in {item["ticket_id"] for item in tickets_payload["data"]["tickets"]}


@pytest.mark.asyncio
async def test_requester_can_create_ticket_for_owned_device_and_not_foreign_device(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    login = "requester-create@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "owned-device"), _device(foreign_device_id, "foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=login)
        await session.commit()

    body = {
        "device_id": owned_device_id,
        "title": "Requester workspace live ticket",
        "description": "Created from authenticated requester workspace",
        "user_display_name": "Requester Create",
    }
    created = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json=body,
    )
    created_payload = await created.json()
    assert created.status == 200, created_payload
    assert created_payload["data"]["ticket"]["ticket_id"]
    async with session_maker() as session:
        ticket = await session.get(Ticket, created_payload["data"]["ticket"]["ticket_id"])
    assert ticket is not None
    assert ticket.device_id == owned_device_id
    assert ticket.requester_person_id == approved["person"]["person_id"]
    assert ticket.requester_binding_id == approved["binding"]["binding_id"]

    denied = await test_client.post(
        "/api/web/requester/tickets",
        headers=_headers(f"{TEST_UI_USER_PREFIX}{login}"),
        json={**body, "device_id": foreign_device_id},
    )
    denied_payload = await denied.json()
    assert denied.status == 403
    assert denied_payload["error_code"] == "REQUESTER_DEVICE_FORBIDDEN"

    agent_denied = await test_client.get(
        "/api/web/requester/bootstrap",
        headers=_headers(f"{TEST_AGENT_PREFIX}{owned_device_id}"),
    )
    assert agent_denied.status == 403


@pytest.mark.asyncio
async def test_requester_ticket_detail_and_message_are_owned_only(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    owned_device_id = str(uuid.uuid4())
    foreign_device_id = str(uuid.uuid4())
    owner_login = "requester-chat-owner@example.test"
    foreign_login = "requester-chat-foreign@example.test"
    async with session_maker() as session:
        session.add_all([_device(owned_device_id, "chat-owned-device"), _device(foreign_device_id, "chat-foreign-device")])
        approved = await _approved_binding(session, device_id=owned_device_id, login=owner_login)
        await _approved_binding(session, device_id=foreign_device_id, login=foreign_login)
        created = await create_ticket_with_side_effects(
            session,
            device_id=owned_device_id,
            requester_id=owner_login,
            title="Requester message ticket",
            description="Visible to owner only",
            user_display_name="Requester Chat Owner",
            requester_profile={"full_name": "Requester Chat Owner", "email": owner_login},
            normalized_priority=build_default_priority_payload({}),
            requester_account={
                "account_mode": "confirmed_binding",
                "person_id": approved["person"]["person_id"],
                "binding_id": approved["binding"]["binding_id"],
            },
            include_public_access=True,
        )
        ticket_id = created["ticket_id"]
        await session.commit()

    owner_headers = _headers(f"{TEST_UI_USER_PREFIX}{owner_login}")
    foreign_headers = _headers(f"{TEST_UI_USER_PREFIX}{foreign_login}")

    detail = await test_client.get(f"/api/web/requester/tickets/{ticket_id}", headers=owner_headers)
    detail_payload = await detail.json()
    assert detail.status == 200, detail_payload
    assert detail_payload["data"]["ticket"]["ticket_id"] == ticket_id
    assert any(
        message.get("text") == "Visible to owner only"
        for message in detail_payload["data"].get("messages", [])
    )

    sent = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=owner_headers,
        json={"text": "Requester authenticated follow-up"},
    )
    sent_payload = await sent.json()
    assert sent.status == 200, sent_payload
    assert sent_payload["data"]["message_id"]

    denied = await test_client.post(
        f"/api/web/requester/tickets/{ticket_id}/message",
        headers=foreign_headers,
        json={"text": "Should not be accepted"},
    )
    denied_payload = await denied.json()
    assert denied.status == 404, denied_payload

    async with session_maker() as session:
        events = (
            await session.execute(
                select(TicketEvent)
                .where(TicketEvent.ticket_id == ticket_id)
                .where(TicketEvent.event_type == "chat_message")
            )
        ).scalars().all()

    texts = [event.payload.get("text") for event in events if isinstance(event.payload, dict)]
    assert "Requester authenticated follow-up" in texts
    assert "Should not be accepted" not in texts
