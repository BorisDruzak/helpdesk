from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.services.ticket_sla_watchdog as watchdog_module
from tickets.timer_projection import pending_sla_breaches


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_watchdog_does_not_record_a_breach_after_an_on_time_sla_pause(monkeypatch):
    now = datetime.now(timezone.utc)
    ticket = SimpleNamespace(
        ticket_id="paused-ticket",
        device_id=None,
        status="waiting_on_user",
        resolution_due_at=now - timedelta(hours=2),
        resolution_at=None,
        resolution_breached_at=None,
        first_response_due_at=None,
        first_response_at=None,
        first_response_breached_at=None,
        sla_paused_at=now - timedelta(hours=3),
        sla_paused_seconds=60,
    )
    session = SimpleNamespace(commit=AsyncMock())
    repository = SimpleNamespace(
        get_tickets_sla_breach_candidates=AsyncMock(return_value=[ticket]),
        get_ticket=AsyncMock(return_value=ticket),
        update_ticket=AsyncMock(),
        add_event=AsyncMock(return_value=None),
    )

    @asynccontextmanager
    async def get_session():
        yield session

    monkeypatch.setattr(watchdog_module, "get_session", get_session)
    monkeypatch.setattr(watchdog_module, "TicketEventsRepo", lambda _: repository)
    monkeypatch.setattr(watchdog_module, "_dispatch_sla_policy_actions", AsyncMock())

    await watchdog_module.TicketSlaWatchdog()._check_breaches()

    repository.update_ticket.assert_not_awaited()
    repository.add_event.assert_not_awaited()


@pytest.mark.no_db
@pytest.mark.parametrize("paused_minutes_ago", [None, 45])
def test_watchdog_keeps_an_sla_breach_that_was_due_before_the_cutoff(paused_minutes_ago):
    now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    ticket = SimpleNamespace(
        first_response_due_at=now - timedelta(hours=3),
        first_response_at=now - timedelta(hours=4),
        resolution_due_at=now - timedelta(hours=2),
        resolution_at=None,
        sla_paused_at=None if paused_minutes_ago is None else now - timedelta(minutes=paused_minutes_ago),
        sla_paused_seconds=1200,
    )

    assert pending_sla_breaches(ticket, now) == {"resolution_breached_at": now}
