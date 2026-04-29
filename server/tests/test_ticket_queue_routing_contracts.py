import uuid

import pytest
from sqlalchemy import delete, select

from app.db.engine import async_sessionmaker
from app.db.models import (
    Ticket,
    TicketBusinessCalendar,
    TicketPriorityMatrix,
    TicketQueue,
    TicketQueueMember,
    TicketQueueOlaTarget,
    TicketRoutingRule,
    TicketSlaPolicy,
    TicketSlaTarget,
    UiUser,
)
from tests.conftest import TEST_UI_SUPPORT_TOKEN


async def _seed_queue(
    session,
    *,
    code: str,
    name: str,
    members: list[str] | None = None,
    auto_assign_enabled: bool = True,
) -> TicketQueue:
    result = await session.execute(select(TicketQueue).where(TicketQueue.code == code))
    queue = result.scalar_one_or_none()
    if queue is None:
        queue = TicketQueue(code=code, name=name, is_triage=False, is_active=True, auto_assign_enabled=auto_assign_enabled)
        session.add(queue)
        await session.flush()
    else:
        queue.name = name
        queue.is_triage = False
        queue.is_active = True
        queue.auto_assign_enabled = auto_assign_enabled
        await session.execute(delete(TicketQueueMember).where(TicketQueueMember.queue_id == queue.id))
    for actor_id in members or []:
        session.add(TicketQueueMember(queue_id=queue.id, actor_id=actor_id, role_in_queue=None))
    return queue


def _support_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_UI_SUPPORT_TOKEN}"}


@pytest.mark.asyncio
async def test_support_ticket_list_and_snapshot_follow_queue_membership(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_b", password_hash="test", actor_role="support", is_active=True),
        ])
        queue_a = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "op_a"])
        queue_b = await _seed_queue(session, code="network", name="Network", members=["op_b"])
        session.add_all([
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=str(uuid.uuid4()),
                title="Visible by queue",
                description="Queue member should see this",
                status="new",
                requester_id="user-a",
                queue_id=queue_a.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=str(uuid.uuid4()),
                title="Hidden by queue",
                description="Different queue",
                status="new",
                requester_id="user-b",
                queue_id=queue_b.id,
            ),
            Ticket(
                ticket_id=str(uuid.uuid4()),
                device_id=str(uuid.uuid4()),
                title="Visible by assignee",
                description="Assigned ticket stays visible",
                status="in_progress",
                requester_id="user-c",
                queue_id=queue_b.id,
                assignee_id="support-test",
            ),
        ])
        await session.commit()

        result = await session.execute(select(Ticket).order_by(Ticket.title.asc()))
        tickets = list(result.scalars().all())
        visible_by_queue = next(ticket for ticket in tickets if ticket.title == "Visible by queue")
        hidden_by_queue = next(ticket for ticket in tickets if ticket.title == "Hidden by queue")
        visible_by_assignee = next(ticket for ticket in tickets if ticket.title == "Visible by assignee")

    list_response = await test_client.get("/api/tickets", headers=_support_headers())
    assert list_response.status == 200, await list_response.text()
    payload = await list_response.json()
    visible_ticket_ids = {item["ticket"]["ticket_id"] for item in payload["tickets"]}

    assert visible_by_queue.ticket_id in visible_ticket_ids
    assert visible_by_assignee.ticket_id in visible_ticket_ids
    assert hidden_by_queue.ticket_id not in visible_ticket_ids

    snapshot_response = await test_client.get(
        f"/api/tickets/{visible_by_queue.ticket_id}/snapshot",
        headers=_support_headers(),
    )
    assert snapshot_response.status == 200, await snapshot_response.text()
    snapshot = await snapshot_response.json()

    assert {member["actor_id"] for member in snapshot["queue_members"]} == {"support-test", "op_a"}
    assert {user["user_login"] for user in snapshot["assignable_users"]} == {"support-test", "op_a"}
    assert any(queue["code"] == "servicedesk_l1" for queue in snapshot["available_queues"])
    assert snapshot["queue_auto_assign_enabled"] is True


@pytest.mark.asyncio
async def test_support_ticket_list_does_not_duplicate_assigned_queue_member_tickets(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_a", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="op_b", password_hash="test", actor_role="support", is_active=True),
        ])
        queue = await _seed_queue(
            session,
            code="servicedesk_l1",
            name="ServiceDesk L1",
            members=["support-test", "op_a", "op_b"],
        )
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            title="Assigned queue ticket",
            description="Should appear once for support assignee",
            status="in_progress",
            requester_id="user-a",
            queue_id=queue.id,
            assignee_id="support-test",
        )
        session.add(ticket)
        ticket_id = ticket.ticket_id
        await session.commit()

    response = await test_client.get("/api/tickets", headers=_support_headers())
    assert response.status == 200, await response.text()
    payload = await response.json()
    listed_ids = [item["ticket"]["ticket_id"] for item in payload["tickets"]]

    assert listed_ids.count(ticket_id) == 1


@pytest.mark.asyncio
async def test_create_ticket_routes_by_requester_profile_field(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        fallback_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        building_queue = await _seed_queue(session, code="office_b", name="Office B")
        session.add(
            TicketRoutingRule(
                enabled=True,
                priority_order=10,
                condition_json={"field": "requester_profile.building", "op": "eq", "value": "Office B"},
                target_queue_id=building_queue.id,
            )
        )
        fallback_queue_id = fallback_queue.id
        building_queue_id = building_queue.id
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Need help on second floor",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "requester_profile": {
                "full_name": "Alice Example",
                "building": "Office B",
                "room": "204",
                "phone": "+7 900 000-00-00",
            },
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.queue_id == building_queue_id
        assert ticket.queue_id != fallback_queue_id


@pytest.mark.asyncio
async def test_create_ticket_routes_by_request_kind_from_form_submission(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        fallback_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        access_queue = await _seed_queue(session, code="access", name="Access Queue")
        session.add(
            TicketRoutingRule(
                enabled=True,
                priority_order=10,
                condition_json={"field": "request_kind", "op": "eq", "value": "access"},
                target_queue_id=access_queue.id,
            )
        )
        fallback_queue_id = fallback_queue.id
        access_queue_id = access_queue.id
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Access request",
            "description": "Need account access",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alice",
            "form_key": "access",
            "form_pack_key": "request_forms",
            "form_payload": {
                "system_name": "ERP",
                "role_name": "accountant",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "access",
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.queue_id == access_queue_id
        assert ticket.queue_id != fallback_queue_id


@pytest.mark.asyncio
async def test_create_ticket_accepts_long_form_request_kind_for_routing(test_client, test_engine):
    assert Ticket.__table__.c.ticket_type.type.length == 64
    session_maker = async_sessionmaker(test_engine)
    request_kind = "software_install_enterprise_package"

    async with session_maker() as session:
        fallback_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        software_queue = await _seed_queue(session, code="software", name="Software Queue")
        session.add(
            TicketRoutingRule(
                enabled=True,
                priority_order=10,
                condition_json={"field": "request_kind", "op": "eq", "value": request_kind},
                target_queue_id=software_queue.id,
            )
        )
        fallback_queue_id = fallback_queue.id
        software_queue_id = software_queue.id
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Software install",
            "description": "Install the enterprise client package",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Alex",
            "ticket_type": request_kind,
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.ticket_type == request_kind
        assert ticket.queue_id == software_queue_id
        assert ticket.queue_id != fallback_queue_id


@pytest.mark.asyncio
async def test_create_ticket_routes_by_request_form_data_field(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        fallback_queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1")
        printer_room_queue = await _seed_queue(session, code="printer_214", name="Printer 214")
        session.add(
            TicketRoutingRule(
                enabled=True,
                priority_order=5,
                condition_json={"field": "request_form_data.room", "op": "eq", "value": "214"},
                target_queue_id=printer_room_queue.id,
            )
        )
        fallback_queue_id = fallback_queue.id
        printer_room_queue_id = printer_room_queue.id
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Printer issue",
            "description": "Paper jam on floor 2",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Nina",
            "form_key": "printer",
            "form_pack_key": "request_forms",
            "form_payload": {
                "room": "214",
                "printer_model": "HP LaserJet",
                "impact_scope": "single_user",
                "work_continuity": "workaround_available",
                "business_importance": "normal",
            },
            "ticket_type": "printer",
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.queue_id == printer_room_queue_id
        assert ticket.queue_id != fallback_queue_id
        assert (ticket.custom_fields or {}).get("request_form_data", {}).get("room") == "214"


@pytest.mark.asyncio
async def test_create_ticket_applies_sla_and_ola_configuration(test_client, test_engine, monkeypatch):
    session_maker = async_sessionmaker(test_engine)
    import config as server_config
    from tickets import ola_service

    monkeypatch.setattr(server_config, "TICKET_OLA_ENABLED", True)
    monkeypatch.setattr(ola_service, "TICKET_OLA_ENABLED", True)

    async with session_maker() as session:
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", auto_assign_enabled=False)
        calendar = TicketBusinessCalendar(
            code="workhours",
            name="Workhours",
            timezone="UTC",
            weekly_hours_json=[{"day": "mon", "start": "09:00", "end": "18:00"}],
            holidays_json=[],
            is_active=True,
        )
        session.add(calendar)
        await session.flush()
        policy = TicketSlaPolicy(
            name="Default SLA",
            timezone="UTC",
            calendar_id=calendar.id,
            is_default=True,
            is_active=True,
        )
        session.add(policy)
        await session.flush()
        session.add_all([
            TicketSlaTarget(policy_id=policy.id, priority="P3", first_response_min=15, resolution_min=120),
            TicketPriorityMatrix(policy_id=policy.id, impact=1, urgency=1, priority="P3"),
            TicketQueueOlaTarget(queue_id=queue.id, priority="P3", ack_min=20, processing_min=90),
        ])
        queue_id = queue.id
        policy_id = policy.id
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "Email issue",
            "description": "Mailbox sync is broken",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "Erin",
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    ticket_id = (await response.json())["ticket"]["ticket_id"]

    async with session_maker() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket is not None
        assert ticket.sla_policy_id == policy_id
        assert ticket.first_response_due_at is not None
        assert ticket.resolution_due_at is not None
        assert ticket.ola_queue_id == queue_id
        assert ticket.ola_ack_due_at is not None
        assert ticket.ola_processing_due_at is not None


@pytest.mark.asyncio
async def test_manual_assignment_requires_queue_membership(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="queue_member", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="outside_operator", password_hash="test", actor_role="support", is_active=True),
        ])
        queue = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "queue_member"])
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            title="Assignment scope",
            description="Only queue members may be assigned",
            status="new",
            requester_id="user-a",
            queue_id=queue.id,
        )
        session.add(ticket)
        ticket_id = ticket.ticket_id
        await session.commit()

    reject_response = await test_client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": "outside_operator"},
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert reject_response.status == 400, await reject_response.text()
    reject_payload = await reject_response.json()
    assert reject_payload["error"] == "assignment_error"

    accept_response = await test_client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assignee_id": "queue_member"},
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert accept_response.status == 200, await accept_response.text()
    accept_payload = await accept_response.json()
    assert accept_payload["ticket"]["assignee_id"] == "queue_member"


@pytest.mark.asyncio
async def test_create_ticket_without_queue_members_stays_unassigned(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add(UiUser(user_login="lonely_support", password_hash="test", actor_role="support", is_active=True))
        await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=[], auto_assign_enabled=True)
        await session.commit()

    response = await test_client.post(
        "/api/tickets/create",
        json={
            "title": "No queue members",
            "description": "Ticket should stay unassigned",
            "device_id": str(uuid.uuid4()),
            "user_display_name": "No Members",
        },
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["ticket"]["assignee_id"] in (None, "")
    assert payload["ticket"]["status"] == "queued"


@pytest.mark.asyncio
async def test_manual_queue_change_reassigns_within_target_queue(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="l1_member", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="network_member", password_hash="test", actor_role="support", is_active=True),
        ])
        queue_a = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "l1_member"])
        queue_b = await _seed_queue(session, code="network", name="Network", members=["network_member"], auto_assign_enabled=True)
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            title="Queue handoff",
            description="Ticket should move to target queue member",
            status="in_progress",
            requester_id="user-a",
            queue_id=queue_a.id,
            assignee_id="support-test",
        )
        session.add(ticket)
        ticket_id = ticket.ticket_id
        target_queue_id = queue_b.id
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/queue",
        json={"queue_id": target_queue_id, "reason": "manual"},
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["ticket"]["queue_id"] == target_queue_id
    assert payload["ticket"]["assignee_id"] == "network_member"
    assert payload["ticket"]["status"] == "assigned"


@pytest.mark.asyncio
async def test_manual_queue_change_clears_assignee_when_target_queue_has_no_autoassign(test_client, test_engine):
    session_maker = async_sessionmaker(test_engine)

    async with session_maker() as session:
        session.add_all([
            UiUser(user_login="support-test", password_hash="test", actor_role="support", is_active=True),
            UiUser(user_login="l1_member", password_hash="test", actor_role="support", is_active=True),
        ])
        queue_a = await _seed_queue(session, code="servicedesk_l1", name="ServiceDesk L1", members=["support-test", "l1_member"])
        queue_b = await _seed_queue(session, code="backoffice", name="Backoffice", members=[], auto_assign_enabled=False)
        ticket = Ticket(
            ticket_id=str(uuid.uuid4()),
            device_id=str(uuid.uuid4()),
            title="Queue handoff without autoassign",
            description="Ticket should come back to queue without assignee",
            status="waiting_on_user",
            requester_id="user-b",
            queue_id=queue_a.id,
            assignee_id="support-test",
        )
        session.add(ticket)
        ticket_id = ticket.ticket_id
        target_queue_id = queue_b.id
        await session.commit()

    response = await test_client.post(
        f"/api/tickets/{ticket_id}/queue",
        json={"queue_id": target_queue_id, "reason": "manual"},
        headers={**_support_headers(), "Content-Type": "application/json"},
    )
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["ticket"]["queue_id"] == target_queue_id
    assert payload["ticket"]["assignee_id"] in (None, "")
    assert payload["ticket"]["status"] == "queued"
