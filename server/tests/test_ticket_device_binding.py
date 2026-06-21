import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from app.repos import DevicesRepo
from tickets.public_access import is_public_unbound_ticket


pytestmark = pytest.mark.db_cleanup("tickets")

@pytest.mark.asyncio
async def test_staff_can_bind_public_ticket_to_existing_device(test_client, test_engine):
    create_response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Веб-заявка",
            "description": "Проверка привязки к агенту",
            "user_display_name": "Веб пользователь",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Не срочно",
            "importance_reason": "Обычная проверка",
            "requester_profile": {
                "full_name": "Тестовый Пользователь",
                "building": "А",
                "room": "101",
                "phone": "+7 900 000 00 00",
            },
        },
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine, expire_on_commit=False)
    device_id = "device-bind-001"
    async with session_maker() as session:
        devices_repo = DevicesRepo(session)
        await devices_repo.ensure_device_exists(device_id)
        await session.commit()

    bind_response = await test_client.post(
        f"/api/tickets/{ticket_id}/device",
        json={"device_id": device_id, "reason": "manual_bind"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert bind_response.status == 200, await bind_response.text()
    payload = await bind_response.json()
    assert payload["ticket"]["device_id"] == device_id
    assert payload["ticket"]["public_ticket_unbound"] is False

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.device_id == device_id
        assert is_public_unbound_ticket(ticket) is False

        events = (
            await session.execute(
                TicketEvent.__table__.select().where(TicketEvent.ticket_id == ticket_id)
            )
        ).mappings().all()
        device_events = [event for event in events if event["event_type"] == "device_changed"]
        assert device_events
        assert device_events[-1]["payload"]["device_id"] == device_id


@pytest.mark.asyncio
async def test_bind_device_rejects_unknown_device(test_client):
    create_response = await test_client.post(
        "/public_api/tickets/create",
        json={
            "title": "Веб-заявка",
            "description": "Проверка ошибки привязки",
            "user_display_name": "Веб пользователь",
            "urgency": False,
            "importance": False,
            "urgency_reason": "Не срочно",
            "importance_reason": "Обычная проверка",
        },
    )
    assert create_response.status == 200, await create_response.text()
    ticket_id = (await create_response.json())["ticket"]["ticket_id"]

    bind_response = await test_client.post(
        f"/api/tickets/{ticket_id}/device",
        json={"device_id": "missing-device"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert bind_response.status == 400, await bind_response.text()
    payload = await bind_response.json()
    assert payload["error"] == "validation_error"
    assert payload["details"]["device_id"] == "unknown device_id"
