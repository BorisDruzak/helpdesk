from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent, UiUser
from tests.conftest import TEST_UI_SUPPORT_TOKEN
from tests.test_ticket_queue_routing_contracts import _seed_queue
from tickets import handlers as tickets
from tickets.assignment_service import TicketAssignmentError
from web_api import support_handlers as support

pytestmark = pytest.mark.db_cleanup("web_support")

_FIELDS = ("status", "queue_id", "assignee_id", "custom_fields", "ola_queue_id", "ola_processing_due_at",
           "ola_processing_at", "ola_ack_due_at", "ola_ack_at")


async def _seed(engine, *, count=1):
    maker = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    marker = uuid.uuid4().hex
    async with maker() as session:
        session.add(UiUser(user_login="support-test", password_hash="!", actor_role="support", is_active=True))
        first = await _seed_queue(session, code="atomic_a_" + marker, name="Atomic A", members=["support-test"], auto_assign_enabled=False)
        second = await _seed_queue(session, code="atomic_b_" + marker, name="Atomic B", members=["support-test"], auto_assign_enabled=False)
        ids = []
        for index in range(count):
            ticket = Ticket(ticket_id=str(uuid.uuid4()), device_id=None, title=f"Atomic workflow {marker} {index}",
                            description="Rollback acceptance", status="new", requester_id="test-requester",
                            queue_id=first.id, assignee_id=None, custom_fields={}, ola_queue_id=first.id,
                            ola_processing_due_at=now + timedelta(hours=1), ola_processing_at=None,
                            ola_ack_due_at=now + timedelta(minutes=10), ola_ack_at=None)
            session.add(ticket)
            ids.append(ticket.ticket_id)
        await session.commit()
        snapshots = {tid: {field: getattr(await session.get(Ticket, tid), field) for field in _FIELDS} for tid in ids}
        return ids, second.id, snapshots


def _headers():
    return {"Authorization": "Bearer " + TEST_UI_SUPPORT_TOKEN}


async def _assert_unchanged(engine, ticket_id, snapshot):
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        ticket = await session.get(Ticket, ticket_id)
        assert {field: getattr(ticket, field) for field in _FIELDS} == snapshot
        assert (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id))).scalar_one() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_type,expected", [(TicketAssignmentError, 409), (RuntimeError, 503)])
async def test_take_in_work_assignment_failure_keeps_initial_state(test_client_light, test_engine, monkeypatch, failure_type, expected):
    ids, _queue, snapshots = await _seed(test_engine)
    failure = AsyncMock(side_effect=failure_type("private assignment details"))
    monkeypatch.setattr(support.TicketAssignmentService, "assign_ticket", failure)
    response = await test_client_light.post(f"/api/web/support/tickets/{ids[0]}/status", headers=_headers(), json={"to_status": "in_progress"})
    failure.assert_awaited_once()
    assert response.status == expected, await response.text()
    assert "private assignment details" not in await response.text()
    await _assert_unchanged(test_engine, ids[0], snapshots[ids[0]])


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/tickets/{id}/queue", "/api/tickets/{id}/reroute",
                                  "/api/web/support/tickets/{id}/queue", "/api/web/support/tickets/{id}/reroute",
                                  "/api/web/support/queue/mass-action"])
@pytest.mark.parametrize("stage", ["close", "start"])
async def test_queue_ola_failure_keeps_queue_timers_and_events(test_client_light, test_engine, monkeypatch, route, stage):
    ids, target, snapshots = await _seed(test_engine)
    module = tickets if route.startswith("/api/tickets/") else support
    failure = AsyncMock(side_effect=RuntimeError("private OLA details"))
    monkeypatch.setattr(module, "close_ola_processing" if stage == "close" else "start_ola_for_ticket", failure)
    if route.endswith("/reroute"):
        async def routing(self, ticket_id, device_id, *, add_events_fn, **_kwargs):
            await self.ticket_repo.update_ticket(ticket_id, queue_id=target)
            await add_events_fn(ticket_id, device_id, "queue_changed", {"queue_id": target})

        monkeypatch.setattr(module.TicketRoutingService, "apply_routing", routing)
    body = {"queue_id": target}
    if route.endswith("mass-action"):
        body.update(action="change_queue", ticket_ids=ids)
    response = await test_client_light.post(route.format(id=ids[0]), headers=_headers(), json=body)
    failure.assert_awaited_once()
    if route.endswith("mass-action"):
        assert response.status == 200, await response.text()
        payload = await response.json()
        assert payload["data"]["error_count"] == 1 and payload["data"]["success_count"] == 0
    else:
        assert response.status == 503, await response.text()
    assert "private OLA details" not in await response.text()
    await _assert_unchanged(test_engine, ids[0], snapshots[ids[0]])


@pytest.mark.asyncio
async def test_mass_queue_failure_preserves_previously_committed_success(test_client_light, test_engine, monkeypatch):
    ids, target, snapshots = await _seed(test_engine, count=2)
    original = support.start_ola_for_ticket

    async def fail_second(session, ticket, **kwargs):
        if ticket.ticket_id == ids[1]:
            raise RuntimeError("private OLA details")
        return await original(session, ticket, **kwargs)

    monkeypatch.setattr(support, "start_ola_for_ticket", fail_second)
    response = await test_client_light.post("/api/web/support/queue/mass-action", headers=_headers(), json={
        "queue_id": target, "ticket_ids": ids, "action": "change_queue",
    })
    assert response.status == 200, await response.text()
    payload = await response.json()
    assert payload["data"]["error_count"] == 1 and payload["data"]["success_count"] == 1
    assert "private OLA details" not in str(payload)
    await _assert_unchanged(test_engine, ids[1], snapshots[ids[1]])
    async with async_sessionmaker(test_engine, expire_on_commit=False)() as session:
        first = await session.get(Ticket, ids[0])
        assert first.queue_id == target
        assert (await session.execute(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ids[0], TicketEvent.event_type == "queue_changed"))).scalar_one() == 1
