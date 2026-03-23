import uuid

import pytest

from app.db.engine import async_sessionmaker
from app.repos.ticket_events_repo import TicketEventsRepo
from tickets.statuses import merge_requester_custom_fields


@pytest.mark.asyncio
async def test_snapshot_enriches_agent_chat_message_with_requester_name(test_client, test_engine):
    ticket_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        repo = TicketEventsRepo(session)
        ticket = await repo.create_ticket(
            ticket_id=ticket_id,
            device_id=device_id,
            title="Sender name test",
            description="Requester name should be visible in agent chat",
            status="in_progress",
            requester_id=device_id,
        )
        custom_fields = merge_requester_custom_fields(
            getattr(ticket, "custom_fields", None),
            user_display_name="Короткое имя",
            requester_profile={
                "full_name": "ФИО Пользователя",
                "building": "A",
                "room": "101",
                "phone": "123",
            },
        )
        await repo.update_ticket(ticket_id, custom_fields=custom_fields)
        inserted = await repo.add_event(
            ticket_id=ticket_id,
            device_id=device_id,
            agent_seq=1,
            event_type="chat_message",
            payload={
                "message_id": str(uuid.uuid4()),
                "sender_role": "agent",
                "from": "agent",
                "text": "Agent-side requester message",
                "visibility": "public",
            },
            trace_id=str(uuid.uuid4()),
        )
        assert inserted is not None
        await session.commit()

    response = await test_client.get(
        f"/api/tickets/{ticket_id}/snapshot",
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert response.status == 200, await response.text()
    snapshot = await response.json()
    chat_events = [event for event in snapshot["events"] if event["event_type"] == "chat_message"]
    assert len(chat_events) == 1

    payload = chat_events[0]["payload"]
    assert payload["sender_display_name"] == "ФИО Пользователя"
    assert payload["requester_display_name"] == "ФИО Пользователя"
