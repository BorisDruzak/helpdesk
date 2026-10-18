from datetime import datetime, timezone
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import AccessGroup, AccessGroupMember, AccessGroupPermission, RegistryPerson, RegistryPersonIdentity, Ticket, TicketApproval, TicketEvent, UiUser
from registry.organization_trust import confirm_fields
from tickets.approval_policy import _resolve_approval_source

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.fixture
def test_client(test_client_light):
    return test_client_light


def headers(login):
    return {"Authorization": "Bearer test-ui-user:" + login}


async def seed(test_engine):
    marker = uuid.uuid4().hex[:12]
    manager_login = f"manager-{marker}@example.test"
    other_login = f"other-{marker}@example.test"
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    async with maker() as session:
        group = AccessGroup(code="assigned-" + marker, name="Assigned approvals test", is_active=True)
        session.add(group)
        await session.flush()
        requester = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Synthetic employee", status="active", metadata_json={})
        manager = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Synthetic manager", status="active", metadata_json={})
        other = RegistryPerson(person_id=str(uuid.uuid4()), display_name="Other manager", status="active", metadata_json={})
        requester.metadata_json = {"manager_person_id": manager.person_id}
        confirm_fields(requester, ["manager_person_id"], actor_id="admin")
        session.add_all([requester, manager, other])
        for person, login in ((requester, "requester-" + marker), (manager, manager_login), (other, other_login)):
            session.add(UiUser(user_login=login, password_hash="test", actor_role="user", is_active=True))
            session.add(RegistryPersonIdentity(person_id=person.person_id, provider="ui_login", identifier=login, normalized_identifier=login, verified=True, source="test"))
            if person is not requester:
                session.add(AccessGroupMember(group_id=group.id, actor_id=login))
        session.add(AccessGroupPermission(group_id=group.id, permission_code="approval.decide.assigned"))
        ticket = Ticket(ticket_id=str(uuid.uuid4()), device_id=None, ticket_code="MGR-" + marker,
                        title="Запрос доступа", description="Нужен доступ к синтетическому ресурсу", status="waiting_on_approval",
                        requester_id="requester-" + marker, requester_person_id=requester.person_id,
                        custom_fields={"internal_secret_test_marker": "DO_NOT_EXPOSE", "request_template": {"approval_policy": {
                            "required": True, "approver_source": {"type": "requester_manager"}, "require_comment_on_reject": True,
                            "statuses": {"waiting_status": "waiting_on_approval", "approved_transition": "in_progress", "rejected_transition": "canceled"},
                        }}})
        session.add(ticket)
        await session.flush()
        approval = TicketApproval(ticket_id=ticket.ticket_id, approval_type="requester_manager", approver_id=manager_login, status="requested", reason="PRIVATE_APPROVAL_REASON", requested_by="support", requested_at=datetime.now(timezone.utc))
        session.add(approval)
        await session.commit()
        return ticket.ticket_id, approval.id, manager_login, other_login, requester.person_id, manager.person_id


@pytest.mark.asyncio
async def test_ordinary_manager_can_only_view_and_decide_assigned_approval(test_client, test_engine):
    ticket_id, approval_id, manager, other, _, _ = await seed(test_engine)
    own = await test_client.get("/api/web/requester/approvals", headers=headers(manager))
    assert own.status == 200, await own.text()
    body = (await own.json())["data"]
    assert [item["approval_id"] for item in body["items"]] == [approval_id]
    assert "DO_NOT_EXPOSE" not in str(body)
    assert "custom_fields" not in str(body)
    empty = await test_client.get("/api/web/requester/approvals", headers=headers(other))
    assert (await empty.json())["data"]["items"] == []
    route = f"/api/web/support/tickets/{ticket_id}/approvals/{approval_id}/decision"
    foreign = await test_client.post(route, headers=headers(other), json={"decision": "approved"})
    assert foreign.status in {403, 404}
    no_comment = await test_client.post(route, headers=headers(manager), json={"decision": "rejected"})
    assert no_comment.status == 400
    approved = await test_client.post(route, headers=headers(manager), json={"decision": "approved"})
    assert approved.status == 200, await approved.text()
    assert "DO_NOT_EXPOSE" not in await approved.text()
    assert "PRIVATE_APPROVAL_REASON" not in await approved.text()
    repeat = await test_client.post(route, headers=headers(manager), json={"decision": "rejected", "comment": "Повтор"})
    assert repeat.status == 409
    for path in ("/api/web/support/queue", f"/api/web/support/tickets/{ticket_id}"):
        denied = await test_client.get(path, headers=headers(manager))
        assert denied.status in {403, 404}
    async with async_sessionmaker(test_engine)() as session:
        assert (await session.get(TicketApproval, approval_id)).status == "approved"
        events = (await session.scalars(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id, TicketEvent.event_type == "approval_approved"))).all()
        assert len(events) == 1
        ticket = await session.get(Ticket, ticket_id)
        custom = dict(ticket.custom_fields)
        custom["request_template"] = {**custom["request_template"], "approval_policy": {**custom["request_template"]["approval_policy"], "approval_mode": "sequential"}}
        ticket.custom_fields = custom
        future = TicketApproval(ticket_id=ticket_id, approval_type="requester_manager", approver_id=manager, status="pending", requested_by="support", requested_at=datetime.now(timezone.utc))
        session.add(future); await session.flush(); future_id = future.id
        await session.commit()
    bypass = await test_client.post(f"/api/web/support/tickets/{ticket_id}/approvals/{future_id}/decision", headers=headers(manager), json={"decision": "approved"})
    assert bypass.status == 409
    async with async_sessionmaker(test_engine)() as session:
        (await session.get(UiUser, manager)).is_active = False
        await session.commit()
    inactive = await test_client.get("/api/web/requester/approvals", headers=headers(manager))
    assert inactive.status == 403


@pytest.mark.asyncio
async def test_requester_manager_ignores_submitted_manager_metadata_and_uses_confirmed_link(test_engine):
    ticket_id, _, manager, _, _, manager_id = await seed(test_engine)
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        ticket = await session.get(Ticket, ticket_id)
        ticket.custom_fields = {**ticket.custom_fields, "requester_profile": {"manager_id": "attacker"}}
        assert await _resolve_approval_source(session, ticket, {"type": "requester_manager"}) == ("requester_manager", [manager])
        person = await session.get(RegistryPerson, manager_id)
        person.status = "inactive"
        assert await _resolve_approval_source(session, ticket, {"type": "requester_manager"}) == ("requester_manager", [])
