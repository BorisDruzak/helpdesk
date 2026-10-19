import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, UiUser
from auth.context import AuthContext, AuthType
from routes import setup_routes
from tests.test_ticket_queue_routing_contracts import _seed_queue
from web_api import support_handlers as support

pytestmark = pytest.mark.db_cleanup("web_support")


@pytest.fixture
async def work_client(test_engine, monkeypatch):
    maker = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    @asynccontextmanager
    async def session_scope():
        async with maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @web.middleware
    async def actors(request, handler):
        actor = request.headers.get("X-Test-Actor", "support1")
        request["auth_context"] = AuthContext(actor_id=actor, actor_role="admin" if actor == "admin" else "support", auth_type=AuthType.UI_TOKEN, token="synthetic")
        return await handler(request)

    monkeypatch.setattr(support, "get_session", session_scope)
    app = web.Application(middlewares=[actors])
    setup_routes(app)
    async with TestClient(TestServer(app)) as client:
        yield client


async def seed_work(engine, *, status="new", assignee=None, members=None):
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all([UiUser(user_login=actor, password_hash="!", actor_role="admin" if actor == "admin" else "support", is_active=True) for actor in ("support1", "support2", "admin")])
        queue = await _seed_queue(session, code="work_" + uuid.uuid4().hex[:12], name="Synthetic support", members=members if members is not None else ["support1", "support2", "admin"], auto_assign_enabled=False)
        ticket_id = str(uuid.uuid4())
        session.add(Ticket(ticket_id=ticket_id, device_id=None, title="UI-SUPPORT-001 synthetic", description="No agent", requester_id="synthetic-requester", status=status, assignee_id=assignee, queue_id=queue.id, custom_fields={}, first_response_due_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        await session.commit()
    return ticket_id


@pytest.mark.asyncio
async def test_nonmember_admin_has_same_denial_in_queue_detail_and_command(work_client, test_engine):
    ticket_id = await seed_work(test_engine, members=["support1", "support2"])
    headers = {"X-Test-Actor": "admin"}
    queue = await work_client.get("/api/web/support/queue", headers=headers)
    assert queue.status == 200, await queue.text()
    item = next(item for item in (await queue.json())["data"]["tickets"] if item["ticket_id"] == ticket_id)
    detail = await work_client.get(f"/api/web/support/tickets/{ticket_id}", headers=headers)
    assert detail.status == 200, await detail.text()
    action = (await detail.json())["data"]["actions"]["take_in_work"]
    assert action == item["take_in_work"]
    assert action["allowed"] is False and action["reason_code"] == "ASSIGNEE_NOT_IN_QUEUE"
    response = await work_client.post(f"/api/web/support/tickets/{ticket_id}/status", headers=headers, json={"to_status": "in_progress"})
    assert response.status == 409
    assert (await response.json())["error_code"] == action["reason_code"]
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "new" and ticket.assignee_id is None and ticket.first_response_at is None


@pytest.mark.asyncio
async def test_competing_take_has_one_persisted_assignee_and_only_owner_can_reply(work_client, test_engine):
    ticket_id = await seed_work(test_engine)
    url = f"/api/web/support/tickets/{ticket_id}"
    rejected = await work_client.post(url + "/messages", json={"text": "Premature public reply"})
    assert rejected.status == 409, await rejected.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.first_response_at is None
        assert (await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalars().all() == []

    actors = ("support1", "support2")
    responses = await asyncio.gather(*(work_client.post(url + "/status", headers={"X-Test-Actor": actor}, json={"to_status": "in_progress"}) for actor in actors))
    assert sorted(response.status for response in responses) == [200, 403], [await response.text() for response in responses]
    winner = actors[next(index for index, response in enumerate(responses) if response.status == 200)]
    loser = next(actor for actor in actors if actor != winner)
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "in_progress" and ticket.assignee_id == winner
        assert ticket.first_response_at is None
        events = (await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalars().all()
        assert sum(event.event_type == "assignee_changed" for event in events) == 1
        assert sum(event.event_type == "status_changed" for event in events) == 1
    rejected = await work_client.post(url + "/messages", headers={"X-Test-Actor": loser}, json={"text": "Unauthorized public reply"})
    assert rejected.status == 403
    accepted = await work_client.post(url + "/messages", headers={"X-Test-Actor": winner}, json={"text": "Authorized public reply"})
    assert accepted.status == 200, await accepted.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.status == "in_progress" and ticket.assignee_id == winner
        assert ticket.first_response_at is not None
        events = (await session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalars().all()
        assert [event.payload["text"] for event in events if event.event_type == "chat_message"] == ["Authorized public reply"]


@pytest.mark.asyncio
async def test_assigned_work_preserves_assignee_and_admin_authority(work_client, test_engine):
    ticket_id = await seed_work(test_engine, status="assigned", assignee="support2")
    url = f"/api/web/support/tickets/{ticket_id}"
    response = await work_client.post(url + "/status", json={"to_status": "in_progress"})
    assert response.status == 403
    response = await work_client.post(url + "/messages", headers={"X-Test-Actor": "admin"}, json={"text": "Too early"})
    assert response.status == 409
    response = await work_client.post(url + "/status", headers={"X-Test-Actor": "admin"}, json={"to_status": "in_progress"})
    assert response.status == 200, await response.text()
    response = await work_client.post(url + "/messages", headers={"X-Test-Actor": "admin"}, json={"text": "Admin assistance"})
    assert response.status == 200, await response.text()
    async with async_sessionmaker(test_engine)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert ticket.assignee_id == "support2" and ticket.status == "in_progress"
