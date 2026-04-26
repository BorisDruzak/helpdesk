from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, UiUser
from tests.conftest import TEST_UI_SUPPORT_TOKEN, TEST_UI_USER_PREFIX
from tests.test_ticket_queue_routing_contracts import _seed_queue


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


def _requester_headers(user_login: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_USER_PREFIX}{user_login}"}


async def _seed_visible_ticket(test_engine, *, requester_id: str = "user-passport") -> str:
    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login=requester_id, password_hash="test", actor_role="user", is_active=True),
        ])
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test"])
        ticket_id = str(uuid.uuid4())
        ticket = Ticket(
            ticket_id=ticket_id,
            device_id=str(uuid.uuid4()),
            title="Паспорт тест",
            description="Нужно собрать паспорт решения",
            status="in_progress",
            requester_id=requester_id,
            queue_id=queue.id,
            requester_status="in_work",
            next_action_owner="support",
        )
        session.add(ticket)
        await session.commit()
        return ticket_id


@pytest.mark.asyncio
async def test_get_passport_returns_missing_state_for_new_ticket(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)

    response = await test_client.get(
        f"/api/web/support/tickets/{ticket_id}/passport",
        headers=_support_headers(),
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["status"] == "success"
    assert payload["data"]["ticket_id"] == ticket_id
    assert payload["data"]["status"] == "missing"
    assert payload["data"]["passport"] is None


@pytest.mark.asyncio
async def test_generate_passport_returns_sections_and_version(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_support_headers(),
        json={"mode": "create", "include_internal_notes": True},
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    passport = payload["data"]["passport"]
    assert passport["version"] == 1
    assert passport["sections"]["problem"].startswith("Паспорт тест")
    assert passport["summary_source"] == "deterministic"


@pytest.mark.asyncio
async def test_add_evidence_updates_passport_payload(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine)
    await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_support_headers(),
        json={"mode": "create"},
    )

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/evidence",
        headers=_support_headers(),
        json={
            "evidence_type": "operation",
            "source_ref": "operation-123",
            "title": "Диагностика устройства",
            "summary": "Команда завершилась успешно",
            "visibility": "internal",
        },
    )

    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["evidence"][0]["title"] == "Диагностика устройства"
    assert payload["data"]["evidence"][0]["source_ref"] == "operation-123"


@pytest.mark.asyncio
async def test_requester_cannot_generate_passport(test_client, test_engine):
    ticket_id = await _seed_visible_ticket(test_engine, requester_id="user-passport")

    response = await test_client.post(
        f"/api/web/support/tickets/{ticket_id}/passport/generate",
        headers=_requester_headers("user-passport"),
        json={"mode": "create"},
    )

    assert response.status in {401, 403}
