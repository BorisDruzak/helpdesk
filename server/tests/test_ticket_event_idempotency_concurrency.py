"""Real PostgreSQL protection after competing server-event prechecks."""
import asyncio
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import Ticket, TicketEvent
from app.repos.ticket_events_repo import TicketEventsRepo

pytestmark = pytest.mark.db_cleanup("full")


@pytest.mark.asyncio
@pytest.mark.parametrize("key_kind", ["event_id", "message_id"])
async def test_competing_server_event_retries_persist_one_event(test_engine, monkeypatch, key_kind):
    maker = async_sessionmaker(test_engine, expire_on_commit=False)
    ticket_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    async with maker() as session:
        session.add(Ticket(ticket_id=ticket_id, device_id=None, title="Event race fixture",
                           description="Synthetic concurrent retry", status="queued"))
        await session.commit()

    method = "_check_duplicate_by_event_id" if key_kind == "event_id" else "_check_duplicate_server_event"
    original = getattr(TicketEventsRepo, method)
    arrived = 0
    release = asyncio.Event()

    async def concurrent_precheck(self, **values):
        nonlocal arrived
        duplicate = await original(self, **values)
        assert duplicate is False
        arrived += 1
        if arrived == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=10)
        return duplicate

    monkeypatch.setattr(TicketEventsRepo, method, concurrent_precheck)
    key = str(uuid.uuid4())
    payload = {"text": "Same server event"}
    if key_kind == "message_id":
        payload["message_id"] = key

    async def retry():
        async with maker() as session:
            result = await TicketEventsRepo(session).add_event(
                ticket_id=ticket_id, device_id=None, agent_seq=None,
                event_type="chat_message", payload=payload, trace_id=trace_id,
                event_id=key if key_kind == "event_id" else None,
            )
            await session.commit()
            return result

    results = await asyncio.wait_for(asyncio.gather(retry(), retry()), timeout=30)
    assert arrived == 2
    assert sum(result is not None for result in results) == 1
    async with maker() as session:
        assert await session.scalar(select(func.count()).select_from(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id)) == 1
        stored = (await session.execute(select(TicketEvent).where(
            TicketEvent.ticket_id == ticket_id))).scalar_one()
        assert stored.payload == payload
        assert stored.event_id == (key if key_kind == "event_id" else None)
