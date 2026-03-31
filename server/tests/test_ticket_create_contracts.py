import uuid

import pytest
from sqlalchemy import delete, select

from app.db.engine import async_sessionmaker
from app.db.models import (
    Ticket,
    TicketBusinessCalendar,
    TicketEvent,
    TicketQueue,
    TicketQueueMember,
    TicketQueueOlaTarget,
    TicketSlaPolicy,
    TicketSlaTarget,
    UiUser,
)


async def _seed_queue(
    session,
    *,
    code: str = "servicedesk_l1",
    name: str = "ServiceDesk L1",
    members: list[str] | None = None,
    auto_assign_enabled: bool = True,
) -> TicketQueue:
    result = await session.execute(select(TicketQueue).where(TicketQueue.code == code))
    queue = result.scalar_one_or_none()
    if queue is None:
        queue = TicketQueue(code=code, name=name, is_triage=True, is_active=True, auto_assign_enabled=auto_assign_enabled)
        session.add(queue)
        await session.flush()
    else:
        queue.name = name
        queue.is_triage = True
        queue.is_active = True
        queue.auto_assign_enabled = auto_assign_enabled
        await session.execute(delete(TicketQueueMember).where(TicketQueueMember.queue_id == queue.id))
    for actor_id in members or []:
        session.add(TicketQueueMember(queue_id=queue.id, actor_id=actor_id, role_in_queue=None))
    return queue


@pytest.mark.asyncio
async def test_create_ticket_uses_requester_auth_and_canonical_initial_message(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "alice"

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Cannot print to office printer",
            "device_id": device_id,
            "user_display_name": "Alice",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    ticket_id = data["ticket"]["ticket_id"]

    session_maker = async_sessionmaker(test_engine)
    async with session_maker() as session:
        ticket_result = await session.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        )
        ticket = ticket_result.scalar_one()

        message_result = await session.execute(
            select(TicketEvent)
            .where(
                TicketEvent.ticket_id == ticket_id,
                TicketEvent.event_type == "chat_message",
            )
            .order_by(TicketEvent.id.asc())
            .limit(1)
        )
        initial_message = message_result.scalar_one()

    assert ticket.status == "new"
    assert ticket.requester_id == user_login
    assert ticket.title == "Printer issue"
    assert ticket.description == "Cannot print to office printer"

    payload = initial_message.payload
    assert payload["sender_role"] == "user"
    assert payload["from"] == "user"
    assert payload["is_initial"] is True
    assert payload["text"] == "Cannot print to office printer"


@pytest.mark.asyncio
async def test_create_ticket_auto_assigns_and_sets_operator_queue_status(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "bob"
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(
            UiUser(
                user_login="op_auto",
                password_hash="test",
                actor_role="support",
                is_active=True,
            )
        )
        await _seed_queue(session, members=["op_auto"])
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Browser issue",
            "description": "Browser keeps crashing",
            "device_id": device_id,
            "user_display_name": "Bob",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )

    assert response.status == 200, await response.text()
    data = await response.json()
    ticket_id = data["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket_result = await session.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        )
        ticket = ticket_result.scalar_one()
        events_result = await session.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket_id)
            .order_by(TicketEvent.id.asc())
        )
        events = list(events_result.scalars().all())

    assert ticket.status == "triaged"
    assert ticket.assignee_id == "op_auto"
    assert any(event.event_type == "assignee_changed" for event in events)
    assert any(
        event.event_type == "status_changed"
        and (event.payload or {}).get("to_status") == "triaged"
        for event in events
    )


@pytest.mark.asyncio
async def test_only_requester_can_confirm_closed_status(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "carol"
    session_maker = async_sessionmaker(test_engine)

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Cannot print",
            "device_id": device_id,
            "user_display_name": "Carol",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.status = "resolved"
        ticket.custom_fields = {
            "resolution_confirmation": {
                "pending": True,
            }
        }
        await session.commit()

    support_close = await test_client.post(
        f"/api/tickets/{ticket_id}/close",
        json={"reason": "manual_close"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert support_close.status == 409, await support_close.text()
    support_data = await support_close.json()
    assert support_data["error"] == "closed_requires_requester_confirmation"

    requester_close = await test_client.post(
        f"/api/tickets/{ticket_id}/close",
        json={"reason": "requester_confirmed_resolution"},
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert requester_close.status == 200, await requester_close.text()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "closed"
        marker = (ticket.custom_fields or {}).get("resolution_confirmation") or {}
        assert marker.get("pending") is False


@pytest.mark.asyncio
async def test_requester_reply_requeues_waiting_ticket(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "dave"
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(
            UiUser(
                user_login="op_wait",
                password_hash="test",
                actor_role="support",
                is_active=True,
            )
        )
        await _seed_queue(session, members=["op_wait", "support-test"])
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Network issue",
            "description": "VPN disconnects",
            "device_id": device_id,
            "user_display_name": "Dave",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    status_progress = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "in_progress"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_progress.status == 200, await status_progress.text()

    status_waiting = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "waiting_on_user"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_waiting.status == 200, await status_waiting.text()

    message_response = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": str(uuid.uuid4()),
            "text": "Вот дополнительная информация",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert message_response.status == 200, await message_response.text()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "triaged"


@pytest.mark.asyncio
async def test_resolution_confirmation_request_uses_structured_metadata(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "erin"
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(
            UiUser(
                user_login="op_confirm",
                password_hash="test",
                actor_role="support",
                is_active=True,
            )
        )
        await _seed_queue(session, members=["op_confirm", "support-test"])
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Email issue",
            "description": "Mailbox sync is broken",
            "device_id": device_id,
            "user_display_name": "Erin",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    status_progress = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "in_progress"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_progress.status == 200, await status_progress.text()

    status_resolved = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "resolved"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_resolved.status == 200, await status_resolved.text()

    ticket_response = await test_client.get(
        f"/api/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert ticket_response.status == 200, await ticket_response.text()
    ticket_data = await ticket_response.json()
    messages = ticket_data["messages"]

    confirmation_message = next(
        message
        for message in reversed(messages)
        if isinstance(message.get("metadata"), dict) and message["metadata"].get("confirmation_request")
    )
    confirmation_request = confirmation_message["metadata"]["confirmation_request"]
    assert confirmation_request["kind"] == "ticket_resolution"
    assert [option["label"] for option in confirmation_request["options"]] == ["Подтверждаю", "Не принято"]
    assert "кнопок ниже" in confirmation_message["text"]
    assert "нажмите «Подтверждаю»" in confirmation_request["message"]

    confirm_response = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": str(uuid.uuid4()),
            "text": "Подтверждаю",
            "metadata": {
                "confirmation_response": {
                    "request_id": confirmation_request["request_id"],
                    "kind": "ticket_resolution",
                    "option_id": "confirm",
                    "label": "Подтверждаю",
                }
            },
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert confirm_response.status == 200, await confirm_response.text()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "closed"


@pytest.mark.asyncio
async def test_resolution_confirmation_reject_requeues_ticket(test_client, test_engine):
    device_id = str(uuid.uuid4())
    user_login = "frank"
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(
            UiUser(
                user_login="op_reject",
                password_hash="test",
                actor_role="support",
                is_active=True,
            )
        )
        await _seed_queue(session, members=["op_reject", "support-test"])
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "VPN issue",
            "description": "VPN still disconnects",
            "device_id": device_id,
            "user_display_name": "Frank",
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    status_progress = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "in_progress"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_progress.status == 200, await status_progress.text()

    status_resolved = await test_client.post(
        f"/api/tickets/{ticket_id}/status",
        json={"to_status": "resolved"},
        headers={"Authorization": "Bearer test-ui-support-token"},
    )
    assert status_resolved.status == 200, await status_resolved.text()

    ticket_response = await test_client.get(
        f"/api/tickets/{ticket_id}",
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert ticket_response.status == 200, await ticket_response.text()
    ticket_data = await ticket_response.json()
    confirmation_message = next(
        message
        for message in reversed(ticket_data["messages"])
        if isinstance(message.get("metadata"), dict) and message["metadata"].get("confirmation_request")
    )
    confirmation_request = confirmation_message["metadata"]["confirmation_request"]

    reject_response = await test_client.post(
        f"/api/tickets/{ticket_id}/message",
        json={
            "message_id": str(uuid.uuid4()),
            "text": "Не принято",
            "metadata": {
                "confirmation_response": {
                    "request_id": confirmation_request["request_id"],
                    "kind": "ticket_resolution",
                    "option_id": "reject",
                    "label": "Не принято",
                }
            },
        },
        headers={"Authorization": f"Bearer test-ui-user:{user_login}"},
    )
    assert reject_response.status == 200, await reject_response.text()

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "triaged"
        marker = (ticket.custom_fields or {}).get("resolution_confirmation") or {}
        assert marker.get("pending") is False
